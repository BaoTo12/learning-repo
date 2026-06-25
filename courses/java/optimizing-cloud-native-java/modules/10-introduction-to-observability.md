# Introduction to Observability

The topic of observability has become more and more important in software development in recent years.

> Observability is moving from being a special concern for a few people to becoming a new field for user experience, systems, and service management in web companies and large businesses alike.
> — *James Governor*

But why should Java developers care about observability? And what is observability anyway?

In this chapter, we will study the concepts and basics of observability. In Chapter 11, we will see how to use these techniques in Java applications using open source libraries and technologies.

---

## The What and the Why of Observability

Some developers think observability is vague and hard to understand. In our view, this is not true. Observability is simple in concept and should be easy to explain. Observability tools are basically a continuation, extension, and broader version of classic monitoring systems. They provide features that go beyond traditional monitoring methods.

To help show the concepts of observability, we will use the Fighting Animals example from Chapter 8.

### What Is Observability?

The steps in an observability solution are basically:
1. **Instrument** production systems and applications to collect observability data.
2. **Send** this data to an external system that can store it.
3. **Analyze** the data using tools that let us get useful information about system behavior for DevOps, SREs, and engineers.

It is very important that observability data is sent out of the production system. It must go into a completely separate observability system running on another cluster (ideally on physically separate hardware). This is shown in Figure 10-1 for the Fighting Animals example.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//08d4c711-7487-44e4-9f78-684212e9bd6f/markdown_4/imgs/img_in_image_box_142_446_865_861.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A35Z%2F-1%2F%2F36412fc8d80fa9c8f064c4aee7ede0754c2b852e0e42e6de73d266b9de256e42" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 10-1. Sending observability data to a separate system</div> </div>

The reason for this is to make sure that when production systems have outages, the data needed to find the cause of the problem is still available. If the telemetry data stays inside the failing production cluster, the outage itself might stop you from getting the diagnostic information needed to fix it.

For the same reason, you must not upgrade the observability system at the same time as the production system that is being watched.

Also, the query and analysis tools must be very flexible.

> Observability means you do not have to plan your questions in advance, or optimize those questions before they are needed.
> — *Charity Majors*

Finding the cause of an outage using observability data is about exploring. It is like testing a theory in data science or physical science. This means that a visual view (like a graph plotter) and a flexible query tool are common user interfaces for observability tools.

Finally, good observability data should give you useful information about the whole system, not just single parts. This means you must connect different services, signals, and systems together in context. This is especially true for larger systems where the amount of telemetry data can be too large to handle.

### Why Observability?

Three main trends led to the use of modern observability:

1. **System Control Theory**: This comes from the question: *“How well can we understand the inside state of a system by looking at its outside outputs?”* This question naturally comes up when fixing incidents, but it is useful in other areas too.
   
   <div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//9eb112b4-5b82-4be7-898b-aa0599eff23d/markdown_0/imgs/img_in_image_box_177_643_253_743.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A15Z%2F-1%2F%2F6f649c42808088e2b43780e8f8dca23df9542b0448d97db9d99480f1194781c4" alt="Image" width="7%" /></div>

   > [!NOTE]
   > One way observability is different from traditional monitoring is that modern applications are very complex. Because of this, you cannot watch application health without knowing a lot about how it works inside. This means you must adopt a DevOps culture where developers share the duty of running the application.

2. **Immutable Cloud Infrastructure**: Cloud-native designs depend heavily on unchangeable infrastructure. For example, a CI/CD system builds a container and deploys it to a Kubernetes cluster. If a container has issues, you do not change it where it is running. Instead, it is restarted, rolled back, or replaced by a new build. This unchangeable nature makes old interactive debugging (like using SSH to log into a live server) outdated. This makes an external observability pipeline necessary.
3. **Application Performance Monitoring (APM)**: In the past, APM was mostly controlled by commercial vendors (such as New Relic, Dynatrace, and AppDynamics). In recent years, open-source projects and new SaaS companies (like Datadog and Honeycomb) have pushed these vendors to use open telemetry standards and move toward general-purpose observability.

---

## The Three Pillars

The three pillars model shows the main data sources used in observability analysis, as shown in Figure 10-2.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//9eb112b4-5b82-4be7-898b-aa0599eff23d/markdown_1/imgs/img_in_image_box_158_439_324_609.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A19Z%2F-1%2F%2F6dda8321857a4b6550a6622bd04699b57565ccc97409fbd81b6d1bd4b7d6f740" alt="Image" width="16%" /></div>
<div style="text-align: center;">**Metrics**<br>Numbers showing a specific process or activity measured over periods of time</div>

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//9eb112b4-5b82-4be7-898b-aa0599eff23d/markdown_1/imgs/img_in_image_box_408_446_573_607.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A20Z%2F-1%2F%2F9e3acdf46930c859714bf04972ac2083d913ab0b63f5c967f64c5b3b484779e4" alt="Image" width="16%" /></div>
<div style="text-align: center;">**Logs**<br>Unchangeable records of separate events that happen over time</div>

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//9eb112b4-5b82-4be7-898b-aa0599eff23d/markdown_1/imgs/img_in_image_box_665_450_831_606.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A21Z%2F-1%2F%2Fa453d7926036b998a60eb7e2bf51b3446b0dead1048966b60e9ae1a17901e33b" alt="Image" width="16%" /></div>
<div style="text-align: center;">**Traces**<br>Data showing the path of a request across services to find failures at the level of each single request</div>

<div style="text-align: center;"><div style="text-align: center;">Figure 10-2. The three pillars</div> </div>

The pillars represent three different data formats:
- **Metrics**
- **Logs**
- **Traces**

### Metrics

Metrics are numbers that measure specific activity grouped over a regular, repeating time period (time series data). These usually take the form of counters or gauges. In this grouping, the fine details of individual transactions are lost. However, the resulting signal is very small and perfect for dashboards and real-time alerts.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//9eb112b4-5b82-4be7-898b-aa0599eff23d/markdown_2/imgs/img_in_image_box_176_249_252_349.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A25Z%2F-1%2F%2F3f4292bbf71d5027c32890af7e4b8306e1998a50dcfd7023a80435d6a7b711be" alt="Image" width="7%" /></div>

> [!NOTE]
> Metrics are often used as the starting point of an investigation to find *that* a problem exists. Logs and traces then give the detailed context to understand *why* it is happening.

A metric usually contains four parts:
- **Timestamp**
- **Value**
- **Name**
- **Dimensions** (Metadata tags)

**Dimensions** are attributes saved as key-value pairs. To be useful as a dimension, you must be able to group the values together mathematically.

For example, you can group system and user CPU usage by adding them together to get total CPU usage. In Prometheus format, this is written as:

```prometheus
cpu_utilization{type="system"} 0.12
cpu_utilization{type="user"} 0.66
```

This is a well-defined dimensional metric: it is named `cpu_utilization` and has a single dimension (`type`) with two possible values that can be grouped together.

On the other hand, you cannot add the temperatures of separate rooms in a house (like the kitchen and bedroom) together in a meaningful way. The best you can do is calculate an average. In this case, it is best to show the temperatures as separate metric names instead of dimensions.

Dimensions should have relatively low **cardinality** (a small number of possible values).

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//9eb112b4-5b82-4be7-898b-aa0599eff23d/markdown_3/imgs/img_in_image_box_176_237_252_337.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A28Z%2F-1%2F%2F762612ee21f12a8bf92053328bfcb83315b1d98de83933abd5930a06f9b54905" alt="Image" width="7%" /></div>

> [!WARNING]
> High cardinality (such as using `user_id` with millions of unique values as a dimension) greatly increases storage size and slows down query performance. This huge increase in cardinality can greatly increase the cost of running your observability platform.

A typical metrics collection architecture is shown in Figure 10-3.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//9eb112b4-5b82-4be7-898b-aa0599eff23d/markdown_3/imgs/img_in_image_box_143_468_865_900.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A29Z%2F-1%2F%2F39cc1b1dfdf28ebcd4fd931a75e20756fa82c80b75918c0ddb9382bac12f3f3b" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 10-3. Example of metrics observability</div> </div>

Prometheus is the most common standard for open source metrics storage and is widely used in Kubernetes environments.

Because metrics are collected at a fixed time period, event-based data (like garbage collection pauses) must be grouped over a fixed time window (often shown as histograms) before being sent out. This results in a loss of fine details.

### Logs

Java has a long history of logging frameworks (SLF4J, Log4j, Logback). Usually, developers use a logging facade pattern to separate the application from the actual exporter (such as a file, console, socket, or database):

```java
// SLF4J Code Example from logging_only branch
@RestController
public class AnimalController {
    private static final Logger LOGGER = LoggerFactory.getLogger(AnimalController.class);

    private String fetchRandomAnimal() throws IOException, InterruptedException {
        var pause = (int) (SERVICES.size() * Math.random());
        LOGGER.info("Pausing for: {}", pause);
        // ...
    }
}
```

A log entry is an unchangeable record of a separate event with a timestamp. Logs are usually unstructured text with a severity level (like `INFO`, `WARN`, or `ERROR`). Because they are human-readable, developers can easily search them using regex or show their frequency on a graph over time.

Logs can also be **structured** (often in JSON format) to show events without severity levels. This makes them easier for automated tools to read.

In a modern cloud design, we usually use a **centralized logging pattern**. This groups logs from all microservices over the network into a single, searchable index:

- **Logstash**: A data processing pipeline that collects, filters, and changes logs.
- **Elasticsearch**: A distributed search and analytics engine used to store and index logs.
- **Kibana**: A visual user interface for searching and viewing logs.

This is the popular **ELK stack**, shown in Figure 10-4.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//aa70228b-10b6-42c0-8a72-6fdc62a85ff8/markdown_1/imgs/img_in_image_box_142_233_864_520.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A00Z%2F-1%2F%2Ffa1a55d57480cfdea67b04d626fb334f8c887f112ce4399c62ff7cbebf66c2e0" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 10-4. Example ELK stack</div> </div>

Running a large ELK stack can use a lot of resources and become very expensive. This leads many companies to use managed SaaS logging solutions.

### Traces

A **distributed trace** is a record of a single, top-level service call (usually representing a user request) as it flows through a distributed system. A trace records:
- Which service instances were called.
- Which containers ran each sub-request.
- Which methods were called.
- The latency of each operation.
- The success or failure status of each call.
- Optional custom metadata (attributes) to make searching easier.

A trace is made of multiple **spans**. A span represents a single unit of work (such as running a method or making an HTTP request). Because spans can start child spans, a trace forms a directed acyclic graph (DAG) or tree structure.

Here is an example of a serialized tracing span in JSON format:

```json
{
  "name": "/v1/app/foo",
  "context": {
    "trace_id": "kDM17LTxLxTj220awNARJw==",
    "span_id": "9ir6veJ4Hdw="
  },
  "parent_id": "",
  "kind": 1,
  "start_time": "2021-10-22 16:04:01.209458162 +0000 UTC",
  "end_time": "2021-10-22 16:04:01.209514132 +0000 UTC",
  "status_code": "STATUS_CODE_OK",
  "status_message": "",
  "attributes": {
    "key": "attr",
    "string.value": "value2"
  },
  "events": [
    {
      "name": "processing_event",
      "message": "OK",
      "timestamp": "2021-10-22 16:04:01.209512872 +0000 UTC"
    }
  ]
}
```

The `trace_id`, `span_id`, and `parent_id` are used to rebuild the call tree across network boundaries. Since this span has an empty `parent_id`, it represents the **root span** of the trace. You can view spans in a **traceview** (Gantt chart format) to quickly find bottlenecks, as shown in the Jaeger UI in Figure 10-5.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//aa70228b-10b6-42c0-8a72-6fdc62a85ff8/markdown_3/imgs/img_in_image_box_145_236_865_525.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A01Z%2F-1%2F%2F6f56dca0f3ce6a8c2e43e34295e66fe5df7a6794c5c379ff652cb87036162c90" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 10-5. Example traceview</div> </div>

Setting up distributed tracing requires:
- **Instrumentation**: Changing code to create spans.
- **Context Propagation**: Passing tracing headers between microservices.
- **Ingest & Storage**: Collecting and saving trace data.
- **Search & Visualization**: Searching and showing traces.

You can do this using open source projects like **OpenTelemetry** (for instrumentation and transport), **Grafana Tempo** (for storage), and **Jaeger** (for viewing), as shown in Figure 10-6.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//aa70228b-10b6-42c0-8a72-6fdc62a85ff8/markdown_4/imgs/img_in_image_box_143_107_865_405.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A01Z%2F-1%2F%2F069cdb18a0cd4e6ad4716c9583a827e142d27d48d86b1f71ab8df3def744a6b2" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 10-6. Example of distributed tracing observability</div> </div>

Context propagation is done by putting tracing metadata into HTTP headers using standard formats like the **W3C Trace Context** specification.

#### Trace Sampling
Because tracing all requests in a high-traffic environment creates huge amounts of data, **sampling** is usually used:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//aa70228b-10b6-42c0-8a72-6fdc62a85ff8/markdown_4/imgs/img_in_image_box_176_1047_253_1148.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A01Z%2F-1%2F%2F1ecb5aee6786f58e98203d3d8ea2872f408103701a425e13eae81f0366853ea0" alt="Image" width="7%" /></div>

> [!NOTE]
> The W3C specification defines the `trace-flags` field, which controls sampling and trace level recommendations passed downstream.

- **Head-Based Sampling**: The sampling decision is made at the start of the trace (such as OpenTelemetry's default `ParentBased Always On` policy). This is simple but cannot guarantee that interesting traces (like those that end in an error) are captured.
- **Tail-Based Sampling**: The sampling decision is made after the trace has finished. This makes sure that all error traces (HTTP 5xx, 4xx) are captured, though this is more complex to run.

---

## Comparing the Pillars

The three pillars are fundamentally different in their data features, growth rates, and storage needs:

- **Metrics**: Grouped numbers showing events over a fixed time period. Storage size stays the same no matter how many requests you have. <sup>1</sup>
- **Logs**: Unstructured text records of separate events. Log size can grow very fast when there are high error rates.
- **Traces**: Structured spans showing how long a request takes to run. Trace size grows at the same rate as request traffic.

Because of these differences, open source projects in the past have focused on only a single pillar. <sup>2</sup> Connecting these signals together using correlation is the real power of observability. This is a major focus of ongoing open source development.

### Profiling: A Fourth Pillar?

There is growing interest in treating **continuous profiling** (CPU and memory allocation profiling) as a fourth pillar:
- **On-Demand Profiling**: Turned on only when needed. It provides a very detailed dataset but requires a trigger method. It does not capture the historical context before an outage.
- **Continuous Profiling**: Always-on profiling designed to keep overhead low enough (<1%) to run in production. This lets you analyze past performance drops.

We will study profiling in detail in Chapter 12.

---

## Observability Architecture Patterns and Antipatterns

### Architectural Patterns for Metrics

Two main formats exist for writing hierarchical metrics:
- **Dotted notation**: Used by OpenTelemetry and many APM vendors (such as `jvm.memory.used`).
- **Snake-cased notation**: Used mostly by Prometheus (such as `jvm_memory_used`).

Metrics systems also differ in where grouping (aggregation) occurs:
- **Client-Side Aggregation**: Samples are grouped (for example, into rates or percentiles) inside the application before being sent out.
- **Server-Side Aggregation**: Raw data is sent out, and all groupings are calculated on the observability server (the Prometheus model).

Finally, metrics can be sent in two ways:
- **Server Poll (Scraping)**: The observability system regularly pulls metrics from a `/metrics` HTTP endpoint on the application (Prometheus default). This requires service discovery.
- **Client Push**: The application actively pushes metrics to a central collector at set time periods.

### Manual vs. Automatic Instrumentation

- **Manual Instrumentation**: Developers write telemetry code directly. While it offers very detailed control, it links the code closely to telemetry APIs. It also risks creating **observability blind spots** if developer assumptions about what is important to trace are wrong.
- **Automatic Instrumentation**: Done using a Java agent (which uses bytecode weaving at load time) or framework-level extensions (like Quarkus's OpenTelemetry extension). It provides instant, complete coverage of standard HTTP, database, and library calls without changing application code.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//585999e1-626c-4446-8277-9e851e8cae04/markdown_0/imgs/img_in_image_box_176_413_252_513.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A10%3A57Z%2F-1%2F%2Fd0808512656ac76628d03c06ef4203f63c154346c42dcac2978267a5996775b6" alt="Image" width="7%" /></div>

> [!TIP]
> In practice, a mixed approach is best: use automatic instrumentation for standard framework and HTTP/gRPC tracing, and manual instrumentation using libraries like Micrometer for business-specific metrics.

---

## Observability Antipatterns

### Antipattern: Shoehorning Data into Metrics

Metrics show data grouped over a fixed time period. Trying to force high-cardinality event data that cannot be grouped into a metric is a bad practice (antipattern).

> As a statistic, averages (including the arithmetic mean) have many practical uses. Properly understanding a distribution is not one of them.
> — *Brendan Gregg*

Also, **never average percentiles**. Calculating percentiles requires the original dataset. Averaging pre-calculated percentiles distorts the data mathematically. This can easily hide severe latency outliers.

Finally, do not try to collect everything. You should only add a metric if you can answer the question: *“What operational issue will this metric help us debug?”*

### Antipattern: Abusing Correlated Logs to Avoid Tracing

Some teams try to avoid setting up a distributed tracing system by manually putting correlation IDs into application logs:

> “If we have an ID that flows through logs, we can follow requests.”

This home-made approach is very fragile and expensive:
- It assumes all logs are captured and indexed.
- It requires paying to collect, index, and store huge amounts of unstructured log text just to rebuild call times.
- It requires manually writing context propagation code for every downstream microservice integration.
- It risks leaking PII if you build correlation IDs carelessly.

Setting up a dedicated distributed tracing system is much more efficient and reliable.

---

## Diagnosing Distributed Application Problems

Distributed systems bring complex failure modes that are hard to understand without observability.

> It is much easier after the event to separate the useful signals from the useless ones. After the event, of course, a signal is always very clear. We can now see what disaster it was signaling because the disaster has already happened. But before the event, it is hidden and full of conflicting meanings.
> — *Roberta Wohlstetter*

### Performance Regressions

Code or configuration changes can worsen latency, CPU usage, or memory allocation rates. By comparing metrics and trace latencies before and after a deployment (or across canary versions), engineers can immediately spot drops in performance, as shown in the canary latency outlier graph in Figure 10-7.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//e1c1ce6a-436f-40fe-98fc-b313cfadf131/markdown_3/imgs/img_in_image_box_143_234_863_593.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A10%3A58Z%2F-1%2F%2F4596894b6f8efc6dbeb9e290783fa6357e5e7efd8cbf16550969539d5c8d3446" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 10-7. Seeing an outlier</div> </div>

Defining **Service Level Objectives (SLOs)** with their error budgets is an excellent SRE practice to automate this check.

### Unstable Components

A change might bring instabilities that only start on specific, rarely run code paths or under specific seasonal traffic profiles. Distributed traces let you separate these failures by filtering for error spans and finding patterns (such as a specific database query or third-party API call causing timeouts). Avoid **recency bias**—which is assuming the most recent deployment is the cause simply because it happened recently.

### Repartitioning and "Split-Brain"

A **split-brain** state occurs when a cluster has a network partition. This causes nodes to break into separate parts that each elect their own leader, as shown in Figure 10-8.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//6fafeed4-a3d1-4116-94fa-b38f4cc3a79b/markdown_0/imgs/img_in_image_box_145_108_865_490.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A15Z%2F-1%2F%2Fa37ec4921fe36fc10cb8aa1a40e21e8106da65d3c0ab6ff59b19ecdd44eccddc" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 10-8. Split-brain</div> </div>

To find this, make sure nodes show a metric that tells which leader is active, and send an alert if they report multiple leaders at the same time.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//6fafeed4-a3d1-4116-94fa-b38f4cc3a79b/markdown_0/imgs/img_in_image_box_176_769_253_869.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A16Z%2F-1%2F%2F40be7af805b220149497928b9d527d4fc8907d905cb1deb529ee2e4a3dc4d4af" alt="Image" width="7%" /></div>

> [!NOTE]
> Data reconciliation and partition recovery are well-studied fields. We will discuss basic distributed data structures in Chapter 14.

When you lose a node in a clustered data store (such as Kafka), a **repartitioning event** happens to rebalance data copies. During repartitioning, data processing may stop, creating a distributed "stop-the-world" latency event. Observability engineers must watch and alert on these states.

### Thundering Herd

A **thundering herd** happens when an event (such as a database restart or removing items from a cache) starts a huge number of requests at the same time from clients to a busy backend resource. This causes queues to fill up and leads to timeouts.

This usually shows up as a sudden spike in active database connections or cache misses that is not related to outside user traffic. Watching the rate of change of active connections helps find these events. Ways to fix this include applying **backpressure** using limited request queues.

### Cascading Failure

A **cascading failure** happens when a failure in a single component spreads to other subsystems. This happens through positive feedback and takes down the whole cluster, as shown in Figure 10-9.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//6fafeed4-a3d1-4116-94fa-b38f4cc3a79b/markdown_2/imgs/img_in_image_box_142_351_864_808.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A23Z%2F-1%2F%2Fab5f59583f5f5d62236019d09f05f2c7066cd6089ee15cdfb709731d1d41c333" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 10-9. Cascading failure</div> </div>

For example, if one replica of a service fails under heavy load, its traffic is sent to the other replicas. This overloads them and starts a domino effect.

Unlike physical power grids, software systems can recover from cascades without permanent hardware damage. This is true as long as the control plane and observability systems are physically separated from the overloaded data plane. This lets operators drop traffic (traffic shedding) and limit rates to let the system recover.

### Compound Failures

Outages often combine multiple failure modes. For example:
- Higher database latency downstream causes HTTP requests upstream to time out.
- This request backup starts a long JVM GC pause.
- The GC pause causes Kubernetes liveness probes to fail, so the container is restarted.
- The restart starts a Kafka repartitioning event, causing a cascading failure.

Distributed traces are very useful here to connect these different events in order of time across the stack. DevOps teams should hold blameless reviews (post-mortems) to regularly improve their alerts and observability practices.

---

## Vendor vs. Open Source Solutions

Choosing between open source (OSS) and commercial SaaS vendors is a basic design decision:

- **Open Source (OSS)**: Usually means combining separate top-quality projects for each pillar (such as Prometheus, Tempo, Loki/ELK) and managing them yourself. You can run them on your own cluster or use a dedicated telemetry pipeline, as shown in Figure 10-10. This avoids license fees but requires a lot of engineering work to maintain and connect the data.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//3031e6fa-bfd9-4fd2-8e35-15742ccf93ca/markdown_0/imgs/img_in_image_box_142_108_864_511.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A11Z%2F-1%2F%2F537a7be39b09966ffbe059e86f0d53a7404d4afe5490993ba40bab38654a1352" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 10-10. Example of an open source pipeline</div> </div>

- **Commercial SaaS**: Provides an ready-to-use, integrated experience with advanced features like anomaly detection, synthetic monitoring, and automatic event connection across the pillars. However, this brings large usage-based licensing fees and possible cloud network transfer costs (egress charges) if you send raw telemetry across region boundaries.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//6fafeed4-a3d1-4116-94fa-b38f4cc3a79b/markdown_4/imgs/img_in_image_box_168_657_253_770.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A29Z%2F-1%2F%2F0e934115db89a18972f1de79eaa7d8ac42b65b566a7722b38a9e0a0766da0652" alt="Image" width="8%" /></div>

> [!NOTE]
> OpenTelemetry is the industry standard for vendor-neutral application instrumentation. It lets you easily switch between different OSS and commercial backends without rewriting your code.

---

## Summary

Observability is becoming a very important practice for cloud native applications.

In this chapter, we introduced you to the basic concepts behind observability:
- We studied the **three pillars model** (Metrics, Logs, and Traces) and compared their storage and scaling behaviors.
- We looked at design patterns, including manual vs. automatic instrumentation and push vs. pull metrics.
- We highlighted critical bad practices (antipatterns) to avoid, such as averaging percentiles or abusing logs instead of tracing.
- We documented common distributed failure modes, including thundering herds, split-brain, cascading failures, and compound outages.
- We discussed the trade-offs between open source self-hosted stacks and commercial SaaS vendor solutions.

In the next chapter, we will build on these basics and explain in detail how to set up an observability solution for a live Java application using OpenTelemetry and Micrometer.
