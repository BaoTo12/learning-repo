# Module 14 — Observability

In this module, we will explore Observability in Spring Kafka pipelines. We will cover how to capture metrics using Micrometer, export them to Prometheus, and visualize system health in Grafana. We will study distributed tracing with OpenTelemetry, tracing context propagation over Kafka record headers, and consumer lag monitoring. Finally, we will cover troubleshooting, answer 5 Socratic questions, and implement hands-on labs with complete code structures.

---

## 1. Academic Lecture: Micrometer, Distributed Tracing & Lag Monitoring

### Basic Level: Metrics Collection & Actuator Integration

#### Metrics vs. Observability
In production systems, you must track client performance:
* **Metrics**: Aggregate numbers tracking performance (e.g. how many messages were consumed, average publish duration).
* **Observability**: The ability to infer the internal states of an application based on external outputs (metrics, traces, logs).

#### Micrometer & Actuator
Spring Boot uses **Micrometer** as its metrics facade. Micrometer automatically binds to Spring Kafka templates and listener containers, exposing core metrics:
* `kafka.producer.send.count`: Total messages published.
* `kafka.listener.seconds`: Consumer listener execution duration.
* These metrics are gathered by Micrometer, exposed via Spring Boot Actuator `/actuator/prometheus`, and collected by a Prometheus server.

---

### Intermediate Level: Distributed Tracing & W3C Propagation

#### Distributed Tracing
Distributed tracing tracks the path of a client request across multiple microservices. Every transaction is assigned a unique **Trace ID**, and individual steps are called **Spans**:
* **Context Propagation**: When a microservice publishes a message, it propagates the active Trace ID by injecting it into the Kafka record **Headers** as a W3C traceparent header (e.g., `traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01`).
* When the downstream consumer reads the record, it extracts the traceparent header and starts a child span. This maps the entire async request flow in tools like Jaeger or Zipkin.

```text
  [ Client Request ] ──► [ Service A (Start Trace ID: 999) ]
                                 │
                         (Injects Header)
                                 │
                                 ▼
                     [ Kafka Record Headers ]
                 { traceparent: 00-999-span-01 }
                                 │
                                 ▼
                         (Extracts Header)
                                 │
                                 ▼
           [ Service B Consumer (Resumes Trace ID: 999) ]
```

---

### Advanced Level: Consumer Lag Monitoring & Alerting

#### Consumer Lag
Consumer lag is the offset difference between the last message written to a partition by producers and the last offset read by a consumer group.
* **Why it matters**: Lag is the most important indicator of consumer health. If lag is increasing, it means your consumer cannot keep up, causing latency in your system.

#### Lag Exporters & Alerting
You can monitor lag using two approaches:
1. **Burrow**: A dedicated consumer lag monitoring tool from LinkedIn that evaluates consumer status without relying on active metrics.
2. **Prometheus Kafka Exporter**: A exporter container that queries the brokers for consumer offsets and exports them as metrics (e.g., `kafka_consumergroup_lag`).
* **Alerting**: Alertmanager rules monitor these metrics. If consumer lag for a critical topic exceeds a threshold for more than 5 minutes, an alert is triggered (e.g. page developers).

---

## 2. Theory & Production Best Practices

### Distributed Tracing vs. Metrics

| Aspect | Metrics (Prometheus) | Distributed Tracing (OpenTelemetry) |
| :--- | :--- | :--- |
| **Data Size** | Extremely Small (numerical counters) | High (detailed string spans and metadata) |
| **Resolution** | System-wide statistics | Single-request transaction flows |
| **Overhead** | Very Low | Low-Medium (depends on trace sampling rate) |
| **Best Use Case** | Alerting on system failures/latencies | Profiling bottlenecks and tracing errors |

### Micrometer Tracing vs. OpenTelemetry Java Agent

| Approach | Customization | Boot Time | Classpath Dependency |
| :--- | :--- | :--- | :--- |
| **Micrometer Tracing** | High (programmatic control in code) | Normal | Yes (compile dependency) |
| **OTel Java Agent** | Low (bytecode instrumentation) | Slow (agent bootstrap overhead) | No (run-time jar agent injection) |

---

## 3. Common Errors & Troubleshooting

### 1. Tracing Context Dropped in Async Thread Pools
* **Symptom**: Distributed trace chains break. The consumer starts a new trace ID instead of joining the parent producer transaction.
* **Root Cause**: The consumer received the message, but handed off the payload to a custom executor thread pool (`ExecutorService`). Since tracing contexts are bound to `ThreadLocal` storage, the child thread does not inherit the parent tracing context.
* **Fix**: Wrap thread pools using Micrometer's `ContextExecutorService` or configure Spring's `ThreadPoolTaskExecutor` with a tracing decorator.

### 2. High-Cardinality Metrics Memory Leak
* **Symptom**: Spring Boot container crashes due to OOM, and Prometheus server memory spikes.
* **Root Cause**: Developers added high-cardinality tags (like `userId` or `messageId`) to Micrometer metric registry meters. Since Prometheus creates a unique time-series database track for every unique tag combination, millions of series are generated, consuming all memory.
* **Fix**: Never use high-cardinality values as metric tags/labels. Only use static fields (e.g. `topicName`, `groupId`).

### 3. Kafka Exporter Timeout during Broker Heavy Load
* **Symptom**: Consumer lag metrics disappear or show false values during load spikes.
* **Root Cause**: The exporter queries the broker coordinator for group offsets using consumer metadata requests. Under heavy traffic, these broker administration ports timeout.
* **Fix**: Increase the query timeout on the exporter config, or decrease polling frequency.

---

## 4. Socratic Review Questions

### Question 1
*How does Micrometer Tracing propagate trace IDs from a publisher JVM to a consumer JVM over Kafka?*
* **Answer**: It serializes the active trace details (Trace ID, Span ID, Sampling Flags) into a W3C traceparent string, and appends this key-value pair to the Kafka `RecordHeader` collection before writing the bytes to the broker.

### Question 2
*Why is consumer lag a better metric for alerting than CPU utilization?*
* **Answer**: Because a consumer can run at 100% CPU usage while processing messages efficiently (no lag). Conversely, a consumer can experience 0% CPU usage because it is locked in a deadlock state (high lag). Lag directly measures system latency.

### Question 3
*What is the impact of metric sampling rate on application performance?*
* **Answer**: If sampling rate is too high (e.g., recording trace details for 100% of transactions in a high-volume 100k msg/sec topic), it causes significant serialization and network overhead. In production, you typically sample a fraction (e.g., 1%-5% of healthy transactions, and 100% of errors).

### Question 4
*What happens to the Kafka metrics registry if we disable Spring Actuator endpoint authorization?*
* **Answer**: The metrics can be scraped by anyone, exposing internal topic names, hostnames, and throughput counts. Always protect the `/actuator/prometheus` path using Spring Security or internal firewalls.

### Question 5
*How can you capture client-side network latency metrics between the producer and the broker?*
* **Answer**: Monitor the native Kafka client metric `request-latency-avg`, which tracks the duration between sending a socket write and receiving the partition acknowledgment.

---

## 5. Hands-on Labs

### Lab 14.1 — Spring Actuator & Prometheus Metric Endpoint

#### Scenario
We will configure a Spring Boot application to collect Kafka metrics, expose the Actuator endpoints, and format them for Prometheus scraping.

#### Application Properties (`application.yml`)
Add the following configuration to expose the Prometheus metric actuator endpoint:

```yaml
management:
  endpoints:
    web:
      exposure:
        include: prometheus,health,info
  metrics:
    tags:
      application: spend-analytics-service
  endpoint:
    prometheus:
      enabled: true
```

#### Complete Actuator Configuration Java Code
Create the file [MetricsConfig.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/src/main/java/com/springkafka/course/config/MetricsConfig.java) with the following content:

```java
package com.springkafka.course.config;

import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.config.MeterFilter;
import org.springframework.boot.actuate.autoconfigure.metrics.MeterRegistryCustomizer;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class MetricsConfig {

    // 1. Customize MeterRegistry to filter out unwanted native client metrics
    @Bean
    public MeterRegistryCustomizer<MeterRegistry> metricsCommonTags() {
        return registry -> registry.config()
            // Tag all metrics with environment name
            .commonTags("env", "production")
            // Deny metrics containing high cardinality keys to prevent memory leaks
            .meterFilter(MeterFilter.deny(id -> {
                String uri = id.getTag("uri");
                return uri != null && (uri.contains("/api/user/") || uri.length() > 50);
            }));
    }
}
```

---

### Lab 14.2 — OpenTelemetry Tracing Configuration

#### Scenario
We will configure Micrometer Tracing with OpenTelemetry exporter settings in Spring Boot 3.x to automatically propagate W3C tracing headers.

#### Complete Tracing Configuration Java Code
Create the file [TracingConfig.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/src/main/java/com/springkafka/course/config/TracingConfig.java) with the following content:

```java
package com.springkafka.course.config;

import io.micrometer.observation.ObservationRegistry;
import io.micrometer.observation.aop.ObservedAspect;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.kafka.config.ConcurrentKafkaListenerContainerFactory;
import org.springframework.kafka.core.ConsumerFactory;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.core.ProducerFactory;

@Configuration
public class TracingConfig {

    // 1. Enable Observed annotation parsing
    @Bean
    public ObservedAspect observedAspect(ObservationRegistry observationRegistry) {
        return new ObservedAspect(observationRegistry);
    }

    // 2. Instrument KafkaTemplate with Observation Registry
    @Bean
    public KafkaTemplate<String, String> tracingKafkaTemplate(
            ProducerFactory<String, String> pf, ObservationRegistry registry) {
        KafkaTemplate<String, String> template = new KafkaTemplate<>(pf);
        // This activates span context injection into Kafka record headers
        template.setObservationRegistry(registry);
        return template;
    }

    // 3. Instrument Listener Container Factory with Observation Registry
    @Bean
    public ConcurrentKafkaListenerContainerFactory<String, String> tracingKafkaListenerContainerFactory(
            ConsumerFactory<String, String> cf, ObservationRegistry registry) {
        ConcurrentKafkaListenerContainerFactory<String, String> factory =
                new ConcurrentKafkaListenerContainerFactory<>();
        factory.setConsumerFactory(cf);
        // This activates span context extraction from Kafka record headers
        factory.getContainerProperties().setObservationRegistry(registry);
        return factory;
    }
}
```

---

### Lab 14.3 — Consumer Lag Alerting Rules

#### Scenario
We will write a Prometheus Alertmanager rule configuration file that evaluates consumer group lag and triggers alerts if lag exceeds 500 records.

#### Complete Prometheus Alerting Rules Configuration
Create the file [consumer-lag-alerts.yml](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/src/main/resources/consumer-lag-alerts.yml) with the following content:

```yaml
groups:
  - name: KafkaConsumerAlerts
    rules:
      - alert: CriticalConsumerLag
        expr: sum by (group, topic) (kafka_consumergroup_lag) > 500
        for: 5m
        labels:
          severity: critical
          tier: messaging
        annotations:
          summary: "Consumer Group Lag Spike Detected"
          description: "Consumer Group '{{ $labels.group }}' on Topic '{{ $labels.topic }}' has a lag of {{ $value }} records for more than 5 minutes."
```

---

### Step-by-Step Code Walkthrough & Parameter Configuration Tables

#### Step-by-Step Code Walkthrough

##### Lab 14.1 Walkthrough
1. **Actuator Web Exposure**: Exposes endpoint metrics for Prometheus scraping.
2. **`MeterFilter.deny`**: Excludes high-cardinality values, protecting microservice memory.

##### Lab 14.2 Walkthrough
1. **`setObservationRegistry` on template**: Directs Spring Kafka to wrap outbox writes with active spans, appending trace details to headers.
2. **`setObservationRegistry` on listener factory**: Directs consumer polling to check headers for parent trace details and start child spans.

##### Lab 14.3 Walkthrough
1. **`expr: kafka_consumergroup_lag > 500`**: Calculates active lag counts.
2. **`for: 5m`**: Prevents false alarms during temporary rebalances.

---

### Configuration Parameter Tables

#### Prometheus Alerting Rule YAML Keys

| Key | Expected Type | Description |
| :--- | :--- | :--- |
| `alert` | `String` | Unique name for the alert configuration rule. |
| `expr` | `PromQL String` | The Prometheus query expression evaluated to trigger alerts. |
| `for` | `Duration String` | The wait duration the expression must stay true before alerting (e.g. `5m`, `1h`). |
| `severity` | `String` | Severity metadata mapping (e.g. `critical`, `warning`). |

