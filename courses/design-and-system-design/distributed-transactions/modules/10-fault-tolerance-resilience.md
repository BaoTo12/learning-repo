# Module 10: Fault Tolerance and Resilience — Circuit Breakers, Retries, and Bulkheads

Welcome back, students. Today we analyze how to keep distributed systems alive when parts of them are failing.

In a distributed architecture containing dozens of microservices, failures are a mathematical certainty. If a downstream service slows down or drops connections, and the upstream services do not protect themselves, threads will block waiting for responses. Within seconds, thread pools across the entire cluster will starve, causing a **cascading failure** that takes down the entire system. We will study **Circuit Breakers**, **Rate Limiters**, **Bulkheads**, and **Retries with Jitter**, and implement them in Java using the industry-standard **Resilience4j** library.

---

## 1. Academic Lecture: The Mathematics of Fault Containment

Resilience is not about preventing failures; it is about **containing** them so that the system degrades gracefully rather than collapsing.

### The Circuit Breaker Pattern

A Circuit Breaker acts as an electrical safety switch. It monitors calls to a downstream resource. If the failure rate crosses a configured threshold, the breaker trips, routing all subsequent requests directly to a **fallback** method without calling the failing service.

```mermaid
stateDiagram-v2
    [*] --> Closed : System Healthy
    Closed --> Open : Failure Rate > Threshold
    Note over Open: Rejects calls immediately (Fast Fail)
    Open --> HalfOpen : Reset Timeout Expires
    HalfOpen --> Closed : Test Calls Succeed
    HalfOpen --> Open : Test Calls Fail
```

*   **Closed**: The circuit is closed; requests flow to the downstream service. The breaker records call outcomes (success/failure) in a sliding window.
*   **Open**: The failure rate exceeded the threshold. The breaker trips. All calls fail fast immediately, invoking the fallback logic to prevent thread starvation.
*   **Half-Open**: After a configured reset timeout (e.g., 30s), the breaker allows a limited number of trial calls through to see if the downstream service has recovered. If they succeed, it returns to **Closed**. If they fail, it returns to **Open**.

### The Bulkhead Pattern

Named after the watertight partitions in a ship's hull, the **Bulkhead Pattern** isolates resources (such as thread pools, memory, or CPU) into distinct pools. 

If Service A queries Database 1 and Database 2, and Database 2 crashes, a shared thread pool would fill up with threads waiting on Database 2. Service A would become completely unavailable, preventing it from serving requests for Database 1. 

By partitioning threads into separate bulkheads:
*   Bulkhead A: 10 threads reserved for Database 1.
*   Bulkhead B: 10 threads reserved for Database 2.
A failure in Database 2 will only saturate Bulkhead B. Database 1 continues to process requests normally.

```
                  +--------------------------------+
                  |     Bulkhead Isolation         |
                  +---------------+----------------+
                                  |
            +---------------------+---------------------+
            | (Max 10 Threads)                          | (Max 10 Threads)
            v                                           v
    [ Thread Pool 1 ]                           [ Thread Pool 2 ]
            |                                           |
            v                                           v
      [ Database 1 ]                            [ Database 2 ] (Crashed!)
    (Runs normally)                            (Saturates, but isolated)
```

### Retries with Backoff and Random Jitter

When a network request fails due to a transient hiccup, retrying the request immediately can resolve the issue. However, if 10,000 clients retry simultaneously, they will overload the recovery database, creating a self-induced Denial-of-Service attack (known as a **retry storm** or **thundering herd**).

To prevent this, we must enforce:
1.  **Exponential Backoff**: The delay between retries increases exponentially:
    $$\text{Delay} = \text{Base} \times 2^{\text{attempt}}$$
2.  **Random Jitter**: Adding a random variation to the delay to desynchronize the clients:
    $$\text{Delay} = (\text{Base} \times 2^{\text{attempt}}) + \text{random\_jitter}$$

---

## 2. Theory vs. Production Trade-offs

### 1. Fallback Strategy Design
When a circuit breaker trips, the application must return a fallback. Designing fallback paths requires business judgment:
*   *Static Fallback*: Return static/default data (e.g., empty recommendations).
*   *Cache Fallback*: Query a local cache (e.g., Redis) containing slightly stale data.
*   *Degraded Fallback*: Turn off non-essential UI features (e.g., hiding reviews but allowing checkouts).

---

## 3. How to Use: Resilience4j Integration in Java 21

Let's configure and chain a **ThreadPool Bulkhead**, a **Circuit Breaker**, and a **Retry** in Java 21 using **Resilience4j**.

```java
package com.capstone.tx.resilience;

import io.github.resilience4j.circuitbreaker.CircuitBreaker;
import io.github.resilience4j.circuitbreaker.CircuitBreakerConfig;
import io.github.resilience4j.bulkhead.ThreadPoolBulkhead;
import io.github.resilience4j.bulkhead.ThreadPoolBulkheadConfig;
import io.github.resilience4j.retry.Retry;
import io.github.resilience4j.retry.RetryConfig;

import java.io.IOException;
import java.time.Duration;
import java.util.concurrent.*;
import java.util.logging.Logger;

/**
 * Production-ready class demonstrating the composition of multiple Resilience4j patterns.
 */
public class ResilientServiceExecutor {
    private static final Logger LOGGER = Logger.getLogger(ResilientServiceExecutor.class.getName());

    private final ThreadPoolBulkhead bulkhead;
    private final CircuitBreaker circuitBreaker;
    private final Retry retry;

    public ResilientServiceExecutor() {
        // 1. Configure ThreadPool Bulkhead (max 5 active threads, queue capacity of 10)
        ThreadPoolBulkheadConfig bulkheadConfig = ThreadPoolBulkheadConfig.custom()
                .maxThreadPoolSize(5)
                .coreThreadPoolSize(3)
                .queueCapacity(10)
                .build();
        this.bulkhead = ThreadPoolBulkhead.of("payment-service-bulkhead", bulkheadConfig);

        // 2. Configure Circuit Breaker (trip if 50% of 10 calls fail, wait 5s in open state)
        CircuitBreakerConfig circuitBreakerConfig = CircuitBreakerConfig.custom()
                .failureRateThreshold(50.0f)
                .slidingWindowSize(10)
                .minimumNumberOfCalls(5)
                .waitDurationInOpenState(Duration.ofSeconds(5))
                .recordExceptions(IOException.class, TimeoutException.class)
                .build();
        this.circuitBreaker = CircuitBreaker.of("payment-service-breaker", circuitBreakerConfig);

        // 3. Configure Retry (max 3 attempts, exponential backoff starting at 100ms)
        RetryConfig retryConfig = RetryConfig.custom()
                .maxAttempts(3)
                .waitDuration(Duration.ofMillis(100))
                .retryExceptions(IOException.class)
                .build();
        this.retry = Retry.of("payment-service-retry", retryConfig);
    }

    /**
     * Executes the call inside the Bulkhead, Circuit Breaker, and Retry decorators.
     * Invokes the fallback method if a recovery threshold is violated.
     */
    public String executePayment(Callable<String> paymentAction) {
        // Decorate the action with Retry and Circuit Breaker
        Callable<String> decoratedAction = CircuitBreaker.decorateCallable(circuitBreaker, paymentAction);
        decoratedAction = Retry.decorateCallable(retry, decoratedAction);

        final Callable<String> finalAction = decoratedAction;

        try {
            // Submit the decorated execution to the isolated ThreadPool Bulkhead
            CompletableFuture<String> futureResult = bulkhead.executeCallable(finalAction);
            return futureResult.get(3, TimeUnit.SECONDS);

        } catch (ExecutionException e) {
            Throwable cause = e.getCause();
            LOGGER.warning("Service execution failed. Running fallback... Cause: " + cause.getMessage());
            return executeFallback(cause);
        } catch (Exception e) {
            LOGGER.warning("Bulkhead queue full, timeout, or interception. Running fallback... Cause: " + e.getMessage());
            return executeFallback(e);
        }
    }

    /**
     * Fallback strategy executed when execution fails or breaker is tripped.
     */
    private String executeFallback(Throwable t) {
        LOGGER.info("Fallback activated. Returning backup payment receipt.");
        return "FALLBACK_RECEIPT_STALE_CACHE_ID: " + UUID.randomUUID();
    }
}
```

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Incorrect Sliding Window Configuration
Setting the sliding window size of a circuit breaker too small (e.g., 2 calls).
*   **Symptom**: The circuit trips continuously on a single minor timeout, causing system instability.
*   **Mitigation**: Set a minimum number of calls (e.g., 20-50 calls) before the breaker is allowed to calculate the failure rate.

### Pitfall 2: Bypassing the Bulkhead Thread pool
Using a Spring `@Bulkhead` annotation but executing database queries on the standard WebMvc servlet thread pool.
*   **Symptom**: The bulkhead does not limit resources, leading to Tomcat server pool lockups anyway.
*   **Mitigation**: Ensure that the bulkhead configuration executes target functions on its own designated, isolated execution thread pool.

---

## 5. Socratic Review Questions

### Question 1
Why is adding **Jitter** to retry intervals critical when building high-scale network clients? What is the mathematical effect on network utilization graphs?

#### Answer
If multiple client connections fail due to a brief network blip, and they all retry using a standard exponential backoff without jitter (e.g., retrying at exactly 1s, 2s, 4s, 8s), their requests remain synchronized. 

On a network utilization graph, this produces severe, periodic utilization spikes (sharp traffic peaks at the retry checkpoints) followed by valleys of inactivity. These synchronized peaks can repeatedly crash the recovering service.

Adding random jitter disperses the retry attempts uniformly across time. Mathematically, it flattens the sharp utilization peaks into a smooth, manageable plateau, allowing the downstream database or service to process the queue without being overwhelmed.

### Question 2
Contrast the **Semaphore Bulkhead** and **ThreadPool Bulkhead** styles in Resilience4j. Under what conditions is one preferred over the other?

#### Answer
*   **ThreadPool Bulkhead**: Executes requests on a separate, dedicated thread pool. If the target service hangs, threads in this pool block, leaving the calling servlet threads free to handle other requests.
    *   *Preferred*: When calling external network resources (e.g., HTTP REST endpoints) where thread execution times can be long, and blocking the calling thread would starve the web container.
*   **Semaphore Bulkhead**: Executes requests on the caller's thread, but limits the number of concurrent executions using a semaphore counter. If the semaphore limit is reached, calling threads are blocked or rejected.
    *   *Preferred*: For lightweight internal operations or when calling high-performance databases, because it avoids the context-switching and memory overhead of creating additional thread pools.

---

## 6. Hands-on Challenge: Building a Multi-Tier Resilient Client

### The Challenge
In this challenge, you will implement a resilient wrapper. Given a downstream client that occasionally throws `IOException` or runs slowly, you must chain a Circuit Breaker and a Retry block using Resilience4j to guarantee that the client retires transient failures, but trips the breaker if the service remains down.

Complete the execution implementation below:

```java
package com.capstone.tx.resilience.challenge;

import io.github.resilience4j.circuitbreaker.CircuitBreaker;
import io.github.resilience4j.retry.Retry;
import java.util.concurrent.Callable;

public class MultiTierResilientClient {

    private final CircuitBreaker circuitBreaker;
    private final Retry retry;

    public MultiTierResilientClient(CircuitBreaker circuitBreaker, Retry retry) {
        this.circuitBreaker = circuitBreaker;
        this.retry = retry;
    }

    /**
     * Executes the downstream action. Chains the Retry and Circuit Breaker decorators.
     * If all attempts fail or the breaker is open, catches the exception and returns the fallbackValue.
     */
    public String executeWithResilience(Callable<String> action, String fallbackValue) {
        // TODO: Complete this implementation.
        // 1. Decorate action with CircuitBreaker.
        // 2. Decorate the result with Retry.
        // 3. Execute, catch exceptions, and return fallbackValue on failure.
        return null;
    }
}
```

Write your code and verify the fallback mechanics. Save your solution notes inside `modules/10-fault-tolerance-resilience.md`.
