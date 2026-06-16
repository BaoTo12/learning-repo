# CS-528: Integrating AI-Driven Services into Java Backend Workflows

Welcome to **CS-528: Integrating AI-Driven Services into Java Backend Workflows**. I am Professor Antigravity. In this course, we will study high-performance integration patterns to orchestrate local and remote AI models using Java 21, Spring Boot 3.x, and reactive frameworks.

Deploying AI capabilities (like Speech-to-Text transcribers, Large Language Models, and Text-to-Speech generators) into web backend architectures introduces severe execution constraints. AI inferences consume massive CPU/GPU cycles, introduce response latencies ranging from seconds to minutes, and require streaming token outputs to preserve user experience. Traditional block-and-wait HTTP calls lead to thread pool starvation, causing the entire backend service to freeze.

To solve this, we will write non-blocking integration layers using **Spring WebFlux WebClient**, manage parallel execution pipelines using **Java 21 Virtual Threads (Loom)**, spawn external audio transcoder binaries securely via **ProcessBuilder**, and stream live token sequences back to user browsers using **Server-Sent Events (SSE)**.

---

## Course Syllabus & Navigation

The course is divided into 6 detailed modules:

| Module | Core Classification | Focus Topics |
| :--- | :--- | :--- |
| **01** | [Async WebClient Integration](file:///c:/Users/Admin/Desktop/projects/learning-repo/java-ai-integration/modules/01-async-webclient-integration.md) | Non-blocking HTTP endpoints routing, WebClient settings, connection pooling, client filters, timeout thresholds, and Jackson JSON mappings. |
| **02** | [Virtual Threads (Loom)](file:///c:/Users/Admin/Desktop/projects/learning-repo/java-ai-integration/modules/02-thread-pools-virtual-threads.md) | Thread starvation mitigation, platform vs. virtual threads, custom Spring AsyncTaskExecutors, and parallel AI execution gates. |
| **03** | [Process Execution & Transcoding](file:///c:/Users/Admin/Desktop/projects/learning-repo/java-ai-integration/modules/03-process-execution-transcoding.md) | Spawning OS subprocesses with ProcessBuilder, safe stream redirections, timeout bounds, and preventing command shell injections. |
| **04** | [Streaming SSE & WebSockets](file:///c:/Users/Admin/Desktop/projects/learning-repo/java-ai-integration/modules/04-streaming-sse-websockets.md) | Real-time response patterns, Server-Sent Events (SSE), HTML5 EventSource, and mapping reactive Flux buffers to chunked HTTP responses. |
| **05** | [Capstone System Design](file:///c:/Users/Admin/Desktop/projects/learning-repo/java-ai-integration/modules/05-capstone-interview-orchestrator.md) | Multi-stage pipeline architecture coordinating FFmpeg transcoding, Whisper STT, Ollama LLM evaluations, and Kokoro TTS audio generation. |
| **06** | [Complete Application Codebase](file:///c:/Users/Admin/Desktop/projects/learning-repo/java-ai-integration/modules/06-complete-application-codebase.md) | Self-contained, copy-paste-ready Spring Boot project containing reactive endpoint controllers, WebClient clients, ProcessBuilder, and JUnit tests. |

---

## Local Environment Configuration

Ensure you have **Java 21 (JDK 21)** and **Maven 3.9+** installed, alongside **FFmpeg** set up in your system's PATH.

### 1. Maven Dependency Configuration (`pom.xml`)
Inject the following dependencies into your Spring Boot Maven project:
```xml
<dependencies>
    <!-- Reactive Web Stack -->
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-webflux</artifactId>
    </dependency>

    <!-- Jackson for JSON parsing -->
    <dependency>
        <groupId>com.fasterxml.jackson.core</groupId>
        <artifactId>jackson-databind</artifactId>
    </dependency>

    <!-- Project Reactor Extra Utilities -->
    <dependency>
        <groupId>io.projectreactor</groupId>
        <artifactId>reactor-core</artifactId>
    </dependency>

    <!-- Testing Suite -->
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-test</artifactId>
        <scope>test</scope>
    </dependency>
    <dependency>
        <groupId>io.projectreactor</groupId>
        <artifactId>reactor-test</artifactId>
        <scope>test</scope>
    </dependency>
</dependencies>
```

---

## Grading Criteria & Defensive Success Metrics

Your progress in this course is evaluated based on the following engineering rubrics:

*   **Reactive Flow Architecture (30%)**: Correctly building non-blocking pipelines, handling backpressure, and streaming chunked data sequences.
*   **Resource Concurrency Safety (25%)**: Implementing virtual thread executors, avoiding thread starvation, and managing process lifecycles.
*   **Subprocess Security (25%)**: Enforcing command validation to block command shell injections during binary execution.
*   **Integration Completeness (20%)**: Implementing test coverage for connection pools, process wrappers, and reactive controller responses.
