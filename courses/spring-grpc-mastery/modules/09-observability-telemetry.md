# Module 09: Observability: Micrometer and OpenTelemetry

## 1. What Problem This Module Solves
Distributed systems are prone to opaque execution issues:
*   **Log Fragmentation**: Downstream errors appear as isolated events, preventing developers from tracing a transaction's lifecycle across network hops.
*   **Invisible Latencies**: Without real-time latency distribution metrics (p95, p99), detecting performance bottlenecks in downstream microservices is guess-work.

This module details how to manually integrate Spring Boot Actuator, Micrometer core, and the OpenTelemetry Java SDK to collect metrics and export trace pipelines to Prometheus and Jaeger.

---

## 2. Telemetry Stack Architecture

```
   [ Incoming Request ] 
            │  (Propagation Header: traceparent)
            ▼
   [ Spring Boot gRPC App ] ───(Export Metrics to Prometheus Port 8081) ───► [ Prometheus ]
            │                                                                      │
            ├─► Injects Span Context to MDC (Slf4j logs)                           ▼
            │                                                                [ Grafana Dashboard ]
            └─► Exports Spans (OTLP gRPC) ─────────────────────────► [ Jaeger Collector ]
```

*   **Prometheus**: Pulls system and business metrics from the Spring Boot `/actuator/prometheus` endpoint.
*   **Jaeger**: Collects distributed trace spans exported via OpenTelemetry OTLP handlers.
*   **Grafana**: Queries Prometheus and Jaeger to visualize system health.

---

## 3. Configuring Actuator and Micrometer (`application.yml`)

Enable Actuator web metrics collection and configure the OpenTelemetry tracing export targets:

```yaml
management:
  endpoints:
    web:
      exposure:
        include: prometheus,health,info,metrics
  endpoint:
    prometheus:
      enabled: true
  metrics:
    distribution:
      percentiles-simple:
        grpc.server.requests: 0.5, 0.95, 0.99 # Latency percentiles
# OpenTelemetry Configuration
otel:
  exporter:
    otlp:
      endpoint: http://localhost:4317 # Jaeger gRPC collector
  resource:
    attributes:
      service.name: user-service
```

---

## 4. Micrometer gRPC Server Metrics Collection

To measure call execution duration and throughput in Spring Boot:

```java
package com.example.grpc.observability;

import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Timer;
import io.grpc.*;
import net.devh.boot.grpc.server.interceptor.GrpcGlobalServerInterceptor;
import org.springframework.beans.factory.annotation.Autowired;

@GrpcGlobalServerInterceptor
public class MetricsServerInterceptor implements ServerInterceptor {

    private final MeterRegistry registry;

    @Autowired
    public MetricsServerInterceptor(MeterRegistry registry) {
        this.registry = registry;
    }

    @Override
    public <ReqT, RespT> ServerCall.Listener<ReqT> interceptCall(
            ServerCall<ReqT, RespT> call,
            Metadata headers,
            ServerMethodDefinition<ReqT, RespT> next) {

        long start = System.nanoTime();
        String methodName = call.getMethodDescriptor().getFullMethodName();

        return next.startCall(new ForwardingServerCall.SimpleForwardingServerCall<ReqT, RespT>(call) {
            @Override
            public void close(Status status, Metadata trailers) {
                long duration = System.nanoTime() - start;
                
                // Record request latency using Micrometer
                Timer.builder("grpc.server.requests")
                    .tag("method", methodName)
                    .tag("status", status.getCode().name())
                    .register(registry)
                    .record(duration, java.util.concurrent.TimeUnit.NANOSECONDS);

                super.close(status, trailers);
            }
        }, headers);
    }
}
```

---

## 5. Distributed Tracing using OpenTelemetry (MDC Linkage)

This server interceptor extracts trace context and maps the active Trace ID to the SLF4J MDC map:

```java
package com.example.grpc.observability;

import io.grpc.*;
import io.opentelemetry.api.trace.Span;
import net.devh.boot.grpc.server.interceptor.GrpcGlobalServerInterceptor;
import org.slf4j.MDC;

@GrpcGlobalServerInterceptor
public class TracingMdcInterceptor implements ServerInterceptor {

    private static final String MDC_TRACE_ID = "traceId";

    @Override
    public <ReqT, RespT> ServerCall.Listener<ReqT> interceptCall(
            ServerCall<ReqT, RespT> call,
            Metadata headers,
            ServerMethodDefinition<ReqT, RespT> next) {

        // Extract the active OpenTelemetry Trace ID from the current execution context
        String traceId = Span.current().getSpanContext().getTraceId();
        if (traceId != null && !traceId.isEmpty() && !traceId.equals("00000000000000000000000000000000")) {
            MDC.put(MDC_TRACE_ID, traceId);
        }

        ServerCall.Listener<ReqT> delegate = next.startCall(call, headers);

        // Wrap execution callbacks to reload the MDC context in worker threads
        return new ForwardingServerCallListener.SimpleForwardingServerCallListener<ReqT>(delegate) {
            @Override
            public void onMessage(ReqT message) {
                MDC.put(MDC_TRACE_ID, traceId);
                try {
                    super.onMessage(message);
                } finally {
                    MDC.remove(MDC_TRACE_ID);
                }
            }

            @Override
            public void onHalfClose() {
                MDC.put(MDC_TRACE_ID, traceId);
                try {
                    super.onHalfClose();
                } finally {
                    MDC.remove(MDC_TRACE_ID);
                }
            }
        };
    }
}
```

Ensure your logback configuration (`logback-spring.xml`) includes `%X{traceId}` in the log pattern:
```xml
<pattern>%d{yyyy-MM-dd HH:mm:ss.SSS} [%thread] %-5level %logger{36} - [TraceID: %X{traceId}] %msg%n</pattern>
```

---

## 6. Common Mistakes and Anti-Patterns
*   **MDC Thread Leakage**: Failing to remove trace IDs from the MDC thread-local map after requests complete. This can cause subsequent requests running on the same thread to log with the previous transaction's Trace ID.
*   **Excessive Metrics Cardinality**: Attaching highly dynamic variables (like transaction IDs or user IDs) as tags/labels to metrics. This causes database index bloat in Prometheus, degrading performance.

---

## 7. Interview Questions

### Q1: Why will a simple Java `ThreadLocal` storage fail to propagate MDC trace contexts inside reactive or asynchronous gRPC services?
**Answer**: 
MDC relies internally on `ThreadLocal` variables to correlate log statements. In asynchronous or reactive (WebFlux) services, execution hops across multiple threads (from Netty loops to application executors). 
Because `ThreadLocal` variables are tied to the physical thread stack, the trace context is lost when execution switches threads. To prevent this, you must wrap executors with OpenTelemetry wrappers or write interceptors that reload MDC values on callback boundaries.

### Q2: What is the benefit of percentiles metrics (p95, p99) over simple average latency metrics in production dashboards?
**Answer**: 
*   **Average Latency**: Hides performance degradation. If 99 requests take 10ms, and 1 request takes 10 seconds, the average latency is ~109ms. This obscures the extreme slow down experienced by the outlier.
*   **Percentiles (p95/p99)**: Show the latency threshold below which a specific percentage of requests fall. A p99 of 10 seconds immediately indicates that 1% of your users are experiencing severe latency issues, allowing you to debug outliers.
