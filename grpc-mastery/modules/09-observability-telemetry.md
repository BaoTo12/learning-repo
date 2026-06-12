# Module 09: Observability: OpenTelemetry and SLF4J in Java

## 1. What Problem This Module Solves
In a microservices ecosystem, tracing a single user transaction across dozens of network hops is impossible without distributed tracing.
*   **Silent Failures**: If a request fails or experiences latency downstream, logs from individual services appear as isolated, disconnected events.
*   **Blind Performance Analysis**: Without structured metrics on RPC latency distributions (p95, p99) and network payload throughput, identifying bottlenecks is guesswork.

This module details how to manually integrate the OpenTelemetry Java SDK, bind context to SLF4J Mapped Diagnostic Context (MDC), and collect gRPC metrics using Micrometer Core without framework dependencies.

---

## 2. Distributed Tracing Mechanics

Distributed tracing relies on propagating a tracking trace context over HTTP/2 headers using standardized formats (like the **W3C Trace Context** specification).

```
   [ Client Request ]
           │  (Header: traceparent = 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01)
           ▼
   [ Gateway Service JVM ]
           │  (Logs bound to MDC: trace_id = 4bf92f3577...)
           ▼  (Injects updated parent span ID to downstream headers)
   [ Inventory Service JVM ]
```

The header contains:
*   **Trace ID**: A 16-byte unique identifier representing the entire transaction.
*   **Span ID**: An 8-byte identifier representing the specific segment of work (RPC call).
*   **Trace Flags**: Control options (e.g. `01` means sampling is active).

---

## 3. Trade-offs and Limitations
*   **Performance Overhead**: Generating trace spans and serializing telemetry data consumes CPU and memory. You must configure a **Sampling Rate** (e.g., sampling only 1% to 5% of requests in production).
*   **Storage Requirements**: Ingestion and storage of metrics and tracing telemetry require substantial server budgets. A central collector (OpenTelemetry Collector) should buffer and export telemetry asynchronously.

---

## 4. Common Mistakes and Anti-Patterns
*   **Using Automatic Java Agent Instrumentation blindly**: Relying on `-javaagent:opentelemetry-javaagent.jar` in high-throughput low-latency servers without custom filters. The agent scans and instrumentations everything (from JDBC queries to regex compilation) using bytecode manipulation, adding 5% to 15% latency. Manual instrumentation using interceptors provides granular control and better performance.
*   **Forgetting to Span.end()**: Failing to close a span in a `finally` block or when `onError`/`onCompleted` is called, which leaks memory and results in corrupt, infinite spans in metrics.

---

## 5. Integrating OpenTelemetry & SLF4J Interceptors

Let's implement a manual W3C Trace Context injector/extractor using the OpenTelemetry API.

### 5.1 OpenTelemetry gRPC Metadata Propagator Wrapper
```java
package com.example.grpc.observability;

import io.grpc.Metadata;
import io.opentelemetry.context.propagation.TextMapGetter;
import io.opentelemetry.context.propagation.TextMapSetter;

// Custom Getter/Setter adapters to map OpenTelemetry TraceContext propagation format to gRPC Metadata.
public final class GrpcMetadataPropagator {

    public static final TextMapSetter<Metadata> SETTER = new TextMapSetter<>() {
        @Override
        public void set(Metadata carrier, String key, String value) {
            if (carrier != null) {
                Metadata.Key<String> metadataKey = Metadata.Key.of(key, Metadata.ASCII_STRING_MARSHALLER);
                carrier.put(metadataKey, value);
            }
        }
    };

    public static final TextMapGetter<Metadata> GETTER = new TextMapGetter<>() {
        @Override
        public Iterable<String> keys(Metadata carrier) {
            return carrier.keys();
        }

        @Override
        public String get(Metadata carrier, String key) {
            if (carrier != null) {
                Metadata.Key<String> metadataKey = Metadata.Key.of(key, Metadata.ASCII_STRING_MARSHALLER);
                return carrier.get(metadataKey);
            }
            return null;
        }
    };
}
```

---

### 5.2 Server Tracing Interceptor (OpenTelemetry SDK + MDC Logging)
```java
package com.example.grpc.observability;

import io.grpc.*;
import io.opentelemetry.api.GlobalOpenTelemetry;
import io.opentelemetry.api.trace.*;
import io.opentelemetry.context.Context;
import io.opentelemetry.context.Scope;
import org.slf4j.MDC;

public class ServerTelemetryInterceptor implements ServerInterceptor {

    private final Tracer tracer;

    public ServerTelemetryInterceptor() {
        // Fetch Tracer from OpenTelemetry SDK singleton registration
        this.tracer = GlobalOpenTelemetry.getTracer("grpc-server-instrumentation", "1.0.0");
    }

    @Override
    public <ReqT, RespT> ServerCall.Listener<ReqT> interceptCall(
            ServerCall<ReqT, RespT> call,
            Metadata headers,
            ServerMethodDefinition<ReqT, RespT> next) {

        // 1. Extract W3C Trace Context from gRPC metadata headers
        Context parentContext = GlobalOpenTelemetry.getPropagators()
            .getTextMapPropagator()
            .extract(Context.current(), headers, GrpcMetadataPropagator.GETTER);

        // 2. Start telemetry Span as child of incoming context
        Span span = tracer.spanBuilder("RPC " + call.getMethodDescriptor().getFullMethodName())
            .setParent(parentContext)
            .setSpanKind(SpanKind.SERVER)
            .startSpan();

        // 3. Inject Trace ID into SLF4J MDC context for structured logging
        String traceId = span.getSpanContext().getTraceId();
        MDC.put("trace_id", traceId);

        // Bind OpenTelemetry context thread-safely
        io.grpc.Context grpcCtx = io.grpc.Context.current();

        try (Scope scope = span.makeCurrent()) {
            ServerCall.Listener<ReqT> listener = next.startCall(
                new ForwardingServerCall.SimpleForwardingServerCall<ReqT, RespT>(call) {
                    @Override
                    public void close(Status status, Metadata trailers) {
                        // Record status, error codes, and close span
                        if (!status.isOk()) {
                            span.setStatus(StatusCode.ERROR, status.getDescription());
                            span.recordException(status.asException());
                        } else {
                            span.setStatus(StatusCode.OK);
                        }
                        span.end();
                        MDC.remove("trace_id"); // Clean up thread local MDC
                        super.close(status, trailers);
                    }
                }, headers
            );

            // Wrap listener execution to preserve trace context in callback threads
            return new ForwardingServerCallListener.SimpleForwardingServerCallListener<ReqT>(listener) {
                @Override
                public void onHalfClose() {
                    try (Scope ignored = span.makeCurrent()) {
                        MDC.put("trace_id", traceId);
                        super.onHalfClose();
                    } finally {
                        MDC.remove("trace_id");
                    }
                }
            };
        }
    }
}
```

---

## 6. Metrics Collection with Micrometer Core

Micrometer Core allows you to measure server throughput and call durations:

```java
package com.example.grpc.observability;

import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Timer;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import java.util.concurrent.TimeUnit;

public class GrpcMetricsCollector {

    private final MeterRegistry registry = new SimpleMeterRegistry();
    private final Timer rpcTimer;

    public GrpcMetricsCollector() {
        this.rpcTimer = Timer.builder("grpc.server.call.duration")
            .description("Duration of incoming gRPC calls")
            .publishPercentiles(0.5, 0.95, 0.99)
            .register(registry);
    }

    public void recordCallDuration(String methodName, long durationNs) {
        rpcTimer.record(durationNs, TimeUnit.NANOSECONDS);
        System.out.printf("[Metrics] Method: %s | Count: %d | p95: %.2f ms | p99: %.2f ms\n",
            methodName, 
            rpcTimer.count(),
            rpcTimer.percentileValues()[1].value() / 1_000_000.0,
            rpcTimer.percentileValues()[2].value() / 1_000_000.0
        );
    }
}
```

---

## 7. Interview Questions

### Q1: Why is mapping trace IDs to SLF4J MDC using ThreadLocal variables risky in reactive or asynchronous gRPC handlers? How do you fix it?
**Answer**: 
*   **Risk**: SLF4J’s MDC relies internally on standard `ThreadLocal` storage. In reactive (non-blocking) or async environments, execution regularly jumps threads. If Thread A handles `onMessage()` and Thread B handles the subsequent database lookup, MDC trace IDs will not propagate to Thread B, leaving Thread B's log outputs untraced while Thread A's context stays stale on its reused thread.
*   **Fix**: Wrap executors using OpenTelemetry context wrappers (e.g. `Context.taskRunner(executor)`) or interceptors that capture OpenTelemetry contexts and reload/unload MDC storage boundaries using `MDC.put()` and `MDC.remove()` on every single callback entry point.

### Q2: What is the benefit of using the W3C Trace Context standard over proprietary formats (like zipkin's B3 specification)?
**Answer**: 
*   **B3 Specification**: Relies on specific headers (`X-B3-TraceId`, `X-B3-SpanId`) which are parsed manually and vary in formatting and naming across vendors.
*   **W3C Trace Context**: A standardized, unified spec defining one global header (`traceparent`) containing trace version, trace ID, parent span ID, and tracing flags in a strict hex format. It ensures that cloud load balancers, CDN providers, application proxies (Envoy), and microservices built across different languages can parse, propagate, and record telemetry data without mapping schemas.
