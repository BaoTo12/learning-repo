# Module 14: Testing Spring gRPC Services

## 1. What Problem This Module Solves
Testing gRPC services in a standard Spring Boot environment introduces several challenges:
*   **Port Bind Collisions**: Bootstrapping real Netty servers on physical ports (like `9090`) during concurrent CI build runs leads to address collision failures.
*   **Slow Test Suites**: Starting the complete Spring context and Netty socket engine for basic unit tests is slow.
*   **Mocking Pitfalls**: Mocking the client stubs directly via Mockito (e.g. `Mockito.mock(UserStub.class)`) bypasses the serialization/deserialization layers, failing to catch critical tag-mapping bugs.

This module details how to write isolated unit tests using gRPC’s **In-Process Transport** layer and how to execute end-to-end integration tests using **Testcontainers**.

---

## 2. In-Process Testing Lifecycle in Spring Boot

To test gRPC services rapidly without socket allocation, gRPC-Java provides the `InProcessServerBuilder` and `InProcessChannelBuilder` classes. The community starter automates this by configuring an in-process server context:

```yaml
# application-test.yml (Testing profile configuration)
grpc:
  server:
    in-process-name: test-server # Virtual in-process server name instead of port
  client:
    user-service:
      address: 'in-process:test-server'
```

Bytes are transferred directly between client and server via memory reference maps, completely bypassing the OS socket layer.

---

## 3. Spring Boot In-Process Integration Test

This test bootstraps the service bean using `@SpringBootTest` and runs requests through the serialization layer:

```java
package com.example.grpc.testing;

import com.example.grpc.user.v1.UserProfile;
import com.example.grpc.user.v1.UserRequest;
import com.example.grpc.user.v1.UserServiceGrpc.UserServiceBlockingStub;
import net.devh.boot.grpc.client.inject.GrpcClient;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.annotation.DirtiesContext;
import org.springframework.test.context.ActiveProfiles;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;

@SpringBootTest(properties = {
    "grpc.server.in-process-name=test-server",
    "grpc.client.user-service.address=in-process:test-server"
})
@ActiveProfiles("test")
@DirtiesContext
public class UserServiceIntegrationTest {

    @GrpcClient("user-service")
    private UserServiceBlockingStub userStub;

    @Test
    public void getUser_shouldReturnProfileFromInProcessServer() {
        UserRequest request = UserRequest.newBuilder().setUserId(99).build();

        // Executes call through in-process memory channels
        UserProfile profile = userStub.getUser(request);

        assertNotNull(profile);
        assertEquals(99, profile.getUserId());
    }
}
```

---

## 4. Testcontainers Database Integration

To test integrations with external systems (like PostgreSQL), configure **Testcontainers** in your test suite:

```java
package com.example.grpc.testing;

import org.junit.jupiter.api.Test;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

import static org.junit.jupiter.api.Assertions.assertTrue;

@Testcontainers
public class DatabaseIntegrationTest {

    @Container
    public static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:15-alpine")
        .withDatabaseName("test_db")
        .withUsername("admin")
        .withPassword("secret");

    @Test
    public void testDatabaseIsRunning() {
        assertTrue(postgres.isRunning());
        String jdbcUrl = postgres.getJdbcUrl();
        System.out.println("Postgres Container dynamic JDBC URL: " + jdbcUrl);
    }
}
```

---

## 5. Common Mistakes and Anti-Patterns
*   **Direct Mockito Stub Mocking**: Mocking the generated blocking stub class (e.g. `Mockito.mock(UserServiceBlockingStub.class)`) instead of loading a real service inside an in-process server. This bypasses the Protobuf serialization layer, failing to verify tag numbers or schema conversions.
*   **Not Cleaning Contexts**: Forgetting to add `@DirtiesContext` on tests that start/stop in-process servers, leaving port mappings or channels open across subsequent tests.

---

## 6. Interview Questions

### Q1: Why is testing stubs using In-Process Channels preferred over making loopback (`localhost:9090`) calls?
**Answer**: 
*   **Port Collisions**: Loopback calls bind to physical TCP ports. If multiple tests execute concurrently on a build agent, they fail due to `AddressAlreadyInUse` exceptions.
*   **Performance**: Loopback calls route bytes through the OS network stack. In-process channels pass deserialized buffers directly through memory pointers, executing tests up to **10x faster** without consuming network ports.

### Q2: Why is the `@DirtiesContext` annotation often required when running multiple Spring gRPC integration tests?
**Answer**: 
Spring caches the `ApplicationContext` across tests to improve execution speeds. If Test A changes properties or registers services on a specific in-process server name, and Test B attempts to configure the same server name, they will conflict. 
Using `@DirtiesContext` forces Spring to destroy and recreate the application context, ensuring each test class executes in a clean, isolated environment.
