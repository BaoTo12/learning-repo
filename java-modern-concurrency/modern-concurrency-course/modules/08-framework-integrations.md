# Module 08: Modern Framework Integrations & Best Practices

## 1. What Problem This Module Solves
Migrating legacy enterprise frameworks (like Spring Boot, Quarkus, or Jakarta EE) to use virtual threads requires careful configuration:
*   **Tomcat Thread Pool Bottlenecks**: By default, Tomcat allocates a fixed pool of platform threads (typically 200). If these threads block on I/O, the gateway will block requests even if the JVM has resources.
*   **Silent Pinning in Third-Party Libraries**: Many legacy third-party libraries still use `synchronized` blocks. Enabling virtual threads globally without audit verification can lead to carrier thread pinning.
*   **Database Pool Exhaustion**: Because virtual threads scale concurrency, they can overwhelm database connection pools if not limited using Semaphores or database-level throttles.

This module details how to configure virtual threads in Spring Boot, Quarkus, and Jakarta EE, and covers migration best practices.

---

## 2. Spring Boot 3.x Integration

Spring Boot 3.2+ provides built-in support for Project Loom.

### 2.1 Enabling Virtual Threads via Configuration
Configure Spring Boot to execute Tomcat requests and task executions using virtual threads by setting the following property in your `application.yml`:

```yaml
spring:
  threads:
    virtual:
      enabled: true # Automatically configures Tomcat and task executors to use Virtual Threads
```

### 2.2 Manual Configuration (For older Spring versions)
If you are using Spring Boot 3.0 or 3.1, you can manually configure Tomcat to use a virtual thread executor:

```java
package com.example.concurrency.frameworks;

import org.springframework.boot.web.embedded.tomcat.TomcatProtocolHandlerCustomizer;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.task.AsyncTaskExecutor;
import org.springframework.core.task.support.TaskExecutorAdapter;
import java.util.concurrent.Executors;

@Configuration
public class LoomTaskExecutorConfig {

    @Bean
    public AsyncTaskExecutor applicationTaskExecutor() {
        // Wrap virtual thread per task executor as Spring AsyncTaskExecutor bean
        return new TaskExecutorAdapter(Executors.newVirtualThreadPerTaskExecutor());
    }

    @Bean
    public TomcatProtocolHandlerCustomizer<?> tomcatProtocolHandlerCustomizer() {
        // Configure Tomcat to process incoming requests using virtual threads
        return protocolHandler -> {
            protocolHandler.setExecutor(Executors.newVirtualThreadPerTaskExecutor());
        };
    }
}
```

---

## 3. Quarkus Integration

Quarkus provides native support for virtual threads. By default, endpoints run on Netty's event-loop thread. To execute an endpoint on a virtual thread, annotate the method with `@RunOnVirtualThread`:

```java
package com.example.concurrency.frameworks;

import jakarta.ws.rs.GET;
import jakarta.ws.rs.Path;
import io.smallrye.common.annotation.RunOnVirtualThread;

@Path("/catalog")
public class ProductCatalogResource {

    @GET
    @Path("/items")
    @RunOnVirtualThread // Directs Quarkus to run this blocking call on a Virtual Thread
    public String getCatalogItems() {
        return fetchItemsFromBlockingDatabase();
    }

    private String fetchItemsFromBlockingDatabase() {
        try {
            Thread.sleep(50); // Simulate database latency
        } catch (InterruptedException ignored) {}
        return "Catalog Payloads";
    }
}
```

---

## 4. Migration Best Practices and Safety Audits

When migrating an application to virtual threads, follow these rules:

1.  **Audit for Pinning**: Run your application tests with the `-Djdk.tracePinnedThreads=full` JVM property active. Identify and refactor any `synchronized` blocks in database or network I/O paths to use `ReentrantLock`.
2.  **Configure Database Pool Sizing**: Virtual threads can scale request concurrency, which can overwhelm database connection pools. Do **not** increase the database pool size to match the virtual thread count. Keep the connection pool sized using core calculations, and use a `Semaphore` in the application layer to throttle database access.
3.  **Audit ThreadLocal Usage**: Inspect libraries for `ThreadLocal` allocations. If a library allocates large maps in `ThreadLocal` context, replace them with `ScopedValue` or limit allocations to prevent memory leaks.

---

## 5. Interview Questions

### Q1: What happens under the hood in Spring Boot when you set `spring.threads.virtual.enabled=true`?
**Answer**: 
Enabling `spring.threads.virtual.enabled=true` triggers several auto-configuration changes:
1.  **Tomcat/Jetty Executor**: Replaces the default platform thread pool with an executor that spawns a new virtual thread for every incoming HTTP request (`Executors.newVirtualThreadPerTaskExecutor()`).
2.  **Spring TaskExecutor**: Replaces the default `SimpleAsyncTaskExecutor` bean with a virtual thread executor, routing all `@Async` tasks and `@Scheduled` tasks to virtual threads.
3.  **Spring Integration**: Configures messaging listeners (like RabbitMQ or Kafka message consumers) to process messages using virtual threads, improving ingestion throughput.

### Q2: Why is increasing your database connection pool size (maximumPoolSize) to match your virtual thread count a major database anti-pattern?
**Answer**: 
Stateless virtual threads are cheap, but stateful database connections are expensive. A database connection pool size is limited by the database server's physical resources (CPU cores, I/O channels, memory).
If you increase the pool size to 5,000 to match the virtual thread count, the database server will waste CPU cycles context-switching between the 5,000 competing connection processes, saturating the database and degrading performance. Keep the connection pool sized to match database cores, and use a `Semaphore` in the application layer to throttle database access.
