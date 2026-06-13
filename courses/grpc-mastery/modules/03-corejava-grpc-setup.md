# Module 03: Core Java gRPC Server & Client Bootstrap

## 1. What Problem This Module Solves
Framework wrappers (like Spring Boot gRPC starters) hide the instantiation mechanics of the underlying networking library (Netty). While convenient, this abstraction leads to major production failures:
*   **Netty Thread Starvation**: By default, gRPC-Java executes business logic on the Netty thread pool if no custom executor is supplied. A single blocking database query or long-running CPU task will stall the network thread loop, blocking all other concurrent requests.
*   **Connection Dropping**: Idle connections are silently terminated by firewalls or stateful NAT routers. Without fine-tuning TCP keep-alives and ping intervals, clients experience unexpected timeouts.
*   **Abrupt Shutdowns**: Tearing down a JVM process without orchestrating a graceful shutdown terminates active flights of requests, causing database corruption and packet drops.

This module details how to manually build, configure, and secure gRPC-Java servers and clients directly using the official `grpc-netty-shaded` library.

---

## 2. Dependencies Setup (Maven)
For pure Java setups, use the following `pom.xml` dependency tree. We use `grpc-netty-shaded` because it embeds its own copy of Netty and `tcnative` (for SSL/TLS), avoiding class loader conflicts with other libraries.

```xml
<properties>
    <maven.compiler.source>17</maven.compiler.source>
    <maven.compiler.target>17</maven.compiler.target>
    <grpc.version>1.62.2</grpc.version>
    <protobuf.version>3.25.3</protobuf.version>
</properties>

<dependencies>
    <!-- gRPC Netty Transport Engine -->
    <dependency>
        <groupId>io.grpc</groupId>
        <artifactId>grpc-netty-shaded</artifactId>
        <version>${grpc.version}</version>
    </dependency>
    <!-- Protobuf support -->
    <dependency>
        <groupId>io.grpc</groupId>
        <artifactId>grpc-protobuf</artifactId>
        <version>${grpc.version}</version>
    </dependency>
    <!-- Client Stubs -->
    <dependency>
        <groupId>io.grpc</groupId>
        <artifactId>grpc-stub</artifactId>
        <version>${grpc.version}</version>
    </dependency>
    <!-- Annotations API (needed for JDK 11+) -->
    <dependency>
        <groupId>javax.annotation</groupId>
        <artifactId>javax.annotation-api</artifactId>
        <version>1.3.2</version>
    </dependency>
</dependencies>
```

---

## 3. Server Threading Architecture

By default, Netty utilizes two main thread groups:
1.  **Boss EventLoop Group**: Responsible for accepting incoming TCP socket connections.
2.  **Worker EventLoop Group**: Responsible for reading/writing raw packets from the sockets.

```
                          [ Client Requests ]
                                   │
                                   ▼
                   [ Netty Boss EventLoop Group ] (Accepts TCP Sockets)
                                   │
                                   ▼
                 [ Netty Worker EventLoop Group ] (Reads Raw Packets)
                                   │
                                   ▼
                 [ Dedicated Executor Thread Pool ] (Executes App Logic)
                    * Sized independently of networking cores
                    * Prevents blocking calls from freezing sockets
```

> [!IMPORTANT]
> **Rule of Thumb**: You MUST pass a dedicated Executor (e.g., `ThreadPoolExecutor` or Virtual Threads) to the `ServerBuilder` so that application processing is isolated from Netty’s network IO loops.

---

## 4. Common Mistakes and Anti-Patterns
*   **Executing Blocking IO on Netty Threads**: Calling third-party REST APIs, database queries (`JDBC`/`JPA`), or reading local files inside a gRPC service without allocating a separate executor pool.
*   **Creating Channels per Request**: Instantiating a `ManagedChannel` for every single RPC request. A channel represents an expensive TCP connection pool. Opening/closing channels per call introduces latency and socket leaks. Re-use a single thread-safe `ManagedChannel` instance for the lifetime of the application.
*   **Missing Keep-Alive Configuration**: Leaving TCP keep-alives disabled. Without periodic HTTP/2 `PING` frames, intermediate firewalls will clean up idle sockets, resulting in abrupt connection terminations.

---

## 5. When NOT to use Pure gRPC-Java Bootstrapping
If you are developing a standard CRUD monolith where the rest of the application is tightly bound to Spring Data, Spring Security, and Spring MVC, building raw Netty servers manually adds unnecessary boilerplate. Use Spring-gRPC wrappers *only* when application configuration uniformity is prioritized over absolute control of the Netty transport layer.

---

## 6. Production Architecture: Thread Pool Sizing
For a high-throughput gRPC application, size the execution pool based on target workloads:
*   **CPU-Bound Services**: Sized to $N+1$ where $N$ is the number of logical CPU cores.
*   **IO-Bound Services**: Sized using the blocking coefficient formula:
    $$\text{Threads} = \text{Cores} \times \left(1 + \frac{\text{Wait Time}}{\text{Service Time}}\right)$$
    Use a bounded queue (`LinkedBlockingQueue` or `SynchronousQueue`) with a rejection handler (`AbortPolicy` or `DiscardPolicy`) to avoid out-of-memory errors.

---

## 7. Hands-on Exercises
1.  Configure a gRPC client to use a custom name resolver and test it against a mock server.
2.  Trigger a simulated memory leak by spawning new `ManagedChannel` instances in a loop, observing OS socket exhaustion using `netstat`.

---

## 8. Mini-Project: Hardened Server and Client Bootstrapper
Build a production-ready server bootstrapper and channel builder with thread pooling, keep-alive settings, and a graceful shutdown lifecycle.

### Server Bootstrapper (`ProductionGrpcServer.java`)
```java
package com.example.grpc.bootstrap;

import io.grpc.BindableService;
import io.grpc.Server;
import io.grpc.ServerBuilder;
import io.grpc.stub.StreamObserver;
import java.io.IOException;
import java.util.concurrent.*;

public class ProductionGrpcServer {

    private final int port;
    private final Server server;
    private final ThreadPoolExecutor appExecutor;

    public ProductionGrpcServer(int port) {
        this.port = port;

        // 1. Define bounded thread pool for application logic to protect Netty EventLoop
        this.appExecutor = new ThreadPoolExecutor(
            16, 64, 60L, TimeUnit.SECONDS,
            new LinkedBlockingQueue<>(1000),
            new ThreadFactory() {
                private int count = 0;
                @Override
                public Thread newThread(Runnable r) {
                    Thread t = new Thread(r, "grpc-app-executor-" + count++);
                    t.setDaemon(true);
                    return t;
                }
            },
            new ThreadPoolExecutor.AbortPolicy() // Reject execution if queue is saturated
        );

        // 2. Configure Netty Server
        this.server = ServerBuilder.forPort(port)
            .executor(appExecutor) // Route business logic to app pool
            .addService(new DummyService()) // Register Service
            // HTTP/2 Keep Alive Settings
            .keepAliveTime(5, TimeUnit.MINUTES)
            .keepAliveTimeout(20, TimeUnit.SECONDS)
            .maxConnectionIdle(15, TimeUnit.MINUTES)
            .build();
    }

    public void start() throws IOException {
        server.start();
        System.out.println("GRPC Production Server listening on port " + port);

        // 3. Register JVM Graceful Shutdown Hook
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            System.err.println("*** Shutting down gRPC server since JVM is shutting down");
            try {
                ProductionGrpcServer.this.stop();
            } catch (InterruptedException e) {
                e.printStackTrace(System.err);
            }
            System.err.println("*** Server shut down successfully");
        }));
    }

    public void stop() throws InterruptedException {
        if (server != null) {
            // Initiate graceful shutdown (stop accepting requests, complete in-flight requests)
            server.shutdown();
            
            // Wait up to 15 seconds for active requests to finish
            if (!server.awaitTermination(15, TimeUnit.SECONDS)) {
                System.err.println("Forcefully terminating active connections...");
                server.shutdownNow();
            }
        }
        
        // Shut down application executor pool
        appExecutor.shutdown();
        if (!appExecutor.awaitTermination(5, TimeUnit.SECONDS)) {
            appExecutor.shutdownNow();
        }
    }

    public void blockUntilShutdown() throws InterruptedException {
        if (server != null) {
            server.awaitTermination();
        }
    }

    // A Dummy Service Implementation
    public static class DummyService extends io.grpc.BindableService {
        @Override
        public io.grpc.ServerServiceDefinition bindService() {
            // For bare metal implementation, we override bindService manually
            // Typically generated by compile stubs
            return io.grpc.ServerServiceDefinition.builder("DummyService").build();
        }
    }

    public static void main(String[] args) throws Exception {
        ProductionGrpcServer server = new ProductionGrpcServer(9091);
        server.start();
        server.blockUntilShutdown();
    }
}
```

### Client Bootstrapper (`ProductionGrpcClient.java`)
```java
package com.example.grpc.bootstrap;

import io.grpc.ManagedChannel;
import io.grpc.ManagedChannelBuilder;
import java.util.concurrent.ForkJoinPool;
import java.util.concurrent.TimeUnit;

public class ProductionGrpcClient {

    public static ManagedChannel buildChannel(String host, int port) {
        return ManagedChannelBuilder.forAddress(host, port)
            // Use custom executor for client callbacks instead of Netty threads
            .executor(ForkJoinPool.commonPool())
            // Prevent silent firewall connection drops
            .keepAliveTime(30, TimeUnit.SECONDS)
            .keepAliveTimeout(10, TimeUnit.SECONDS)
            .keepAliveWithoutCalls(true) // Send pings even if no active RPCs
            .usePlaintext() // For local development only (no TLS)
            .build();
    }

    public static void main(String[] args) throws Exception {
        ManagedChannel channel = buildChannel("localhost", 9091);
        System.out.println("ManagedChannel successfully constructed and pooled.");
        
        // Graceful channel shutdown
        channel.shutdown().awaitTermination(5, TimeUnit.SECONDS);
    }
}
```

---

## 9. Interview Questions

### Q1: What happens if you run a blocking database query inside a gRPC service method and do NOT configure a custom executor pool on the `ServerBuilder`?
**Answer**: 
If no custom executor is configured, gRPC-Java executes service logic on Netty's worker EventLoop threads. The worker EventLoop group is typically sized to match the number of CPU cores. If a database query blocks (e.g., waiting 500ms for a table lock), the Netty thread executing it is frozen. If all EventLoop threads get blocked, the server will stop processing TCP packets, causing incoming request packets to queue up in the OS TCP buffer, eventually leading to timeouts and dropped connections across the *entire* server.

### Q2: What is the purpose of `keepAliveWithoutCalls(true)` on the `ManagedChannelBuilder`, and what danger does it present in production?
**Answer**: 
*   **Purpose**: It forces the client to send HTTP/2 `PING` frames to the server even if there are no active RPCs on the channel. This prevents middleboxes (like NAT gateways, firewalls, load balancers) from dropping idle TCP connections.
*   **Danger**: If thousands of idle clients connect to a server with `keepAliveWithoutCalls(true)` enabled, they will collectively bombard the server with constant ping frames. This is known as a **Keep-Alive Storm**, and it can exhaust server CPU resources and network bandwidth. To protect servers, the `ServerBuilder` has `permitKeepAliveWithoutCalls(false)` to refuse pings on idle channels and `permitKeepAliveTime()` to enforce minimum ping intervals.
