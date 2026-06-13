# Course 9: Windowing, Timestamps, and Stream Time

Welcome to **Course 9: Windowing, Timestamps, and Stream Time**. This course covers how Kafka Streams handles time-based processing, including the different types of windows, managing out-of-order events using grace periods and suppression, extracting timestamps, and how "Stream Time" advances internally.

## Syllabus & Modules

1. **[Module 01: Window Types & Time Alignment](file:///c:/Users/Admin/Desktop/projects/learning-repo/kafka-stream-inaction/courses/09-windowing-timestamps/01-window-types.md)**
   * Learn the mechanics and configurations of Tumbling, Hopping, Session, and Sliding windows.
   * Understand window alignment, windowed keys (`Windowed<K>`), and custom Serdes for windowed records.
   * Examine querying and retrieving windowed aggregation results.
2. **[Module 02: Out-of-Order Data, Grace Periods & Suppression](file:///c:/Users/Admin/Desktop/projects/learning-repo/kafka-stream-inaction/courses/09-windowing-timestamps/02-out-of-order-grace-periods.md)**
   * Dive into the challenges of late-arriving events and network partitions.
   * Configure grace periods with `ofSizeAndGrace()` and suppress intermediate updates using the `suppress()` API.
   * Explore Eager vs. Strict buffering and emission strategies.
3. **[Module 03: Timestamps & Stream Time Advancement](file:///c:/Users/Admin/Desktop/projects/learning-repo/kafka-stream-inaction/courses/09-windowing-timestamps/03-timestamps-stream-time.md)**
   * Understand the difference between Event Time, Ingestion Time, and Processing Time.
   * Write and configure custom `TimestampExtractor` implementations.
   * Analyze the internal algorithm governing how Stream Time advances across partitions and tasks.

## Course Prerequisites
* Completed **Course 6: Developing Streams** and **Course 7: Stateful Stream Processing**.
* Strong understanding of stream-table duality and partition repartitioning.
