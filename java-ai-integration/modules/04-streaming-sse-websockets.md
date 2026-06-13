# Module 04: Streaming, Server-Sent Events (SSE), and WebSockets

Welcome class. Today we analyze **Streaming, Server-Sent Events (SSE), and WebSockets (CS-528)**.

When dealing with large language models, generating a complete response can take several seconds to minutes. Waiting for the final token to be calculated before sending the HTTP response packet back to the client creates an unacceptable user experience. Candidates will stare at a loading spinner for 10 seconds, wondering if the application has crashed.

Today, we study **Real-Time Token Streaming**. We will contrast HTTP Polling, WebSockets, and Server-Sent Events (SSE), configure Spring WebFlux to stream tokens dynamically via Project Reactor `Flux`, and implement a secure, resilient streaming controller.

---

## 1. Academic Lecture: Real-Time Communication Protocols & Backpressure

### 1. The Streaming Paradigm
When an LLM generates text, it does so token by token (roughly corresponding to word fragments). The network layer should replicate this generation cadence. Instead of sending a single buffered JSON response, the server writes individual tokens to the HTTP connection socket as they emerge from the local Ollama process.

### 2. Protocol Comparison
To push updates from server to client in real-time, three primary architectures exist:
1.  **Short/Long Polling**: The client repeatedly queries `/api/status` at a fixed interval. This creates massive overhead from continuous TCP handshakes and HTTP header decoding, overloading the server.
2.  **WebSockets (RFC 6455)**: A full-duplex, bi-directional protocol running over a single, long-lived TCP connection. Excellent for interactive multi-user applications (like collaborative editors or games). However, WebSockets do not run over standard HTTP/2 out-of-the-box, bypass traditional HTTP authorization headers after the initial handshake, and require complex custom frame parsing.
3.  **Server-Sent Events (SSE - HTML5)**: A uni-directional streaming protocol utilizing a persistent, standard HTTP connection (`text/event-stream`). The browser's native `EventSource` API handles reconnection and parsing out-of-the-box. Since it is standard HTTP, it respects existing Spring Security configurations, cookie contexts, and proxies.

### 3. Reactive SSE Streams & Backpressure
Under Spring WebFlux, SSE streaming is powered by Project Reactor's **`Flux<T>`**. Netty maps the `Flux` emissions directly to chunked HTTP responses. 
However, streaming introduces **backpressure** concerns: what happens if the Ollama engine streams tokens at 100 tokens/sec, but a client on a poor mobile connection can only read at 10 tokens/sec? If the server buffers these tokens in memory, we risk an `OutOfMemoryError` (OOM). Project Reactor's non-blocking event loops throttle the upstream source automatically, suspending socket reads from Ollama until the client's socket buffers clear.

```text
[Browser (Client)]                   [Spring WebFlux SSE]                [Ollama Engine]
        │                                     │                                 │
        │ ── Get /stream?prompt=Hello ──────> │                                 │
        │                                     │ ── POST /api/generate (stream) ─> │
        │ <── Establish HTTP 200 (SSE) ────── │                                 │
        │                                     │ <── Token Chunk ("Hello") ────── │
        │ <── data: {"token": "Hello"} ────── │                                 │
        │                                     │ <── Token Chunk (" world") ───── │
        │ <── data: {"token": " world"} ───── │                                 │
        │                                     │ <── Token Chunk (done=true) ──── │
        │ <── event: complete ─────────────── │                                 │
        │                                     │                                 │
```

---

## 2. Theory vs. Production Trade-offs

Here is a comparison of streaming approaches for LLM outputs:

| Dimension / Metric | Long Polling | WebSockets (Full Duplex) | Server-Sent Events (SSE) |
| :--- | :--- | :--- | :--- |
| **Directionality** | Client-to-Server pull | Bi-directional push/pull | Server-to-Client push |
| **Protocol Layer** | Standard HTTP | WebSocket Upgrade (TCP) | Standard HTTP (`text/event-stream`) |
| **Spring Security Integration** | Native & Simple | Complex (Requires handshake auth) | Native & Simple (Standard filters) |
| **Reconnection Support** | Manual client-side logic | Manual client-side logic | Built-in browser `EventSource` |
| **Throughput / Overhead** | Very Low Efficiency | Excellent (No HTTP headers) | High Efficiency (Chunked HTTP) |
| **Proxy / Firewall Friendly** | Yes | Often blocked by enterprise proxies| Yes |

---

## 3. How to Use: Reactive SSE Token Streaming Controller

Let us write a compile-grade Java 21 Spring Boot controller and configuration that calls a local Ollama service, streams JSON response chunks, maps them to SSE tokens, and implements client-disconnect termination.

### A. The Inefficient Blocking Controller (Anti-Pattern)

Avoid reading the entire stream into a list or blocking on each token before flushing. This locks the HTTP response stream:

```java
package com.security.api.controller;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.reactive.function.client.WebClient;
import java.util.List;

@RestController
public class NaiveStreamingController {

    private final WebClient webClient;

    public NaiveStreamingController(WebClient webClient) {
        this.webClient = webClient;
    }

    // DANGER: This controller blocks on each chunk or resolves the entire list before responding.
    // It completely defeats the purpose of streaming and risks blocking Netty worker threads.
    @GetMapping("/api/naive-stream")
    public List<String> naiveStream(@RequestParam String prompt) {
        return webClient.post()
            .uri("/api/generate")
            .bodyValue(java.util.Map.of("model", "qwen2.5:3b", "prompt", prompt, "stream", false))
            .retrieve()
            .bodyToMono(OllamaResponse.class)
            .map(OllamaResponse::response)
            .collectList() // DANGER: Blocks until the full response is generated
            .block();
    }

    private static record OllamaResponse(String response) {}
}
```

### B. The Hardened Reactive SSE Controller (Production Pattern)

Here is the hardened production pattern. We implement an SSE streaming controller. We map the incoming stream from Ollama to Spring's `ServerSentEvent` wrappers. We handle network connection timeouts, filter empty tokens, ensure connection clean-up on client disconnect, and protect the stream endpoint with Spring Security configurations.

First, the Spring Security configuration for the SSE endpoint:

```java
package com.security.api.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.web.reactive.EnableWebFluxSecurity;
import org.springframework.security.config.web.server.ServerHttpSecurity;
import org.springframework.security.web.server.SecurityWebFilterChain;

@Configuration
@EnableWebFluxSecurity
public class StreamSecurityConfig {

    @Bean
    public SecurityWebFilterChain securityWebFilterChain(ServerHttpSecurity http) {
        return http
            .csrf(csrf -> csrf.disable()) // Disabled for local LLM proxy endpoints
            .authorizeExchange(exchanges -> exchanges
                .pathMatchers("/api/stream-tokens").authenticated() // Keep streaming secured
                .anyExchange().permitAll()
            )
            .httpBasic(httpBasic -> {}) // Basic authentication for demonstration
            .build();
    }
}
```

Next, the reactive service that consumes the Ollama stream:

```java
package com.security.api.service;

import com.fasterxml.jackson.annotation.JsonProperty;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Flux;
import java.time.Duration;
import java.util.Map;

@Service
public class OllamaStreamService {

    private final WebClient webClient;

    public OllamaStreamService(WebClient webClient) {
        this.webClient = webClient;
    }

    public Flux<String> streamTokens(String prompt) {
        Map<String, Object> payload = Map.of(
            "model", "qwen2.5:3b",
            "prompt", prompt,
            "stream", true
        );

        return this.webClient.post()
            .uri("/api/generate")
            .contentType(MediaType.APPLICATION_JSON)
            .bodyValue(payload)
            .retrieve()
            .bodyToFlux(OllamaChunk.class)
            .timeout(Duration.ofSeconds(15)) // Timeout if Ollama fails to respond with a token for 15s
            .map(OllamaChunk::response)
            .filter(token -> token != null && !token.isEmpty())
            .onErrorResume(e -> {
                // Return a structured error token and terminate the stream gracefully
                return Flux.just(" [Inference Error: Stream interrupted] ");
            });
    }

    // Jackson mappings for Ollama's stream chunk payload
    public record OllamaChunk(
        @JsonProperty("response") String response,
        @JsonProperty("done") boolean done
    ) {}
}
```

Finally, the Controller that publishes the Server-Sent Events stream:

```java
package com.security.api.controller;

import com.security.api.service.OllamaStreamService;
import org.springframework.http.MediaType;
import org.springframework.http.codec.ServerSentEvent;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import reactor.core.publisher.Flux;

@RestController
public class StreamController {

    private final OllamaStreamService streamService;

    public StreamController(OllamaStreamService streamService) {
        this.streamService = streamService;
    }

    @GetMapping(value = "/api/stream-tokens", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public Flux<ServerSentEvent<String>> streamInterviewFeedback(@RequestParam String prompt) {
        return streamService.streamTokens(prompt)
            .map(token -> ServerSentEvent.<String>builder()
                .data(token)
                .event("token")
                .build())
            // Send an explicit "complete" event to inform the frontend client to close its EventSource connection
            .concatWith(Flux.just(ServerSentEvent.<String>builder()
                .event("complete")
                .data("[DONE]")
                .build()))
            // Log connection terminations (e.g. client clicks away or closes browser tab)
            .doOnCancel(() -> System.out.println("Reactive Stream: Client cancelled connection. Releasing upstream pipeline."));
    }
}
```

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Missing the `MediaType.TEXT_EVENT_STREAM_VALUE` Header
Returning a raw `Flux<String>` without configuring the controller response mapping `produces = MediaType.TEXT_EVENT_STREAM_VALUE`.
*   **Why it fails**: Standard Spring Boot controllers fall back to JSON serialization. WebFlux will wait for the entire `Flux` stream to complete, buffer all the values in memory, convert the array into a giant JSON document, and return a single chunk, bypassing streaming entirely.
*   **Mitigation**: Always declare `produces = MediaType.TEXT_EVENT_STREAM_VALUE` inside the `@GetMapping` annotation parameters.

### Pitfall 2: Memory Leaks on Client Abandonment
Leaving the connection pool configured to never close abandoned client sockets.
*   **Why it fails**: If the candidate closes their web browser tab halfway through an LLM generation, the client connection breaks. If WebClient's HTTP client is not configured to propagate cancellation signals, it will continue pulling tokens from Ollama and keeping buffers active, causing thread leaks.
*   **Mitigation**: Implement `.doOnCancel()` to capture client disconnect signals and make sure Reactor Netty propagates the cancellation down to the HTTP client socket level.

---

## 5. Socratic Review Questions

### Question 1
Why does a standard Web Browser's native JS `EventSource` object reconnect automatically if the Spring WebFlux server restarts mid-session? How do we prevent infinite loops on complete generation events?

#### Answer
The HTML5 SSE standard specifies that the browser must attempt to reconnect to the endpoint if the TCP connection is unexpectedly severed. The server can control this by sending a `retry` instruction. However, once the model is done, we do not want a reconnect. We send an explicit application event (`complete` or `[DONE]`) inside our stream. The frontend JavaScript client listens for this specific event type and calls `eventSource.close()` immediately, preventing the browser from attempting reconnection.

### Question 2
What is the difference in handling Backpressure between Server-Sent Events and WebSockets when client throughput drops?

#### Answer
Server-Sent Events run over HTTP/1.1 or HTTP/2 chunked transfer encoding. Backpressure is managed at the TCP/IP level via flow control windows. If the client stops reading data, the browser's TCP receive buffer fills up, the OS stops acknowledging TCP packets, and the server's TCP send buffer fills up. Netty detects this socket-write bottleneck, triggers a backpressure signal back up to the Project Reactor publisher, and suspends emissions. WebSockets operate similarly at the TCP level, but because it is a bi-directional custom framing protocol, handling backpressure requires custom application-level frame management protocols to prevent queue bloat.

---

## 6. Hands-on Challenge: Reactive Stream Token Filter

### The Challenge
In this challenge, you will implement a reactive stream processing pipeline in Java.
Your task:
1. Complete `filterAndTransformStream` inside `StreamProcessor`.
2. Given a input stream `Flux<String>` representing raw token inputs:
   - Filter out any blank tokens or tokens containing only whitespace.
   - Stop processing (terminate the stream) if you encounter a termination token: `"[TERMINATE]"`.
   - Wrap each remaining token inside a `ServerSentEvent` object with event name `"feedback"`.
   
Complete the implementation stub below:

```java
package com.security.api;

import org.springframework.http.codec.ServerSentEvent;
import reactor.core.publisher.Flux;
import org.junit.jupiter.api.Test;
import java.util.List;
import static org.junit.jupiter.api.Assertions.*;

class StreamProcessor {

    public Flux<ServerSentEvent<String>> filterAndTransformStream(Flux<String> inputFlux) {
        // TODO: Implement the reactive pipeline:
        // 1. Take inputFlux.
        // 2. Filter out null, empty, or purely blank strings.
        // 3. Use takeUntil to stop processing if the token equals "[TERMINATE]" (and exclude it from SSE emissions).
        // 4. Map the valid tokens into ServerSentEvent<String> with event name "feedback".
        
        return Flux.empty();
    }
}
```

### Verification JUnit 5 Test

Write a test file named `src/test/java/com/security/api/StreamProcessorTest.java` (or run locally) to assert that your filtering rules work correctly:

```java
package com.security.api;

import org.junit.jupiter.api.Test;
import org.springframework.http.codec.ServerSentEvent;
import reactor.core.publisher.Flux;
import reactor.test.StepVerifier;

class StreamProcessorTest {

    @Test
    void testFilterAndTransformStream() {
        StreamProcessor processor = new StreamProcessor();
        Flux<String> input = Flux.just("Hello", " ", "", "World", "[TERMINATE]", "Ignored");

        Flux<ServerSentEvent<String>> result = processor.filterAndTransformStream(input);

        StepVerifier.create(result)
            .expectNextMatches(sse -> "feedback".equals(sse.event()) && "Hello".equals(sse.data()))
            .expectNextMatches(sse -> "feedback".equals(sse.event()) && "World".equals(sse.data()))
            .expectComplete()
            .verify();
    }
}
```

Verify that whitespace tokens are dropped and that the stream terminates immediately upon reaching the shutdown keyword.
