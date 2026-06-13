# Module 01: Async WebClient Integration & Event Loops

Welcome class. Today we analyze **Async WebClient Integration & Event Loops (CS-528)**.

Traditional HTTP communications in Java utilize blocking clients, such as `RestTemplate` or standard `HttpURLConnection`. These clients follow the thread-per-request model: the executing thread blocks, doing zero work while waiting for the remote socket to return bytes. Since AI model queries (like speech transcription or LLM reasoning) take anywhere from 500ms to 30s to complete, blocking server worker threads pool will quickly lead to thread pool starvation, causing the entire backend to freeze under even minimal load.

Today we study **Non-Blocking Reactive HTTP Client Integration**. We will analyze Project Reactor paradigms (`Mono` and `Flux`), configure Spring WebFlux **`WebClient`** for high-latency endpoints, and write a resilient connection-pooled client in **Java 21**.

---

## 1. Academic Lecture: Thread Starvation vs. Non-Blocking Event Loops

### 1. The Bottleneck of Blocking RestTemplate
In Spring Web MVC, each incoming request is assigned to a TomCat container thread. If your controller calls a local Ollama instance using `RestTemplate`:
1.  The thread sends the request payload.
2.  The thread blocks, waiting for the model to predict tokens.
3.  If 200 concurrent candidates query the API, 200 threads are locked in memory. Subsequent candidates cannot establish connections, leading to immediate HTTP 504 gateway timeouts.

### 2. The Reactive Event Loop Paradigm
Spring WebFlux `WebClient` utilizes **Netty**, a high-performance event-driven network application framework:
*   **The Non-Blocking Graph**: Instead of one thread per request, Netty runs a tiny number of event-loop threads (usually matching CPU core count).
*   **Reactive Flow**: When a request is sent, the event loop registers a socket channel listener and immediately releases the thread to handle other tasks. When the remote AI server returns the response packet, the OS triggers a socket interrupt. Netty captures the event, delegates the bytes parsing to Jackson, and emits the resulting object as a **Project Reactor `Mono`** or **`Flux`**.

### 3. Hitting Memory Limits on Large Payloads
By default, Spring WebFlux limits in-memory codec buffers to **256 Kilobytes** (`262144` bytes) to prevent resource exhaustion attacks. Because LLM outputs and transcribed audio text manifests can easily exceed this size, attempting to parse large JSON responses without overriding this parameter raises a `DataBufferLimitException`.

```text
[Incoming request] ──> [Spring WebFlux Controller]
                                │
                                ▼
                       [WebClient Dispatch]
                                │
                                ├─ Register Socket Channel on Event Loop
                                └─ Release Thread immediately (Thread can work elsewhere)
                                │
                       (Ollama computes: 10s)
                                │
                       [Remote HTTP Response]
                                │
                                ▼
                       [Socket Interrupt] ──> [Netty Event Loop captures bytes]
                                                  │
                                                  ▼
                                       [Jackson JSON Deserializer]
                                                  │
                                                  ▼
                                       [Emit Mono / Flux payload]
```

---

## 2. Theory vs. Production Trade-offs

When choosing an integration layer for high-latency APIs, compare these HTTP clients:

| Dimension / Metric | Blocking RestTemplate | Java 11 HttpClient (Async) | WebFlux WebClient (Non-Blocking) |
| :--- | :--- | :--- | :--- |
| **Concurrency Model** | Thread-per-request | Thread pool callback | Non-blocking Event Loop (Netty) |
| **Throughput under Load**| Low (Tied to thread count)| Moderate (Thread-limited) | Excellent (Handles thousands of calls) |
| **Code Style** | Imperative (Simple try-catch) | Callback-based (CompletableFuture)| Declarative Reactive (Streams) |
| **Timeout Granularity** | Global Read/Connect limits | Connect/Request limits | Pool, Connect, Read, Write channels |
| **Resource Footprint** | High (Each thread consumes 1MB) | Moderate | Very Low |

---

## 3. How to Use: High-Performance WebClient Configuration

Let us write a compile-grade Java 21 Spring Configuration class that initializes a non-blocking `WebClient` bean with customized Connection Pools, HTTP timeouts, and buffer limits.

### A. The Brittle Client Instantiation (Anti-Pattern)

Avoid creating WebClient instances on the fly without overriding default timeouts or buffer sizes. This blocks concurrent socket allocations:

```java
package com.security.api.config;

import org.springframework.web.reactive.function.client.WebClient;

public class NaiveClientConfig {
    // DANGER: Creating WebClient with default settings inherits the 256KB buffer limit.
    // Additionally, it uses default timeouts, allowing slow AI models to hang the connection
    // indefinitely under network partition errors.
    public WebClient getNaiveClient() {
        return WebClient.create("http://localhost:11434"); // VULNERABLE to buffer limits and timeouts
    }
}
```

### B. The Hardened WebClient Configuration (Production Pattern)

Here is the hardened pattern. We write a configuration class that overrides the default memory codecs to 10MB, configures a Netty `ConnectionProvider` with customized keep-alive limits, and sets strict read/write timeouts.

```java
package com.security.api.config;

import io.netty.channel.ChannelOption;
import io.netty.handler.timeout.ReadTimeoutHandler;
import io.netty.handler.timeout.WriteTimeoutHandler;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.reactive.ReactorClientHttpConnector;
import org.springframework.http.codec.json.Jackson2JsonDecoder;
import org.springframework.http.codec.json.Jackson2JsonEncoder;
import org.springframework.web.reactive.function.client.ExchangeStrategies;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.netty.http.client.HttpClient;
import reactor.netty.resources.ConnectionProvider;

import java.time.Duration;
import java.util.concurrent.TimeUnit;

@Configuration
public class SecureWebClientConfig {

    @Bean
    public WebClient ollamaWebClient() {
        // 1. Configure Connection Provider (Pool limits)
        ConnectionProvider connectionProvider = ConnectionProvider.builder("ollama-pool")
            .maxConnections(50)                    // Limit max active sockets
            .pendingAcquireTimeout(Duration.ofSeconds(10)) // Max time to wait for free connection
            .maxIdleTime(Duration.ofSeconds(30))   // Evict idle connections from pool
            .build();

        // 2. Build Netty HttpClient with strict timeout channels
        HttpClient httpClient = HttpClient.create(connectionProvider)
            .option(ChannelOption.CONNECT_TIMEOUT_MILLIS, 5000) // Connect timeout (5s)
            .doOnConnected(connection -> connection
                .addHandlerLast(new ReadTimeoutHandler(30, TimeUnit.SECONDS))  // Read timeout (30s)
                .addHandlerLast(new WriteTimeoutHandler(10, TimeUnit.SECONDS)) // Write timeout (10s)
            );

        // 3. Override Default Codec Max Memory Limits to 10 Megabytes
        ExchangeStrategies exchangeStrategies = ExchangeStrategies.builder()
            .codecs(configurer -> {
                configurer.defaultCodecs().maxInMemorySize(10 * 1024 * 1024); // 10MB
                configurer.defaultCodecs().jackson2JsonDecoder(new Jackson2JsonDecoder());
                configurer.defaultCodecs().jackson2JsonEncoder(new Jackson2JsonEncoder());
            })
            .build();

        // 4. Construct the hardened WebClient bean
        return WebClient.builder()
            .baseUrl("http://localhost:11434")
            .clientConnector(new ReactorClientHttpConnector(httpClient))
            .exchangeStrategies(exchangeStrategies)
            .build();
    }
}
```

Now let us write the service that queries the endpoint returning a reactive `Mono`:

```java
package com.security.api.service;

import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

import java.util.Map;

@Service
public class OllamaService {

    private final WebClient webClient;

    public OllamaService(WebClient webClient) {
        this.webClient = webClient;
    }

    public Mono<String> queryLocalModel(String prompt) {
        Map<String, Object> payload = Map.of(
            "model", "qwen2.5:3b",
            "prompt", prompt,
            "stream", false
        );

        return this.webClient.post()
            .uri("/api/generate")
            .bodyValue(payload)
            .retrieve()
            // Map JSON response: {"response": "text..."}
            .bodyToMono(OllamaResponse.class)
            .map(OllamaResponse::response)
            // Handle HTTP error codes gracefully
            .onErrorReturn("Inference Error: Local model query failed.");
    }

    private static record OllamaResponse(String response) {}
}
```

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Calling `.block()` inside WebClient Reactive Streams
Using `.block()` to convert a `Mono<String>` back into a standard `String` string inside the controller context.
*   **Why it fails**: Calling `.block()` forces the thread to halt execution. If this is executed on Netty's event-loop thread, it locks the entire event loop, preventing all other concurrent request sockets from handling data updates.
*   **Mitigation**: Always return `Mono` or `Flux` directly to the controller output, letting the Spring WebFlux dispatcher resolve subscription processes asynchronously.

### Pitfall 2: Memory Starvation via Excessive Pool Sizes
Configuring `maxConnections(1000)` inside the `ConnectionProvider` builder parameters on a memory-constrained machine.
*   **Why it fails**: Each open connection consumes OS file descriptors and TCP socket buffers. Under heavy load, opening 1000 concurrent sockets to a local Ollama service will cause VRAM starvation or thread locks.
*   **Mitigation**: Set connection pool limits conservatively (e.g. 50-100 max connections), and implement circuit breakers to fail-fast when the queue saturates.

---

## 5. Socratic Review Questions

### Question 1
Why does calling `.block()` on a reactive type raise an `IllegalStateException` when executed inside a running WebFlux server thread pool?

#### Answer
Spring WebFlux inspects the calling thread. If the execution thread belongs to Netty's non-blocking event loop (e.g. a thread named `reactor-http-epoll-...`), calling `.block()` violates the core non-blocking contract. Netty throws this exception to prevent engineers from accidentally locking the entire network loop, which would halt all server traffic.

### Question 2
What is the difference between `Connection Timeout` and `Read Timeout` in HTTP integrations?

#### Answer
`Connection Timeout` measures the maximum time allowed to establish the initial TCP socket connection handshakes with the remote server. `Read Timeout` measures the maximum time allowed between receiving consecutive data packets from the remote socket. For slow AI models, the TCP handshake completes instantly (low connection latency), but the model processing takes seconds before yielding the first byte, requiring a long read timeout threshold.

---

## 6. Hands-on Challenge: WebClient Request Router with Timeout Fallbacks

### The Challenge
In this challenge, you will implement a WebClient request routing function in Java.
Your task:
1. Complete the implementation of `fetchModelResponse` inside `ModelRequestEngine`.
2. Send a POST request to `/api/generate` with the JSON payload.
3. Configure a strict timeout of 5 seconds on the reactive Mono stream.
4. Implement a fallback using `.onErrorResume` to return a default error message when a timeout occurs.

Complete the implementation stub below:

```java
package com.security.api;

import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;
import java.time.Duration;
import java.util.Map;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class ModelRequestEngine {
    private final WebClient webClient;

    public ModelRequestEngine(WebClient webClient) {
        this.webClient = webClient;
    }

    public Mono<String> fetchModelResponse(String model, String prompt) {
        Map<String, Object> body = Map.of(
            "model", model,
            "prompt", prompt,
            "stream", false
        );

        // TODO: Implement the WebClient call:
        // 1. Initiate a POST request to "/api/generate".
        // 2. Set the body content to the Map body object.
        // 3. Retrieve the response.
        // 4. Map the body to Mono of Map.class.
        // 5. Extract the "response" key as a String.
        // 6. Apply a timeout of 5 seconds (.timeout(Duration.ofSeconds(5))).
        // 7. Chain .onErrorResume(...) to return Mono.just("Timeout Fallback Response") if any exception occurs.

        return Mono.empty();
    }
}
```

Write the reactive stream configurations. Save the completed file and verify that timeout boundaries behave correctly under `modules/01-async-webclient-integration.md`.
