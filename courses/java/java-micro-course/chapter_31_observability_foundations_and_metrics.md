# Chapter 31: Observability Foundations & Metrics

As microservices scale to dozens or hundreds of independent services, identifying system failures becomes increasingly complex. High velocity deployments, independent scaling, network boundaries, and transient infrastructure make it difficult to determine the health of a distributed system. 

To manage this complexity, we must build an **Observability Foundation**. Telemetry is divided into three key areas: metrics, logs, and traces. While logs provide diagnostic detail and traces map request flows across network boundaries, **metrics** are the bedrock of availability monitoring. They provide a quantitative, real-time signal of system performance. 

This chapter covers the technical design and implementation of application metrics. We will compare black-box vs. white-box monitoring, analyze dimensional vs. hierarchical metrics, detail the architecture of the **Micrometer** metrics facade, implement custom meters (Gauges, Counters, Timers, Long Task Timers, and Distribution Summaries), examine latency distributions (bimodal curves and coordinated omission), configure registry customizers, and apply advanced cost-control filters.

---

## Learning Objectives

By the end of this chapter, you will be able to:
1. Compare the use cases of black-box and white-box monitoring.
2. Outline the trade-offs between Graphite-style hierarchical metrics and Prometheus-style dimensional metrics.
3. Configure Micrometer's `MeterRegistry` and autoconfigure composite registries in Spring Boot.
4. Implement Gauges to track instantaneous system states (collection sizes, thread queues, memory usage).
5. Implement Counters to monitor event counts and throughput.
6. Calculate request throughput rates and percentiles in PromQL.
7. Configure Timers to measure latency and record durations.
8. Compare standard Timers and Long Task Timers.
9. Analyze bimodal latency distributions caused by garbage collection pauses.
10. Define coordinated omission and explain how it affects latency measurements during load testing.
11. Implement `MeterFilter` rules to restrict tag cardinality and control storage costs.

---

## 31.1 Observability: Black-Box vs. White-Box Monitoring

Monitoring a distributed system involves two complementary patterns:

### 1. Black-Box Monitoring
Black-box monitoring observes a service from the outside, testing its behavior as a user would. It queries public endpoints and measures response codes, response times, and connection failures. 

* **Advantage**: Identifies user-facing failures immediately.
* **Limitation**: Cannot diagnose the root cause of a failure. If an endpoint returns an HTTP 500 error, black-box monitoring cannot tell whether the cause is database exhaustion, a memory leak, or a null pointer exception.

### 2. White-Box Monitoring
White-box monitoring relies on internal telemetry. It exposes internal JVM metrics, database connection pool statistics, garbage collection durations, and application exceptions.

* **Advantage**: Provides the diagnostic detail needed to debug root causes.
* **Limitation**: Can be noisy. A spike in thread context switching or CPU usage does not necessarily mean the system is failing to serve users.

---

## 31.2 Dimensional vs. Hierarchical Metrics

To store and query metric series, monitoring systems organize data in one of two ways:

### 1. Hierarchical Metrics (Graphite Style)
Hierarchical metrics use a dot-separated naming tree to encode all context into a single string:

`region.us-east.env.production.host.gamer-app-1.http.requests.get.status.200`

If you want to view the average response time across the entire us-east region, your query engine must parse and match wildcards on these dot paths. Adding a new attribute (like a deployment version tag) shifts the hierarchy, breaking existing dashboards and alert definitions.

### 2. Dimensional Metrics (Prometheus / Atlas Style)
Dimensional metrics separate the name of the metric from its metadata, using key-value pairs (tags or labels):

`http_requests_total{region="us-east", env="production", host="gamer-app-1", method="GET", status="200"}`

This allows query engines to filter, slice, and aggregate metrics dynamically by any combination of tags (for example, summing throughput across all hosts in a region).

---

## 31.3 Micrometer Telemetry Facade

**Micrometer** serves as the metrics facade for JVM applications, acting like SLF4J but for metrics. It defines a clean Java API for instrumenting code, allowing you to ship telemetry to backends (such as Prometheus, Datadog, InfluxDB, Atlas, or New Relic) without coupling your codebase to vendor-specific libraries.

### 31.3.1 MeterRegistry Hierarchy
The core abstraction in Micrometer is the `MeterRegistry`. Meters (Counters, Gauges, Timers) are created and stored within a registry:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//1e43451a-fa33-4042-b5e6-615b0936b650/markdown_4/imgs/img_in_image_box_247_119_758_447.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A24%3A25Z%2F-1%2F%2F0f4f04025c9f42581b01d3065a4056c30722d9a1d613de47c6d5b0e1575a91b4" alt="Image" width="50%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 2-1. Relationship between global static registry and your application's registries</div> </div>

As illustrated in Figure 2-1, applications can register multiple backend-specific registries with a single `CompositeMeterRegistry`, allowing you to dual-publish metrics (e.g. shipping operational metrics to Prometheus while sending infrastructure metrics to CloudWatch).

---

### 31.3.2 Metric Naming Conventions
A metric name should remain consistent across your codebase, using a dot-separated format (e.g., `http.server.requests`). Micrometer's registry implementation then translates this name into the naming convention of your target monitoring system:

* **Prometheus**: `http_server_requests_total`
* **InfluxDB**: `http_server_requests`
* **Graphite**: `http.server.requests`

It is important to avoid combining metrics with different frequencies or semantics into a single name:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//82ce712a-162a-4c4a-9477-45c4a4b0c285/markdown_2/imgs/img_in_image_box_141_109_863_345.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A24%3A23Z%2F-1%2F%2Fc75b21e924820efdd502ad9b071a6e075607604cadc662ef4eca8d3d3df4867b" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 2-2. Naming charts impact on data usability</div> </div>

As shown in Figure 2-2, if you merge two distinct calls (such as low-frequency HTTP requests and high-frequency database calls) under a generic metric name like `calls`, the resulting chart becomes difficult to interpret. We must use specific names and segregate types using dimension tags.

---

## 31.4 Classes of Meters in Micrometer

Micrometer provides several specialized meter types, each designed for specific telemetry use cases.

### 31.4.1 Gauges: Tracking Instantaneous States
A `Gauge` measures an instantaneous value. Gauges are ideal for tracking resources that fluctuate up and down (like collection sizes, active threads, database connection pool usage, memory, and CPU utilization):

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//6336b302-e874-456c-b19b-f4b119ff8c56/markdown_3/imgs/img_in_chart_box_144_598_859_997.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A24%3A15Z%2F-1%2F%2Fc17a0a4e78da65340b0818934122b0057007819ade13119101d23f73bfa59636" alt="Image" width="70%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 2-3. JVM Memory space gauge metrics stacked by space type</div> </div>

As shown in Figure 2-3, tags allow a single metric (like `jvm.memory.used`) to be split into separate time series (such as heap, non-heap, Metaspace, or Eden Space) for visualization.

#### 1. Creating a Gauge
A Gauge should observe a state variable. Do not update a Gauge manually; instead, pass a reference to the object you want to monitor, allowing Micrometer to query its value during scrape intervals:

```java
package com.ftgo.order.metrics;

import io.micrometer.core.instrument.Gauge;
import io.micrometer.core.instrument.MeterRegistry;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

@Component
public class QueueMonitor {

    private final List<String> taskQueue = Collections.synchronizedList(new ArrayList<>());

    public QueueMonitor(MeterRegistry registry) {
        // Register the gauge. Pass a reference to taskQueue and a lambda to check its size.
        Gauge.builder("queue.tasks.size", taskQueue, List::size)
                .description("Number of tasks currently queued")
                .tag("queue.name", "orders")
                .register(registry);
    }

    public void addTask(String task) {
        taskQueue.add(task);
    }

    public void processTask() {
        if (!taskQueue.isEmpty()) {
            taskQueue.remove(0);
        }
    }
}
```

---

### 31.4.2 Counters: Tracking Event Occurrences
A `Counter` is a monotonically increasing value that starts at zero and can only increment. Counters are used to track event occurrences, throughput, and error counts.

#### 1. Creating a Counter
```java
package com.ftgo.order.metrics;

import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.MeterRegistry;
import org.springframework.stereotype.Component;

@Component
public class OrderMetrics {

    private final Counter orderCreatedCounter;

    public OrderMetrics(MeterRegistry registry) {
        this.orderCreatedCounter = Counter.builder("orders.created")
                .description("Total number of orders created since startup")
                .tag("region", "us-east")
                .register(registry);
    }

    public void recordOrderCreated() {
        this.orderCreatedCounter.increment();
    }
}
```

#### 2. Querying Counter Rates in Prometheus
Because counters reset to zero when an application restarts, you should query the rate of change rather than the raw value. The Prometheus query below calculates the average rate of change per second over a 5-minute window:

```promql
rate(orders_created_total[5m])
```

---

### 31.4.3 Timers: Measuring Durations and Throughput
A `Timer` measures short-duration events, tracking both latency and event counts. When you record an event using a Timer, Micrometer automatically tracks:

1. **Count**: The number of times the event has occurred (representing throughput).
2. **Sum**: The total duration of all events combined.
3. **Max**: The maximum duration recorded.

#### 1. Aggregating Averages Across Region Contexts
Consider Figure 2-4, where a load balancer routes requests across Region 1 and Region 2. Micrometer tracks counts and sums for each instance:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//b03b9b30-ba29-46ef-b648-722464b9ba61/markdown_1/imgs/img_in_image_box_174_310_864_628.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A33Z%2F-1%2F%2F63e38b5a0582f9986ab957429f10c8790d7fc1da4936fdd328f39e7b52d5a21b" alt="Image" width="68%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 2-4. Timings for requests going to a hypothetical application</div> </div>

We calculate the average request latency by dividing the rate of the duration sum by the rate of the count:

$$\text{Average Latency} = \frac{\text{Rate of Sum (Duration)}}{\text{Rate of Count (Throughput)}}$$

This rate-normalized calculation handles restarts and scaling events cleanly, unlike static averages.

#### 2. Ring Buffers and Decaying Maximums
To ensure the maximum value reflects recent performance rather than a single spike that occurred hours ago, Micrometer records maximums using a **Ring Buffer** that decays over a configured time window:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//9ad28410-1af5-46a5-96ea-ef56592e29ea/markdown_0/imgs/img_in_chart_box_143_111_862_375.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A33Z%2F-1%2F%2Feed7cd5997e4e70d890f05dac4a8109123220c872a07627f030f8b05558dd255" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 2-5. The decaying maximum lingers on a chart for some time</div> </div>

As shown in Figure 2-5, a 30 ms response time spike remains visible on the chart for the duration of the decay window before dropping back to zero.

This decay is managed using a ring buffer of sub-elements. When the current buffer slot expires, the system rotates to the next slot:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//9ad28410-1af5-46a5-96ea-ef56592e29ea/markdown_0/imgs/img_in_image_box_143_904_646_1107.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A33Z%2F-1%2F%2Fd1408abca671109d7e5e59b79ef4313c365ac08c9cc1537580f83a8ea39a386c" alt="Image" width="49%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 2-6. A ring buffer of three elements</div> </div>

Figure 2-7 illustrates how this ring buffer evolves over time as values expire:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//9ad28410-1af5-46a5-96ea-ef56592e29ea/markdown_1/imgs/img_in_image_box_143_223_864_514.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A33Z%2F-1%2F%2F7816b6e69bd8f7c859a89be264199ee74e480dfef82f182f408fdb122738012e" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 2-7. A timer max ring buffer of length 3 and two-minute expiry</div> </div>

#### 3. Timer Base Units
Micrometer standardizes on **seconds** as its base unit of time. However, charting libraries (like Grafana) can automatically scale and display these values in milliseconds or microseconds:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//9ad28410-1af5-46a5-96ea-ef56592e29ea/markdown_3/imgs/img_in_image_box_143_246_864_509.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A35Z%2F-1%2F%2Fe580982c1b6fd136ebe69b44470fd6f5193f605c2746ef6bae3aa09399ecdc09" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 2-8. A timer shipped with seconds base units displayed in milliseconds</div> </div>

We configure the charting library to interpret these units correctly in its metadata settings:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//9ad28410-1af5-46a5-96ea-ef56592e29ea/markdown_3/imgs/img_in_image_box_142_682_863_1000.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A35Z%2F-1%2F%2F0f6dfad32f95b08a70c3363dfd3bb4585ffe60ea08f8ec192ffd9c06889fabc5" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 2-9. Informing the charting library how to interpret timer base units</div> </div>

#### 4. Implementing a Timer
```java
package com.ftgo.order.metrics;

import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Timer;
import org.springframework.stereotype.Component;

import java.util.concurrent.Callable;

@Component
public class LatencyMetrics {

    private final Timer orderCreationTimer;

    public LatencyMetrics(MeterRegistry registry) {
        this.orderCreationTimer = Timer.builder("order.creation.latency")
                .description("Time taken to process and write order records")
                .tag("database.engine", "postgres")
                .publishPercentiles(0.5, 0.95, 0.99) // Publish pre-computed percentiles
                .register(registry);
    }

    public <T> T recordExecution(Callable<T> task) throws Exception {
        // Record the duration of a Callable task execution
        return this.orderCreationTimer.recordCallable(task);
    }
}
```

---

## 31.5 Latency Distributions and Statistical Models

In distributed systems, request response times do not follow a simple bell curve (normal distribution):

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//f88def43-9565-4cc3-a79d-5f1c0f4747c7/markdown_3/imgs/img_in_chart_box_142_376_864_675.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A34Z%2F-1%2F%2F012995ac7fc8d0cce03db4a2fba5728cfbccdbebd45a737761b9bfc59b7fb616" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 2-10. The normal distribution curve</div> </div>

Java applications typically exhibit a **bimodal** (or multimodal) latency distribution:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//f88def43-9565-4cc3-a79d-5f1c0f4747c7/markdown_3/imgs/img_in_chart_box_143_898_864_1133.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A34Z%2F-1%2F%2F8a6ef30ee6204dfd5793b48bdc013ecb89cd23703ff2090045017758e51e6b39" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 2-11. A typical bimodal distribution of Java latencies</div> </div>

As illustrated in Figure 2-11, bimodal distributions contain two peaks:
* **Left Peak (Fast)**: Standard executions that resolve quickly.
* **Right Peak (Slow)**: Executions delayed by Garbage Collection pauses, JIT compilation tasks, or network timeout retries.

Because of this bimodal distribution, average latency is a misleading metric that obscures performance issues. We must use **percentiles** (p95, p99) to track the performance of the slowest requests.

---

### 31.5.1 Visualizing Percentiles
We can query and plot specific percentiles to identify outliers:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//61ba0438-a2c5-4222-9db2-115ebab93eb4/markdown_3/imgs/img_in_chart_box_143_107_864_434.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A53Z%2F-1%2F%2Ff47738e5fae66916c6d94e1b485d67693d7747c1c32bb54ec026339a0acc5c55" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 2-12. 99th percentile of a single timer for individual application instances</div> </div>

As a cluster scales, plotting percentiles for every instance can clutter your dashboard. We use functions like `topk()` to limit the visualization to the worst-performing instances:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//61ba0438-a2c5-4222-9db2-115ebab93eb4/markdown_3/imgs/img_in_chart_box_142_685_865_1011.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A53Z%2F-1%2F%2Fb9931ce1f12cfa061c28097349a6b24116d18d2298b8b686dc73c5356fbe6a73" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 2-13. Top three worst 99th percentile of a single timer for individual application instances</div> </div>

---

### 31.5.2 Latency Histograms and Heatmaps
Instead of computing percentiles on the client, we can export raw **histograms** to let the monitoring backend compute percentiles dynamically. Histograms are exported in one of two formats:

<div style="text-align: center;">
  <img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//fa8e580e-0f1e-4415-b15d-a81b83d94407/markdown_0/imgs/img_in_chart_box_143_108_497_428.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A49Z%2F-1%2F%2F875ea633f4dc42489a5f7744e4635ccce881f6744edcaa8e15546a78a3fc179f" alt="Image" width="35%" />
  <img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//fa8e580e-0f1e-4415-b15d-a81b83d94407/markdown_0/imgs/img_in_chart_box_514_109_865_430.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A49Z%2F-1%2F%2Fca98b079d22a2851023718bbef0b81da6831a533f0771c48114bcb735e814d74" alt="Image" width="34%" />
</div>

<div style="text-align: center;"><div style="text-align: center;">Figure 2-14. Cumulative (left) versus normal (right) histogram distributions</div> </div>

Plotting histograms over time generates a **heatmap**, which provides a visual breakdown of your system's latency spectrum:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//fa8e580e-0f1e-4415-b15d-a81b83d94407/markdown_0/imgs/img_in_chart_box_143_716_863_1092.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A49Z%2F-1%2F%2Fe05e1aafb12f5e88920088d1d526c976efacc239b9e9c76a7a1f128ac4a2fbe7" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 2-15. Latency heatmap showing performance distribution over time</div> </div>

---

## 31.6 SLO Boundaries and Alert Queries

Rather than tracking every millisecond, we can configure our histograms with specific **SLO boundaries** (e.g. 100 ms, 500 ms, 1000 ms) to monitor whether requests comply with our Service Level Objectives:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//fa8e580e-0f1e-4415-b15d-a81b83d94407/markdown_4/imgs/img_in_chart_box_143_169_864_463.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A54Z%2F-1%2F%2F510e34c295b6427dd3b653ea5361feea13933a5af9a534dc6ed5b18f4409f376" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 2-16. Histogram of SLO boundaries</div> </div>

Combining percentile histograms and SLO boundaries provides a more complete view of latency distributions:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//fa8e580e-0f1e-4415-b15d-a81b83d94407/markdown_4/imgs/img_in_chart_box_202_799_859_1069.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A55Z%2F-1%2F%2Fdf8a96f799a29c84b10856a909a75e31e9c2f1efc3f0921a3d84a20d516eaa51" alt="Image" width="65%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 2-17. Mixed histogram of service level objective boundaries and percentile histogram bucket boundaries</div> </div>

We use these metrics to construct alerts in systems like Atlas and Prometheus:

<div style="text-align: center;">
  <img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//297e8482-6a3b-4beb-8665-f681bb9a737a/markdown_1/imgs/img_in_image_box_143_110_867_408.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A33Z%2F-1%2F%2Fd12f04d2302c5e1c324534c0cfc26068b083bdb2ee7ef2ed3a028e46b4c95bfe" alt="Image" width="71%" />
  <img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//297e8482-6a3b-4beb-8665-f681bb9a737a/markdown_1/imgs/img_in_chart_box_527_110_867_406.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A33Z%2F-1%2F%2F99eea844ec6614891dc10d4ac61e01987291ab4fbc3d43f33a2ebaa75a3b76ac" alt="Image" width="33%" />
</div>

<div style="text-align: center;"><div style="text-align: center;">Figure 2-18. SLO boundary alert queries: Atlas (left) versus Prometheus (right)</div> </div>

---

## 31.7 Long Task Timers

A standard `Timer` records an event only after it completes. If a task runs for hours, the timer reports no data until the task finishes, leaving you blind to active, long-running processes (like batch jobs or file uploads).

To solve this, we use a `LongTaskTimer`. It reports metrics for active tasks *during* their execution, tracking the active task count, total duration, and maximum duration of currently running operations:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//297e8482-6a3b-4beb-8665-f681bb9a737a/markdown_4/imgs/img_in_chart_box_267_110_734_549.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A35Z%2F-1%2F%2Ff63839418c6a75871a120a0c711b366e675c8e4bfd38de094f6b01280f80c376" alt="Image" width="46%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 2-19. Long task timer active and total duration for two tasks</div> </div>

#### 1. Implementing a Long Task Timer
```java
package com.ftgo.order.metrics;

import io.micrometer.core.instrument.LongTaskTimer;
import io.micrometer.core.instrument.MeterRegistry;
import org.springframework.stereotype.Component;

@Component
public class BatchJobMetrics {

    private final LongTaskTimer batchJobTimer;

    public BatchJobMetrics(MeterRegistry registry) {
        this.batchJobTimer = LongTaskTimer.builder("batch.job.execution")
                .description("Tracks active execution time of long-running batch migrations")
                .tag("job.type", "data-migration")
                .register(registry);
    }

    public void runMigration() {
        LongTaskTimer.Sample sample = this.batchJobTimer.start();
        try {
            // Execute long-running migration task...
            Thread.sleep(10000);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        } finally {
            sample.stop();
        }
    }
}
```

---

## 31.8 Coordinated Omission in Telemetry

**Coordinated Omission** is a measurement error that occurs when a load tester coordinates with a system's delays, inadvertently excluding wait times from its latency measurements.

Consider a drive-through restaurant with a pressure plate that tracks service times. If a bus halts at the drive-through, the service time for that vehicle spikes. Cars queued behind the bus wait for hours, but the pressure plate only measures the time spent at the service window once they arrive, ignoring their wait time in the queue:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//fb246973-9b69-47a5-a318-b05f1ddf26fe/markdown_0/imgs/img_in_image_box_143_108_864_505.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A33Z%2F-1%2F%2Fea05e84eaed442f5b5cf2c34431ef1e94d25fb515a486eab48247c8a6349f125" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 2-20. Coordinated omission caused by a bus in the drive-through</div> </div>

In software testing, blocking load test clients exhibit this same behavior. If a service degrades and response times spike, the blocking client pauses its requests. As a result, it records a few slow requests but fails to measure the queue time of the requests it was blocked from sending, underreporting the true latency experienced by users.

To avoid coordinated omission, we must use **non-blocking (reactive) load testers** that send requests at a constant rate regardless of the system's response times:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//fb246973-9b69-47a5-a318-b05f1ddf26fe/markdown_3/imgs/img_in_chart_box_150_105_862_584.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A35Z%2F-1%2F%2F985384ed8a199074a916efd52b8698d3d75aea7adacb74f471f5905506c16f37" alt="Image" width="70%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 2-21. Blocking load test versus a nonblocking (reactive) load test</div> </div>

As shown in Figure 2-21, a reactive load test exposes the true latency impact of system saturation, revealing delays up to 200 ms that a blocking test would miss.

This measurement difference affects all major latency metrics:

* **Maximum Latency**:
<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//fb246973-9b69-47a5-a318-b05f1ddf26fe/markdown_3/imgs/img_in_chart_box_143_703_863_1067.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A35Z%2F-1%2F%2Fe36405c285364fc300f15d39eb59b43e1801f29498d90a445d702df7e92e472d" alt="Image" width="71%" /></div>
<div style="text-align: center;"><div style="text-align: center;">Figure 2-22. Max latency recorded by blocking vs. reactive load tests</div> </div>

* **99th Percentile Latency**:
<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//fb246973-9b69-47a5-a318-b05f1ddf26fe/markdown_4/imgs/img_in_chart_box_143_219_863_587.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A36Z%2F-1%2F%2Fcfae603d4f9bac97d278662619f428dcf3eb3d04e910a9dbd56aff0d40f1020a" alt="Image" width="71%" /></div>
<div style="text-align: center;"><div style="text-align: center;">Figure 2-23. 99th percentile recorded by blocking vs. reactive load tests</div> </div>

* **Completed Throughput**:
<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//b0484439-a41e-410e-9bb8-016db9221d58/markdown_0/imgs/img_in_chart_box_144_106_864_473.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A33Z%2F-1%2F%2Faf15f797bc85fa4369077b7d7ec408659eca0200ba3f170d038bcc8d56f3d329" alt="Image" width="71%" /></div>
<div style="text-align: center;"><div style="text-align: center;">Figure 2-24. Throughput measurements recorded by blocking vs. reactive load tests</div> </div>

* **Average Latency**:
<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//b0484439-a41e-410e-9bb8-016db9221d58/markdown_0/imgs/img_in_chart_box_143_647_864_972.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A33Z%2F-1%2F%2F54c91a8a6bb8ed58a43586ebab7fabf9585775069fc1b091cb0cf252a2f9020a" alt="Image" width="71%" /></div>
<div style="text-align: center;"><div style="text-align: center;">Figure 2-25. Average latency measurements recorded by blocking vs. reactive load tests</div> </div>

---

## 31.9 Managing Cost: Tag Cardinality Controls

While dimensional tags are powerful, they present a cost risk. Every unique combination of tag values generates a new time series. If a tag's value count explodes (high cardinality), the number of time series stored in your database will spike, increasing storage and query costs.

For example, tracking request latency using a status code tag yields low cardinality:

$$\text{Cardinality} = 2 \text{ methods} \times 4 \text{ statuses} \times 2 \text{ outcomes} \times 1 \text{ URI} \times 3 \text{ exceptions} = 48 \text{ timeseries}$$

However, if you add a high-cardinality tag like the user's ID or session ID to a metric:

$$\text{Cardinality} = 48 \times 1,000,000 \text{ user IDs} = 48,000,000 \text{ timeseries}$$

This cardinality explosion will overload your monitoring database. **Never tag metrics with high-cardinality values.** Use distributed tracing for request-level diagnostics instead.

---

### 31.9.1 Implementing Meter Filters
We can use Micrometer `MeterFilter` configurations to drop unwanted metrics, restrict tag keys, or replace high-cardinality values dynamically:

```java
package com.ftgo.order.config;

import io.micrometer.core.instrument.Meter;
import io.micrometer.core.instrument.config.MeterFilter;
import io.micrometer.core.instrument.config.MeterFilterReply;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class MetricsConfiguration {

    @Bean
    public MeterFilter denyKafkaMetricsFilter() {
        // Drop all metrics containing 'kafka' in the name
        return MeterFilter.deny(id -> id.getName().contains("kafka"));
    }

    @Bean
    public MeterFilter replaceHighCardinalityTags() {
        return new MeterFilter() {
            @Override
            public Meter.Id map(Meter.Id id) {
                if (id.getName().startsWith("http.server.requests")) {
                    // Replace a potential high-cardinality path variable with a generic tag
                    return id.withTag(io.micrometer.core.instrument.Tag.of("uri", "/orders/{orderId}"));
                }
                return id;
            }
        };
    }
}
```

This filter pipeline allows you to control telemetry collection costs at the application level before shipping data to backends:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//d36824a5-5a8a-47fa-b2a6-72f87d12adae/markdown_1/imgs/img_in_image_box_142_711_864_1146.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A50Z%2F-1%2F%2F932a026790012a08bca0ccb202a1d5f8a29dfd99cbde637a50913e4b1096f012" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 2-26. Shipping metrics to both Prometheus and Cloudwatch using filters</div> </div>

---

---

## 31.10 Exposing Metrics using Distribution Summaries

While timers are specialized for measuring durations (time in seconds), a `DistributionSummary` is designed to track distributions of values that represent other measurements, such as payload sizes in bytes, database row counts per query, or ticket queue counts.

Like standard timers, distribution summaries record count, sum of values, and maximums:

```java
package com.ftgo.order.metrics;

import io.micrometer.core.instrument.DistributionSummary;
import io.micrometer.core.instrument.MeterRegistry;
import org.springframework.stereotype.Component;

@Component
public class PayloadMetrics {

    private final DistributionSummary payloadSizeSummary;

    public PayloadMetrics(MeterRegistry registry) {
        this.payloadSizeSummary = DistributionSummary.builder("http.server.payload.size")
                .description("Distribution of incoming HTTP request sizes in bytes")
                .baseUnit("bytes")
                .publishPercentiles(0.5, 0.9, 0.99)
                .register(registry);
    }

    public void recordPayloadSize(long bytes) {
        this.payloadSizeSummary.record(bytes);
    }
}
```

---

## 31.11 Implementing a Custom Meter Binder

In addition to using the standard registry builders, we can package custom metrics groups as a reusable `MeterBinder`.

This allows us to encapsulate domain-specific metrics code cleanly:

```java
package com.ftgo.order.metrics;

import io.micrometer.core.instrument.Gauge;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.binder.MeterBinder;
import org.springframework.stereotype.Component;

import java.lang.management.ManagementFactory;
import java.lang.management.ThreadMXBean;

@Component
public class ThreadDeadlockMetrics implements MeterBinder {

    private final ThreadMXBean threadMXBean = ManagementFactory.getThreadMXBean();

    @Override
    public void bindTo(MeterRegistry registry) {
        // Expose deadlocked threads count as a gauge
        Gauge.builder("jvm.threads.deadlocked", threadMXBean, this::getDeadlockedThreadCount)
                .description("Total number of JVM threads currently in a deadlocked state")
                .tag("telemetry.source", "thread-mxbean")
                .register(registry);
    }

    private double getDeadlockedThreadCount(ThreadMXBean bean) {
        long[] deadlockedThreads = bean.findDeadlockedThreads();
        return (deadlockedThreads == null) ? 0.0 : deadlockedThreads.length;
    }
}
```

---

## 31.12 Spring Boot Actuator and Prometheus Scrape Endpoint Config

In Spring Boot, we expose the Micrometer Prometheus registry endpoints by importing Spring Boot Actuator and configuring properties inside `application.yml`:

```yaml
management:
  endpoints:
    web:
      exposure:
        include: "prometheus,health,info"
  endpoint:
    prometheus:
      enabled: true
  metrics:
    tags:
      # Inject global common tags into all metrics automatically
      application: "order-service"
      region: "us-east-1"
```

Once configured, Prometheus scrapes metrics by hitting the `/actuator/prometheus` endpoint, which renders the metrics in the Prometheus exposition text format.

---

## 31.13 Reliability Mathematics: PromQL Histogram Percentiles

When exporting histograms containing SLO boundaries or default buckets, we compute percentiles on the server side using the PromQL `histogram_quantile()` function:

$$\text{Quantile Value} = \text{histogram\_quantile}(q, \text{sum}(\text{rate}(\text{metric\_bucket}[I])) \text{ by } (\text{le}))$$

### 1. Prometheus Percentile Calculation Formula
```promql
# Calculate the 99th percentile response time over a 5-minute window
histogram_quantile(0.99, sum(rate(http_server_requests_seconds_bucket[5m])) by (le))
```

* **`le` (Less or Equal)**: Represents the bucket boundary tag. Prometheus groups request occurrences by their bucket boundaries.
* **`rate(...[5m])`**: Calculates the rate of request increases per second for each bucket over the 5-minute interval.
* **`sum(...) by (le)`**: Aggregates the rates across all container instances in the cluster. This allows us to calculate an accurate cluster-wide 99th percentile.

This calculation is far more accurate than averaging precomputed percentiles from individual instances, which is statistically invalid.

---

---

## 31.14 Comparative Analysis: Pull vs. Push Metrics Architecture

Different monitoring systems collect application metrics using one of two architectures:

<table border="1" style="margin: auto; width: 90%; text-align: center; border-collapse: collapse;">
  <thead>
    <tr style="background: #f2f2f2;">
      <th>Telemetry Attribute</th>
      <th>Pull Architecture (e.g. Prometheus)</th>
      <th>Push Architecture (e.g. StatsD / Datadog)</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><strong>Transport Protocol</strong></td>
      <td><strong>HTTP/TCP</strong>: The monitoring server requests metrics by scraping the application's Actuator endpoint.</td>
      <td><strong>UDP/HTTP</strong>: The application pushes metric payloads to a local daemon or SaaS gateway.</td>
    </tr>
    <tr>
      <td><strong>Reliability</strong></td>
      <td>High: The server controls scrape rates, detecting connection drops or application outages immediately.</td>
      <td>Lower over UDP: Packages can drop silently during network congestion.</td>
    </tr>
    <tr>
      <td><strong>Network Firewalling</strong></td>
      <td>Requires firewall rules allowing the monitoring cluster to query pod networks.</td>
      <td>Requires only egress firewall access to send payloads outward.</td>
    </tr>
    <tr>
      <td><strong>State Management</strong></td>
      <td>Application registry aggregates counts and sums in memory between scrapes.</td>
      <td>Application pushes raw data points; the daemon or server aggregates them.</td>
    </tr>
  </tbody>
</table>

---

## 31.15 Prometheus Exposition Text Format Schema

To understand what Prometheus scrapes, we examine the raw text format returned by querying the `/actuator/prometheus` endpoint:

```
# HELP jvm_threads_deadlocked Total number of JVM threads currently in a deadlocked state
# TYPE jvm_threads_deadlocked gauge
jvm_threads_deadlocked{application="order-service",region="us-east-1",telemetry_source="thread-mxbean"} 0.0

# HELP http_server_requests_seconds_bucket Latency histogram buckets
# TYPE http_server_requests_seconds_bucket counter
http_server_requests_seconds_bucket{application="order-service",region="us-east-1",uri="/orders/{orderId}",le="0.1"} 120.0
http_server_requests_seconds_bucket{application="order-service",region="us-east-1",uri="/orders/{orderId}",le="0.5"} 145.0
http_server_requests_seconds_bucket{application="order-service",region="us-east-1",uri="/orders/{orderId}",le="1.0"} 150.0
http_server_requests_seconds_bucket{application="order-service",region="us-east-1",uri="/orders/{orderId}",le="+Inf"} 150.0

# HELP http_server_requests_seconds_count Number of completed requests
# TYPE http_server_requests_seconds_count counter
http_server_requests_seconds_count{application="order-service",region="us-east-1",uri="/orders/{orderId}"} 150.0

# HELP http_server_requests_seconds_sum Sum of request durations
# TYPE http_server_requests_seconds_sum counter
http_server_requests_seconds_sum{application="order-service",region="us-east-1",uri="/orders/{orderId}"} 45.5
```

---

## 31.16 Solving Coordinated Omission in Load Testing Tools

In section 31.8, we analyzed coordinated omission. To get accurate latency charts during performance testing, we must use load testing tools designed to track wait times:

* **wrk2**: Modifies the original `wrk` tool to inject requests using a constant throughput timer. It calculates latency by comparing the actual completion time with the *scheduled arrival time* rather than the actual start time of the socket.
* **Gatling**: Uses Akka's non-blocking actors to generate virtual users independently. If the target microservice degrades, Gatling's generators continue spawning virtual users, recording the queue delays accurately.
* **JMeter**: By default, JMeter uses a thread-per-user model, making it susceptible to coordinated omission. We must configure it with the **ConcurrentTargetingTimer** or use non-blocking plugins to decouple request generation from execution.

---

---

## 31.17 Monitoring Database Connection Pools: Hikari Binder

To ensure we detect saturation issues in our database layer, the platform team must register connection pool metrics with the registry. 

Below is a complete Java implementation of a custom binder that tracks Hikari connection pool metrics dynamically:

```java
package com.ftgo.order.metrics;

import com.zaxxer.hikari.HikariDataSource;
import io.micrometer.core.instrument.Gauge;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.binder.MeterBinder;
import org.springframework.stereotype.Component;

@Component
public class HikariPoolCustomBinder implements MeterBinder {

    private final HikariDataSource dataSource;

    public HikariPoolCustomBinder(HikariDataSource dataSource) {
        this.dataSource = dataSource;
    }

    @Override
    public void bindTo(MeterRegistry registry) {
        // Expose active connections count
        Gauge.builder("db.pool.connections.active", dataSource, ds -> ds.getHikariPoolMXBean().getActiveConnections())
                .description("Number of active database connections currently in use")
                .tag("pool.name", dataSource.getPoolName())
                .register(registry);

        // Expose idle connections count
        Gauge.builder("db.pool.connections.idle", dataSource, ds -> ds.getHikariPoolMXBean().getIdleConnections())
                .description("Number of idle database connections currently available")
                .tag("pool.name", dataSource.getPoolName())
                .register(registry);

        // Expose threads awaiting a connection
        Gauge.builder("db.pool.threads.pending", dataSource, ds -> ds.getHikariPoolMXBean().getThreadsAwaitingConnection())
                .description("Number of threads currently blocked waiting for a connection")
                .tag("pool.name", dataSource.getPoolName())
                .register(registry);
    }
}
```

---

## 31.18 Prometheus Alert Rules Configuration (`prometheus.rules.yml`)

Using the metrics and SLO boundaries registered in section 31.13, we declare alerting rules in Prometheus to notify operations teams when thresholds are violated:

```yaml
groups:
  - name: order-service-alerts
    rules:
      - alert: HighOrderResponseLatency
        expr: histogram_quantile(0.99, sum(rate(http_server_requests_seconds_bucket[5m])) by (le)) > 2.0
        for: 2m
        labels:
          severity: page
          tier: backend
        annotations:
          summary: "99th percentile response latency is high"
          description: "The 99th percentile response latency has exceeded 2 seconds for 2 minutes (current value: {{ $value }}s)."

      - alert: DatabasePoolExhaustion
        expr: db_pool_threads_pending > 0
        for: 1m
        labels:
          severity: critical
          tier: database
        annotations:
          summary: "Database connection pool exhaustion detected"
          description: "There are currently threads blocked waiting for database connections (current count: {{ $value }} threads)."
```

---

## 31.19 Summary of Micrometer Metrics and Observability Controls

This table summarizes the configurations, classes, and parameters used to build observability foundations:

| Telemetry Element | Micrometer Class / Config | Main Implementation Target | Scope Location |
| :--- | :--- | :--- | :--- |
| **Telemetry Facade** | `MeterRegistry` | Coordinates the collection and publishing of metrics. | Spring Context |
| **Instantaneous State**| `Gauge` | Tracks fluctuating resources like queue size or memory. | Java Class |
| **Monotonic Event** | `Counter` | Monitors event counts and throughput. | Java Class |
| **Latency Tracking** | `Timer` | Measures counts, durations, and maximums. | Java Class |
| **Active Duration** | `LongTaskTimer` | Tracks currently running operations. | Java Class |
| **Cost Protection** | `MeterFilter` | Drops metrics or replaces high-cardinality tags. | Configuration |
| **SLO Boundary** | `ServiceLevelObjective` | Defines latency limits for SLA reporting. | Timer Config |
| **Aggregation Rule** | Rate-normalized Sum / Count | Calculates cluster-wide average latency. | Dashboard Query |
| **Decay Management** | Ring Buffer | Expires historical maximum values. | Timer Config |

---

## Chapter Summary

* Black-box monitoring observes a service from the outside to identify user-facing failures, while white-box monitoring relies on internal telemetry to diagnose root causes.
* Hierarchical metrics use a dot-separated naming tree, while dimensional metrics separate the metric name from its metadata using key-value tags.
* **Micrometer** serves as the metrics facade for JVM applications, translating metric names into the format required by your target backend.
* We use **Gauges** to monitor fluctuating resources (like memory usage or queue size), and **Counters** to track monotonic events (like transaction counts).
* **Timers** track count, sum of durations, and maximum values. You should compute averages by dividing sum rates by count rates.
* To prevent transient spikes from skewing charts permanently, maximum timer values are aged out using a decaying **Ring Buffer**.
* Latency in JVM applications follows a **bimodal distribution** caused by standard executions and garbage collection pauses.
* **Coordinated Omission** occurs when a load tester coordinates with a system's delays, underreporting latency by omitting wait times from its measurements.
* We must limit tag cardinality to prevent storage and query costs from exploding. Never include high-cardinality values like user IDs in metric tags.
* **Meter Filters** allow you to filter metrics, drop tags, and control cost limits programmatically.
---

## 31.12 Production-Grade FTGO Order Reviews Custom Metrics and Alerting Rules

In this section, we present the complete, production-grade custom metrics instrumentation and alerting configuration for the **review-service** in the **FTGO Order Reviews** system. We write a Spring Configuration class using the **Spring Boot Micrometer** registry to instrument service performance, and define **Prometheus Alert Rules** using actual PromQL expressions to trigger operations notifications on performance drops.

```
+---------------------------------------------------------------------------------+
|                         PROMETHEUS METRICS PIPELINE                             |
+---------------------------------------------------------------------------------+
|                                                                                 |
|   [ OrderReviewsResource ] ===(instruments)===> [ Micrometer MeterRegistry ]   |
|                                                                │                |
|                                                     (Exposes Prometheus API)    |
|                                                                v                |
|   [ Ops Notifications ] <===(alerts)=== [ Alertmanager ] <=== [ Prometheus ]    |
|                                                                                 |
+---------------------------------------------------------------------------------+
```

---

### Scenario: Instrumenting Review Submission Latency, Queue Size, and Ratings
We configure our microservice to expose white-box metrics to Prometheus. We register three metrics:
1. **`ftgo.order.reviews.submitted.count`** (Counter): Tracks the total count of reviews written, tagged by their rating value and status.
2. **`ftgo.order.reviews.fetch.latency`** (Timer): Records latency percentiles (p50, p90, p99) for reviews search queries.
3. **`ftgo.order.reviews.queue.size`** (Gauge): Tracks the size of the reviews asynchronous indexing background queue.

#### 1. The Spring Configuration Class: `OrderReviewsMetricsConfig.java`
```java
package com.ftgo.review.metrics;

import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.Gauge;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Timer;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.time.Duration;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.Queue;

@Configuration
public class OrderReviewsMetricsConfig {

    private final Queue<Runnable> reviewProcessingQueue = new LinkedBlockingQueue<>(1000);

    @Bean
    public Queue<Runnable> reviewProcessingQueue() {
        return this.reviewProcessingQueue;
    }

    /**
     * Registers a custom Gauge to track the size of the reviews background processor queue.
     * @param registry the Micrometer meter registry facade.
     * @return the registered Gauge tracking queue size.
     */
    @Bean
    public Gauge queueSizeGauge(MeterRegistry registry) {
        return Gauge.builder("ftgo.order.reviews.queue.size", reviewProcessingQueue, Queue::size)
                .description("Tracks the size of the reviews background indexing queue")
                .tag("service", "review-service")
                .register(registry);
    }

    /**
     * Configures a custom Timer builder capturing request latency percentiles.
     * @param registry the Micrometer meter registry facade.
     * @return the configured Timer instance.
     */
    @Bean
    public Timer reviewsFetchTimer(MeterRegistry registry) {
        return Timer.builder("ftgo.order.reviews.fetch.latency")
                .description("Measures search query duration for order reviews")
                .tag("service", "review-service")
                .publishPercentiles(0.50, 0.90, 0.99) // Publish standard percentiles
                .publishPercentileHistogram()         // Export hist values for Prometheus SLO PromQL
                .sla(Duration.ofMillis(50), Duration.ofMillis(100), Duration.ofMillis(200), Duration.ofMillis(500))
                .minimumExpectedValue(Duration.ofMillis(10))
                .maximumExpectedValue(Duration.ofSeconds(5))
                .register(registry);
    }

    /**
     * Helper factory to increment counter submissions, tag-categorized by rating score and result.
     * @param registry the Micrometer registry.
     * @param rating review rating (1 to 5).
     * @param status submission status (success, error).
     */
    public static void incrementSubmissionCounter(MeterRegistry registry, int rating, String status) {
        Counter.builder("ftgo.order.reviews.submitted.count")
                .description("Tracks the total count of reviews submitted")
                .tag("service", "review-service")
                .tag("rating", String.valueOf(rating))
                .tag("status", status)
                .register(registry)
                .increment();
    }
}
```

---

#### 2. The Prometheus Alerting Rules Configuration: `alerts.rules.yml`
We configure Prometheus alerting rules to warn the operations team if review fetch latency spikes or if the error rate exceeds the SLO limit.

```yaml
groups:
  - name: ftgo-reviews-alert-rules
    rules:
      # Alert 1: Warn when the 99th percentile (p99) request latency exceeds 500ms
      - alert: ReviewsServiceLatencySpike
        expr: histogram_quantile(0.99, sum(rate(ftgo_order_reviews_fetch_latency_seconds_bucket[5m])) by (le)) > 0.5
        for: 2m
        labels:
          severity: critical
          service: review-service
        annotations:
          summary: "Latency spike detected on review service"
          description: "The p99 latency for fetching order reviews is {{ $value }}s, exceeding the 500ms threshold for over 2 minutes."

      # Alert 2: Warn when review submission error rate exceeds 1% of total queries
      - alert: ReviewsSubmissionErrorsHigh
        expr: sum(rate(ftgo_order_reviews_submitted_count_total{status="error"}[5m])) / sum(rate(ftgo_order_reviews_submitted_count_total[5m])) > 0.01
        for: 5m
        labels:
          severity: warning
          service: review-service
        annotations:
          summary: "Review submission error rate is high"
          description: "Review submission failures account for {{ $value | humanizePercentage }} of total submissions, exceeding the 1% SLO limit."

      # Alert 3: Warn when the background processor queue is saturating
      - alert: ReviewsProcessorQueueSaturating
        expr: ftgo_order_reviews_queue_size > 800
        for: 3m
        labels:
          severity: warning
          service: review-service
        annotations:
          summary: "Reviews indexing background queue is saturating"
          description: "The reviews queue size has reached {{ $value }} items, indicating worker thread pool bottlenecks."
```
