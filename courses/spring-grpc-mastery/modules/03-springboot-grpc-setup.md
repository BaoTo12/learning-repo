# Module 03: Spring Boot gRPC Server & Client Setup

## 1. What Problem This Module Solves
Integrating raw gRPC libraries into standard Spring Boot applications introduces boilerplate overhead:
*   **Manual Port Binding**: Writing code to manually bind `ServerBuilder` to ports, adding shutdown hooks, and starting server threads.
*   **Context Isolation**: Raw gRPC services cannot easily access Spring beans (e.g. database repositories, security filters, configurations) because their lifecycles are managed outside the Spring container.
*   **Stub Configuration Overhead**: Manually instantiating `ManagedChannel` and stubs for every service integration requires writing complex builder wrappers.

Using the community **Spring Boot gRPC Starter** resolves this by automating bean registration, server bootstrapping, and dependency injection of stubs.

---

## 2. Dependency Management (Maven)

Include the server and client starters in your `pom.xml`:

```xml
<dependencies>
    <!-- gRPC Spring Boot Server Starter -->
    <dependency>
        <groupId>net.devh</groupId>
        <artifactId>grpc-server-spring-boot-starter</artifactId>
        <version>2.15.0.RELEASE</version>
    </dependency>

    <!-- gRPC Spring Boot Client Starter -->
    <dependency>
        <groupId>net.devh</groupId>
        <artifactId>grpc-client-spring-boot-starter</artifactId>
        <version>2.15.0.RELEASE</version>
    </dependency>
</dependencies>
```

---

## 3. Configuration Management (`application.yml`)

Configure the port, threads, keep-alive settings, and downstream client channels in your environment config:

```yaml
# Server Settings
grpc:
  server:
    port: 9090                    # Port to bind Netty server
    address: 0.0.0.0              # Address to bind
    keep-alive-time: 5m           # HTTP/2 ping interval
    keep-alive-timeout: 20s       # Ping ack timeout
    max-connection-idle: 15m      # Max idle connection lifecycle
# Client Settings
  client:
    user-service:
      address: 'static://localhost:9090' # Target URL
      negotiation-type: plaintext         # Plaintext h2c (use TLS in production)
      keep-alive-time: 30s
      keep-alive-timeout: 10s
```

---

## 4. Implementing a Unary Service Bean (Server)

An application service implementation is declared by annotating the class with `@GrpcService`. The starter registers the bean automatically with the Netty server container:

```java
package com.example.grpc.user;

import com.example.grpc.user.v1.UserProfile;
import com.example.grpc.user.v1.UserRequest;
import com.example.grpc.user.v1.UserServiceGrpc;
import com.example.grpc.user.v1.UserStatus;
import io.grpc.stub.StreamObserver;
import net.devh.boot.grpc.server.service.GrpcService;
import org.springframework.beans.factory.annotation.Autowired;

@GrpcService
public class UserServiceImpl extends UserServiceGrpc.UserServiceImplBase {

    private final UserRepository userRepository; // Access standard Spring JPA repository

    @Autowired
    public UserServiceImpl(UserRepository userRepository) {
        this.userRepository = userRepository;
    }

    @Override
    public void getUser(UserRequest request, StreamObserver<UserProfile> responseObserver) {
        int userId = request.getUserId();
        
        // Query JPA database
        UserEntity entity = userRepository.findById(userId)
            .orElseThrow(() -> new IllegalArgumentException("User not found: " + userId));

        // Map database model to Protobuf structure
        UserProfile response = UserProfile.newBuilder()
            .setUserId(entity.getId())
            .setEmail(entity.getEmail())
            .setStatus(UserStatus.USER_STATUS_ACTIVE)
            .build();

        // Send response down the socket
        responseObserver.onNext(response);
        responseObserver.onCompleted();
    }
}
```

---

## 5. Injecting Client Stubs (Client)

To inject stubs into your Spring controllers or services, use the `@GrpcClient` annotation:

```java
package com.example.grpc.user;

import com.example.grpc.user.v1.UserProfile;
import com.example.grpc.user.v1.UserRequest;
import com.example.grpc.user.v1.UserServiceGrpc.UserServiceBlockingStub;
import net.devh.boot.grpc.client.inject.GrpcClient;
import org.springframework.stereotype.Service;

@Service
public class UserGatewayService {

    // Inject the blocking stub. The client starter automatically configures it
    // using properties under grpc.client.user-service
    @GrpcClient("user-service")
    private UserServiceBlockingStub userStub;

    public UserProfile fetchUserProfile(int userId) {
        UserRequest request = UserRequest.newBuilder()
            .setUserId(userId)
            .build();
        
        // Execute unary call
        return userStub.getUser(request);
    }
}
```

---

## 6. Common Mistakes and Anti-Patterns
*   **Multiple Server Builders**: Creating custom `Server` beans manually while using the Spring gRPC Starter. The starter automatically bootstraps a server bean. Defining your own can cause port bind collisions and duplicate registrations.
*   **Hardcoded Downstream Addresses**: Hardcoding static IP targets directly inside client `@GrpcClient` injection declarations. Always map addresses using configuration keys (`application.yml`) to support environment overrides (e.g. testing vs staging).
*   **Neglecting Connection Pooling**: Creating separate `ManagedChannel` instances in helper functions instead of letting the starter manage connection pools. Channels should be registered as singleton scoped beans.

---

## 7. Mini Project: User Validation Service
Build a user verification endpoint in Spring Boot that coordinates database records and responds to incoming client requests.

### JPA entity definition (`UserEntity.java`)
```java
package com.example.grpc.user;

import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

@Entity
@Table(name = "users")
public class UserEntity {
    @Id
    private int id;
    private String email;

    public UserEntity() {}
    public UserEntity(int id, String email) {
        this.id = id;
        this.email = email;
    }
    public int getId() { return id; }
    public String getEmail() { return email; }
}
```

### Spring Repository (`UserRepository.java`)
```java
package com.example.grpc.user;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface UserRepository extends JpaRepository<UserEntity, Integer> {}
```

---

## 8. Interview Questions

### Q1: How does `@GrpcService` registration work under the hood during Spring Boot bootstrap?
**Answer**: 
During Spring's context refresh phase, the `GrpcServerAutoConfiguration` class intercepts initialization using a bean post-processor. It scans the `ApplicationContext` for any beans annotated with `@GrpcService` (which inherit from `BindableService`). 
The configuration collector registers these service definitions to a central `GrpcServiceRegistry`. When all beans are loaded, it creates a `Server` instance, binds the registered services to it, and invokes `server.start()` on a non-blocking daemon thread.

### Q2: What is the benefit of the `@GrpcClient` annotation over manual `ManagedChannel` bean injection?
**Answer**: 
*   **Metadata Integration**: `@GrpcClient` manages stub creation dynamically. It maps the configuration settings directly from `application.yml` (e.g. timeouts, TLS certs, keep-alives) to the injected stub instance.
*   **Interceptor Binding**: It allows you to bind specific client interceptors to specific client stubs via application configurations rather than manually chaining interceptors in Java code.
*   **Lifecycle Isolation**: It automatically handles channel shutdowns when the Spring ApplicationContext terminates.
