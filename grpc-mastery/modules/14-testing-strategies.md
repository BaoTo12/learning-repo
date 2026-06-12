# Module 14: Testing Strategies: Unit & Integration Testing

## 1. What Problem This Module Solves
Testing gRPC microservices is challenging:
*   **Port Collision Risks**: Bootstrapping real Netty servers on physical ports (like `9090`) during automated CI build runs leads to port collisions, flaky tests, and slow executions.
*   **Network Latency Overhead**: Testing stubs over loopback networks (`localhost`) adds serialization overhead and slows down test suites.
*   **External Resource Mocks**: Testing service methods that read from databases or publish to message brokers requires setting up local environments, which often differ from production configurations.

This module details how to write isolated unit tests using gRPC’s **In-Process Transport** layer and how to implement end-to-end integration tests using **Testcontainers**.

---

## 2. In-Process Testing Architecture

To test gRPC services rapidly without allocating network sockets, gRPC provides the `InProcessServerBuilder` and `InProcessChannelBuilder`:

```
[ JUnit Test Thread ]
       │
       ▼ (Invokes blockingStub.getFeature())
[ InProcessChannel ]
       │  (Direct memory pointer handoff - NO socket, NO TCP loopback)
       ▼
[ InProcessServer ]
       │
       ▼
[ Service under Test ]
```

*   **In-Process Server**: Runs inside the same JVM process as your test runner. It listens on a virtual target string rather than a TCP port.
*   **In-Process Channel**: Connects directly to the virtual target. Bytes are passed between the client and server via direct memory references, avoiding OS socket calls and loopback network layers.

---

## 3. Trade-offs and Limitations
*   **Missed Socket Configuration Bugs**: Since in-process tests do not use Netty, they cannot detect bugs related to transport-level settings (like SSL/TLS configurations, ALPN issues, or TCP buffer sizes).
*   **Container Startup Latency**: Testcontainers require spinning up actual Docker containers, which adds overhead (5-15 seconds per container) to integration test suites.

---

## 4. Common Mistakes and Anti-Patterns
*   **Leaving Channels and Servers Open**: Failing to clean up servers and channels after tests run. This leaks file descriptors and memory, eventually slowing down the JVM test runner.
    *   *Correction*: Use the `GrpcCleanupRule` or JUnit 5 `@AfterEach` blocks to guarantee server/channel termination.
*   **Mocking the gRPC Stubs**: Attempting to mock the compiled gRPC client stubs (e.g. `Mockito.mock(UserServiceBlockingStub.class)`) instead of using in-process server implementations. Mocking stubs bypasses the serialization layer and interceptors, missing critical serialization bugs (like unset required fields or mismatched enum values).

---

## 5. In-Process Unit Testing with JUnit 5

Let's build a complete unit test for `RouteGuideService` using gRPC's in-process transport:

```java
package com.example.grpc.testing;

import io.grpc.ManagedChannel;
import io.grpc.Server;
import io.grpc.inprocess.InProcessChannelBuilder;
import io.grpc.inprocess.InProcessServerBuilder;
import io.grpc.testing.GrpcCleanupRule;
import com.example.grpc.routeguide.Point;
import com.example.grpc.routeguide.Feature;
import com.example.grpc.routeguide.RouteGuideGrpc;
import com.example.grpc.routeguide.RouteGuideService;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.util.concurrent.TimeUnit;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;

public class RouteGuideServiceTest {

    private String serverName;
    private Server inProcessServer;
    private ManagedChannel inProcessChannel;
    private RouteGuideGrpc.RouteGuideBlockingStub blockingStub;

    @BeforeEach
    public void setUp() throws IOException {
        // Generate a unique virtual server name for this test run
        serverName = InProcessServerBuilder.generateName();

        // 1. Build and start the In-Process Server registering our service
        inProcessServer = InProcessServerBuilder.forName(serverName)
            .directExecutor() // Keep execution on the test thread to simplify debugging
            .addService(new RouteGuideService())
            .build()
            .start();

        // 2. Build the In-Process Channel pointing to the virtual server name
        inProcessChannel = InProcessChannelBuilder.forName(serverName)
            .directExecutor()
            .usePlaintext()
            .build();

        // 3. Create the blocking client stub
        blockingStub = RouteGuideGrpc.newBlockingStub(inProcessChannel);
    }

    @AfterEach
    public void tearDown() throws InterruptedException {
        // Clean up and shutdown channels and servers gracefully
        if (inProcessChannel != null) {
            inProcessChannel.shutdown().awaitTermination(2, TimeUnit.SECONDS);
        }
        if (inProcessServer != null) {
            inProcessServer.shutdown().awaitTermination(2, TimeUnit.SECONDS);
        }
    }

    @Test
    public void getFeature_shouldReturnLocationFeature() {
        Point request = Point.newBuilder().setLatitude(4000).setLongitude(5000).build();

        // Execute target call
        Feature response = blockingStub.getFeature(request);

        // Verify response values
        assertNotNull(response);
        assertEquals("Database Feature at 4000", response.getName());
        assertEquals(4000, response.getLocation().getLatitude());
    }
}
```

---

## 6. Integration Testing with Testcontainers

For database or external service integration tests, use Testcontainers to spin up isolated container instances:

```java
package com.example.grpc.testing;

import org.junit.jupiter.api.Test;
import org.testcontainers.containers.GenericContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.utility.DockerImageName;

import static org.junit.jupiter.api.Assertions.assertTrue;

@Testcontainers
public class DatabaseIntegrationTest {

    // Spin up an isolated PostgreSQL container for integration testing
    @Container
    public static GenericContainer<?> postgres = new GenericContainer<>(DockerImageName.parse("postgres:15-alpine"))
        .withEnv("POSTGRES_DB", "test_db")
        .withEnv("POSTGRES_USER", "admin")
        .withEnv("POSTGRES_PASSWORD", "secret")
        .withExposedPorts(5432);

    @Test
    public void testDatabaseConnection() {
        // Retrieve the dynamic host IP and mapped port allocated by docker
        String dbHost = postgres.getHost();
        Integer dbPort = postgres.getMappedPort(5432);

        System.out.printf("Database Container running at: %s:%d\n", dbHost, dbPort);
        assertTrue(postgres.isRunning());
    }
}
```

---

## 7. Interview Questions

### Q1: Why is mocking the client stub class using Mockito (e.g. `Mockito.mock(MyServiceBlockingStub.class)`) considered a testing anti-pattern? What is the correct alternative?
**Answer**: 
*   **Why it's an anti-pattern**: Mocking the stub class bypasses the entire gRPC framework serialization, deserialization, interceptor pipeline, and metadata header injection. A mock stub only tests if Java interfaces match, which hides bugs like incorrect tag mappings in `.proto` files, missing required fields, or authentication failures in interceptors.
*   **Alternative**: Use the **In-Process Transport** layer. Write an `InProcessServer` and load the real service implementation (injecting mocks into the service constructor if you need to mock database layers). This runs the call through the actual serialization, routing, and interceptor layers, catching realistic integration failures.

### Q2: What is the benefit of passing `.directExecutor()` to both `InProcessServerBuilder` and `InProcessChannelBuilder` in test setups?
**Answer**: 
By default, gRPC executes client callbacks and server method implementations on separate executor thread pools.
Passing `.directExecutor()` forces gRPC to run client calls, server execution, and response processing **on the single thread executing the JUnit test**. This simplifies debugging (allows standard breakpoints), removes race conditions in tests, and ensures that tracing contexts (like thread-local variables) remain visible throughout the test lifecycle.
