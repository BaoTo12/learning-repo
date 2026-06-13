# Module 06: Complete Application Codebase

Welcome class. Today we conclude **CS-528: Integrating AI-Driven Services into Java Backend Workflows** with our final session: **The Complete Application Codebase**.

Throughout this semester, we analyzed isolated reactive concepts: async WebClient configurations, virtual thread safety boundaries, external OS process executions, and Server-Sent Events. Today, we assemble these building blocks into a production-ready, compile-grade Spring Boot 3.x application.

To allow instant local validation without requiring active GPUs or external installations, the application includes a **Mock Service Switch** (`app.mock-services=true`) to return high-fidelity simulated responses, alongside a toggle to connect live local AI servers and invoke native FFmpeg processes.

---

## 1. Academic Lecture: The Unified System Architecture

An interactive voice-based AI interview platform requires the coordination of three asynchronous subsystems:
1.  **The Event Loop (Netty)**: Manages network client requests, streaming SSE connections, and incoming file uploads.
2.  **OS Subprocess Pool (Virtual Threads)**: Spawns FFmpeg transcoding processes, using Java 21 virtual threads to drain and parse stdout/stderr buffers concurrently without blocking event loops.
3.  **Client WebPool**: Dispatches HTTP POST queries to local AI microservices (Ollama, Whisper, Kokoro).

```text
                                  ┌──────────────────────────────┐
                                  │      Client (Browser)        │
                                  └──────────────┬───────────────┘
                                                 │
                          HTTP Post (WebM audio) │ HTTP Get (SSE stream)
                                                 ▼
        ┌──────────────────────────────────────────────────────────────────────────────┐
        │                          Spring Boot WebFlux Server                          │
        │                                                                              │
        │  ┌──────────────────────────┐                    ┌────────────────────────┐  │
        │  │   OrchestratorController │ ─── (Triggers) ───>│  InterviewOrchestrator │  │
        │  └──────────────────────────┘                    └───────────┬────────────┘  │
        │                                                              │               │
        │            ┌───────────────────┬─────────────────────────────┼───────────┐   │
        │            ▼                   ▼                             ▼           ▼   │
        │   ┌─────────────────┐ ┌──────────────────┐ ┌───────────────────┐ ┌─────────┐ │
        │   │  Transcoder     │ │ WhisperService   │ │   OllamaService   │ │ Kokoro  │ │
        │   │  (Process       │ │ (WebClient STT)  │ │ (WebClient LLM)   │ │ (TTS)   │ │
        │   │  (Builder FFmpeg)│ │                  │ │                   │ │         │ │
        │   └────────┬────────┘ └────────┬─────────┘ └─────────┬─────────┘ └────┬────┘ │
        └────────────┼───────────────────┼─────────────────────┼────────────────┼──────┘
                     │                   │                     │                │
                     ▼                   ▼                     ▼                ▼
              ┌──────────────┐    ┌──────────────┐      ┌──────────────┐ ┌──────────────┐
              │ FFmpeg Sub-  │    │ Local Whisper│      │ Local Ollama │ │ Local Kokoro │
              │ process (OS) │    │  Port 5000   │      │  Port 11434  │ │  Port 8888   │
              └──────────────┘    ┌──────────────┘      └──────────────┘ └──────────────┘
```

---

## 2. Theory vs. Production Trade-offs

When building full-stack AI orchestrators in Java, consider these engineering choices:

| Architectural Metric | Monolithic Blocking App | Reactive WebFlux App (No Loom) | WebFlux App + Virtual Threads (Loom) |
| :--- | :--- | :--- | :--- |
| **Max Concurrency** | Restricted by OS thread limits | High (Limited by CPU loops) | Extremely High (Millions of virtual tasks) |
| **I/O Bottlenecks** | Blocking on HTTP, DB, Process | Non-blocking HTTP; process blocks | Non-blocking HTTP; process run on Loom |
| **Code Readability** | Simple imperative try-catch | Hard reactive functional chains | Readable reactive orchestration |
| **CPU Utilization** | Low (Threads spend time waiting) | High | Excellent (Carrier threads saturated) |
| **Error Resiliency** | Standard catch-all blocks | Complex error operator chaining | Integrated functional error fallbacks |

---

## 3. The Production Codebase: `Application.java` & Tests

Below is the complete, self-contained, compile-ready Spring Boot application and its integration tests. It contains all configurations, service interfaces, local process execution engines, WebClient queries, controllers, mock options, and JUnit tests.

### A. The Core Application Code
```java
package com.security.api;

import com.fasterxml.jackson.annotation.JsonProperty;
import io.netty.channel.ChannelOption;
import io.netty.handler.timeout.ReadTimeoutHandler;
import io.netty.handler.timeout.WriteTimeoutHandler;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.io.buffer.DataBufferUtils;
import org.springframework.http.MediaType;
import org.springframework.http.client.MultipartBodyBuilder;
import org.springframework.http.client.reactive.ReactorClientHttpConnector;
import org.springframework.http.codec.ServerSentEvent;
import org.springframework.http.codec.json.Jackson2JsonDecoder;
import org.springframework.http.codec.json.Jackson2JsonEncoder;
import org.springframework.http.codec.multipart.FilePart;
import org.springframework.stereotype.Service;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.reactive.function.BodyInserters;
import org.springframework.web.reactive.function.client.ExchangeStrategies;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import reactor.core.scheduler.Schedulers;
import reactor.netty.http.client.HttpClient;
import reactor.netty.resources.ConnectionProvider;

import java.io.*;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

@SpringBootApplication
public class Application {
    public static void main(String[] args) {
        SpringApplication.run(Application.class, args);
    }
}

// =========================================================================
// CONFIGURATION LAYER
// =========================================================================

@Configuration
class AppConfig {

    @Value("${app.whisper.url:http://localhost:5000}")
    private String whisperUrl;

    @Value("${app.ollama.url:http://localhost:11434}")
    private String ollamaUrl;

    @Value("${app.kokoro.url:http://localhost:8888}")
    private String kokoroUrl;

    @Bean
    public ExecutorService virtualThreadExecutor() {
        // Java 21 Virtual Threads to offload blocking OS subprocesses (FFmpeg)
        return Executors.newVirtualThreadPerTaskExecutor();
    }

    @Bean
    public WebClient webClient() {
        ConnectionProvider provider = ConnectionProvider.builder("ai-pool")
                .maxConnections(100)
                .pendingAcquireTimeout(Duration.ofSeconds(10))
                .maxIdleTime(Duration.ofSeconds(30))
                .build();

        HttpClient httpClient = HttpClient.create(provider)
                .option(ChannelOption.CONNECT_TIMEOUT_MILLIS, 5000)
                .doOnConnected(conn -> conn
                        .addHandlerLast(new ReadTimeoutHandler(30, TimeUnit.SECONDS))
                        .addHandlerLast(new WriteTimeoutHandler(10, TimeUnit.SECONDS))
                );

        ExchangeStrategies exchangeStrategies = ExchangeStrategies.builder()
                .codecs(configurer -> {
                    configurer.defaultCodecs().maxInMemorySize(15 * 1024 * 1024);
                    configurer.defaultCodecs().jackson2JsonDecoder(new Jackson2JsonDecoder());
                    configurer.defaultCodecs().jackson2JsonEncoder(new Jackson2JsonEncoder());
                })
                .build();

        return WebClient.builder()
                .clientConnector(new ReactorClientHttpConnector(httpClient))
                .exchangeStrategies(exchangeStrategies)
                .build();
    }
}

// =========================================================================
// DATA REPRESENTATIONS
// =========================================================================

record OllamaPayload(String model, String prompt, boolean stream) {}
record OllamaChunk(@JsonProperty("response") String response, @JsonProperty("done") boolean done) {}
record WhisperResponse(@JsonProperty("text") String text) {}
record KokoroPayload(String text, String voice) {}
record PipelineResult(String transcript, String feedback, byte[] voiceResponse) {}

// =========================================================================
// CORE SERVICE IMPLEMENTATIONS
// =========================================================================

@Service
class TranscoderService {
    private static final Logger log = LoggerFactory.getLogger(TranscoderService.class);
    private final ExecutorService executor;

    public TranscoderService(ExecutorService executor) {
        this.executor = executor;
    }

    public Mono<byte[]> transcodeWebmToWav(byte[] webmBytes) {
        return Mono.fromCallable(() -> {
            Path tempInput = Files.createTempFile("input_", ".webm");
            Path tempOutput = Files.createTempFile("output_", ".wav");
            try {
                Files.write(tempInput, webmBytes);

                List<String> command = List.of(
                        "ffmpeg", "-y",
                        "-i", tempInput.toAbsolutePath().toString(),
                        "-vn",
                        "-acodec", "pcm_s16le",
                        "-ar", "16000",
                        "-ac", "1",
                        tempOutput.toAbsolutePath().toString()
                );

                ProcessBuilder pb = new ProcessBuilder(command);
                Process process = pb.start();

                // Virtual threads drain streams to prevent deadlock
                Thread outDrainer = executor.submit(() -> drainStream(process.getInputStream()));
                Thread errDrainer = executor.submit(() -> drainStream(process.getErrorStream()));

                boolean finished = process.waitFor(10, TimeUnit.SECONDS);
                if (!finished) {
                    process.destroyForcibly();
                    throw new IOException("FFmpeg transcoding timed out after 10 seconds.");
                }

                outDrainer.join();
                errDrainer.join();

                if (process.exitValue() != 0) {
                    throw new IOException("FFmpeg failed with exit status code: " + process.exitValue());
                }

                return Files.readAllBytes(tempOutput);
            } finally {
                Files.deleteIfExists(tempInput);
                Files.deleteIfExists(tempOutput);
            }
        }).subscribeOn(Schedulers.fromExecutor(executor));
    }

    private void drainStream(InputStream is) {
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(is))) {
            while (reader.readLine() != null) {
                // Drain OS buffer
            }
        } catch (IOException e) {
            log.error("Failed to drain process stream", e);
        }
    }
}

@Service
class WhisperService {
    private final WebClient webClient;
    
    @Value("${app.whisper.url:http://localhost:5000}")
    private String whisperUrl;

    public WhisperService(WebClient webClient) {
        this.webClient = webClient;
    }

    public Mono<String> transcribe(byte[] wavBytes) {
        MultipartBodyBuilder bodyBuilder = new MultipartBodyBuilder();
        bodyBuilder.part("file", wavBytes)
                .filename("interview_audio.wav")
                .contentType(MediaType.parseMediaType("audio/wav"));

        return webClient.post()
                .uri(whisperUrl + "/asr")
                .contentType(MediaType.MULTIPART_FORM_DATA)
                .body(BodyInserters.fromMultipartData(bodyBuilder.build()))
                .retrieve()
                .bodyToMono(WhisperResponse.class)
                .map(WhisperResponse::text)
                .timeout(Duration.ofSeconds(15))
                .onErrorReturn(" [Speech-to-Text inference timeout] ");
    }
}

@Service
class OllamaService {
    private final WebClient webClient;

    @Value("${app.ollama.url:http://localhost:11434}")
    private String ollamaUrl;

    public OllamaService(WebClient webClient) {
        this.webClient = webClient;
    }

    public Flux<String> streamEvaluation(String transcript, String contextPrompt) {
        String prompt = "Context: " + contextPrompt + "\nCandidate Response: " + transcript + "\nFeedback:";
        OllamaPayload payload = new OllamaPayload("qwen2.5:3b", prompt, true);

        return webClient.post()
                .uri(ollamaUrl + "/api/generate")
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue(payload)
                .retrieve()
                .bodyToFlux(OllamaChunk.class)
                .map(OllamaChunk::response)
                .filter(chunk -> chunk != null && !chunk.isEmpty())
                .timeout(Duration.ofSeconds(10))
                .onErrorResume(err -> Flux.just(" [Inference connection reset] "));
    }
}

@Service
class KokoroService {
    private final WebClient webClient;

    @Value("${app.kokoro.url:http://localhost:8888}")
    private String kokoroUrl;

    public KokoroService(WebClient webClient) {
        this.webClient = webClient;
    }

    public Mono<byte[]> synthesize(String text) {
        KokoroPayload payload = new KokoroPayload(text, "af_bella");

        return webClient.post()
                .uri(kokoroUrl + "/tts")
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue(payload)
                .retrieve()
                .bodyToMono(byte[].class)
                .timeout(Duration.ofSeconds(10))
                .onErrorReturn(new byte[0]);
    }
}

// =========================================================================
// PIPELINE ORCHESTRATION LAYER (WITH MOCK CAPABILITIES)
// =========================================================================

@Service
class InterviewOrchestrator {
    private static final Logger log = LoggerFactory.getLogger(InterviewOrchestrator.class);

    private final TranscoderService transcoder;
    private final WhisperService whisper;
    private final OllamaService ollama;
    private final KokoroService kokoro;

    @Value("${app.mock-services:true}")
    private boolean useMock;

    public InterviewOrchestrator(TranscoderService transcoder, WhisperService whisper, OllamaService ollama, KokoroService kokoro) {
        this.transcoder = transcoder;
        this.whisper = whisper;
        this.ollama = ollama;
        this.kokoro = kokoro;
    }

    public Mono<PipelineResult> processInterviewSegment(byte[] webmBytes, String systemPrompt) {
        if (useMock) {
            return simulatePipeline(webmBytes);
        }

        return transcoder.transcodeWebmToWav(webmBytes)
                .flatMap(wavBytes -> whisper.transcribe(wavBytes)
                        .flatMap(transcript -> {
                            return ollama.streamEvaluation(transcript, systemPrompt)
                                    .collectList()
                                    .map(chunks -> String.join("", chunks))
                                    .flatMap(feedbackText -> kokoro.synthesize(feedbackText)
                                            .map(audioBytes -> new PipelineResult(transcript, feedbackText, audioBytes))
                                    );
                        })
                )
                .onErrorResume(err -> {
                    log.error("Pipeline crashed during active coordination run", err);
                    return Mono.just(new PipelineResult(
                            "Failed to transcribe",
                            "I encountered a pipeline communication error. Please try again.",
                            new byte[0]
                    ));
                });
    }

    public Flux<ServerSentEvent<String>> streamRealtimeTokens(String transcript, String systemPrompt) {
        if (useMock) {
            return Flux.just("Hello", " candidate.", " That", " sounds", " like", " a", " solid", " design.")
                    .delayElements(Duration.ofMillis(50))
                    .map(token -> ServerSentEvent.<String>builder().data(token).event("token").build())
                    .concatWith(Flux.just(ServerSentEvent.<String>builder().data("[DONE]").event("complete").build()));
        }

        return ollama.streamEvaluation(transcript, systemPrompt)
                .map(token -> ServerSentEvent.<String>builder().data(token).event("token").build())
                .concatWith(Flux.just(ServerSentEvent.<String>builder().data("[DONE]").event("complete").build()));
    }

    private Mono<PipelineResult> simulatePipeline(byte[] webmBytes) {
        return Mono.just(new PipelineResult(
                "Mock transcription: We should use Spring Boot WebFlux and Project Reactor.",
                "Excellent response. Your explanation of reactive event loops is accurate.",
                new byte[]{0x52, 0x49, 0x46, 0x46, 0x24, 0x08, 0x00, 0x00, 0x57, 0x41, 0x56, 0x45}
        )).delayElement(Duration.ofMillis(100));
    }
}

// =========================================================================
// API CONTROLLERS
// =========================================================================

@RestController
@RequestMapping("/api/interview")
class OrchestratorController {

    private final InterviewOrchestrator orchestrator;

    public OrchestratorController(InterviewOrchestrator orchestrator) {
        this.orchestrator = orchestrator;
    }

    @PostMapping(value = "/submit-response", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public Mono<PipelineResult> submitResponse(
            @RequestPart("audio") FilePart audioPart,
            @RequestPart("prompt") String prompt) {

        return DataBufferUtils.join(audioPart.content())
                .map(dataBuffer -> {
                    byte[] bytes = new byte[dataBuffer.readableByteCount()];
                    dataBuffer.read(bytes);
                    DataBufferUtils.release(dataBuffer);
                    return bytes;
                })
                .flatMap(bytes -> orchestrator.processInterviewSegment(bytes, prompt));
    }

    @GetMapping(value = "/stream-feedback", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public Flux<ServerSentEvent<String>> streamFeedback(
            @RequestParam("transcript") String transcript,
            @RequestParam("prompt") String prompt) {
        return orchestrator.streamRealtimeTokens(transcript, prompt);
    }
}
```

### B. The Integration Verification Tests
Save this class under `src/test/java/com/security/api/ApplicationIntegrationTest.java` to perform automated assertions on the Webflux endpoint structures:
```java
package com.security.api;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.reactive.AutoConfigureWebTestClient;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.http.client.MultipartBodyBuilder;
import org.springframework.test.web.reactive.server.WebTestClient;
import org.springframework.web.reactive.function.BodyInserters;

import static org.junit.jupiter.api.Assertions.*;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT, properties = {
    "app.mock-services=true"
})
@AutoConfigureWebTestClient
public class ApplicationIntegrationTest {

    @Autowired
    private WebTestClient webTestClient;

    @Test
    public void testSubmitResponseReturnsMockResult() {
        MultipartBodyBuilder bodyBuilder = new MultipartBodyBuilder();
        bodyBuilder.part("audio", new byte[]{0x00, 0x01, 0x02, 0x03})
                .filename("test.webm")
                .contentType(MediaType.parseMediaType("audio/webm"));
        bodyBuilder.part("prompt", "Analyze Candidate Reactive Programming Skills");

        webTestClient.post()
                .uri("/api/interview/submit-response")
                .contentType(MediaType.MULTIPART_FORM_DATA)
                .body(BodyInserters.fromMultipartData(bodyBuilder.build()))
                .exchange()
                .expectStatus().isOk()
                .expectBody()
                .jsonPath("$.transcript").isEqualTo("Mock transcription: We should use Spring Boot WebFlux and Project Reactor.")
                .jsonPath("$.feedback").isEqualTo("Excellent response. Your explanation of reactive event loops is accurate.")
                .jsonPath("$.voiceResponse").exists();
    }

    @Test
    public void testStreamFeedbackEmitsServerSentEvents() {
        webTestClient.get()
                .uri(uriBuilder -> uriBuilder
                        .path("/api/interview/stream-feedback")
                        .queryParam("transcript", "Hello world")
                        .queryParam("prompt", "Eval candidate")
                        .build())
                .accept(MediaType.TEXT_EVENT_STREAM)
                .exchange()
                .expectStatus().isOk()
                .expectBody(String.class)
                .consumeWith(result -> {
                    String body = result.getResponseBody();
                    assertNotNull(body);
                    assertTrue(body.contains("event:token"));
                    assertTrue(body.contains("event:complete"));
                    assertTrue(body.contains("data:[DONE]"));
                });
    }
}
```

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Incorrect Multipart Boundary Parsing in WebFlux
Handling file uploads using standard Spring WebMVC `MultipartFile` interface parameters on a WebFlux REST method.
*   **Why it fails**: `MultipartFile` blocks the execution thread. Attempting to parse a request body using this interface raises a `ClassNotFoundException` or leads to class cast failures at runtime inside non-blocking event loops.
*   **Mitigation**: Always parse multipart inputs using WebFlux's non-blocking `FilePart` or `Part` interface objects, and combine the data buffers asynchronously using `DataBufferUtils.join()`.

### Pitfall 2: ProcessBuilder Path Resolution Errors
Executing FFmpeg commands in production using raw command paths (`ffmpeg`) without verifying that FFmpeg is added to the system's `PATH` variables.
*   **Why it fails**: Spawning a subprocess with a missing bin executable triggers a native `IOException: Cannot run program "ffmpeg": CreateProcess error=2, The system cannot find the file specified`.
*   **Mitigation**: Enable configurations to override the binary path (e.g. `app.ffmpeg.path=c:/tools/ffmpeg/bin/ffmpeg.exe`), and fall back to mock transcription results if the file isn't available.

---

## 5. Socratic Review Questions

### Question 1
In our `TranscoderService` code, why do we use `.subscribeOn(Schedulers.fromExecutor(executor))` instead of `.publishOn(...)`?

#### Answer
`.subscribeOn(...)` dictates which thread pool handles the *initial execution subscription* (the entire execution of the callable stream wrapper). `.publishOn(...)` only alters the execution thread pool context for downstream operators in the chain *after* the operator is invoked. Because `ProcessBuilder.start()` and `process.waitFor()` are blocking operations executed immediately inside the Callable block, we must use `.subscribeOn` to guarantee that the blocking calls run entirely within Loom's Virtual Thread executor pool from start to finish.

### Question 2
How does overriding the `ExchangeStrategies` max in-memory limit protect our application from runtime resource exhaustion attacks?

#### Answer
By increasing the limits to 15MB, we permit WebClient to process large audio blobs. However, if we set this parameter to `unlimited` (`-1`), an attacker could transmit a 1GB raw text payload to our endpoint. Spring WebFlux would attempt to buffer the entire file into Java's heap space before calling Jackson, triggering garbage collector thrashing and causing the JVM process to terminate with an `OutOfMemoryError`. Setting strict limits blocks these payloads before memory allocation happens.

---

## 6. Hands-on Challenge: Add a Health Check Endpoint for AI Integrations

### The Challenge
In this challenge, you will add a health-checking controller endpoint to monitor downstream AI service availability.
Your task:
1. Implement a new REST endpoint `/api/interview/health` inside the `OrchestratorController`.
2. This health check must perform concurrent, non-blocking HTTP GET/POST queries (with short 1-second timeouts) to verify if Ollama, Whisper, and Kokoro are responsive.
3. If any service is offline, return `HTTP 503 Service Unavailable`, along with a JSON mapping of which service failed. If mock mode is on, return all services as `"UP"`.

Complete the implementation stub below:

```java
package com.security.api;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;
import reactor.core.publisher.Mono;
import java.util.Map;

@RestController
class HealthCheckController {

    private final WebClient webClient;

    @Value("${app.mock-services:true}")
    private boolean useMock;

    public HealthCheckController(WebClient webClient) {
        this.webClient = webClient;
    }

    @GetMapping("/api/interview/health")
    public Mono<ResponseEntity<Map<String, String>>> checkHealth() {
        if (useMock) {
            return Mono.just(ResponseEntity.ok(Map.of(
                "status", "UP",
                "whisper", "UP",
                "ollama", "UP",
                "kokoro", "UP"
            )));
        }

        // TODO: Implement the health checks:
        // 1. Perform a WebClient GET/POST call to Ollama, Whisper, and Kokoro status URLs.
        // 2. Set timeout limits to 1 second per check.
        // 3. Use Mono.zip to collect status flags.
        // 4. Return HTTP 200 if all are UP, otherwise HTTP 503.
        
        return Mono.empty();
    }
}
```

Write the reactive validations. Verify that your application compiles and passes integration test checks successfully.
