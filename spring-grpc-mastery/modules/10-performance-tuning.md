# Module 10: Performance Engineering & JVM GC Tuning

## 1. What Problem This Module Solves
In high-throughput microservices, performance issues are usually caused by resource contention, memory management overhead, and networking configuration issues:
*   **GC Stop-the-World Pauses**: Heavy object allocation during serialization (like mapping JSON structures) fills the JVM Young Generation, triggering garbage collection runs that stall active threads.
*   **Memory Buffering Copies**: Copying bytes from the OS socket buffer to Java heap arrays, and then mapping them to application models, consumes CPU cycles and memory bandwidth.

This module details how to optimize memory use, configure Netty for zero-copy allocations, enable Gzip compression, and tune JVM Garbage Collectors (G1GC and ZGC) to achieve low latencies.

---

## 2. Protocol Performance Comparison

| Metric / Feature | REST (JSON) | GraphQL (JSON) | gRPC (Protobuf) | WebSockets (Binary) |
| :--- | :--- | :--- | :--- | :--- |
| **Payload Size** | Large (Text metadata keys) | Large (Query AST + JSON) | Tiny (Compact tags) | Small (Raw frames) |
| **CPU Overhead** | High (Text parsing) | Very High (Parsing AST) | Extremely Low (Tag-value) | Low (Custom byte offsets) |
| **Multiplexing** | No (Serial connections) | No (Serial connections) | Yes (HTTP/2 streams) | Yes (Single connection) |
| **Schema validation** | Runtime (JSON Schema) | Runtime (GraphQL engine) | Compile-time | Runtime (Manual check) |

---

## 3. JVM Garbage Collection Optimization

To keep latency low, tune your JVM Garbage Collector flags to minimize Stop-the-World (STW) pauses.

### 3.1 ZGC (Z Garbage Collector) - Recommended for Java 17+
ZGC is a scalable, low-latency garbage collector designed to execute collection phases concurrently with application threads, keeping STW pauses under 1 millisecond.

```bash
# JVM Flags to activate ZGC
java -XX:+UseZGC \
     -XX:ZAllocationSpikeTolerance=5 \
     -XX:+UnlockDiagnosticVMOptions \
     -XX:-ZProactive \
     -Xms16g -Xmx16g \
     -jar app.jar
```
*   `ZAllocationSpikeTolerance`: Allocates memory faster when allocations spike suddenly.
*   `-XX:-ZProactive`: Prevents ZGC from initiating garbage collection proactively when the application is idle, conserving CPU resources.

---

### 3.2 G1GC (Garbage-First Garbage Collector) - Traditional Alternative
If ZGC is not available, G1GC can be configured to prioritize low latency:

```bash
# JVM Flags to optimize G1GC
java -XX:+UseG1GC \
     -XX:MaxGCPauseMillis=20 \
     -XX:InitiatingHeapOccupancyPercent=45 \
     -XX:G1ReservePercent=15 \
     -XX:+ParallelRefProcEnabled \
     -jar app.jar
```
*   `MaxGCPauseMillis=20`: Informs G1GC to target a maximum GC pause time of 20ms.
*   `ParallelRefProcEnabled`: Enables parallel reference processing, shortening reference lifecycle cleanup times.

---

## 4. Netty Memory & Thread Pool Tuning in Spring Boot

Configure Netty properties in your `application.yml` to optimize thread pools and enable off-heap memory allocations:

```yaml
grpc:
  server:
    # Use direct, off-heap memory buffers to avoid GC heap churn
    netty:
      allocator: pooled
    # Sizing Netty Thread Pools
    # bossEventLoopGroup size = 1 (responsible only for accepting TCP connections)
    # workerEventLoopGroup size = CPU Cores (responsible for network IO read/write)
```

By default, the community starter creates a separate thread pool for execution. Map thread pool parameters to match your workload requirements:

```yaml
grpc:
  server:
    executor:
      # Sizing Thread Pool independently of Networking Cores to prevent starvation
      core-size-factor: 2.0  # corePoolSize = Cores * factor
      max-size-factor: 4.0   # maxPoolSize = Cores * factor
      queue-capacity: 1000
```

---

## 5. Selective Serialization Compression
To balance network bandwidth and CPU usage, configure compression thresholds. Enabling compression on small payloads (e.g. less than 1KB) can increase latency due to CPU compression overhead.

Configure compression on your client stubs:
```java
@GrpcClient("user-service")
private UserServiceBlockingStub userStub;

public UserProfile fetchProfile(int id) {
    UserRequest request = UserRequest.newBuilder().setUserId(id).build();
    
    // Enable GZIP compression on this stub call
    return userStub.withCompression("gzip").getUser(request);
}
```

---

## 6. Common Mistakes and Anti-Patterns
*   **Thread Starvation on Netty EventLoops**: Executing blocking database queries (`JDBC`/`JPA`) or calling slow external APIs directly in the gRPC service class thread without configuring an application executor pool.
*   **Buffer Copies**: Mapping protobuf objects into JSON or intermediate entities redundantly. For optimal performance, serialize protobuf classes directly to byte streams.

---

## 7. Interview Questions

### Q1: What is the "Zero-Copy" principle, and how does Netty's Pooled Direct Allocator implement it in Spring Boot?
**Answer**: 
*   **Zero-Copy**: Prevents the CPU from copying data bytes between memory buffers during network read/write operations.
*   **Netty pooled allocator**: Standard Java objects live on the JVM heap. To send them over TCP, the JVM must copy heap bytes to an off-heap direct buffer memory region first, because the OS socket layer cannot read directly from the moving heap (due to GC garbage collection relocations).
By allocating off-heap **Direct ByteBufs**, Netty writes bytes directly from the network card to this off-heap space. The application reads and processes the bytes in this direct region, bypassing the JVM heap copy cycle entirely and significantly reducing memory bus overhead.

### Q2: Why is ZGC preferred over G1GC for low-latency gRPC services? What is the trade-off?
**Answer**: 
*   **ZGC Preference**: ZGC performs all collection phases concurrently with application threads. Pauses do not increase with heap size, keeping GC pause latency under 1ms. This eliminates the latency spikes associated with G1GC's Stop-the-World pauses.
*   **The Trade-off**: ZGC consumes about **5% to 10% more CPU overhead** than G1GC because garbage collection threads run concurrently with application threads. This can slightly reduce overall throughput under maximum load.
