# Chapter 33: Alerting, Visualization, & SLO Dashboards

Availability signals collected via metrics and distributed tracing are only useful if they are translated into actionable dashboards and reliable alert notifications. In microservice architectures, developers are easily overwhelmed by "alert fatigue" and cluttered dashboards, which obscure the actual health of the system.

To build a high-performance operations platform, we must adopt rigorous dashboard design principles and SRE alerting practices. We will examine the design differences in modern monitoring backends, maximize the "data-ink ratio" in dashboard panels, configure accessible and sorted stacked charts, implement alerts for each of the **Four Golden Signals** (Latency, Traffic, Errors, and Saturation) in PromQL, implement rolling counts to eliminate chatty alert thresholds, analyze single-exponential smoothing and naive forecasting mathematical algorithms, and apply Gunther's **Universal Scalability Law (USL)** to predict and chart microservice capacity limits.

---

## Learning Objectives

By the end of this chapter, you will be able to:

1. Compare pull-based rate calculations (Prometheus) with legacy push-based precomputed rates (Dropwizard/Graphite).
2. Maximize the data-ink ratio in Grafana dashboards by adjusting line width, step options, and shading.
3. Design accessible dashboard charts that distinguish errors and successes using shapes and line styles rather than just red/green colors.
4. Solve the "legend explosion" problem in "Top k" visualizations by using sorted tables.
5. Write PromQL alerts to monitor error rates and error ratios, and explain when to use each.
6. Customize Spring Boot RestTemplate and WebClient path variable substitutions to protect metric cardinality.
7. Alert on outbound http client response latency by client name and path.
8. Monitor JVM Garbage Collection overhead (pause times and proportion of time spent in collection).
9. Write PromQL queries to detect JVM memory leaks by analyzing old generation pool patterns.
10. Alert on OS-level saturation signals, including CPU utilization, memory pressure, and file descriptor limits.
11. Implement rolling count alerts to prevent transient spikes from triggering false alarms.
12. Build naive forecasting and single-exponential smoothing alerts using Prometheus subqueries.
13. Model microservice performance limitations (contention and crosstalk) using the Universal Scalability Law.

---

## 33.1 Architecture Differences: Pull vs. Push Query Capabilities

Before designing charts, we must understand the query architecture of our monitoring system. Modern metrics backends (such as Prometheus, Datadog, and Netflix Atlas) have distinct query engines that influence how we instrument application code:

- **Legacy Systems (e.g. Graphite / Dropwizard Metrics)**: Lack rate-calculating functions. The application library must compute rates (e.g., 1-minute, 5-minute, and 15-minute moving averages) and export them as distinct time series. This requires developers to choose between `@Counted` and `@Metered` annotations during instrumentation, leading to redundant metrics.
- **Modern Systems (e.g. Prometheus / Atlas)**: Perform rate calculations at query time on raw cumulative counters. The application registry only exports a single monotonic counter, and the server computes rates using PromQL or Atlas query logic.

There is an inverse relationship between the number of time series a metrics library must publish and the query capabilities of the target metrics backend:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//b3dffaef-0bd1-4335-acb0-61005d0df67a/markdown_2/imgs/img_in_image_box_143_107_864_371.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A35Z%2F-1%2F%2Fd1027e348847149a0bdcc743eb7c9138b7ec9fe8c67abafe2aa81df70b0cc544" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 4-2. Inverse relationship between published time series and backend query capabilities</div> </div>

As illustrated in Figure 4-2, highly capable query engines allow the metrics registry to ship raw cumulative metrics, significantly reducing application-side CPU overhead and memory footprint.

Micrometer handles these differences transparently. For example, a single Micrometer `Counter` is exported to Prometheus as a simple cumulative count, but to Graphite as multiple precomputed moving rates:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//b3dffaef-0bd1-4335-acb0-61005d0df67a/markdown_3/imgs/img_in_image_box_142_109_783_601.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A36Z%2F-1%2F%2F2a713d24d1d65e3b26f78e163359d1fd40cbb40a9b8dccce93e8ee47107a5e88" alt="Image" width="63%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 4-3. Metrics instrumentation capability overlap between libraries and engines</div> </div>

---

## 33.2 Dashboard Design: Maximizing the Data-Ink Ratio

Edward Tufte introduced the concept of the **Data-Ink Ratio**, which represents the proportion of a graphic's ink devoted to the non-redundant display of data-information. On an operations dashboard:

$$\text{Data-Ink Ratio} = \frac{\text{Ink representing telemetry data}}{\text{Total ink used to render the dashboard panel}}$$

To maximize this ratio in Grafana, we modify default panel styles:

1. **Line Width**: Increase the solid line width from 1px to 2px.
2. **Fill/Shading**: Remove the 10% transparent background fill under the lines. Background shading reduces readability when multiple lines overlap, causing visual noise.
3. **Interpolation**: Change the interpolation from smooth/linear diagonals to step curves. Diagonal lines imply that metrics changed continuously between scrape intervals, which is misleading. Step curves accurately reflect the discrete nature of scraped time-series data.

The differences between default and recommended styles are shown below:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//7cd55587-560f-44cd-947a-eafdcd17a914/markdown_2/imgs/img_in_chart_box_154_113_853_369.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A39Z%2F-1%2F%2F79f2c9262dc9f90b65f4d2b1b3bcce0a05399ba0743ff78261100e79955fb397" alt="Image" width="69%" /></div>

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//7cd55587-560f-44cd-947a-eafdcd17a914/markdown_2/imgs/img_in_chart_box_157_378_853_631.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A39Z%2F-1%2F%2F644f064500f1330c652c9d0bb6b6a70b1d33e148cf77a5169ce1394d29dba3d5" alt="Image" width="69%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 4-4. Default Grafana chart style (top) versus recommended data-ink optimized step style (bottom)</div> </div>

We configure these recommended settings in the Grafana panel editor:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//7cd55587-560f-44cd-947a-eafdcd17a914/markdown_2/imgs/img_in_image_box_142_764_865_1015.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A39Z%2F-1%2F%2F153dc8e0a0948ae202f996a4e1cedbb41c15f860ce9ebb262c8ba981d239da11" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 4-5. Grafana line options showing step interpolation configurations</div> </div>

---

## 33.3 Accessibility and Ordering in Stacked Charts

When plotting request outcomes, avoid relying solely on red/green colors. Approximately 8% of men and 0.5% of women have color vision deficiencies (like deuteranopia and protanopia), making red and green indistinguishable.

### 1. Visual Indicators for Errors

Rather than relying on color alone, distinguish errors from successes using line style overrides (such as displaying successes as solid lines and errors as thick points or dashed lines):

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//7cd55587-560f-44cd-947a-eafdcd17a914/markdown_3/imgs/img_in_chart_box_142_416_863_780.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A41Z%2F-1%2F%2Ff86a3ed0b2c182516f3827735721d23462fb0b0deda5f4e3aaeb1bc39e4051c4" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 4-6. Displaying errors with a dotted marker line style to ensure accessibility</div> </div>

As shown in Figure 4-6, styling errors as discrete points above a stacked line allows engineers to identify failures even on monochromatic displays or printed media.

### 2. Query Ordering in Grafana Stacks

Grafana lacks built-in options to specify the order of series in a stacked chart. To ensure that "success" always sits at the bottom of the stack with "error" on top, split the metrics into separate queries (Query A for successes, Query B for errors) and order the queries in the editor:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//7cd55587-560f-44cd-947a-eafdcd17a914/markdown_4/imgs/img_in_image_box_142_108_864_407.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A43Z%2F-1%2F%2F02a7a20facaa9a3fab4ff2cecd2795fa5cf9e5e9a52911da67fb817e312f4d80" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 4-7. Separating success and error counts into ordered Grafana queries</div> </div>

We then apply visual overrides to target each query individually:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//7cd55587-560f-44cd-947a-eafdcd17a914/markdown_4/imgs/img_in_image_box_142_508_860_808.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A43Z%2F-1%2F%2F119597f4d2e8d08bddd16afa94996f652d9f1ba993261be3c912a3786b0fde16" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 4-8. Overriding query-specific line styles inside the visualization tab</div> </div>

---

## 33.4 Solving "Legend Overload" in "Top k" Visualizations

We use "Top k" query functions (such as PromQL's `topk()`) to display the worst-performing resources. However, over a large time interval, the worst-performing resources can change repeatedly, adding new time series to the chart and cluttering the legend:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//91cbfc0e-c305-4bad-a6a0-3bb5e07ebe20/markdown_0/imgs/img_in_chart_box_142_110_865_377.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A33Z%2F-1%2F%2Fce8075d663ea1dcd91140dd2fa2db10b2a017e17e3e84c9f30904270350c89cc" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 4-9. Top k chart demonstrating legend overload over time</div> </div>

To solve this, configure the Grafana legend to display as a table on the right side of the panel, and enable a summary statistic (such as "maximum" or "last"). This allows engineers to sort the table dynamically and quickly identify the worst-performing instance:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//91cbfc0e-c305-4bad-a6a0-3bb5e07ebe20/markdown_1/imgs/img_in_image_box_143_110_859_387.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A34Z%2F-1%2F%2F8bd29afa30fd31c19ca89aa80f97192532ddcb680555e8d12daf583ddc51d676" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 4-11. Displaying the legend as a sorted table with max values</div> </div>

---

## 33.5 Golden Signal: Traffic and Throughput Monitoring

Traffic measures the demand placed on your system (such as HTTP requests/second or network I/O bytes/second).

### 1. PromQL Query for HTTP Server Traffic Rate

```promql
# Rate of HTTP requests per second averaged over 5 minutes
sum(rate(http_server_requests_seconds_count[5m])) by (uri, status)
```

> [!WARNING]
> Do not set alerts directly on raw cumulative counts. Cumulative counts increase over time and do not represent current system load.

Always calculate the rate over a lookback window, as shown in Figure 4-14:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//91cbfc0e-c305-4bad-a6a0-3bb5e07ebe20/markdown_4/imgs/img_in_chart_box_143_113_863_394.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A36Z%2F-1%2F%2F4ddc8803f1f954a169bd20c0c8690ed5003e73058d40abd067435a15e84d0355" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 4-14. Counter rates (line) vs. cumulative counts (dots) under load</div> </div>

### 2. Handling Periodic Traffic Spikes

Throughput fluctuates periodically based on peak and off-peak business hours:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//91cbfc0e-c305-4bad-a6a0-3bb5e07ebe20/markdown_4/imgs/img_in_chart_box_143_747_865_1010.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A36Z%2F-1%2F%2F462d7ed10509dc8bd39f14fc52931a2e7aece5aa2c8532e172db41f1877a327b" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 4-15. Periodic traffic fluctuations over a 24-hour business cycle</div> </div>

A static threshold alert (e.g. firing if traffic falls below 30 RPS) is ineffective. It may detect major outages during peak hours, but it will fail to detect significant partial drops during off-peak hours.

To solve this, use a dynamic threshold based on historical patterns, such as a **double-exponentially smoothed** baseline:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//0c752ea9-cb99-42c1-a620-39da94ff69e6/markdown_0/imgs/img_in_chart_box_147_247_861_735.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A34Z%2F-1%2F%2F4963f28b53998fe4d088c2497ea7e89d953a4562e03a7b5fa8334a4a1920bb7a" alt="Image" width="70%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 4-16. Dynamic alerts using a double-exponentially smoothed threshold</div> </div>

---

## 33.6 Golden Signal: Latency and Response Time Monitoring

Latency measures the time it takes to service a request.

### 1. Alerting on Max Latency

Gil Tene notes: _"Your heart will keep beating 99.9% of the time is not a reassuring statement for pacemaker performance."_

While p99 latency represents the experience of most users, you must also monitor **Maximum Latency** to detect edge-case blockages and system stalls.

Response latency is typically tightly packed around the 99th percentile, with a separate peak near the maximum representing GC pauses or VM stalls:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//0c752ea9-cb99-42c1-a620-39da94ff69e6/markdown_3/imgs/img_in_chart_box_142_742_864_1024.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A36Z%2F-1%2F%2F872ec207824a1d24449a0102de062b0f42c0e7356a2a8bbd5e773f927a989d81" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 4-19. Order-of-magnitude difference between P99 and maximum latency</div> </div>

Under high load, the average latency can float above the 99th percentile due to extreme outliers:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//0c752ea9-cb99-42c1-a620-39da94ff69e6/markdown_4/imgs/img_in_chart_box_146_115_862_391.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A37Z%2F-1%2F%2F7a6731f30b2b90f9e29c2f6888c91023c0055efba0b36f6fda4c097ec73ae5a6" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 4-20. Average vs. P99 latency demonstrating average skew from outliers</div> </div>

### 2. Visualizing Latency Distributions using Heatmaps

To visualize the full distribution of latencies, use a **Heatmap** dashboard panel instead of a simple line chart:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//0c752ea9-cb99-42c1-a620-39da94ff69e6/markdown_4/imgs/img_in_chart_box_143_855_865_1046.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A37Z%2F-1%2F%2F9aaab215ee4f401bdf498b49f5f2be5bb2a50bf8a1a5462e358723d9fcb3353e" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 4-21. Grafana timer latency distribution heatmap</div> </div>

As shown in Figure 4-21, each column represents a latency histogram at a specific point in time, with hotter colors representing higher request frequencies.

### 3. Monitoring Inbound vs. Outbound Client Latency

Spring Boot autoconfigures two core timer metrics:

- `http.server.requests`: Inbound server latency.
- `http.client.requests`: Outbound client latency (measured by RestTemplate or WebClient).

Outbound client metrics help you monitor external dependency latency across instances:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//4920bd8e-06b1-4843-8d69-7a686b0fe3c3/markdown_0/imgs/img_in_image_box_142_746_864_1060.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A33Z%2F-1%2F%2F9fcdac20d650834a07329ce0bdf025435c1322daaf25554450aa057eeab9d5ee" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 4-24. Multi-caller client-side outbound request tracing path</div> </div>

---

## 33.7 Golden Signal: Error Rate and Error Ratio Monitoring

Errors measure the rate of failed requests.

### 1. Error Rate vs. Error Ratio

- **Error Rate**: The raw number of failed requests per second.
- **Error Ratio**: The percentage of failed requests relative to total traffic.

$$\text{Error Ratio} = \frac{\sum \text{rate}(\text{http\_server\_requests\_seconds\_count}\{\text{status}\sim\text{"5.."}\}[5m])}{\sum \text{rate}(\text{http\_server\_requests\_seconds\_count}[5m])}$$

If you have a high-throughput service, minor errors can trigger alerts on raw error rates, while the error ratio remains normal. Conversely, low-throughput services require error rate alerts, as a single error can trigger an alert on error ratios.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//4d4c241d-a192-4569-bd60-23dcb5a8a572/markdown_1/imgs/img_in_chart_box_142_107_864_455.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A38Z%2F-1%2F%2F7d8cb6ca04155a863c3309ae7bc61004852d0deeedaa0d0a9c603b46201621b7" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 4-23. Error ratio vs. error rate under fluctuating traffic</div> </div>

As shown in Figure 4-23, the error ratio normalizes the rate of errors, preventing false alarms during traffic spikes.

---

## 33.8 Golden Signal: Saturation and Resource Monitoring

Saturation measures system constraints and resource utilization (such as memory capacity, CPU limits, or thread pool exhaustion).

### 1. JVM Garbage Collection Overhead

Alert on the proportion of time the JVM spends in stop-the-world garbage collection pauses:

```promql
# Percentage of time spent in GC pauses over a 5-minute window
sum(rate(jvm_gc_pause_seconds_sum[5m])) * 100
```

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//946b1009-b1a9-47e4-9717-da0b7b529340/markdown_2/imgs/img_in_chart_box_146_109_853_745.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A34Z%2F-1%2F%2F6bbffc8532b01b2f5d726af7910638fadbac8252728745fd99443e7377f34c5e" alt="Image" width="70%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 4-26. Proportion of JVM execution time spent in GC pause events</div> </div>

### 2. JVM Heap Utilization and Memory Leaks

A static threshold alert (e.g. firing if heap usage exceeds 80%) is ineffective. Garbage collection routinely brings memory usage back down, resulting in false alarms:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//80ec209d-4ad6-4f1d-b2b6-313b1f12ba98/markdown_0/imgs/img_in_image_box_148_179_854_819.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A34Z%2F-1%2F%2Fe42362dab2e492a38618baa0604bd1aea066d0f44d261440852d433beddd1bd9" alt="Image" width="70%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 4-27. Memory utilization alerts using a static threshold</div> </div>

To monitor heap pressure accurately, alert on **memory pool usage after garbage collection** (specifically the JVM Old Generation space). If memory usage continues to rise after major collection events, it indicates a memory leak:

```promql
# Prometheus query analyzing heap usage trends after GC collections
predict_linear(jvm_memory_used_bytes{area="heap",id=~".*Old Gen.*"}[1h], 86400) > jvm_memory_max_bytes{area="heap",id=~".*Old Gen.*"}
```

---

## 33.9 Limiting Alert Fatigue: Rolling Counts and Aggregations

To prevent transient spikes from triggering false alarms, configure alerts to evaluate data over multiple intervals:

- **Atlas Rolling Count**: Alert only when a threshold is exceeded $n$ times within a window of $m$ intervals (e.g. 3 out of the last 5 intervals):

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//80ec209d-4ad6-4f1d-b2b6-313b1f12ba98/markdown_1/imgs/img_in_image_box_147_110_847_748.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A35Z%2F-1%2F%2F98fbc315977014852f45781aa89633774f8b2b6430ec38757878d16d61f9dc23" alt="Image" width="69%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 4-28. Using rolling counts to limit memory alert chattiness</div> </div>

- **PromQL `max_over_time`**: Analyzes the maximum value of a metric over a moving lookback window:

```promql
# Evaluate max Eden memory usage over a 1-minute lookback window
max_over_time(jvm_memory_used_bytes{id="G1 Eden Space"}[1m])
```

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//80ec209d-4ad6-4f1d-b2b6-313b1f12ba98/markdown_3/imgs/img_in_image_box_143_108_864_391.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A36Z%2F-1%2F%2Ffe0c3bd75d0ad5d6ba0aa8e212427d2b1f0732ed3660d01f2fe963ea2ed0b30a" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 4-29. Using Prometheus max_over_time to track Eden space usage</div> </div>

---

## 33.10 Alerting on OS-Level Saturation Signals

In addition to JVM metrics, monitor host resource saturation to prevent performance degradation:

### 1. Process CPU Utilization

Alert when the process CPU usage approaches host limits:

```promql
# Alert when process CPU utilization exceeds 85% of host capacity
process_cpu_seconds_total /  on(instance) machine_cpu_cores > 0.85
```

Ensure the y-axis is formatted as a percentage (range 0.0 to 1.0):

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//ffdfad0c-8291-4776-a702-8fd4f3da6ea9/markdown_0/imgs/img_in_chart_box_143_630_863_911.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A34Z%2F-1%2F%2F5080ce5296f68343a9ac76cdae1210ab7063f7312f3bd5780ead92498d470800" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 4-31. Charting process CPU usage as a percentage</div> </div>

Ensure you select `percent (0.0-1.0)` in the Grafana panel options:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//ffdfad0c-8291-4776-a702-8fd4f3da6ea9/markdown_1/imgs/img_in_image_box_142_106_865_439.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A35Z%2F-1%2F%2Ff3550d80fd11b2861061341cd1a7fc91f4a9003def26d5766f90cc911ffc0b40" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 4-32. Selecting the percent unit inside Grafana's panel options</div> </div>

### 2. File Descriptors Exhaustion

Microservices consume file descriptors for socket connections and file I/O. If a service exhausts its file descriptor limit, it cannot open new network connections or accept HTTP requests.

```promql
# Alert when process file descriptor usage exceeds 85% of its limit
process_open_fds / process_max_fds > 0.85
```

---

## 33.11 Mathematical Forecasting: Naive & Exponential Smoothing

To detect anomalies before they cause outages, use mathematical forecasting models.

### 1. Naive Forecasting

The naive method predicts future values by looking back at a prior interval (e.g. comparing current traffic to traffic from 7 days ago):

```promql
# Alert when traffic falls below 50% of the value from 7 days ago
sum(rate(http_server_requests_seconds_count[5m])) < 0.50 * sum(rate(http_server_requests_seconds_count[5m] offset 7d))
```

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//46d08d24-2e02-404d-b58f-de70222ac5f3/markdown_2/imgs/img_in_chart_box_144_574_862_893.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A35Z%2F-1%2F%2F6bbe85386d687d5fb79403cffa6f9980282f3c40aa686a8a461f82c9f187bd45" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 4-34. Forecasting with the naive offset method</div> </div>

### 2. Single-Exponential Smoothing

Single-exponential smoothing applies a weighted moving average to historical data, giving more weight to recent observations:

$$S_t = \alpha Y_t + (1 - \alpha) S_{t-1}$$

Where:

- $S_t$ is the smoothed forecast value at time $t$.
- $Y_t$ is the actual metric value at time $t$.
- $\alpha$ is the smoothing factor ($0 < \alpha < 1$).

We construct this smoothing series in Prometheus using nested subqueries:

```promql
# Single-exponential smoothing approximation in PromQL
sum(rate(http_server_requests_seconds_count[5m]))
  - (0.3 * sum(rate(http_server_requests_seconds_count[5m] offset 10m)))
  - (0.21 * sum(rate(http_server_requests_seconds_count[5m] offset 20m)))
```

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//46d08d24-2e02-404d-b58f-de70222ac5f3/markdown_4/imgs/img_in_chart_box_147_511_862_894.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A36Z%2F-1%2F%2Ff01b2e67a99a23ccbf96613a49cd19649617e59ae7e5374672193c5768116ad9" alt="Image" width="70%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 4-35. Scaling effect of choosing different terms in the smoothing series</div> </div>

We evaluate how varying $\alpha$ and term count ($T$) affects the smoothed threshold:

<div style="text-align: center;">
  <img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//1d453a77-5b91-4f28-8df8-f4e7e9c882cb/markdown_0/imgs/img_in_chart_box_146_113_508_314.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A34Z%2F-1%2F%2F0a49a85ed44380b4e68d6c87170cc46bfc83b26c3da2fff8ddaeed09c713d97c" alt="Sub-image 1" width="45%" />
  <img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//1d453a77-5b91-4f28-8df8-f4e7e9c882cb/markdown_0/imgs/img_in_chart_box_513_113_863_311.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A35Z%2F-1%2F%2Ff74f9480d293021525c59dc45e7fc70ff8bfd90a6345a9dc437625d2469bc23d" alt="Sub-image 2" width="45%" />
</div>
<div style="text-align: center;">
  <img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//1d453a77-5b91-4f28-8df8-f4e7e9c882cb/markdown_0/imgs/img_in_chart_box_150_324_505_521.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A35Z%2F-1%2F%2F7a515aa8f069da7eea3ce2730d0bd021f385929ad6fa8593b46193cc158f3dc0" alt="Sub-image 3" width="45%" />
  <img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//1d453a77-5b91-4f28-8df8-f4e7e9c882cb/markdown_0/imgs/img_in_chart_box_513_324_861_522.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A35Z%2F-1%2F%2F2c816a0416889e1eacecab3e94f0574ba779ca59f19c691a27b14b3214ff83ec" alt="Sub-image 4" width="45%" />
</div>

<div style="text-align: center;"><div style="text-align: center;">Figure 4-36. Effect of varying smoothing factor alpha and term count on threshold calculations</div> </div>

---

## 33.12 Gunther's Universal Scalability Law (USL)

To predict how a service will scale under load, use Gunther's **Universal Scalability Law (USL)**.

The USL models system throughput ($X(N)$) as a function of concurrency ($N$):

$$X(N) = \frac{\lambda N}{1 + \sigma(N-1) + \kappa N(N-1)}$$

Where:

- **$\lambda$ (Lambda)**: Unloaded performance (throughput of a single thread).
- **$\sigma$ (Sigma)**: Contention coefficient (concurrency limits from shared serialization queues or locks).
- **$\kappa$ (Kappa)**: Crosstalk coefficient (performance overhead from inter-node communication and data consistency checks).

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//1d453a77-5b91-4f28-8df8-f4e7e9c882cb/markdown_2/imgs/img_in_chart_box_143_428_863_881.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A36Z%2F-1%2F%2F883e53a0bd1d44fffd1541f3ddc71ff9792bf53a5ae752b57badb5ba3ee9093c" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 4-37. USL model showing predicted throughput limits under load</div> </div>

As shown in Figure 4-37, the USL models the point of diminishing returns. After this peak, adding more nodes or threads degrades performance due to crosstalk overhead.

To collect USL parameters, register custom Micrometer metrics that track execution times under varying loads:

```java
package com.ftgo.order.metrics;

import io.micrometer.core.instrument.Gauge;
import io.micrometer.core.instrument.MeterRegistry;
import org.springframework.stereotype.Component;

import java.util.concurrent.atomic.AtomicReference;

@Component
public class UslForecastingMetrics {

    private final AtomicReference<Double> contention = new AtomicReference<>(0.0);
    private final AtomicReference<Double> crosstalk = new AtomicReference<>(0.0);
    private final AtomicReference<Double> lambda = new AtomicReference<>(0.0);

    public UslForecastingMetrics(MeterRegistry registry) {
        // Register USL parameters as gauges
        Gauge.builder("timer.name.contention", contention, AtomicReference::get)
                .description("USL contention parameter (sigma)")
                .register(registry);

        Gauge.builder("timer.name.crosstalk", crosstalk, AtomicReference::get)
                .description("USL crosstalk parameter (kappa)")
                .register(registry);

        Gauge.builder("timer.name.unloaded.performance", lambda, AtomicReference::get)
                .description("USL single-threaded throughput (lambda)")
                .register(registry);
    }

    public void updateUslParameters(double sigma, double kappa, double lam) {
        this.contention.set(sigma);
        this.crosstalk.set(kappa);
        this.lambda.set(lam);
    }
}
```

---

## 33.13 Custom WebMvcTagsProvider for Path Substitutions

When building REST controllers, endpoints often include path variables (e.g. `/api/orders/{orderId}`). If not handled correctly, the metrics registry will generate a new tag value for every unique path variable, leading to tag cardinality explosion.

Below is a custom Spring WebMvc configurations bean to normalize path variables and clean user agent tags:

```java
package com.ftgo.order.config;

import io.micrometer.core.instrument.Tag;
import io.micrometer.core.instrument.Tags;
import org.springframework.boot.actuate.metrics.web.servlet.DefaultWebMvcTagsProvider;
import org.springframework.boot.actuate.metrics.web.servlet.WebMvcTagsProvider;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;

@Configuration
public class NormalizedMetricsConfig {

    @Bean
    public WebMvcTagsProvider webMvcTagsProvider() {
        return new DefaultWebMvcTagsProvider() {
            @Override
            public Iterable<Tag> getTags(HttpServletRequest request, HttpServletResponse response,
                                         Object handler, Throwable exception) {
                // 1. Get default tags (URI, Method, Status)
                Iterable<Tag> defaultTags = super.getTags(request, response, handler, exception);

                // 2. Extract and parse the User-Agent header
                String userAgent = request.getHeader("User-Agent");
                String clientType = parseUserAgent(userAgent);

                // 3. Append clean tags to default set
                return Tags.concat(defaultTags, "client.type", clientType);
            }
        };
    }

    private String parseUserAgent(String userAgent) {
        if (userAgent == null) {
            return "unknown";
        }
        if (userAgent.contains("Mozilla")) {
            return "browser";
        }
        if (userAgent.contains("Postman") || userAgent.contains("curl")) {
            return "api-client";
        }
        return "internal-service";
    }
}
```

---

---

## 33.14 Reliability Math: SLOs, Error Budgets, and Burn Rates

A Service Level Objective (SLO) defines the target reliability level for a service. To monitor SLOs effectively, SREs track the **Error Budget**, which is the total allowable unreliability over a specific window (e.g. 30 days).

$$\text{Error Budget} = 100\% - \text{SLO Target}$$

For example, a **99.9% availability SLO** allows for a **0.1% error budget**.

### 1. Burn Rate Calculation

The **Burn Rate** represents the speed at which a service consumes its error budget. A burn rate of 1 means the service will exhaust its entire budget exactly by the end of the window.

$$\text{Time to Exhaustion} = \frac{\text{SLO Window}}{\text{Burn Rate}}$$

To avoid late notifications, SREs write alerts on elevated burn rates using multiple lookback windows:

```promql
# Alert on a 14.4x burn rate (consuming 2% of budget in 1 hour)
sum(rate(http_server_requests_seconds_count{status=~"5.."}[1h])) / sum(rate(http_server_requests_seconds_count[1h])) > 14.4 * (1 - 0.999)
```

```promql
# Alert on a 6x burn rate (consuming 5% of budget in 6 hours)
sum(rate(http_server_requests_seconds_count{status=~"5.."}[6h])) / sum(rate(http_server_requests_seconds_count[6h])) > 6.0 * (1 - 0.999)
```

---

## 33.15 Dispatching Notifications: Prometheus Alertmanager Configuration

Prometheus evaluates alert rules and routes them to **Alertmanager**, which groups, deduplicates, and dispatches them to incident response systems (like Slack or PagerDuty).

Below is a complete `alertmanager.yml` routing configuration:

```yaml
global:
    resolve_timeout: 5m

route:
    group_by: ["alertname", "cluster", "service"]
    group_wait: 30s
    group_interval: 5m
    repeat_interval: 12h
    receiver: "default-slack"
    routes:
        - match:
              severity: critical
          receiver: "pagerduty-critical"

inhibit_rules:
    # If a host goes down, suppress alerts for applications running on that host
    - source_match:
          alertname: "NodeDown"
      target_match_eq:
          - "instance"

receivers:
    - name: "default-slack"
      slack_configs:
          - api_url:
            channel: "#telemetry-alerts"
            send_resolved: true
            title: "[[{{ .Status | toUpper }}]] {{ .CommonLabels.alertname }}"
            text: >-
                {{ range .Alerts -}}
                *Alert:* {{ .Annotations.summary }}
                *Description:* {{ .Annotations.description }}
                *Severity:* {{ .Labels.severity }}
                {{- end }}

    - name: "pagerduty-critical"
      pagerduty_configs:
          - routing_key: "pd-production-service-key"
            send_resolved: true
```

---

## 33.16 Grafana Dashboard Panel JSON Schema Template

Grafana dashboards are declared as JSON files. Below is a snippet of a dashboard panel JSON config that applies our recommended styling rules (2px line width, step interpolation, and table legend):

```json
{
    "id": 1,
    "title": "Normalized HTTP Requests Throughput",
    "type": "timeseries",
    "datasource": "Prometheus",
    "targets": [
        {
            "expr": "sum(rate(http_server_requests_seconds_count[5m])) by (uri)",
            "legendFormat": "{{uri}}",
            "refId": "A"
        }
    ],
    "fieldConfig": {
        "defaults": {
            "custom": {
                "drawStyle": "line",
                "lineInterpolation": "stepAfter",
                "lineWidth": 2,
                "fillOpacity": 0
            },
            "unit": "reqps"
        }
    },
    "options": {
        "legend": {
            "calcs": ["max", "last"],
            "displayMode": "table",
            "placement": "right"
        }
    }
}
```

---

## 33.17 Monitoring Edge Routers: Spring Cloud Gateway Metric Filters

To monitor edge saturation, we record requests processing latency at the API Gateway using a global filter:

```java
package com.ftgo.gateway.metrics;

import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Timer;
import org.springframework.cloud.gateway.filter.GatewayFilterChain;
import org.springframework.cloud.gateway.filter.GlobalFilter;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ServerWebExchange;
import reactor.core.publisher.Mono;

import java.util.concurrent.TimeUnit;

@Component
public class GatewayLatencyMetricsFilter implements GlobalFilter {

    private final MeterRegistry registry;

    public GatewayLatencyMetricsFilter(MeterRegistry registry) {
        this.registry = registry;
    }

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, GatewayFilterChain chain) {
        long startTime = System.nanoTime();

        return chain.filter(exchange).doFinally(signalType -> {
            long duration = System.nanoTime() - startTime;
            String routeId = exchange.getAttribute("org.springframework.cloud.gateway.support.ServerWebExchangeUtils.gatewayRouteIdAttr");

            // Record gateway routing duration categorized by target route
            Timer.builder("gateway.route.duration")
                    .description("API Gateway request processing duration")
                    .tag("route.id", routeId != null ? routeId : "unknown")
                    .register(registry)
                    .record(duration, TimeUnit.NANOSECONDS);
        });
    }
}
```

---

---

## 33.18 Understanding Prometheus Rate Selection Mechanics

When charting counter throughput, the PromQL `rate()` function requires a lookback interval (e.g. `rate(http_server_requests_seconds_count[5m])`).

### 1. Extrapolation and Scrape Intervals

Prometheus scrapes metrics at discrete intervals (e.g., every 30 seconds). To calculate a rate, it needs at least two successful scrapings within the lookback window. If the lookback window is too short (e.g., `[1m]` with a 30s scrape interval), the rate function is susceptible to:

- **Counter Reset Gaps**: If a JVM application restarts, Prometheus detects the counter reset but cannot calculate a rate across the reset boundary without at least two new data points.
- **Jagged Spikes**: Variations in scrapings timing (jitter) cause the rate calculation to fluctuate, creating a jagged chart.

As a general rule, set the rate lookback interval to at least **4 times the scrape interval** (e.g., for a 30s scrape interval, use a lookback window of at least `[2m]`). A longer window (such as `[5m]` or `[10m]`) acts as a moving average, smoothing out transient spikes and revealing long-term throughput trends.

---

## 33.19 Resiliency Visualizations: Resilience4j Circuit Breaker Dashboards

To monitor outbound dependency resilience, you must track **Resilience4j Circuit Breaker** metrics.

Below is the Java registry customizer that registers circuit breaker states and call outcomes with Micrometer:

```java
package com.ftgo.order.metrics;

import io.github.resilience4j.circuitbreaker.CircuitBreaker;
import io.github.resilience4j.circuitbreaker.CircuitBreakerRegistry;
import io.micrometer.core.instrument.Gauge;
import io.micrometer.core.instrument.MeterRegistry;
import org.springframework.context.annotation.Configuration;

import javax.annotation.PostConstruct;

@Configuration
public class CircuitBreakerMetricsConfig {

    private final CircuitBreakerRegistry cbRegistry;
    private final MeterRegistry meterRegistry;

    public CircuitBreakerMetricsConfig(CircuitBreakerRegistry cbRegistry, MeterRegistry meterRegistry) {
        this.cbRegistry = cbRegistry;
        this.meterRegistry = meterRegistry;
    }

    @PostConstruct
    public void bindCircuitBreakerMetrics() {
        cbRegistry.getAllCircuitBreakers().forEach(cb -> {
            String name = cb.getName();

            // Expose circuit breaker state as an integer gauge:
            // Closed = 0, Half-Open = 1, Open = 2
            Gauge.builder("resilience4j.circuitbreaker.state", cb, this::getNumericalState)
                    .tag("name", name)
                    .description("Numerical state of the circuit breaker")
                    .register(meterRegistry);
        });
    }

    private double getNumericalState(CircuitBreaker cb) {
        switch (cb.getState()) {
            case CLOSED: return 0.0;
            case HALF_OPEN: return 1.0;
            case OPEN: return 2.0;
            case FORCED_OPEN: return 3.0;
            case DISABLED: return 4.0;
            default: return -1.0;
        }
    }
}
```

On your Grafana dashboard, plot this state gauge as a stepped line chart alongside the error rate. This allows engineers to correlate outbound dependency failures with circuit breaker state transitions.

---

## 33.20 SRE Practices: When to Stop Creating Dashboards

Dashboards are a powerful diagnostic tool, but creating too many panels leads to cognitive overload.

To keep your dashboards clean and maintainable:

- **Service Dashboard Templates**: Build a single template dashboard for all microservices in the cluster. This dashboard should display only the Four Golden Signals (Latency, Traffic, Errors, and Saturation) alongside JVM memory metrics.
- **Ad-hoc Debugging Dashboards**: Do not save ad-hoc dashboards created during an active incident. Save the relevant query details in your post-mortem logs instead.
- **Delete Unused Panels**: Review dashboard usage metrics regularly and delete panels that have not been viewed in the last 30 days. If an engineer cannot explain what action to take when a panel's metric changes, delete it.

---

## 33.20 SRE Case Study: The File Descriptor Exhaustion Problem

During the writing of this guide, we experienced a real-world file descriptor leak while running stress tests on an orchestration microservice. The service became unresponsive, refusing to accept new HTTP connections.

### 1. Diagnosing with Unix Shell Commands

To diagnose this problem on the host machine, we checked current limits using `ulimit`:

```bash
# Display all current resource limits for the current shell
ulimit -a

# Output:
# core file size          (blocks, -c) 0
# data seg size           (kbytes, -d) unlimited
# scheduling priority             (-e) 0
# file size               (blocks, -f) unlimited
# pending signals                 (-i) 62799
# max locked memory       (kbytes, -l) 64
# max memory size         (kbytes, -m) unlimited
# open files                      (-n) 1024        <-- Soft limit (Too low!)
# pipe size            (512 bytes, -p) 8
# POSIX message queues     (bytes, -q) 819200
# real-time priority              (-r) 0
# stack size              (kbytes, -s) 8192
# cpu time               (seconds, -t) unlimited
# max user processes              (-u) 62799
# virtual memory          (kbytes, -v) unlimited
# file locks                      (-x) unlimited
```

The system soft limit on open files was set to `1024`. Because our microservice was handling hundreds of concurrent Keep-Alive HTTP client sessions and connection pool sockets, it quickly hit the limit, triggering the classic Java error: `java.io.IOException: Too many open files`.

### 2. Remediating Host Limits

To resolve file descriptor leaks, we modified the security limits inside `/etc/security/limits.conf`:

```
# Increase file descriptor limits for all users running services
*               soft    nofile          65535
*               hard    nofile          65535
```

For systemd-managed services, we configured limits inside the service definition file (`/etc/systemd/system/order-service.service`):

```ini
[Service]
LimitNOFILE=65535
```

---

## 33.21 Summary of Alerting, Visualization, & SLO Dashboard Configurations

This table summarizes the configurations, rules, and parameters used to build alerting and visualization systems:

| Telemetry Element     | PromQL / Metric Term     | Main Implementation Target                      | Scope Location      |
| :-------------------- | :----------------------- | :---------------------------------------------- | :------------------ |
| **Data-Ink Ratio**    | Step Interpolation       | Grafana chart styling options.                  | Dashboard           |
| **Top k Table**       | Legend Table sorting     | Displays Worst performers cleanly.              | Dashboard           |
| **Throughput Alert**  | `rate(counter[5m])`      | Monitors request volume trends.                 | Prometheus Rule     |
| **Outlier Latency**   | `timer_max_seconds`      | Tracks worst-case response times.               | Prometheus Rule     |
| **GC Overhead Alert** | `rate(jvm_gc_pause_sum)` | Monitors JVM pause time percentage.             | Prometheus Rule     |
| **Memory Leak Alert** | `predict_linear()`       | Predicts JVM Old Gen exhaustion trends.         | Prometheus Rule     |
| **File Descriptor**   | `process_open_fds`       | Monitors open socket saturation.                | Prometheus Rule     |
| **Rolling Count**     | Lookback interval        | Limits alert chattiness for transient spikes.   | Alert Configuration |
| **Offset Forecast**   | `offset 7d`              | Compares current traffic to prior periods.      | Prometheus Rule     |
| **Smoothing Alert**   | Double-exponential       | Dynamic threshold adjusting for business hours. | Prometheus Rule     |
| **USL Contention**    | `timer.name.contention`  | Tracks contention limits (sigma).               | Micrometer Gauge    |
| **USL Crosstalk**     | `timer.name.crosstalk`   | Tracks crosstalk limits (kappa).                | Micrometer Gauge    |

---

## Chapter Summary

- Legacy monitoring systems required precomputed metrics, whereas modern systems (Prometheus, Atlas) calculate rates and percentiles on the server side using raw cumulative counters.
- To maximize readability on dashboards, increase line width, remove background shading, and use step curves instead of diagonal interpolation.
- Stacked charts should remain readable without relying on color. Style errors using distinct markers, and split metrics into separate queries to control stacking order.
- Use sorted tables to display "Top k" lists, preventing the legend from growing illegibly as the worst-performing resources change.
- Inbound server metrics (`http.server.requests`) do not account for socket connection delays. Outbound client metrics (`http.client.requests`) should be monitored to track external dependency latency.
- Monitor JVM Garbage Collection overhead by measuring the proportion of execution time spent in GC pauses.
- Alert on memory pool usage after garbage collection (rather than total memory usage) to detect JVM memory leaks.
- Use Prometheus `predict_linear` functions to predict resource exhaustion (like memory limits or file descriptor limits) before it causes outages.
- Configure rolling counts to evaluate alerts over multiple intervals, preventing transient spikes from triggering false alarms.
- Use Gunther's Universal Scalability Law (USL) to model system throughput, accounting for contention and crosstalk bottlenecks.
- Track SLO error budget burn rates (e.g., 14.4x for 1-hour and 6x for 6-hour windows) to detect outages early.
- Group and route alerts using Prometheus Alertmanager configuration files to minimize alert fatigue.
- Export Resilience4j circuit breaker state changes as numerical gauges to correlate outbound dependency failures.
- Check soft and hard file descriptor limits using ulimit -a to resolve socket exhaustion issues under heavy stress.
- Wrap REST requests provider configuration classes to normalize path variables, protecting metrics registries from cardinality explosion.

---

## 33.16 Production-Grade FTGO Order Reviews Grafana SLO Dashboard Schema

To visualize microservice reliability against target objectives, platform engineering teams deploy declarative **Grafana Service Level Objective (SLO)** dashboards. Below is the complete JSON schema mapping a Grafana time-series panel that displays the **99% Review Fetch Latency SLO** and the **99.9% Review Submission Success SLO** for the **review-service**.

```
+---------------------------------------------------------------------------------+
|                         GRAFANA DASHBOARD STRUCTURE                             |
+---------------------------------------------------------------------------------+
|                                                                                 |
|   [ Time-Series SLO Panel ]                                                     |
|     - Target A: histogram_quantile(0.99, rate(fetch_latency_bucket[5m]))        |
|     - Target B: Static Threshold (0.5s SLO Limit line)                          |
|     - Gauge Panel: Rolling Error Budget Remaining                               |
|                                                                                 |
+---------------------------------------------------------------------------------+
```

This dashboard panel defines:

1. **Query targets** extracting rate metric histograms from Prometheus.
2. **Visual thresholds** indicating SLO warning (orange) and breach (red) zones.
3. **Axis mapping** formatting latency scales dynamically to milliseconds.

---

### The Grafana Panel JSON Schema: `review-service-slo-panel.json`

```json
{
    "id": 101,
    "gridPos": {
        "h": 8,
        "w": 12,
        "x": 0,
        "y": 0
    },
    "type": "timeseries",
    "title": "FTGO Review Service: p99 Latency vs. SLO",
    "datasource": {
        "type": "prometheus",
        "uid": "prometheus-prod-cluster"
    },
    "targets": [
        {
            "datasource": {
                "type": "prometheus",
                "uid": "prometheus-prod-cluster"
            },
            "editorMode": "code",
            "expr": "histogram_quantile(0.99, sum(rate(ftgo_order_reviews_fetch_latency_seconds_bucket{service=\"review-service\"}[5m])) by (le))",
            "legendFormat": "p99 Execution Latency (seconds)",
            "range": true,
            "refId": "A"
        },
        {
            "datasource": {
                "type": "prometheus",
                "uid": "prometheus-prod-cluster"
            },
            "editorMode": "code",
            "expr": "0.5",
            "legendFormat": "SLO Limit (500ms)",
            "range": true,
            "refId": "B"
        }
    ],
    "fieldConfig": {
        "defaults": {
            "custom": {
                "drawStyle": "line",
                "lineInterpolation": "smooth",
                "lineWidth": 2,
                "fillOpacity": 10,
                "gradientMode": "opacity",
                "spanNulls": false,
                "showPoints": "never"
            },
            "unit": "s",
            "min": 0,
            "decimals": 3,
            "thresholds": {
                "mode": "absolute",
                "steps": [
                    {
                        "color": "green",
                        "value": null
                    },
                    {
                        "color": "orange",
                        "value": 0.4
                    },
                    {
                        "color": "red",
                        "value": 0.5
                    }
                ]
            }
        }
    },
    "options": {
        "tooltip": {
            "mode": "single",
            "sort": "none"
        },
        "legend": {
            "showLegend": true,
            "displayMode": "table",
            "placement": "bottom",
            "calcs": ["mean", "lastNotNull", "max"]
        }
    }
}
```
