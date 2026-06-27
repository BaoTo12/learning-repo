# Chapter 32: Distributed Tracing & Log Correlation

While metrics provide aggregated availability signals, they do not trace the path of individual transactions. If a user complains that checking out takes 10 seconds, metrics can show a spike in p99 latency but cannot explain *which* specific database query, downstream API call, or serialization step delayed that checkout. Logs provide diagnostic details, but in a busy microservice environment, log lines from thousands of concurrent requests are interleaved, making it impossible to reconstruct a single user's transaction flow without correlation.

To solve this, we use **Distributed Tracing**. Distributed tracing tracks individual requests as they travel across network boundaries, database drivers, and messaging queues. This chapter covers the technical design and implementation of distributed tracing. We will analyze the core components of a trace (Spans, Trace IDs, and Parent IDs), examine context propagation protocols (B3, W3C Trace Context), configure **Spring Cloud Sleuth** and **Zipkin** for Java microservices, detail tracing instrumentation strategies (Automatic, Agent-based, Manual), analyze tracing sampling methodologies (probabilistic, boundary, rate-limiting), map metric-to-trace correlation using Exemplars, and implement trace context injection for automated chaos testing.

---

## Learning Objectives

By the end of this chapter, you will be able to:
1. Explain how distributed tracing complements metrics and logging in observability.
2. Outline the structure of a distributed trace, detailing the relationship between Trace IDs, Span IDs, and Parent IDs.
3. Track context propagation across HTTP boundaries using B3 and W3C trace headers.
4. Configure Spring Cloud Sleuth and Zipkin in a Spring Boot application.
5. Create custom spans and inject business tags programmatically using the OpenTelemetry API.
6. Compare framework-based, agent-based (bytecode injection), and service mesh-based tracing.
7. Evaluate the trade-offs of probabilistic, rate-limiting, and boundary sampling strategies.
8. Identify the impact of sampling on anomaly detection (the statistics of seeing rare outliers).
9. Implement Trace Exemplars to link latency heatmaps in Grafana directly to Zipkin traces.
10. Utilize trace context headers to propagate failure injection targets for chaos experimentation.

---

## 32.1 The Pillars of Telemetry: Metrics, Logs, and Traces

An observability foundation relies on three telemetry signals:

* **Metrics**: Aggregated availability signals. They have a constant, predictable storage footprint that does not increase with traffic. Metrics are used to identify *if* the system is broken and to test against Service Level Objectives (SLOs).
* **Logs**: Detailed, event-based text records. Logs grow proportionally with system throughput. They are used to diagnose local code failures.
* **Traces**: Causal chains of events that trace requests across multiple services. Like logs, traces grow with throughput. They are used to identify *where* a bottleneck occurs in a distributed call graph.

As Jeff Hodges notes: *"Tracing can be difficult to retrofit into an existing system, as each collaborator in an end-to-end process must be configured to propagate trace context forward. Distributed tracing shines especially for a particular type of performance problem where the entire system is slower than it should be but there is no obvious hotspot to quickly optimize."*

---

## 32.2 Components of a Distributed Trace: Spans and Icicles

A **Trace** represents the lifecycle of a single user request. It is composed of a tree of **Spans**, which represent individual units of work (such as an HTTP request, a SQL query execution, or a message queue serialization).

Spans are organized hierarchically. Each span contains:
* **Trace ID**: A unique identifier shared by all spans in the request tree.
* **Span ID**: A unique identifier for the specific unit of work.
* **Parent ID**: The Span ID of the calling process. If a span lacks a parent ID, it is the **Root Span**.

These spans can be assembled chronologically into an **Icicle Graph** (or waterfall chart) to visualize request durations:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//9144bd0e-e3c8-4684-b0dd-9c1bba9abbcf/markdown_1/imgs/img_in_image_box_144_598_865_852.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A38Z%2F-1%2F%2Ff03ca60e91a6e9e3f0a39b552db76cdf2fb8695e0b7ebb6919a94916a50e074f" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 3-1. Zipkin icicle graph showing nested service spans</div> </div>

As illustrated in Figure 3-1, nested spans show the order of service executions, helping you locate network bottlenecks and serial call patterns.

We query these traces inside the **Zipkin UI** using tags (like HTTP methods or status codes):

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//9144bd0e-e3c8-4684-b0dd-9c1bba9abbcf/markdown_3/imgs/img_in_image_box_142_108_863_635.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A41Z%2F-1%2F%2F7c3d382577a7f27b4ab153d67491bddca645340e8b1bad86c9c7b7e7753fb8ad" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 3-2. Searching for traces in the Zipkin Lens UI</div> </div>

---

## 32.3 Context Propagation and Trace Headers

To trace a transaction across network boundaries, services must propagate the trace context. When a service calls another, it injects trace metadata into the egress request headers. The downstream service extracts these headers to configure its local span context.

### 1. B3 Propagation Protocol
Developed by Zipkin, the B3 protocol specifies standard HTTP headers for trace context:

* `X-B3-TraceId`: The global Trace ID.
* `X-B3-SpanId`: The current Span ID.
* `X-B3-ParentSpanId`: The calling Span ID.
* `X-B3-Sampled`: A binary flag (`1` or `0`) indicating whether the request should be sampled.

### 2. W3C Trace Context Standard
The W3C Trace Context standard replaces vendor-specific headers with two unified headers:

* `traceparent`: Combines version, trace ID, parent span ID, and trace flags.
  Example: `00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01`
* `tracestate`: Transports vendor-specific routing metadata.

---

## 32.4 Sleuth and Zipkin Maven Configurations (`pom.xml`)

To add tracing to your Spring Boot microservices, include the Spring Cloud Sleuth starter and the Zipkin export client in your `pom.xml`:

```xml
<dependencyManagement>
    <dependencies>
        <dependency>
            <groupId>org.springframework.cloud</groupId>
            <artifactId>spring-cloud-dependencies</artifactId>
            <version>2021.0.8</version>
            <type>pom</type>
            <scope>import</scope>
        </dependency>
    </dependencies>
</dependencyManagement>

<dependencies>
    <!-- Sleuth for tracing and log correlation -->
    <dependency>
        <groupId>org.springframework.cloud</groupId>
        <artifactId>spring-cloud-starter-sleuth</artifactId>
    </dependency>
    <!-- Sleuth reporter to export spans to Zipkin over HTTP -->
    <dependency>
        <groupId>org.springframework.cloud</groupId>
        <artifactId>spring-cloud-sleuth-zipkin</artifactId>
    </dependency>
</dependencies>
```

---

## 32.5 Types of Tracing Instrumentation

You can add tracing instrumentation to your services using three primary strategies:

### 1. Framework/Library Instrumentation
Frameworks (like Spring Cloud Sleuth) intercept incoming and outgoing requests using MVC filters, rest template interceptors, and database wrapper proxies. Sleuth automatically configures log formatting (e.g. SLF4J MDC) to inject the `traceId` and `spanId` into every log line:

```
2026-06-27 13:44:00.120 [order-service,4bf92f3577b34da6a3ce929d0e0e4736,00f067aa0ba902b7,true] INFO ...
```

### 2. Agent Instrumentation (Bytecode Manipulation)
Java Agents (like the OpenTelemetry Java Agent) intercept class loading at JVM startup, injecting tracing logic into database drivers, HTTP clients, and libraries without requiring code changes:

```bash
java -javaagent:opentelemetry-javaagent.jar -jar order-service.jar
```

### 3. Service Mesh Instrumentation
Service meshes (like Istio/Envoy) trace network communication by generating spans at the proxy sidecar boundary. 

> [!IMPORTANT]
> A service mesh *must* still receive trace headers from the application. If your application code does not forward the incoming B3 or W3C headers to its outbound HTTP calls, the service mesh cannot link the spans, breaking the trace into separate fragments.

---

## 32.6 Manual Tracing: Creating Custom Spans

While automatic instrumentation captures network calls, you can use the OpenTelemetry API to create custom spans around complex business logic or CPU-intensive tasks within a service:

```java
package com.ftgo.order.tracing;

import io.opentelemetry.api.GlobalOpenTelemetry;
import io.opentelemetry.api.trace.Span;
import io.opentelemetry.api.trace.Tracer;
import io.opentelemetry.context.Scope;
import org.springframework.stereotype.Service;

@Service
public class OrderProcessingService {

    // Initialize the tracer
    private final Tracer tracer = GlobalOpenTelemetry.getTracer("order-service-processing");

    public void processOrderAllocation(Long orderId) {
        // Create and start a custom span
        Span span = tracer.spanBuilder("calculateAllocationPriority")
                .setAttribute("order.id", orderId)
                .setAttribute("priority.strategy", "strict-fifo")
                .startSpan();

        // Establish the scope to bind the span to the active thread context
        try (Scope scope = span.makeCurrent()) {
            // Execute business logic...
            performComplexPriorityMath();
        } catch (Exception e) {
            span.recordException(e);
            span.setStatus(io.opentelemetry.api.trace.StatusCode.ERROR, e.getMessage());
            throw e;
        } finally {
            // Close the span to record the duration
            span.end();
        }
    }

    private void performComplexPriorityMath() {
        try {
            Thread.sleep(150);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }
}
```

---

## 32.7 Tracing Sampling Methodologies

Collecting and storing traces for 100% of requests in a high-throughput production environment can be cost-prohibitive, exhausting storage and network bandwidth. 

To manage cost, we apply sampling strategies:

### 1. Probabilistic Sampling
This strategy uses a random number generator to sample a percentage of requests (e.g. 1%):

```yaml
spring:
  sleuth:
    sampler:
      probability: 0.01 # Sample 1% of transactions
```

### 2. Rate-Limiting Sampling
This strategy sets a maximum number of traces to record per second (e.g. 100 traces/sec), dropping any excess. This protects your monitoring infrastructure from traffic spikes.

### 3. Boundary Sampling
To avoid missing trace spans (holes) in downstream services, the sampling decision is made once at the system edge (the API Gateway) and propagated downstream using HTTP headers:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//054a2241-aa5d-4c63-81a7-498ee4a271e4/markdown_0/imgs/img_in_image_box_141_744_865_946.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A33Z%2F-1%2F%2Fe728d04aa430c933fe3f0ab9f02aadcf765312f6b59f81871fd572e367078c2c" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 3-3. B3 trace headers propagate the sampling decision downstream</div> </div>

As shown in Figure 3-3, downstream microservices read the `X-B3-Sampled` flag and collect spans accordingly, ensuring complete traces.

---

### 32.7.1 Impact of Sampling on Anomaly Detection

> [!WARNING]
> While probabilistic sampling controls storage costs, it reduces your ability to detect rare anomalies and outliers.

If we sample 1% of requests, our chance of recording a specific outlier above the 99th percentile is only 1%:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//054a2241-aa5d-4c63-81a7-498ee4a271e4/markdown_1/imgs/img_in_chart_box_149_353_864_724.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A34Z%2F-1%2F%2F81bbd0a195557f0a8cf1f356dd01d074646278aebb6b9bd02276f99e78e67571" alt="Image" width="70%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 3-4. Probability of recording a rare outlier over time at 1% sampling</div> </div>

As shown in Figure 3-4, if your system processes 1,000 requests/second and experiences 10 outliers per second, a 1% sampler will only record about 1 outlier every 5 minutes. 

For critical endpoints, you should use **Adaptive/Tail-Based Sampling**. This strategy evaluates the trace's latency and response code before making a sampling decision, ensuring that failed or slow requests are recorded at 100% while standard successful requests are sampled at 1%.

---

## 32.8 Correlation: Metric-to-Trace Exemplars

To bridge the gap between metrics and traces, we use **Exemplars**. An Exemplar links a specific metric data point to a representative trace ID.

When Grafana displays a latency heatmap using Prometheus histogram data, it plots Exemplars as interactive data points. You can hover over a cell in the heatmap and click through directly to the corresponding Zipkin trace:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//054a2241-aa5d-4c63-81a7-498ee4a271e4/markdown_3/imgs/img_in_chart_box_144_388_865_668.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A35Z%2F-1%2F%2F2d96bfffb17f7616f42d668ea6c2d2052d38668df1623a6fca030cfc6dd07819" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 3-5. Zipkin trace exemplars displayed on a Prometheus latency heatmap in Grafana</div> </div>

This integration relies on correlating tags and trace IDs behind the scenes:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//054a2241-aa5d-4c63-81a7-498ee4a271e4/markdown_4/imgs/img_in_image_box_143_172_862_448.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A36Z%2F-1%2F%2F696001ddc36cc5e8f46fc39e44b8d8142b38fcca0ca70bdc4b31213946d83d06" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 3-6. How Prometheus metrics and Zipkin traces are correlated in Grafana</div> </div>

---

## 32.9 Trace Context for Failure Injection Testing (FIT)

Beyond debugging, you can use trace context to orchestrate **Failure Injection Testing (FIT)**. 

To test system resilience under stress, the API Gateway injects failure metadata (e.g. latency targets or error classes) into the trace context header. Downstream microservices parse these headers and simulate the requested failure mode automatically:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//9f55d08b-9987-405a-91da-238f097e91a6/markdown_0/imgs/img_in_image_box_144_332_862_791.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A34Z%2F-1%2F%2F9f35fd37c4f76ce913ad82f7983d1080882a39ca3af4a7f3ff9122a8f421f50d" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 3-7. Flow of a failure injection test propagating via trace context headers</div> </div>

This pattern allows you to test system resilience in production without impacting real user requests.

---

## 32.10 Propagating Context: Sleuth Baggage and Tag Fields

Standard trace headers (Trace ID, Span ID) propagate system-level identifiers. However, you may need to propagate business-level metadata (such as a customer ID, a transaction region, or a tenant classification) across your microservices.

Spring Cloud Sleuth supports this through **Baggage**:
* **Baggage Fields**: Transport key-value pairs inside the network headers of a transaction. Unlike span tags, baggage is automatically forwarded downstream to every service in the call graph.
* **Tag Fields**: In addition to propagating key-value pairs, Sleuth can write baggage fields to the local span tags automatically, making them searchable in Zipkin or Elasticsearch.

### 1. Baggage Configuration (`application.yml`)
```yaml
spring:
  sleuth:
    baggage:
      # Baggage fields propagated across HTTP boundaries
      remote-fields:
        - "customerId"
        - "transactionType"
      # Baggage fields written to local span tags
      tag-fields:
        - "customerId"
```

### 2. Reading and Writing Baggage Programmatically in Java
```java
package com.ftgo.order.tracing;

import org.springframework.cloud.sleuth.BaggageField;
import org.springframework.cloud.sleuth.Tracer;
import org.springframework.stereotype.Service;

@Service
public class BillingContextService {

    private final Tracer tracer;

    public BillingContextService(Tracer tracer) {
        this.tracer = tracer;
    }

    public void processPayment() {
        // 1. Retrieve or create the baggage field
        BaggageField customerField = BaggageField.getByName("customerId");
        
        if (customerField != null) {
            // 2. Set the value dynamically
            customerField.updateValue("cust-prod-9992");
        }

        // 3. Log with Sleuth automatically correlating traceId and baggage
        System.out.println("Processing billing records...");
    }
}
```

---

## 32.11 OpenTelemetry Trace Exporter Bean Configuration

When building modern microservices, we standardise our exporters on **OpenTelemetry**. Below is the Java configuration to export trace spans to the OpenTelemetry Collector:

```java
package com.ftgo.order.config;

import io.opentelemetry.api.common.Attributes;
import io.opentelemetry.sdk.resources.Resource;
import io.opentelemetry.sdk.trace.SdkTracerProvider;
import io.opentelemetry.sdk.trace.export.BatchSpanProcessor;
import io.opentelemetry.sdk.trace.export.SpanExporter;
import io.opentelemetry.semconv.resource.attributes.ResourceAttributes;
import io.opentelemetry.exporter.otlp.trace.OtlpGrpcSpanExporter;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class OpenTelemetryTracingConfig {

    @Bean
    public SpanExporter otlpSpanExporter() {
        // Build the exporter pointing to the local OpenTelemetry Collector daemon
        return OtlpGrpcSpanExporter.builder()
                .setEndpoint("http://localhost:4317")
                .build();
    }

    @Bean
    public SdkTracerProvider sdkTracerProvider(SpanExporter spanExporter) {
        // Declare service resource metadata
        Resource serviceResource = Resource.getDefault().merge(
                Resource.create(Attributes.of(
                        ResourceAttributes.SERVICE_NAME, "order-service",
                        ResourceAttributes.SERVICE_NAMESPACE, "production"
                ))
        );

        // Configure batch span processing
        return SdkTracerProvider.builder()
                .addSpanProcessor(BatchSpanProcessor.builder(spanExporter).build())
                .setResource(serviceResource)
                .build();
    }
}
```

---

## 32.12 Logback MDC Log Correlation Configuration (`logback.xml`)

To correlate logs with traces, Logback writes Sleuth context variables (such as `traceId`, `spanId`, and `parentId`) to the **Mapped Diagnostic Context (MDC)**.

Below is a complete `logback.xml` layout configuration that formats correlation identifiers for log forwarders:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<configuration>
    <!-- Console Appender -->
    <appender name="CONSOLE" class="ch.qos.logback.core.ConsoleAppender">
        <encoder>
            <pattern>%d{yyyy-MM-dd HH:mm:ss.SSS} [%thread] %-5level %logger{36} - [TraceId: %X{traceId:-N/A}, SpanId: %X{spanId:-N/A}] - %msg%n</pattern>
        </encoder>
    </appender>

    <!-- Root Logger -->
    <root level="INFO">
        <appender-ref ref="CONSOLE" />
    </root>
</configuration>
```

---

## 32.13 Running the OpenTelemetry Collector as a Daemon Sidecar

Rather than exporting spans from your application directly to SaaS providers, we route them through an **OpenTelemetry Collector** sidecar container. 

This collector receives spans, batches them, and exports them to multiple storage backends (like Zipkin, Jaeger, or Elasticsearch):

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: otel-collector-config
  namespace: telemetry
data:
  otel-collector-config.yaml: |
    receivers:
      otlp:
        protocols:
          grpc:
          http:
    processors:
      batch:
        timeout: 1s
        send_batch_size: 256
    exporters:
      zipkin:
        endpoint: "http://zipkin.telemetry.svc:9411/api/v2/spans"
      logging:
        verbosity: normal
    service:
      pipelines:
        traces:
          receivers: [otlp]
          processors: [batch]
          exporters: [zipkin, logging]
```

---

## 32.14 Tracing Asynchronous Task Executions and Thread Pools

By default, tracing context is bound to a single thread using local variables (`ThreadLocal`). If your Java application spawns a new thread or delegates work to an asynchronous pool (e.g. using Spring's `@Async` or Java's `CompletableFuture`), the tracing context is lost unless explicitly delegated.

To ensure Trace IDs propagate across asynchronous boundaries, we configure Spring's `ThreadPoolTaskExecutor` with a Sleuth-enabled decorator:

```java
package com.ftgo.order.config;

import org.springframework.beans.factory.BeanFactory;
import org.springframework.cloud.sleuth.instrument.async.LazyTraceExecutor;
import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.annotation.AsyncConfigurerSupport;
import org.springframework.scheduling.annotation.EnableAsync;
import org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor;

import java.util.concurrent.Executor;

@Configuration
@EnableAsync
public class AsyncTracingConfiguration extends AsyncConfigurerSupport {

    private final BeanFactory beanFactory;

    public AsyncTracingConfiguration(BeanFactory beanFactory) {
        this.beanFactory = beanFactory;
    }

    @Override
    public Executor getAsyncExecutor() {
        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        executor.setCorePoolSize(5);
        executor.setMaxPoolSize(10);
        executor.setQueueCapacity(25);
        executor.setThreadNamePrefix("async-trace-pool-");
        executor.initialize();

        // Wrap the executor in a LazyTraceExecutor to delegate trace context
        return new LazyTraceExecutor(beanFactory, executor);
    }
}
```

This configuration ensures that when a method annotated with `@Async` is executed, Sleuth intercepts the task submission, copies the parent thread's `traceId` and `spanId` to the worker thread's MDC context, and starts a child span.

---



---

## 32.14 Custom Logging Appender with JSON Formatting

In production, log forwarders (like FluentBit or Logstash) process application log files more efficiently when they are structured as JSON. 

We can configure a Logback JSON encoder to output Trace and Span context metadata as top-level JSON fields, enabling rapid queries in search engines like Elasticsearch:

```xml
<configuration>
    <appender name="JSON" class="ch.qos.logback.core.ConsoleAppender">
        <encoder class="net.logstash.logback.encoder.LoggingEventCompositeJsonEncoder">
            <providers>
                <timestamp/>
                <logLevel/>
                <threadName/>
                <loggerName/>
                <message/>
                <mdc/> <!-- Automatically includes traceId, spanId, and parentId -->
                <arguments/>
                <stackTrace/>
            </providers>
        </encoder>
    </appender>

    <root level="INFO">
        <appender-ref ref="JSON"/>
    </root>
</configuration>
```

---

## 32.15 Custom Baggage Propagator Parser

To propagate custom metadata keys that standard Sleuth configurations do not parse automatically, we write a custom `Propagator` parser bean to inject and extract keys from HTTP request headers:

```java
package com.ftgo.order.tracing;

import io.opentelemetry.context.Context;
import io.opentelemetry.context.propagation.TextMapGetter;
import io.opentelemetry.context.propagation.TextMapPropagator;
import io.opentelemetry.context.propagation.TextMapSetter;

import javax.annotation.Nullable;
import java.util.Collections;
import java.util.List;

public class CustomTenantPropagator implements TextMapPropagator {

    private static final String TENANT_HEADER = "X-Custom-Tenant-Id";

    @Override
    public List<String> fields() {
        return Collections.singletonList(TENANT_HEADER);
    }

    @Override
    public <C> void inject(Context context, @Nullable C carrier, TextMapSetter<C> setter) {
        if (carrier == null || setter == null) {
            return;
        }
        // Extract tenant ID from context and set it as an HTTP header
        String tenantId = context.get(CustomTenantKey.KEY);
        if (tenantId != null) {
            setter.set(carrier, TENANT_HEADER, tenantId);
        }
    }

    @Override
    public <C> Context extract(Context context, @Nullable C carrier, TextMapGetter<C> getter) {
        if (carrier == null || getter == null) {
            return context;
        }
        // Read the custom header during request interception
        String tenantId = getter.get(carrier, TENANT_HEADER);
        if (tenantId != null) {
            return context.with(CustomTenantKey.KEY, tenantId);
        }
        return context;
    }
}
```

---

---

## 32.16 Tracing API Gateways: Spring Cloud Gateway Interceptor

To track transactions starting from the gateway, we must configure a global tracing filter inside the **API Gateway**.

This filter extracts incoming headers, creates a root span, and injects context headers before forwarding requests:

```java
package com.ftgo.gateway.filter;

import io.opentelemetry.api.GlobalOpenTelemetry;
import io.opentelemetry.api.trace.Span;
import io.opentelemetry.api.trace.Tracer;
import io.opentelemetry.context.Context;
import io.opentelemetry.context.Scope;
import io.opentelemetry.context.propagation.TextMapSetter;
import org.springframework.cloud.gateway.filter.GatewayFilterChain;
import org.springframework.cloud.gateway.filter.GlobalFilter;
import org.springframework.http.server.reactive.ServerHttpRequest;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ServerWebExchange;
import reactor.core.publisher.Mono;

@Component
public class GatewayGlobalTracingFilter implements GlobalFilter {

    private final Tracer tracer = GlobalOpenTelemetry.getTracer("api-gateway");

    private static final TextMapSetter<ServerHttpRequest.Builder> setter =
            (carrier, key, value) -> {
                if (carrier != null) {
                    carrier.header(key, value);
                }
            };

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, GatewayFilterChain chain) {
        // 1. Start a gateway span
        Span span = tracer.spanBuilder("gatewayRoute")
                .setSpanKind(io.opentelemetry.api.trace.SpanKind.SERVER)
                .startSpan();

        try (Scope scope = span.makeCurrent()) {
            ServerHttpRequest.Builder requestBuilder = exchange.getRequest().mutate();
            
            // 2. Inject trace context headers into outbound request builder
            GlobalOpenTelemetry.getPropagators().getTextMapPropagator().inject(
                    Context.current(),
                    requestBuilder,
                    setter
            );

            ServerWebExchange mutatedExchange = exchange.mutate()
                    .request(requestBuilder.build())
                    .build();

            // 3. Complete filter chain
            return chain.filter(mutatedExchange)
                    .doOnError(span::recordException)
                    .doFinally(signalType -> span.end());
        }
    }
}
```

---

## 32.17 Message Queue Tracing: Kafka Producer Interceptor

Context propagation is also required for asynchronous messaging. 

Below is a Kafka `ProducerInterceptor` implementation that injects tracing context into Kafka record headers:

```java
package com.ftgo.order.tracing;

import io.opentelemetry.api.GlobalOpenTelemetry;
import io.opentelemetry.context.Context;
import io.opentelemetry.context.propagation.TextMapSetter;
import org.apache.kafka.clients.producer.ProducerInterceptor;
import org.apache.kafka.clients.producer.ProducerRecord;
import org.apache.kafka.clients.producer.RecordMetadata;
import org.apache.kafka.common.header.Headers;

import java.nio.charset.StandardCharsets;
import java.util.Map;

public class KafkaTraceProducerInterceptor<K, V> implements ProducerInterceptor<K, V> {

    private static final TextMapSetter<Headers> setter = (carrier, key, value) -> {
        if (carrier != null) {
            // Remove existing header keys if present to prevent duplication
            carrier.remove(key);
            carrier.add(key, value.getBytes(StandardCharsets.UTF_8));
        }
    };

    @Override
    public ProducerRecord<K, V> onSend(ProducerRecord<K, V> record) {
        Headers headers = record.headers();
        
        // Inject active trace context into Kafka message headers
        GlobalOpenTelemetry.getPropagators().getTextMapPropagator().inject(
                Context.current(),
                headers,
                setter
        );
        
        return record;
    }

    @Override
    public void onAcknowledgement(RecordMetadata metadata, Exception exception) {}

    @Override
    public void close() {}

    @Override
    public void configure(Map<String, ?> configs) {}
}
```

---

## 32.18 SQL Query Tracing: Datasource Wrapper Configuration

To trace database calls, we must configure a wrapper proxy around the standard SQL `DataSource`. 

This wrapper intercepts database queries, measures execution durations, and generates child spans containing database metadata (such as the SQL statement and connection pool tags):

```java
package com.ftgo.order.config;

import net.ttddyy.dsproxy.listener.logging.SLF4JLogLevel;
import net.ttddyy.dsproxy.support.ProxyDataSourceBuilder;
import org.springframework.beans.factory.config.BeanPostProcessor;
import org.springframework.context.annotation.Configuration;

import javax.sql.DataSource;

@Configuration
public class DatabaseTracingPostProcessor implements BeanPostProcessor {

    @Override
    public Object postProcessAfterInitialization(Object bean, String beanName) {
        if (bean instanceof DataSource) {
            DataSource dataSource = (DataSource) bean;
            
            // Wrap the database connection pool in a tracing proxy datasource
            return ProxyDataSourceBuilder.create(dataSource)
                    .name("order-db-proxy")
                    .logQueryBySLF4J(SLF4JLogLevel.INFO)
                    .multiline()
                    // Sleuth intercepts proxy calls to capture SQL spans automatically
                    .build();
        }
        return bean;
    }
}
```

This configuration integrates SQL statements into the parent trace, helping you identify N+1 query bottlenecks and slow database indexes directly inside the Zipkin UI.

---

## 32.18 Client HTTP Call Tracing Interceptor

To capture HTTP requests made via standard RestTemplate clients, we register a custom interceptor that forwards trace contexts inside outbound headers:

```java
package com.ftgo.order.tracing;

import io.opentelemetry.api.GlobalOpenTelemetry;
import io.opentelemetry.context.Context;
import io.opentelemetry.context.propagation.TextMapSetter;
import org.springframework.http.HttpRequest;
import org.springframework.http.client.ClientHttpRequestExecution;
import org.springframework.http.client.ClientHttpRequestInterceptor;
import org.springframework.http.client.ClientHttpResponse;

import java.io.IOException;

public class TracingRestTemplateInterceptor implements ClientHttpRequestInterceptor {

    private static final TextMapSetter<HttpRequest> setter = 
            (carrier, key, value) -> {
                if (carrier != null) {
                    carrier.getHeaders().set(key, value);
                }
            };

    @Override
    public ClientHttpResponse intercept(HttpRequest request, byte[] body, ClientHttpRequestExecution execution)
            throws IOException {
        
        // Inject current OpenTelemetry trace context into outbound request headers
        GlobalOpenTelemetry.getPropagators().getTextMapPropagator().inject(
                Context.current(),
                request,
                setter
        );

        return execution.execute(request, body);
    }
}
```

This intercepts client requests, linking outbound HTTP spans to parent tracing scopes.

---



## 32.19 Summary of Distributed Tracing and Log Correlation Controls

This table summarizes the configurations, headers, and annotations used to build distributed tracing solutions:

| Telemetry Axis | Tracing Component / Header | Main Implementation Target | Scope Location |
| :--- | :--- | :--- | :--- |
| **Global Trace** | `Trace ID` | Links all spans belonging to a single transaction. | Trace Context |
| **Local Span** | `Span ID` | Tracks the lifecycle of a specific unit of work. | Trace Context |
| **Causal Link** | `Parent ID` | Organizes spans into a hierarchical tree structure. | Trace Context |
| **Context Header** | `X-B3-TraceId` | Propagates trace context across network boundaries. | HTTP Request |
| **Propagation Standard**| `traceparent` | Standardized W3C context propagation header. | HTTP Request |
| **Automated Binding** | SLF4J MDC | Injects trace context into application log lines. | Logging Appender |
| **Exemplar Mapping** | `exemplar` | Links Prometheus metric data points to Zipkin traces. | Metrics Registry |
| **Edge Decision** | `@Sampler` (Boundary) | Evaluates and applies sampling decisions at the gateway. | API Gateway |
| **Chaos Injection** | Failure tag (FIT) | Propagates failure injection instructions to downstream services. | Trace Context |

---

## Chapter Summary

* Distributed tracing tracks the flow of individual requests as they travel across network boundaries, database drivers, and messaging queues.
* A trace is a tree of spans. Each span contains a Trace ID, Span ID, and Parent ID.
* We propagate trace context across HTTP boundaries using header protocols like **B3** or the **W3C Trace Context** standard.
* **Spring Cloud Sleuth** autoconfigures Java microservices to generate spans and inject trace context into application logs.
* Tracing can be added using automatic library instrumentation, Java Agents (bytecode manipulation), or service mesh sidecars (Envoy).
* To manage storage and network costs, we use sampling strategies (probabilistic, rate-limiting, or boundary sampling).
* Probabilistic sampling reduces your ability to detect rare outliers. You should use tail-based sampling for critical endpoints.
* **Exemplars** link metric data points to representative trace IDs, allowing you to click through from Grafana heatmaps directly to Zipkin traces.
* We can use trace context to propagate failure injection instructions downstream, enabling targeted chaos testing.
* Custom thread pool decorators like `LazyTraceExecutor` ensure that trace context is not lost during asynchronous executions.
* Structured JSON logging appenders allow log forwarders to index trace metadata efficiently for rapid search.
* Database datasource wrappers integrate SQL statement durations and connection pool metadata directly into child spans.
---

## 32.14 Production-Grade FTGO Order Reviews OpenTelemetry Span Customization

To identify performance degradation across distributed microservice boundaries, the platform engineering team enforces context-aware transaction correlation. In this section, we present the Java implementation for custom **OpenTelemetry Span** instrumentation and Mapped Diagnostic Context (MDC) log correlation inside the **review-service**.

We implement:
1. **`OrderReviewsTracingConfig.java`**: Configures the OpenTelemetry bean registry, adding a custom span processor to extract business attributes.
2. **`OrderReviewsTraceCorrelationFilter.java`**: A servlet filter that intercepts incoming review requests, extracts context-propagated parameters (like `restaurantId` and `customerId`), adds baggage attributes, and writes them directly into the SLF4J MDC context blocks.
3. **`logback-spring.xml`**: A Logback appender mapping the custom MDC trace context variables into standard JSON log outputs.

```
+---------------------------------------------------------------------------------+
|                        OPENTELEMETRY TRACING INJECTION                          |
+---------------------------------------------------------------------------------+
|                                                                                 |
|   [ HTTP Request ] ===(Headers: traceparent)===> [ TraceCorrelationFilter ]     |
|                                                               │                 |
|                                                      (Binds custom attributes)  |
|                                                               v                 |
|   [ OpenTelemetry Active Span ]                       [ SLF4J MDC Logging ]     |
|     - Tag: ftgo.restaurant.id                           - %X{traceId}           |
|     - Tag: ftgo.customer.id                             - %X{restaurantId}      |
|                                                                                 |
+---------------------------------------------------------------------------------+
```

---

### 1. OpenTelemetry Custom Span Configuration: `OrderReviewsTracingConfig.java`
```java
package com.ftgo.review.tracing;

import io.opentelemetry.api.common.AttributeKey;
import io.opentelemetry.api.trace.Span;
import io.opentelemetry.sdk.trace.ReadWriteSpan;
import io.opentelemetry.sdk.trace.ReadableSpan;
import io.opentelemetry.sdk.trace.SpanProcessor;
import io.opentelemetry.context.Context;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class OrderReviewsTracingConfig {

    /**
     * Registers a custom SpanProcessor to verify trace attributes on creation.
     */
    @Bean
    public SpanProcessor customSpanProcessor() {
        return new SpanProcessor() {
            @Override
            public void onStart(Context parentContext, ReadWriteSpan span) {
                // Pre-populate core metadata labels on span initialization
                span.setAttribute("ftgo.service.name", "review-service");
                span.setAttribute("ftgo.environment", "production");
            }

            @Override
            public boolean isStartRequired() {
                return true;
            }

            @Override
            public void onEnd(ReadableSpan span) {
                // Executed when span is finished and exported
            }

            @Override
            public boolean isEndRequired() {
                return false;
            }
        };
    }

    /**
     * Programmatic helper to record business context variables inside the current tracing span.
     * @param restaurantId unique restaurant identifier.
     * @param customerId unique customer identifier.
     */
    public static void enrichActiveSpan(String restaurantId, String customerId) {
        Span activeSpan = Span.current();
        if (activeSpan.isRecording()) {
            activeSpan.setAttribute(AttributeKey.stringKey("ftgo.restaurant.id"), restaurantId);
            activeSpan.setAttribute(AttributeKey.stringKey("ftgo.customer.id"), customerId);
        }
    }
}
```

---

### 2. Servlet Interceptor Filter: `OrderReviewsTraceCorrelationFilter.java`
```java
package com.ftgo.review.tracing;

import jakarta.servlet.*;
import jakarta.servlet.http.HttpServletRequest;
import org.slf4j.MDC;
import org.springframework.stereotype.Component;

import java.io.IOException;

@Component
public class OrderReviewsTraceCorrelationFilter implements Filter {

    private static final String RESTAURANT_ID_HEADER = "X-FTGO-RESTAURANT-ID";
    private static final String CUSTOMER_ID_HEADER = "X-FTGO-CUSTOMER-ID";

    private static final String MDC_RESTAURANT_ID = "restaurantId";
    private static final String MDC_CUSTOMER_ID = "customerId";

    @Override
    public void doFilter(ServletRequest request, ServletResponse response, FilterChain chain)
            throws IOException, ServletException {

        if (request instanceof HttpServletRequest) {
            HttpServletRequest httpRequest = (HttpServletRequest) request;
            
            // Extract custom routing metadata propagated by the API Gateway
            String restaurantId = httpRequest.getHeader(RESTAURANT_ID_HEADER);
            String customerId = httpRequest.getHeader(CUSTOMER_ID_HEADER);

            // Populate tracing span attributes if present
            if (restaurantId != null) {
                MDC.put(MDC_RESTAURANT_ID, restaurantId);
            }
            if (customerId != null) {
                MDC.put(MDC_CUSTOMER_ID, customerId);
            }

            // Enrich the running OpenTelemetry Spancontext with extracted tags
            if (restaurantId != null || customerId != null) {
                OrderReviewsTracingConfig.enrichActiveSpan(
                        restaurantId != null ? restaurantId : "unknown",
                        customerId != null ? customerId : "unknown"
                );
            }
        }

        try {
            chain.doFilter(request, response);
        } finally {
            // Clean MDC context stack immediately on response termination
            MDC.remove(MDC_RESTAURANT_ID);
            MDC.remove(MDC_CUSTOMER_ID);
        }
    }

    @Override
    public void init(FilterConfig filterConfig) throws ServletException {}

    @Override
    public void destroy() {}
}
```

---

### 3. Logback Configuration Pattern: `logback-spring.xml`
We configure our log output format to print correlated Trace IDs, Span IDs, restaurant IDs, and customer IDs, making it easy to search through splunk or Elasticsearch logs.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<configuration>
    <appender name="CONSOLE" class="ch.qos.logback.core.ConsoleAppender">
        <encoder>
            <!-- Pattern includes traceId, spanId, restaurantId, customerId from MDC -->
            <pattern>%d{yyyy-MM-dd HH:mm:ss.SSS} [%thread] %-5level [review-service,traceId=%X{trace_id:-},spanId=%X{span_id:-},restaurantId=%X{restaurantId:-},customerId=%X{customerId:-}] %logger{36} - %msg%n</pattern>
        </encoder>
    </appender>

    <root level="INFO">
        <appender-ref ref="CONSOLE" />
    </root>
</configuration>
```
