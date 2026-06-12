# Module 10: Performance Engineering & Java GC Tuning

## 1. What Problem This Module Solves
At high scale, network communication layer optimizations dictate CPU utilization, memory profiles, and response times.
*   **Garbage Collection Spikes**: Standard JSON serialization allocates millions of temporary objects (strings, maps, wrappers) that quickly fill the JVM Young Generation, triggering frequent "Stop-the-World" GC pauses.
*   **Buffer Copy Overhead**: Moving bytes from the OS network buffer to Java heap arrays, and then into application structures, requires redundant memory copy instructions, placing high overhead on CPU caches.

This module details how to minimize serialization footprints, configure Netty's Pooled Direct Byte Buffers for zero-copy operations, enable compression, and tune Java Garbage Collectors (G1GC and ZGC) for low-latency gRPC services.

---

## 2. Serialization Cost Profile comparison

To understand the CPU efficiency, let's analyze payload sizes and parsing performance for transmitting a dataset:

| Protocol / Format | Payload Size (Bytes) | Parsing CPU Cycles | Concurrency Support | Serialization Mechanism |
| :--- | :--- | :--- | :--- | :--- |
| **REST + JSON** | ~450 B | High (Text Scanning) | Synchronous / Pipelining | Text encoding, Reflection |
| **GraphQL + JSON** | ~380 B | Very High (Parsing + Query AST) | Single TCP Stream | Text encoding, Reflection |
| **WebSockets** | ~350 B | Low (Binary / Text) | Bidirectional (Single Stream) | Custom Framing |
| **gRPC + Protobuf** | **~80 B** | **Extremely Low (Varints/Tags)** | **Bidirectional (Multiplexed)** | **Binary Tag-Value, No reflection** |

---

## 3. Java Garbage Collection Tuning

For low-latency gRPC, you must configure GC JVM parameters to minimize Stop-the-World (STW) pauses.

### 3.1 ZGC (Z Garbage Collector) - Recommended for Java 17+
ZGC is a scalable, low-latency garbage collector. Its pauses do **not** scale with heap size, keeping STW pauses under **1 millisecond**.

```bash
# JVM Flags to activate ZGC
java -XX:+UseZGC \
     -XX:ZAllocationSpikeTolerance=5 \
     -XX:+UnlockDiagnosticVMOptions \
     -XX:-ZProactive \
     -Xms16g -Xmx16g \
     -jar app.jar
```
*   `ZAllocationSpikeTolerance`: Helps allocate memory faster when allocations spike suddenly.
*   `-XX:-ZProactive`: Prevents ZGC from initiating garbage collection proactively when the application is idle, conserving CPU resources.

---

### 3.2 G1GC (Garbage-First Garbage Collector) - Traditional Option
If ZGC is not available, G1GC can be tuned to prioritize low latencies:

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

## 4. Common Mistakes and Anti-Patterns
*   **Heap-Allocating Large Payloads**: Instantiating large byte arrays (`byte[]`) in memory. If your server processes large file transfers or image files, it will exhaust the heap.
    *   *Correction*: Use Netty's **Direct Buffers** (which allocate memory off-heap, bypassing GC tracking) and stream the payload in chunks.
*   **Enabling Gzip Compression on Small Payloads**: Enabling Gzip compression for short payloads (e.g. 50-byte RPC responses). The CPU cycle overhead of executing the compression algorithm is greater than the network transfer savings, actually increasing latency.
    *   *Correction*: Apply compression selectively for payloads larger than 1KB.

---

## 5. Configuring Netty Buffer Allocations & Stub Compression

By default, the `grpc-netty-shaded` library is configured to use Pooled Direct Byte Buffers to avoid heap allocation.

### 5.1 Enforcing Direct Off-Heap Memory on Server
```java
package com.example.grpc.performance;

import io.grpc.Server;
import io.grpc.netty.shaded.io.grpc.netty.NettyServerBuilder;
import io.grpc.netty.shaded.io.netty.buffer.PooledByteBufAllocator;
import java.io.IOException;

public class PerformanceTunedServer {

    public static Server buildOptimizedServer(int port) throws IOException {
        return NettyServerBuilder.forPort(port)
            // Enforce Pooled off-heap allocator to recycle memory and prevent GC heap churn
            .channelFactory(io.grpc.netty.shaded.io.grpc.netty.NettyServerBuilder.DEFAULT_CHANNEL_FACTORY)
            .bossEventLoopGroup(new io.grpc.netty.shaded.io.netty.channel.nio.NioEventLoopGroup(1))
            .workerEventLoopGroup(new io.grpc.netty.shaded.io.netty.channel.nio.NioEventLoopGroup(Runtime.getRuntime().availableProcessors()))
            .build();
    }
}
```

---

### 5.2 Enabling Payload Compression on Client Stub
```java
package com.example.grpc.performance;

import io.grpc.ManagedChannel;
import io.grpc.ManagedChannelBuilder;
import com.example.grpc.routeguide.RouteGuideGrpc;
import com.example.grpc.routeguide.RouteGuideGrpc.RouteGuideBlockingStub;

public class CompressedStubClient {

    public static void main(String[] args) {
        ManagedChannel channel = ManagedChannelBuilder.forAddress("localhost", 9091)
            .usePlaintext()
            .build();

        // Instantiate stub and enable GZIP compression
        RouteGuideBlockingStub stub = RouteGuideGrpc.newBlockingStub(channel)
            .withCompression("gzip"); // Enable compression

        System.out.println("Stub configured with GZIP compression compression metadata.");
        channel.shutdown();
    }
}
```

---

## 6. Mini-Project: Benchmark JSON vs Protobuf Serialization
Write a benchmark utility to compare execution time and byte sizes when serializing 100,000 objects in Java using Jackson (JSON) vs Protobuf.

### Implementation Code (`SerializationBenchmark.java`)
```java
package com.example.grpc.performance;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.example.grpc.protobuf.model.UserProfile; // Generated profile class from Module 02
import java.io.ByteArrayOutputStream;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public class SerializationBenchmark {

    public static class JsonUser {
        public int userId;
        public String email;
        public List<String> roles;
        public String status;
        public Map<String, String> metadata;
    }

    public static void main(String[] args) throws Exception {
        int iterations = 100_000;
        ObjectMapper objectMapper = new ObjectMapper();

        // 1. Prepare JSON test target
        JsonUser jsonUser = new JsonUser();
        jsonUser.userId = 1500;
        jsonUser.email = "benchmark-user-test-email@example.com";
        jsonUser.roles = List.of("USER", "ADMIN", "AUDITOR");
        jsonUser.status = "STATUS_ACTIVE";
        jsonUser.metadata = Map.of("key1", "val1", "key2", "val2");

        // 2. Prepare Protobuf test target
        UserProfile protoUser = UserProfile.newBuilder()
            .setUserId(1500)
            .setEmail("benchmark-user-test-email@example.com")
            .addAllRoles(List.of("USER", "ADMIN", "AUDITOR"))
            .setStatusValue(1) // STATUS_ACTIVE
            .putMetadata("key1", "val1")
            .putMetadata("key2", "val2")
            .build();

        // Warm up JVM
        for (int i = 0; i < 10_000; i++) {
            objectMapper.writeValueAsBytes(jsonUser);
            protoUser.toByteArray();
        }

        // --- Execute JSON Benchmark ---
        long startJson = System.nanoTime();
        byte[] rawJsonBytes = null;
        for (int i = 0; i < iterations; i++) {
            rawJsonBytes = objectMapper.writeValueAsBytes(jsonUser);
        }
        long durationJson = System.nanoTime() - startJson;

        // --- Execute Protobuf Benchmark ---
        long startProto = System.nanoTime();
        byte[] rawProtoBytes = null;
        for (int i = 0; i < iterations; i++) {
            rawProtoBytes = protoUser.toByteArray();
        }
        long durationProto = System.nanoTime() - startProto;

        // --- Output Metrics ---
        System.out.println("====== BENCHMARK RESULTS ======");
        System.out.printf("JSON Payload size:       %d bytes\n", rawJsonBytes.length);
        System.out.printf("Protobuf Payload size:   %d bytes (%.2f%% smaller)\n", 
            rawProtoBytes.length, (1.0 - (double)rawProtoBytes.length / rawJsonBytes.length) * 100);
        System.out.printf("JSON Total Time:         %.2f ms\n", durationJson / 1_000_000.0);
        System.out.printf("Protobuf Total Time:     %.2f ms (%.2fx faster)\n", 
            durationProto / 1_000_000.0, (double) durationJson / durationProto);
    }
}
```

---

## 7. Interview Questions

### Q1: What is the "Zero-Copy" principle in Netty, and how does Pooled Direct ByteBuf memory allocation achieve it?
**Answer**: 
*   **Zero-Copy** means preventing the CPU from performing unnecessary memory copies when reading or writing data blocks from the network interface card (NIC).
*   **Pooled Direct ByteBuf**: Standard Java objects live on the JVM heap. To send them over TCP, the JVM must copy heap bytes to an off-heap direct buffer memory region first, because the OS socket layer cannot read directly from the moving heap (due to GC garbage collection relocations).
By allocating off-heap **Direct ByteBufs**, Netty writes bytes directly from the network card to this off-heap space. The application reads and processes the bytes in this direct region, bypassing the JVM heap copy cycle entirely and significantly reducing memory bus overhead.

### Q2: When comparing ZGC and G1GC for high-throughput gRPC microservices, what is the key architectural trade-off?
**Answer**: 
*   **ZGC (Z Garbage Collector)**: Minimizes GC pause latency to sub-millisecond durations by executing collection phases concurrently with application execution threads. The trade-off is a **5% to 10% loss in overall throughput** compared to G1GC, because concurrent GC threads consume CPU cores that would otherwise execute application business logic.
*   **G1GC (Garbage-First GC)**: Maximizes throughput by executing garbage collection in short STW pause bursts (e.g. targeting 20-50ms). It consumes fewer CPU cores concurrently but introduces small latency spikes.
**Conclusion**: For real-time APIs (like financial order execution or video streaming) ZGC is preferred. For high-volume async worker processing, G1GC is more resource-efficient.
