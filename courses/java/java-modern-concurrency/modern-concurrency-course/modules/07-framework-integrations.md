# Module 07: Modern Framework Integrations & Best Practices

With virtual threads finalized in the Java ecosystem, modern frameworks have introduced official integrations. Updating frameworks to use virtual threads lets applications handle high concurrency using simple, imperative, block-tolerant programming models.

In this module, we will explore virtual thread integrations in **Spring Boot**, **Quarkus**, and **Jakarta EE**, analyze database connection pool bottlenecks, outline production best practices, and implement three hands-on integration labs.

---

## 1. Spring Boot Integration (3.2+)

Historically, Spring Boot applications have used a **thread-per-request** model (via platform thread pools in Tomcat, Jetty, or Undertow). In high-scale workloads, blocking operations bound platform threads, causing thread pool exhaustion.

### Auto-Configuration
Starting with Spring Boot 3.2, you can switch the execution engine to virtual threads using a single property:

```properties
# application.properties
spring.threads.virtual.enabled=true
```

Or in YAML format:

```yaml
# application.yml
spring:
  threads:
    virtual:
      enabled: true
```

When enabled:
1. **Tomcat/Jetty/Undertow** protocol executors automatically switch from platform thread pools to a virtual-thread-per-task executor.
2. **Task Execution** (`@Async`) and **Task Scheduling** (`@Scheduled`) automatically use virtual threads via `SimpleAsyncTaskExecutor` and `SimpleAsyncTaskScheduler`.

### Under the Hood: Tomcat Request Execution

Without virtual threads, Tomcat maintains a pool of platform threads (typically capped at 200). When a request arrives, Tomcat assigns it a worker thread. If the service makes a blocking database query, the worker thread is pinned and cannot process other requests.

```
[Request 1] ──► Tomcat Thread Pool Worker 1 ──► [Blocks on DB (1s)] (Worker 1 pinned)
[Request 2] ──► Tomcat Thread Pool Worker 2 ──► [Blocks on DB (1s)] (Worker 2 pinned)
...
[Request 201] ──► Tomcat Thread Pool Exhausted! ──► (Request Queued or Dropped)
```

With `spring.threads.virtual.enabled=true`:
* Tomcat configures its protocol executor to use `Executors.newVirtualThreadPerTaskExecutor()`.
* Every HTTP request runs on a new virtual thread.
* If a request blocks on a database or HTTP call, the virtual thread yields its continuation state, allowing the carrier platform thread to execute other virtual threads.

```
[Request 1] ──► Virtual Thread 1 ──► [Blocks on DB (1s)] (Yields Carrier Thread 1)
[Request 2] ──► Virtual Thread 2 ──► [Blocks on DB (1s)] (Yields Carrier Thread 1)
...
[Request 10,000] ──► Virtual Thread 10,000 ──► (Carrier Thread 1 continues executing other tasks)
```

### Tomcat's Request Dispatching Mechanics: Acceptor/Poller Thread Model

To understand the scalability benefits of virtual threads, we must examine how Tomcat's non-blocking I/O endpoint dispatcher handles requests. Tomcat uses three groups of threads:

1. **Acceptor Threads**:
   - Run in a loop executing socket accept calls: `serverSocket.accept()`.
   - When a client connects, the Acceptor thread accepts the TCP connection and hands the socket channel (`SocketChannel`) to a **Poller Thread**.

2. **Poller Threads**:
   - Maintain an OS-level selector loop (`java.nio.channels.Selector`).
   - Monitor thousands of socket channels for read events. When a client sends HTTP bytes, the selector fires.
   - The Poller thread reads the incoming headers, wraps the socket event in a request execution task, and hands it off to the **Protocol Executor**.

3. **Protocol Executor**:
   - Under standard configuration, this is a bounded platform thread pool (`ThreadPoolExecutor`, default max size 200).
   - If a request task blocks (e.g. executing a database read for 1 second), the pool worker thread is pinned to that request, unable to return to the pool.
   - If 200 concurrent requests block, the pool is saturated. When the Poller thread attempts to dispatch the 201st request task, the executor rejects or queues it, causing client request timeouts even though CPU usage is low.

#### The Virtual Thread Dispatching Workflow

When `spring.threads.virtual.enabled=true` is set:

```
[Client Request] 
      │
      ▼
[Tomcat Acceptor]  ──► (Accepts TCP socket)
      │
      ▼
 [Tomcat Poller]   ──► (Detects read bytes via Selector)
      │
      ▼
[ThreadPerTaskExecutor] ──► Spawns new VThread per request
      │
      ├─► [VThread 1] ──► Blocks on DB ──► Yields carrier thread stack to heap
      ├─► [VThread 2] ──► Blocks on DB ──► Yields carrier thread stack to heap
      └─► [Carrier Threads] remain free to run other tasks or process new requests
```

1. Tomcat customizes the Protocol Executor, wrapping it in `Executors.newVirtualThreadPerTaskExecutor()`.
2. When the Poller thread detects read bytes and submits the task, the executor bypasses the queue and allocates a new virtual thread on the heap for the request.
3. The virtual thread executes the Spring controller lifecycle. When it queries the database or calls a downstream microservice, the driver executes `LockSupport.park()`.
4. The JVM intercepts the park command, pauses the continuation, moves the virtual thread's stack frames to the heap, and frees the carrier thread.
5. The carrier platform thread returns to the ForkJoinPool scheduler. It is immediately available to process other requests or run other active virtual threads.
6. The Tomcat Poller thread remains unblocked and can continue to read socket data, dispatching requests without queue starvation.

### Manual Configuration
If you require custom configurations or are integrating virtual threads into older versions of Spring Boot (pre-3.2), you can define custom beans:

#### 1. Embedded Tomcat Virtual Thread Customizer
```java
import org.apache.coyote.ProtocolHandler;
import org.springframework.boot.web.embedded.tomcat.TomcatProtocolHandlerCustomizer;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import java.util.concurrent.Executors;

@Configuration
public class TomcatVirtualThreadConfig {

    @Bean
    public TomcatProtocolHandlerCustomizer<?> tomcatProtocolHandlerCustomizer() {
        return protocolHandler -> {
            System.out.println("Customizer: Setting Tomcat Executor to Virtual Thread Executor");
            protocolHandler.setExecutor(Executors.newVirtualThreadPerTaskExecutor());
        };
    }
}
```

#### 2. Virtual Thread Executor for `@Async` Tasks
In Spring's async task execution model, methods annotated with `@Async` are dispatched to a task executor bean. We can customize this bean to use virtual threads:

```java
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.task.AsyncTaskExecutor;
import org.springframework.core.task.support.TaskExecutorAdapter;
import org.springframework.scheduling.annotation.EnableAsync;
import java.util.concurrent.Executor;
import java.util.concurrent.Executors;

@Configuration
@EnableAsync
public class AsyncVirtualThreadConfig {

    @Bean(name = "taskExecutor")
    public Executor taskExecutor() {
        // TaskExecutorAdapter adapts standard java.util.concurrent.Executor to Spring AsyncTaskExecutor
        return new TaskExecutorAdapter(Executors.newVirtualThreadPerTaskExecutor());
    }
}
```

#### 3. Virtual Thread Task Scheduler Config
To run `@Scheduled` cron jobs on virtual threads:

```java
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.TaskScheduler;
import org.springframework.scheduling.annotation.EnableScheduling;
import org.springframework.scheduling.concurrent.SimpleAsyncTaskScheduler;

@Configuration
@EnableScheduling
public class ScheduledVirtualThreadConfig {

    @Bean
    public TaskScheduler taskScheduler() {
        SimpleAsyncTaskScheduler scheduler = new SimpleAsyncTaskScheduler();
        scheduler.setVirtualThreads(true);
        scheduler.setThreadNamePrefix("scheduled-vt-");
        return scheduler;
    }
}
```

##### Code Walkthrough: Spring Manual Configurations

1. **Tomcat Protocol Handler Customization**:
   - In `TomcatVirtualThreadConfig`, the method `tomcatProtocolHandlerCustomizer()` declares a customization bean. This interface allows configuration hooks into the embedded Tomcat container.
   - The customizer registers a lambda that receives the Tomcat `ProtocolHandler`.
   - It calls `protocolHandler.setExecutor(Executors.newVirtualThreadPerTaskExecutor())` to override the default platform thread pool with a virtual thread executor.
   - When an HTTP request is received, Tomcat bypasses its internal queue and immediately spawns a new virtual thread, allowing high concurrency with minimal overhead.

2. **Async Task Offloading**:
   - In `AsyncVirtualThreadConfig`, the method defines a bean named `taskExecutor()`. Spring Boot relies on a bean of this name to process methods annotated with `@Async`.
   - It uses Spring's `TaskExecutorAdapter` class. Since Spring's core scheduler API expects an instance of Spring's `AsyncTaskExecutor`, `TaskExecutorAdapter` acts as an adapter, wrapping the standard Java virtual thread executor.
   - When a method with `@Async` is called, Spring runs the method inside a newly spawned virtual thread.

3. **Background Job Scheduling**:
   - In `ScheduledVirtualThreadConfig`, a custom `TaskScheduler` bean is defined to support `@Scheduled` methods (like cron tasks).
   - It instantiates `SimpleAsyncTaskScheduler`, which can execute tasks using a separate thread per execution.
   - It calls `scheduler.setVirtualThreads(true)` to execute each scheduled task inside a virtual thread.
   - It configures the thread name prefix to `"scheduled-vt-"`, helping developers monitor scheduled tasks in JFR or thread dumps.

---

### Spring Data JPA & Connection Pool Sizing
Virtual threads allow you to process thousands of requests concurrently. However, if your service queries a relational database, the database connection pool (like HikariCP) will become the primary bottleneck.

```
[Virtual Threads: 10,000 requests] ──► [HikariCP Connection Pool: max-size = 10] ──► (Blocked Threads waiting for DB connections)
```

**Tuning Guidelines**:
* **Do Not Scale the Pool to Match Thread Count**: Setting the HikariCP pool size to 10,000 will overwhelm the database server's CPU, disk I/O, and memory capacity, crashing the database engine.
* **Size According to Database Capabilities**: Size the connection pool to match the physical core and disk capability of the database server (typically $\text{Pool Size} = (\text{CPU Cores} \times 2) + \text{Disk Spindle Count}$).
* **Limit Concurrency via Semaphores**: Protect the connection pool from exhaustion by using a `Semaphore` in the application layer. Blocked threads will wait in memory as suspended virtual threads with zero carrier thread overhead.

### Connection Pool Wait Queue Starvation & Semaphore Backpressure Mechanics

To understand why scaling the database connection pool to match virtual thread count causes issues, we must analyze the interaction between the connection pool manager, the JVM thread scheduler, and the database engine.

#### 1. Database Engine Resource Exhaustion
A database server (such as PostgreSQL or MySQL) processes queries using operating system processes or platform threads. Each active connection established by a client spawns a corresponding worker thread or processes query locks on the database server.
* If HikariCP is configured with a maximum pool size of 10,000, and 10,000 virtual threads concurrently acquire connections:
  - The database server must manage 10,000 physical connections.
  - The database server’s CPU cores are overwhelmed by context switching, locking contention, and disk write synchronization.
  - The database server's memory is exhausted by connection context allocations, leading to system crashes or severe performance degradation.

#### 2. HikariCP Queue Starvation
HikariCP manages connections using a `ConcurrentBag` structure. When a thread requests a connection, HikariCP first checks if an idle connection is available in its local bag. If not, it enqueues the requesting thread in a synchronization wait queue.
* Under standard platform threads, if the connection wait queue fills up, only 200 threads wait (since Tomcat limits concurrent request handling to 200).
* Under virtual threads, if 10,000 virtual threads request a connection from a pool of size 50, then 9,950 virtual threads are enqueued in the connection pool's internal wait queues.
* Each parked virtual thread waits for a connection. While this is cheap in terms of memory, the wait queues inside the connection pool can experience high contention. If connection duration is slow, many virtual threads will timeout waiting for a connection, throwing exceptions.

#### 3. Resolving Bottlenecks using Semaphore Backpressure
The solution is to decouple request concurrency from database connection concurrency by applying a rate-limiting `Semaphore` in the application layer.

```
                  [VThread Requests: 10,000]
                              │
                              ▼
                [Semaphore: max permits = 50]  ◄── Throttling happens here
                              │
              ┌───────────────┴───────────────┐
              ▼ (Permit Acquired)             ▼ (Permit Unavailable)
     [HikariCP Pool: size = 50]       [VThreads Suspended in Memory]
              │                         (Yields Carrier Threads)
              ▼
    [Database Connection]
```

* **The Safe Flow**:
  - The application instantiates a `Semaphore(50)` (matching or slightly below the database pool size).
  - Before querying the database, the virtual thread must call `semaphore.acquire()`.
  - If 1,000 requests arrive, 50 virtual threads acquire permits and proceed to query HikariCP, immediately obtaining a database connection without queuing.
  - The other 950 virtual threads fail to acquire a permit. They are parked by the JVM. Their stack frames are moved to the heap, and their carrier threads are released to run other tasks.
  - Once a transaction completes, the worker virtual thread releases the semaphore permit in a `finally` block, prompting the JVM to reschedule one of the suspended virtual threads.
  - This keeps the database pool contention low, protects the database engine, and prevents connection acquisition timeouts.

#### Hikari Connection Pool Monitor Service
Below is a utility to monitor Hikari connection pool usage metrics to help identify bottlenecks in high-concurrency systems:

```java
import com.zaxxer.hikari.HikariDataSource;
import com.zaxxer.hikari.HikariMXBean;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

import javax.sql.DataSource;

@Service
public class HikariPoolMonitor {

    private final HikariDataSource dataSource;

    @Autowired
    public HikariPoolMonitor(DataSource dataSource) {
        if (dataSource instanceof HikariDataSource) {
            this.dataSource = (HikariDataSource) dataSource;
        } else {
            this.dataSource = null;
        }
    }

    @Scheduled(fixedRate = 1000)
    public void reportPoolMetrics() {
        if (dataSource != null) {
            HikariMXBean mxBean = dataSource.getHikariPoolMXBean();
            if (mxBean != null) {
                System.out.printf("Hikari Metrics -> Active Connections: %d | Idle: %d | Threads Awaiting Connection: %d%n",
                        mxBean.getActiveConnections(),
                        mxBean.getIdleConnections(),
                        mxBean.getThreadsAwaitingConnection());
            }
        }
    }
}
```

#### Database Blocking Mitigation: Throttled Data Source Wrapper
To guarantee that virtual threads do not crash the connection pool under sudden spikes in load, we can construct a throttled `DataSource` wrapper that controls access to connection acquisition:

```java
import java.io.PrintWriter;
import java.sql.Connection;
import java.sql.SQLException;
import java.sql.SQLFeatureNotSupportedException;
import java.util.concurrent.Semaphore;
import java.util.logging.Logger;
import javax.sql.DataSource;

/**
 * A decorator DataSource that uses a Semaphore to limit the number of concurrent
 * database connection requests. This prevents connection timeouts under heavy virtual thread load.
 */
public class ThrottledDataSource implements DataSource {

    private final DataSource delegate;
    private final Semaphore semaphore;

    public ThrottledDataSource(DataSource delegate, int maxConcurrentConnections) {
        this.delegate = delegate;
        this.semaphore = new Semaphore(maxConcurrentConnections);
    }

    @Override
    public Connection getConnection() throws SQLException {
        try {
            // Blocks the calling virtual thread if all connection permits are taken.
            // Under virtual threads, this blocking yields the carrier thread, preserving resources.
            semaphore.acquire();
            Connection connection = delegate.getConnection();
            // Wrap connection to release permit on close
            return new ThrottledConnection(connection, semaphore);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new SQLException("Interrupted while waiting for a database connection slot", e);
        }
    }

    @Override
    public Connection getConnection(String username, String password) throws SQLException {
        try {
            semaphore.acquire();
            Connection connection = delegate.getConnection(username, password);
            return new ThrottledConnection(connection, semaphore);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new SQLException("Interrupted while waiting for a database connection slot", e);
        }
    }

    // Delegate methods
    @Override public PrintWriter getLogWriter() throws SQLException { return delegate.getLogWriter(); }
    @Override public void setLogWriter(PrintWriter out) throws SQLException { delegate.setLogWriter(out); }
    @Override public void setLoginTimeout(int seconds) throws SQLException { delegate.setLoginTimeout(seconds); }
    @Override public int getLoginTimeout() throws SQLException { return delegate.getLoginTimeout(); }
    @Override public Logger getParentLogger() throws SQLFeatureNotSupportedException { return delegate.getParentLogger(); }
    @Override public <T> T unwrap(Class<T> iface) throws SQLException { return delegate.unwrap(iface); }
    @Override public boolean isWrapperFor(Class<?> iface) throws SQLException { return delegate.isWrapperFor(iface); }
}

class ThrottledConnection implements Connection {
    private final Connection delegate;
    private final Semaphore semaphore;
    private boolean closed = false;

    public ThrottledConnection(Connection delegate, Semaphore semaphore) {
        this.delegate = delegate;
        this.semaphore = semaphore;
    }

    @Override
    public void close() throws SQLException {
        if (!closed) {
            try {
                delegate.close();
            } finally {
                closed = true;
                semaphore.release(); // Return permit to the throttler
            }
        }
    }

    // Delegate remaining Connection methods...
    @Override public void commit() throws SQLException { delegate.commit(); }
    @Override public void rollback() throws SQLException { delegate.rollback(); }
    @Override public boolean isClosed() throws SQLException { return delegate.isClosed(); }
    @Override public void setAutoCommit(boolean autoCommit) throws SQLException { delegate.setAutoCommit(autoCommit); }
    @Override public boolean getAutoCommit() throws SQLException { return delegate.getAutoCommit(); }
}
```

##### Code Walkthrough: `ThrottledDataSource`
1. **Permit Acquisition Throttling**:
   - In `ThrottledDataSource`, when the service layer calls `getConnection()`, the code runs `semaphore.acquire()`. If all connection permits are allocated, the calling thread blocks.
   - If the caller is a virtual thread, it yields its carrier thread. This prevents connection timeouts and carrier thread exhaustion.
2. **Decorator Injection**:
   - The database driver retrieves the physical connection using the wrapped `delegate.getConnection()`.
3. **Automatic Resource Release**:
   - The connection is returned inside a decorator `ThrottledConnection`.
   - When the transaction finishes and calls `close()`, `ThrottledConnection` closes the underlying delegate connection, then calls `semaphore.release()`. This returns the permit to the semaphore, preventing resource leaks.

---

### Spring WebFlux: Event Loop Offloading & Event Loop Bypass Internals

Spring WebFlux is built around non-blocking event loop engines (usually Netty). The primary rule of reactive architectures is: **Never block the event loop**. If an event loop thread is blocked (e.g., by a legacy blocking driver or a complex CPU calculation), Netty cannot process any incoming requests, freezing the application.

#### Netty's Selector Loop & The Blocking Freeze
Netty processes network traffic using a small pool of platform threads called **Event Loops** (typically $2 \times \text{CPU Cores}$). Each event loop thread runs in an infinite selector loop, waiting for channel events (like read, write, accept).
* When an HTTP request arrives, Netty's event loop parses the HTTP bytes, invokes the reactive handler pipeline, and expects the method to return a publisher (`Flux`/`Mono`) immediately.
* If a database query or legacy SOAP client blocks (e.g. blocking the thread for 250ms) directly inside the handler executing on the Netty event loop thread, the selector loop is frozen.
* While frozen, Netty cannot process TCP packets for *any other* connection mapped to that event loop. Incoming requests are buffered in the OS TCP backlog queue, eventually causing packet drops and timeouts.

#### Offloading to Virtual Threads via `publishOn`
With virtual threads, we can easily bypass reactive stream complexity and safely offload blocking queries without event loop starvation:

```
[Netty Event Loop (Channel read)] 
             │
             ▼
[Mono.fromCallable() pipeline]
             │
             ▼  (.publishOn(vtScheduler))
[Enqueue task in Virtual Thread Queue] ──► (Netty Event Loop returns to selector loop)
             │
             ▼
[Virtual Thread spawned on Carrier]
             │
             ▼
[Blocking JDBC Driver Call] ──► (Yields Continuation context to heap)
             │
             ▼ (Database ready event)
[Remounted on Carrier Thread] ──► (Returns response stream to Netty loop)
```

1. We wrap the blocking call inside a `Mono.fromCallable()` segment.
2. We declare a Project Reactor `Scheduler` adapted from `Executors.newVirtualThreadPerTaskExecutor()`.
3. By invoking `.publishOn(vtScheduler)`, we instruct Project Reactor to execute all downstream operators on the virtual thread scheduler.
4. When the request is processed, the Netty event loop thread enqueues the execution task in the virtual thread executor's queue and immediately returns to its socket selector loop.
5. A carrier thread fetches the task, mounts the virtual thread, and executes the blocking call.
6. When the JDBC driver blocks on I/O, the virtual thread's continuation yields, and the carrier thread is returned to the ForkJoinPool scheduler. Netty event loops are kept completely free, retaining network scalability.

#### Event Loop Bypass Handler Code

Below is a WebFlux service configuration demonstrating how to offload blocking tasks to virtual threads using Project Reactor's scheduler bindings:

```java
import org.springframework.stereotype.Service;
import reactor.core.publisher.Mono;
import reactor.core.scheduler.Scheduler;
import reactor.core.scheduler.Schedulers;
import java.util.concurrent.Executors;

@Service
public class ReactiveOffloadingService {

    // Instantiating a Project Reactor Scheduler wrapper around a Virtual Thread Executor
    private final Scheduler vtScheduler = Schedulers.fromExecutor(
            Executors.newVirtualThreadPerTaskExecutor()
    );

    public Mono<String> processWebFluxRequest(String param) {
        return Mono.fromCallable(() -> performLegacyBlockingCall(param))
                // Offloads the execution from Netty event loop threads to virtual threads
                .publishOn(vtScheduler); 
    }

    private String performLegacyBlockingCall(String param) throws InterruptedException {
        // Simulate a legacy blocking call (e.g. SOAP call or JDBC query)
        Thread.sleep(200); 
        return "Processed: " + param;
    }
}
```

##### Code Walkthrough: `ReactiveOffloadingService`
1. **Scheduler Instantiation**:
   - We construct `vtScheduler` using `Schedulers.fromExecutor(Executors.newVirtualThreadPerTaskExecutor())`. This bridges the reactive scheduling API with modern Java's virtual thread manager.
2. **Callable Wrap**:
   - We wrap the blocking logic inside `Mono.fromCallable()`. When first subscribed to, this logic runs on the calling thread.
3. **Reactive Offloading**:
   - By invoking `.publishOn(vtScheduler)`, we instruct Project Reactor to dispatch the execution of the callback downstream (including the blocking `performLegacyBlockingCall`) onto our virtual thread scheduler.
   - The Netty event loop thread is immediately released to handle other incoming TCP connections and network packets, preventing event loop starvation.

---

#### Async Controller Parallel Database Calls Example
Below is a REST controller demonstrating fanning out to parallel database queries using `CompletableFuture` backed by virtual threads:

```java
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.Executor;
import java.util.concurrent.Executors;

@RestController
public class ParallelDbController {

    private final Executor vtExecutor = Executors.newVirtualThreadPerTaskExecutor();

    @GetMapping("/db-parallel")
    public CompletableFuture<String> fetchParallelDetails() {
        // Run database queries concurrently on virtual threads
        CompletableFuture<String> userTask = CompletableFuture.supplyAsync(this::queryUserDb, vtExecutor);
        CompletableFuture<String> orderTask = CompletableFuture.supplyAsync(this::queryOrderDb, vtExecutor);

        return userTask.thenCombine(orderTask, (user, order) -> 
            "Result: [User: " + user + ", Order: " + order + "]"
        );
    }

    private String queryUserDb() {
        try { Thread.sleep(100); } catch (InterruptedException e) { Thread.currentThread().interrupt(); }
        return "UserData";
    }

    private String queryOrderDb() {
        try { Thread.sleep(150); } catch (InterruptedException e) { Thread.currentThread().interrupt(); }
        return "OrderData";
    }
}
```

##### Code Walkthrough: `ParallelDbController`

1. **Non-Blocking Parallel Forking**:
   - In `ParallelDbController`, the REST controller instantiates a virtual thread per task executor: `vtExecutor = Executors.newVirtualThreadPerTaskExecutor()`.
   - When the `/db-parallel` endpoint is called, it submits two database queries concurrently using `CompletableFuture.supplyAsync()`.
   - The tasks `queryUserDb` and `queryOrderDb` execute concurrently in two separate virtual threads.

2. **Asynchronous Hand-Off**:
   - The controller method returns `CompletableFuture<String>` directly to the Spring MVC container.
   - Returning a future tells Spring that the HTTP request is asynchronous. The container releases the Tomcat request thread back to Tomcat's pool immediately, so the server can accept more connections.

3. **Yielding Carrier Threads**:
   - Inside `queryUserDb()` and `queryOrderDb()`, the query operations block the executing virtual threads (using `Thread.sleep()`).
   - Rather than blocking a physical thread, the virtual threads yield their carrier threads. The carrier threads are released to run other active tasks.
   - When the queries complete, the virtual threads are rescheduled, they resolve their futures, and the `thenCombine()` callback compiles the result, returning the response.

---

### WebClient vs. RestTemplate/RestClient under Project Loom

#### The Core Dilemma: Imperative Simplicity vs. Reactive Streams
With the finalization of Project Loom (Virtual Threads), developers face an architectural decision: *Should we continue using Spring WebFlux's non-blocking `WebClient`, or should we migrate back to the simpler, imperative `RestTemplate` (or the newer `RestClient`)?*

Historically, `WebClient` was introduced because blocking platform threads inside `RestTemplate` limited scalability. Under Virtual Threads, however, blocking operations are cheap because they yield the carrier thread. To make the correct choice, we must analyze the internal mechanics of both clients.

#### 1. Concurrency Models under Virtual Threads
* **RestTemplate / RestClient (Synchronous Blocking)**:
  - Each remote call executes synchronously inside the calling virtual thread.
  - The client makes a socket read or write call, delegating to Java's modern Socket implementation (`NioSocketImpl`).
  - When the socket blocks waiting for network packets, the virtual thread's continuation yields control.
  - The underlying platform carrier thread is detached and returned to Tomcat's scheduler.
  - The virtual thread remains suspended on the heap until the OS network card notifies the JVM selector loop that data is available.
  - *Pros*: Simple code, linear stack traces, standard try-catch exceptions, and ScopedValues/ThreadLocals are preserved naturally.
  - *Cons*: Risk of carrier thread pinning if the underlying HTTP client library uses legacy `synchronized` blocks (e.g., older versions of Apache HttpClient).

* **WebClient (Reactive Non-Blocking)**:
  - Built on Netty's event loop architecture.
  - When a virtual thread invokes `WebClient`, the request is handed off to Netty's event loop threads (which are platform threads).
  - The calling virtual thread does not block on socket I/O; Netty manages the socket connections asynchronously using OS-level selectors (`epoll` or `kqueue`).
  - If we call `.block()` on the WebClient publisher inside a virtual thread, the virtual thread is parked using `LockSupport.park()`.
  - Netty processes the response bytes in its event loop. Once Netty finishes parsing the HTTP payload, it publishes the data and triggers `LockSupport.unpark()` on the virtual thread.
  - *Pros*: Optimized socket management, native streaming support (Server-Sent Events), advanced retry/backpressure mechanisms, and zero pinning risk.
  - *Cons*: Netty's event loops are still platform threads. If you execute heavy CPU work or JSON parsing inside WebClient's reactive callbacks (like `.map()`), you block the Netty event loops, starving other connections. Complex reactive APIs make debugging difficult, and context propagation (like Scoped Values) requires specialized reactive subscriber context bindings.

#### 2. Architectural Comparison: RestTemplate vs. WebClient
Let's compare the runtime behavior of both HTTP clients under virtual threads:

| Criterion | RestTemplate / RestClient | WebClient (with `.block()`) |
| :--- | :--- | :--- |
| **API Style** | Imperative, synchronous | Reactive, functional |
| **Threading Model** | Virtual-thread-per-request | Netty event loops (platform) + Virtual Thread parking |
| **Stack Trace Complexity** | Minimal (linear call stack) | High (deep reactive chain) |
| **Context Propagation** | Inherited naturally | Requires reactive context adapters |
| **Streaming / SSE** | Poor (entire payload buffered) | Excellent (native streaming) |
| **Pinning Risk** | High (if using legacy HTTP libraries) | None (uses Netty NIO selector loops) |
| **Memory Allocation** | Medium (spawns stack frames on heap) | High (reactor operators, publishers, mappings) |

#### 3. Tomcat NioEndpoint Reactor Loops & Task Executor Proxies
To trace how Spring Boot and Tomcat coordinate virtual threads and request interception, let's look at the class hierarchy:

1. **`org.apache.tomcat.util.net.NioEndpoint`**:
   - Tomcat's network socket layer uses `NioEndpoint` to handle non-blocking TCP socket channels.
   - It runs an internal `Acceptor` thread to accept connections.
   - It assigns sockets to a `Poller` thread which uses a Java NIO `Selector` to monitor connections.
   - When HTTP request headers are fully read, Tomcat's `NioEndpoint.SocketProcessor` executes the task.
   - When virtual threads are enabled, Tomcat wraps its request executor in `Executors.newVirtualThreadPerTaskExecutor()`, spawning a new virtual thread to run the servlet and Spring MVC handler mapping.

2. **Spring Task Executor Proxies**:
   - When a Spring bean annotated with `@Async` is called, Spring intercepts the call using a dynamic proxy wrapper.
   - The interceptor (`AsyncExecutionInterceptor`) retrieves the configured `Executor` bean (such as `TaskExecutorAdapter` wrapping a virtual thread executor).
   - The proxy wraps the target method invocation inside a `Runnable` and submits it to the virtual thread executor.
   - This ensures that transactions, security scopes (like Spring Security's `SecurityContext`), and other thread-bound resources are propagated to the newly spawned virtual thread.

Let's illustrate the execution flow of `WebClient` vs. `RestTemplate` in a diagram:

```
=== RestTemplate / RestClient Workflow ===
[VThread Request] ──► RestTemplate ──► NioSocketImpl ──► Socket Write (epoll/kqueue)
                                                                 │
                                                   (VThread yields carrier thread)
                                                                 │
[Carrier Thread] ◄── Rescheduled ◄── OS Socket Ready ◄───────────┘

=== WebClient Workflow ===
[VThread Request] ──► WebClient ──► Netty Event Loop Thread ──► Event Loop processes TCP I/O
                            │
              (VThread parks via park())
                            │
[Carrier Thread] ◄── unpark() callback ◄── Netty parses JSON/payload ──► OS Socket Ready
```

#### 4. Production-Ready Spring HTTP Client Comparison
Below is a REST controller demonstrating the coexistence of both approaches under virtual threads. The `RestClient` implementation is configured to use the modern, non-pinning `JdkClientHttpRequestFactory`, and the `WebClient` implementation includes proper timeout handling and reactive scheduling:

```java
package com.example.concurrency;

import org.springframework.boot.web.client.RestTemplateBuilder;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

import java.time.Duration;
import java.net.http.HttpClient;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.Executor;
import java.util.concurrent.Executors;

@Configuration
class HttpClientConfig {

    /**
     * Build RestTemplate using JDK's native HttpClient request factory.
     * This avoids pinning carrier threads because java.net.http.HttpClient
     * is fully adapted for virtual threads under the hood.
     */
    @Bean
    public RestTemplate jdkRestTemplate(RestTemplateBuilder builder) {
        HttpClient httpClient = HttpClient.newBuilder()
                .connectTimeout(Duration.ofSeconds(2))
                .build();
        return builder
                .requestFactory(() -> new JdkClientHttpRequestFactory(httpClient))
                .build();
    }

    @Bean
    public RestClient restClient(RestTemplate restTemplate) {
        return RestClient.create(restTemplate);
    }

    @Bean
    public WebClient webClient() {
        return WebClient.builder()
                .baseUrl("https://api.chucknorris.io")
                .build();
    }
}

@RestController
@RequestMapping("/api/http-compare")
public class HttpClientCompareController {

    private final RestClient restClient;
    private final WebClient webClient;
    private final Executor vtExecutor = Executors.newVirtualThreadPerTaskExecutor();

    public HttpClientCompareController(RestClient restClient, WebClient webClient) {
        this.restClient = restClient;
        this.webClient = webClient;
    }

    /**
     * Executes external API request using synchronous RestClient.
     * The executing virtual thread yields during network I/O, preventing
     * carrier thread blocks without needing reactive structures.
     */
    @GetMapping("/rest-client")
    public String executeViaRestClient() {
        return restClient.get()
                .uri("https://api.chucknorris.io/jokes/random")
                .retrieve()
                .body(String.class);
    }

    /**
     * Executes external API request using WebClient, blocking the virtual thread.
     * The virtual thread is parked while Netty runs the network client loop,
     * showing how to consume reactive APIs safely from virtual thread handlers.
     */
    @GetMapping("/web-client")
    public String executeViaWebClient() {
        Mono<String> responseMono = webClient.get()
                .uri("/jokes/random")
                .retrieve()
                .bodyToMono(String.class)
                .timeout(Duration.ofSeconds(3));

        // block() parks the virtual thread, yielding its carrier thread to the pool.
        // Once Netty signals completion, the virtual thread is unparked and continues.
        return responseMono.block();
    }

    /**
     * Executes parallel HTTP requests concurrently using RestClient and CompletableFuture.
     */
    @GetMapping("/parallel")
    public CompletableFuture<String> executeParallel() {
        CompletableFuture<String> callOne = CompletableFuture.supplyAsync(
                () -> restClient.get().uri("https://api.chucknorris.io/jokes/random").retrieve().body(String.class),
                vtExecutor
        );

        CompletableFuture<String> callTwo = CompletableFuture.supplyAsync(
                () -> restClient.get().uri("https://api.chucknorris.io/jokes/random").retrieve().body(String.class),
                vtExecutor
        );

        return callOne.thenCombine(callTwo, (res1, res2) -> 
            "{\"callOne\":" + res1 + ",\"callTwo\":" + res2 + "}"
        );
    }
}
```

##### Code Walkthrough: HTTP Client Comparison

1. **`JdkClientHttpRequestFactory` Injection**:
   - In `HttpClientConfig`, the configuration builds a `RestTemplate` using `JdkClientHttpRequestFactory`.
   - By default, standard RestTemplate uses Java's older HTTP client, which blocks standard sockets. To ensure maximum compatibility and zero pinning on JDK 21/25, we override the client factory to use `java.net.http.HttpClient` via `JdkClientHttpRequestFactory`.
   - The JDK `HttpClient` relies on virtual thread-friendly park/unpark semantics rather than raw synchronized blocks.

2. **WebClient Blocking Mechanics**:
   - In `HttpClientCompareController.executeViaWebClient()`, the request executes a `webClient.get()` call. Since WebClient is reactive, it returns a `Mono<String>` immediately.
   - The code calls `responseMono.block()` inside the controller execution path.
   - Under standard WebFlux, calling `.block()` in the event loop thread causes an `IllegalStateException`.
   - However, since this controller runs on Tomcat configured with virtual threads, the calling thread is a virtual thread. The Reactor framework detects this and parks the virtual thread using `LockSupport.park()`.
   - The Netty event loop thread continues to run, reads the HTTP socket bytes, parses the payload, and calls `LockSupport.unpark()` to reschedule our virtual thread.
   - The carrier thread is returned to Tomcat's ForkJoinPool immediately when parked, ensuring no carrier threads are frozen.

3. **Concurrency Fan-out**:
   - In `executeParallel()`, the method forks two concurrent tasks using `CompletableFuture.supplyAsync()` passed with `vtExecutor`.
   - Both HTTP calls are executed in parallel on two separate virtual threads, and both block waiting for network sockets.
   - The carrier threads are yielded and remain available to execute other incoming requests. Once both HTTP responses arrive, the results are merged and returned, illustrating a clean, non-reactive way to execute concurrent HTTP calls.

---

## 2. Quarkus Integration

Quarkus uses **Vert.x** as its core reactive event-loop engine. In a reactive system, blocking the event loop is unacceptable. Quarkus addresses this by integrating virtual threads directly with Vert.x, offloading blocking operations from event loops to virtual threads.

### Configuration
To configure the framework to support virtual thread resource managers globally:

```properties
# application.properties
quarkus.virtual-threads.enabled=true
```

### `@RunOnVirtualThread`
To execute a REST endpoint or CDI bean method on a virtual thread, annotate it with `@RunOnVirtualThread`. This offloads execution from the Vert.x event loop:

```java
import io.smallrye.common.annotation.RunOnVirtualThread;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.MediaType;

@Path("/quarkus-vt")
public class QuarkusResource {

    @GET
    @RunOnVirtualThread // Executed on a lightweight virtual thread
    @Produces(MediaType.TEXT_PLAIN)
    public String handleRequest() {
        // Safe to execute blocking operations here without blocking Vert.x event loop
        performBlockingNetworkCall();
        return "Processed on " + Thread.currentThread().toString();
    }

    private void performBlockingNetworkCall() {
        try { Thread.sleep(200); } catch (InterruptedException e) { Thread.currentThread().interrupt(); }
    }
}
```

### Reactive Integration: Mutiny Uni
When utilizing reactive client libraries (such as SmallRye Mutiny), you can await results on virtual threads without block-starvation concerns:

```java
import io.smallrye.common.annotation.RunOnVirtualThread;
import io.smallrye.mutiny.Uni;
import jakarta.inject.Inject;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.Path;
import java.time.Duration;

@Path("/quarkus-reactive-vt")
public class QuarkusReactiveVtResource {

    @Inject
    ReactiveHelloService helloService;

    @GET
    @RunOnVirtualThread
    public String getReactiveResult() {
        // Wait on the virtual thread for the reactive stream item
        return helloService.fetchMessage()
                .await()
                .atMost(Duration.ofSeconds(2));
    }
}

class ReactiveHelloService {
    public Uni<String> fetchMessage() {
        return Uni.createFrom().item("Hello from Quarkus Reactive Uni")
                .onItem().delayIt().by(Duration.ofMillis(100));
    }
}
```

##### Code Walkthrough: Quarkus Virtual Thread Resources

1. **Quarkus Standard Resource Routing**:
   - The class `QuarkusResource` is annotated with JAX-RS path `@Path("/quarkus-vt")`. Under Quarkus defaults, endpoints are processed directly on Netty's reactive event loop.
   - The method is annotated with `@RunOnVirtualThread`.
   - When a client issues a GET request, Quarkus intercepts the invocation, takes it off the Netty event loop thread, and executes the body of `handleRequest()` inside a newly allocated virtual thread.
   - The call to `performBlockingNetworkCall()` executes `Thread.sleep(200)`. Because it is executing on a virtual thread, the thread yields the carrier thread, allowing Netty to process other network packets.

2. **Reactive and Imperative Bridging**:
   - The endpoint `/quarkus-reactive-vt` in `QuarkusReactiveVtResource` is annotated with `@RunOnVirtualThread`.
   - The method executes `helloService.fetchMessage()`, which returns a Mutiny reactive stream object `Uni<String>`.
   - Instead of subscribing with callback hooks (like `subscribe().with(...)`), the virtual thread calls Mutiny's blocking retrieval: `.await().atMost(Duration.ofSeconds(2))`.
   - The thread blocks until the Uni completes. Because this thread is a virtual thread, blocking is lightweight and has no platform-level thread resource cost. This allows developers to consume reactive libraries using simple, imperative, blocking style.

---

## 3. Jakarta EE Integration

Jakarta Concurrency 3.1 (introduced in Jakarta EE 11) provides built-in support for virtual threads using standard configurations.

### Configuration via Annotations
You can define a virtual-thread-backed executor using the `@ManagedExecutorDefinition` annotation by setting `virtual = true`:

```java
import jakarta.enterprise.concurrent.ManagedExecutorDefinition;
import jakarta.enterprise.concurrent.ManagedExecutorService;
import jakarta.inject.Inject;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.MediaType;
import java.util.concurrent.ExecutionException;

@ManagedExecutorDefinition(
    name = "java:module/concurrent/virtual-executor",
    qualifiers = VirtualExecutor.class,
    virtual = true // Enables virtual threads for this Managed Executor
)
@Path("/jakarta-vt")
public class JakartaResource {

    @Inject
    @VirtualExecutor
    private ManagedExecutorService executor;

    @GET
    @Produces(MediaType.TEXT_PLAIN)
    public String executeTask() throws ExecutionException, InterruptedException {
        return executor.submit(() -> {
            return "Executed task on: " + Thread.currentThread().toString();
        }).get();
    }
}
```

##### Code Walkthrough: `JakartaResource`

1. **Managed Executor Declaration**:
   - In `JakartaResource`, the class is annotated with `@ManagedExecutorDefinition`. This declares a concurrent executor resource managed directly by the Jakarta EE container.
   - The JNDI name is configured as `"java:module/concurrent/virtual-executor"`.
   - The key configuration is `virtual = true` (finalized in Jakarta Concurrency 3.1). This tells the application server (such as Open Liberty or WildFly) to allocate virtual threads when executing tasks submitted to this executor.
   - The qualifier is set to `VirtualExecutor.class` to bind standard CDI injections.

2. **Resource Injection**:
   - Inside `JakartaResource`, a `ManagedExecutorService` field is annotated with `@Inject` and `@VirtualExecutor`.
   - The CDI container matches the qualifiers and injects the virtual-thread-backed managed executor.

3. **Task Submission**:
   - The endpoint executes `executor.submit(...)`.
   - The container spawns a new virtual thread, runs the callback, prints the current thread's name, and returns the response.
   - The JAX-RS handler thread blocks on the return of `Future.get()`. If the handler is executing on a virtual thread, it yields the carrier thread, guaranteeing high efficiency across the application stack.

---

### Qualified Injection Binder Interface
To map the qualifier bean to the defined executor, you declare an interface qualifier:

```java
import java.lang.annotation.Retention;
import java.lang.annotation.Target;
import jakarta.inject.Qualifier;
import static java.lang.annotation.ElementType.*;
import static java.lang.annotation.RetentionPolicy.RUNTIME;

@Qualifier
@Retention(RUNTIME)
@Target({METHOD, FIELD, PARAMETER, TYPE})
public @interface VirtualExecutor {}
```

---

## 4. General Production Best Practices

1. **Replace Bounded Thread Pools**: Remove fixed pools (`Executors.newFixedThreadPool()`) for I/O-bound tasks and replace them with `Executors.newVirtualThreadPerTaskExecutor()`.
2. **Maintain Connection Limits**: Do not scale database connection pool sizes to match the number of virtual threads. Use semaphores or rate limiters.
3. **Use Semaphores for Throttling**: Bounding concurrency protects backend APIs:
   ```java
   private final Semaphore rateLimiter = new Semaphore(10); // Max 10 concurrent HTTP calls
   ```
4. **Avoid Synchronized Blocks**: Replace `synchronized` blocks wrapping long-running I/O calls with `ReentrantLock` to prevent carrier thread pinning.
5. **Profile with Java Flight Recorder (JFR)**: Check for pinning events (`jdk.VirtualThreadPinned`) in your application by starting a recording:
   ```bash
   java -XX:StartFlightRecording=filename=vt_rec.jfr,settings=profile -jar app.jar
   ```

---

## 5. Hands-On Labs

### Lab 7.1 — Spring Boot with Virtual Threads
**Objective**: Build a Spring Boot REST controller exposing sequential and parallel endpoints utilizing virtual threads, and measure performance differences.

```java
package com.example.demo;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;
import java.time.Duration;
import java.time.Instant;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.Executor;
import java.util.concurrent.Executors;

@SpringBootApplication
public class Lab71Application {
    public static void main(String[] args) {
        SpringApplication.run(Lab71Application.class, args);
    }
}

@RestController
class BenchmarkController {

    private final Executor vtExecutor = Executors.newVirtualThreadPerTaskExecutor();

    // 1. Sequential execution (Blocks Tomcat thread sequentially)
    @GetMapping("/sequential")
    public String getSequential() {
        Instant start = Instant.now();
        String service1 = callSlowService("Service-1", 1000);
        String service2 = callSlowService("Service-2", 1000);
        long elapsed = Duration.between(start, Instant.now()).toMillis();
        return "Sequential Result: [" + service1 + ", " + service2 + "] in " + elapsed + "ms";
    }

    // 2. Parallel execution using virtual threads
    @GetMapping("/parallel")
    public String getParallel() throws Exception {
        Instant start = Instant.now();
        CompletableFuture<String> task1 = CompletableFuture.supplyAsync(() -> callSlowService("Service-1", 1000), vtExecutor);
        CompletableFuture<String> task2 = CompletableFuture.supplyAsync(() -> callSlowService("Service-2", 1000), vtExecutor);

        CompletableFuture.allOf(task1, task2).join();
        long elapsed = Duration.between(start, Instant.now()).toMillis();
        return "Parallel Result: [" + task1.get() + ", " + task2.get() + "] in " + elapsed + "ms";
    }

    private String callSlowService(String name, long delay) {
        try {
            Thread.sleep(delay);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
        return name + "Response";
    }
}
```

#### Step-by-Step Walkthrough: `Lab71Application`

1. **Bootstrap and Executor Mapping**:
   - The Spring Boot application starts.
   - Inside `BenchmarkController`, we manually create a virtual thread per task executor: `vtExecutor = Executors.newVirtualThreadPerTaskExecutor()`.
   - When requests hit `/sequential`, the code invokes `callSlowService` sequentially on the HTTP request handler thread.
   - The thread blocks on each call for 1000ms, resulting in a total elapsed time of $\approx 2000$ms.

2. **Parallel Task Forking with CompletableFuture**:
   - When requests hit `/parallel`, the handler thread executes `CompletableFuture.supplyAsync()` twice, passing the queries and our virtual thread executor.
   - Two separate virtual threads are spawned. Each virtual thread calls `callSlowService()`.
   - The threads block concurrently on `Thread.sleep(1000)`. Because they run concurrently, the actual blocking occurs in parallel, and both threads finish after $\approx 1000$ms.
   - The code calls `CompletableFuture.allOf(task1, task2).join()`, which blocks the handler thread until both virtual threads have completed, resulting in a total elapsed time of $\approx 1000$ms.

3. **Under the Hood Tomcat Thread Release**:
   - If `spring.threads.virtual.enabled=true` is enabled, the Tomcat request handler thread itself is a virtual thread.
   - Calling `join()` on the `CompletableFuture` blocks this virtual handler thread.
   - The virtual thread yields its carrier thread, allowing the CPU to execute other tasks during the 1-second sleep delay, maximizing throughput.

---

### Lab 7.2 — Quarkus `@RunOnVirtualThread`
**Objective**: Create a Quarkus endpoint annotated with `@RunOnVirtualThread` that forks three concurrent REST service requests using Java’s `HttpClient`.

```java
package org.acme;

import io.smallrye.common.annotation.RunOnVirtualThread;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.MediaType;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.Executor;
import java.util.concurrent.Executors;

@Path("/quarkus-benchmark")
public class QuarkusLabResource {

    private final HttpClient httpClient = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(5))
            .build();
            
    private final Executor vtExecutor = Executors.newVirtualThreadPerTaskExecutor();

    @GET
    @RunOnVirtualThread // Runs the coordinator on a virtual thread
    @Produces(MediaType.APPLICATION_JSON)
    public List<String> processParallelApiRequests() {
        System.out.println("Coordinator running on: " + Thread.currentThread());

        CompletableFuture<String> req1 = CompletableFuture.supplyAsync(() -> fetchUri("https://httpbin.org/delay/1"), vtExecutor);
        CompletableFuture<String> req2 = CompletableFuture.supplyAsync(() -> fetchUri("https://httpbin.org/delay/1"), vtExecutor);
        CompletableFuture<String> req3 = CompletableFuture.supplyAsync(() -> fetchUri("https://httpbin.org/delay/1"), vtExecutor);

        // Blocks virtual thread without pinning the event loop
        return CompletableFuture.allOf(req1, req2, req3)
                .thenApply(v -> List.of(req1.join(), req2.join(), req3.join()))
                .join();
    }

    private String fetchUri(String url) {
        try {
            HttpRequest request = HttpRequest.newBuilder().uri(URI.create(url)).GET().build();
            HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
            return "Status: " + response.statusCode();
        } catch (Exception e) {
            return "Error: " + e.getMessage();
        }
    }
}
```

#### Step-by-Step Walkthrough: `QuarkusLabResource`

1. **Endpoint Routing and Virtual Thread Assignment**:
   - The REST endpoint is exposed at JAX-RS path `/quarkus-benchmark`.
   - The class method `processParallelApiRequests` is annotated with `@RunOnVirtualThread`.
   - When an HTTP client hits this route, Quarkus routes the request to a virtual thread. The print statement validates that the executor assigned is a virtual thread.

2. **Concurrent Request Forking using CompletableFuture**:
   - Inside the method, the code spawns three asynchronous operations (`req1`, `req2`, `req3`) to query the external HTTP benchmark service `https://httpbin.org/delay/1` (which introduces a 1-second delay).
   - These requests run concurrently on separate virtual threads using `vtExecutor`.
   - The HTTP calls are initiated using Java's standard `HttpClient` (`httpClient.send()`).

3. **Yielding and Rescheduling inside HttpClient**:
   - Java's standard `HttpClient` is designed to be virtual-thread-aware. When it performs a blocking socket write/read, the executing virtual thread yields the carrier thread, allowing other requests to run.
   - The code joins the three futures: `CompletableFuture.allOf(...)`.
   - The coordinator virtual thread blocks at the `join()` call, yielding its carrier thread.
   - Once all three requests complete, the virtual thread is rescheduled, reads the results via `req.join()`, compiles the list, and returns the response. The Vert.x event loop is never blocked, maintaining high reactivity.

---

### Lab 7.3 — Configuration Comparison

#### Spring Boot 3.2+ Configuration
```properties
# application.properties
spring.threads.virtual.enabled=true
```

#### Quarkus Configuration
```properties
# application.properties
quarkus.virtual-threads.enabled=true
```

#### Jakarta EE 11 Configuration (Open Liberty)
```xml
<!-- server.xml -->
<featureManager>
    <feature>jakartaEE-11.0</feature>
    <feature>concurrent-3.1</feature>
</featureManager>

<!-- Managed Executor configured to run tasks using virtual threads -->
<managedExecutor id="virtualExecutor" jndiName="java:module/concurrent/virtual-executor">
    <concurrencyPolicy virtual="true" />
</managedExecutor>
```

---

## 6. Pitfalls & Knowledge Check

### Deep Dive: Database Connection Pool (HikariCP) Management and Sizing under Virtual Threads

While Project Loom allows applications to spawn millions of virtual threads, it does not scale the database. Databases are bounded by physical resources: CPU cores, disk I/O, lock contention, and the size of their connection pools. Transitioning to virtual threads changes how connection pools (such as **HikariCP**) behave, introducing performance risks.

#### 1. How HikariCP Works Internally (The ConcurrentBag)
To understand connection pool bottlenecks under Loom, you must understand how HikariCP coordinates connection access. At its core is `ConcurrentBag`, a lock-free, thread-safe pool container:

```
+-------------------------------------------------------------+
|                         CONCURRENTBAG                       |
+-------------------------------------------------------------+
|                                                             |
|  [ThreadLocal Cache] ──► FastList (Thread-local connections)|
|                                                             |
|  [Shared Queue]      ──► CopyOnWriteArrayList (All pool connections)
|                                                             |
|  [Hand-off Queue]    ──► SynchronousQueue (For waiting threads)
|                                                             |
+-------------------------------------------------------------+
```

When a thread calls `dataSource.getConnection()`, HikariCP performs a three-step search:
1. **ThreadLocal Cache Look-up**: It first checks the current thread's private cache (a specialized list structure called `FastList` stored inside a `ThreadLocal`). If the thread previously held a connection and returned it, it is reused immediately, avoiding shared queue synchronization.
2. **Shared Queue Scan**: If the thread-local cache is empty, it scans a shared list (`sharedList`, backed by `CopyOnWriteArrayList`). It uses CAS operations to borrow an idle connection.
3. **Synchronous Hand-off**: If no connections are available, the borrowing thread registers its request on a hand-off queue (backed by `SynchronousQueue`) and blocks.

#### 2. The Loom Breakdown: ThreadLocal Cache Explosion
HikariCP's ThreadLocal cache is optimized for a fixed, bounded pool of platform threads (e.g., Tomcat's pool of 200 threads).
- **In Platform Threads**: 200 threads allocate 200 `FastList` caches. The garbage collection and memory footprint of these lists are negligible.
- **In Virtual Threads**: If the application spawns 1,000,000 virtual threads that borrow connections, HikariCP allocates 1,000,000 `FastList` thread-local cache maps.
- **Performance Impact**:
  - **Memory Bloats**: Spawning millions of short-lived list instances on the heap generates significant garbage collection pressure.
  - **Search Degradation**: Since virtual threads are disposable, they rarely execute subsequent queries. The hit rate on the ThreadLocal cache drops to near 0%. Every connection request misses the ThreadLocal cache and falls back to scanning the shared queue or blocking on the hand-off queue, increasing lock contention on the pool container.

#### 3. The Connection Starvation Paradox
Under heavy load, spawning unlimited virtual threads that execute database queries can cause connection starvation and deadlocks:
- **Scenario**: A service executes a transaction that borrows a database connection, executes a fast query, then makes a downstream REST call (taking 2 seconds) *while holding the connection*, and finally executes a second database write.
- **Under Platform Threads**: The Tomcat pool bounds execution to 200 concurrent requests. At most 200 connections are active. The remaining requests queue up at the HTTP network layer, providing natural backpressure.
- **Under Virtual Threads**: The server spawns 10,000 virtual threads concurrently.
  - All 10,000 threads execute the first query and borrow a connection from a pool of size 100.
  - 100 threads successfully acquire connections and enter their 2-second sleep state (waiting on the REST call), *keeping their connections borrowed*.
  - The remaining 9,900 virtual threads block waiting for a connection to become available.
  - The database connection pool is completely saturated, but the CPU utilization is 0%. The application is deadlocked on connection resources, leading to request timeouts.

#### 4. Sizing the Connection Pool: A Mathematical Sizing Proof
To prevent connection starvation under virtual threads, you must size the pool using a mathematical approach based on **Little's Law** and database limits.

##### Little's Law Recall:
$$N = \lambda \times d$$

Where:
* $N$ is the number of concurrent operations.
* $\lambda$ is the request arrival rate (throughput).
* $d$ is the average duration of the operation.

##### Sizing Proof:
Let:
- $T_{\text{active}}$ be the average number of active virtual threads handling requests.
- $t_{\text{request}}$ be the total request duration.
- $t_{\text{db}}$ be the duration the thread actively holds the database connection during the request.
- $C$ be the target connection pool size.

For the system to remain stable without starvation, the rate of connection requests must not exceed the capacity of the pool.
The connection request rate is:
$$\lambda_{\text{conn}} = \frac{T_{\text{active}}}{t_{\text{request}}}$$

Since each connection is held for $t_{\text{db}}$ duration, the concurrent connection demand $D$ is:
$$D = \lambda_{\text{conn}} \times t_{\text{db}} = T_{\text{active}} \times \left( \frac{t_{\text{db}}}{t_{\text{request}}} \right)$$

If the pool size $C < D$, threads will block waiting for connections, leading to timeouts.
Therefore, the pool size must satisfy:
$$C \geq T_{\text{active}} \times \left( \frac{t_{\text{db}}}{t_{\text{request}}} \right)$$

##### Concrete Sizing Example:
A microservice gateway processes 2,000 concurrent requests ($T_{\text{active}} = 2000$).
- Total request processing time is 500ms ($t_{\text{request}} = 500$ms).
- The database write operations take 50ms in total ($t_{\text{db}} = 50$ms).
- The remaining 450ms is spent waiting on external HTTP APIs.

Applying our sizing formula:
$$C \geq 2000 \times \left( \frac{50}{500} \right) = 200 \text{ connections}$$

##### Tuning Guidelines:
1. **Never scale connections to match virtual thread counts**: A pool of size 2,000 will overwhelm the database server's CPU and disk I/O, leading to connection failures.
2. **Protect connection pools using Semaphores**: Limit the number of virtual threads allowed to request a connection concurrently:
   ```java
   private static final Semaphore DB_THROTTLE = new Semaphore(100);
   ```
3. **Keep transactions short**: Do not hold connections while waiting on external network calls. Release the connection back to the pool before invoking REST or gRPC APIs.

---

### The Database Driver Pinning Pitfall
When executing blocking operations inside `synchronized` blocks in older JDBC database drivers (e.g., MySQL Connector/J pre-v9.0 or older PostgreSQL JDBC drivers), the virtual thread is unable to unmount from its carrier thread. This results in **carrier thread pinning**. Under heavy load, this can quickly saturate the underlying ForkJoinPool, causing application-wide starvation.

#### JEP 491 (JDK 24) Solution:
JDK 24 introduces JEP 491 to mitigate pinning by updating the JVM scheduler to yield virtual threads even when blocked inside `synchronized` blocks. However, legacy platforms running on JDK 21 must still replace synchronized locks with `ReentrantLock` in critical hot paths to prevent starvation:

```java
// Legacy JDBC synchronized wrapper patch:
private final ReentrantLock dbLock = new ReentrantLock();

public void executeSafeDatabaseQuery() {
    dbLock.lock();
    try {
        // execute driver query
    } finally {
        dbLock.unlock();
    }
}
```

### Knowledge Check

#### Question 1: Connection Pool Starvation
What is the primary risk of using virtual threads with standard database connection pools like HikariCP?
- A) Connection pools automatically scale to millions of connections, exhausting database memory.
- B) The connection pool becomes a synchronization bottleneck; virtual threads wait in memory for a connection slot, potentially causing pool starvation and request timeouts if pool limits are not protected.
- C) Virtual threads bypass connection pool constraints.
- D) None of the above.

*Answer*: **B**
*Explanation*: Spawning 10,000 virtual threads that perform database queries does not increase the physical connection capacity of the database server. If the connection pool limit is small (e.g. 100 connections), thousands of threads will block waiting to acquire a connection. Without protection (like an application-level semaphore), this causes connection timeouts.

#### Question 2: Quarkus Integration
Which annotation is used in Quarkus to delegate incoming REST event-loop requests onto virtual threads?
- A) `@Asynchronous`
- B) `@RunOnVirtualThread`
- C) `@VirtualExecutor`
- D) `@RunOnReactiveLoop`

*Answer*: **B**
*Explanation*: Quarkus provides `@RunOnVirtualThread` to offload REST endpoint and CDI bean method execution from the reactive Vert.x Netty event loop threads to virtual threads.

#### Question 3: synchronized Blocks and Pinning (JDK 24 JEP 491)
How does JEP 491 (finalized in JDK 24/25) change the behavior of virtual threads encountering synchronized blocks?
- A) It removes the `synchronized` keyword from Java.
- B) It allows the JVM scheduler to yield and unmount virtual threads even when blocking inside synchronized blocks or methods, resolving most carrier thread pinning cases.
- C) It converts all synchronized blocks into ReentrantLocks automatically.
- D) It deprecates virtual threads.

*Answer*: **B**
*Explanation*: In JDK 21, blocking inside a `synchronized` block pins the virtual thread to its carrier thread. JEP 491 refactors the JVM thread scheduler and object monitor code, allowing virtual threads to unmount and yield their carrier thread when blocking inside synchronized blocks.

#### Question 4: Spring Boot Global Property
When setting `spring.threads.virtual.enabled=true` in a Spring Boot 3.2+ application, what underlying JVM change occurs to Tomcat's request handler?
- A. Tomcat allocates a pool of 200 virtual threads and keeps them active.
- B. Tomcat customizes its protocol executor to use `Executors.newVirtualThreadPerTaskExecutor()`, spawning a new virtual thread for each incoming connection request.
- C. Tomcat converts all database queries to use reactive drivers.
- D. Tomcat disables HTTP caching.

*Answer*: **B**
- *Explanation*: Enabling this property swaps Tomcat's internal request pool with a virtual-thread-per-task executor. Every HTTP request gets its own virtual thread, allowing the application to scale requests with minimal memory footprint.

#### Question 5: Starving the WebFlux Event Loop
Why is blocking netty event loop threads considered critical in a Spring WebFlux application, and how does Project Reactor bypass this with virtual threads?
- A. WebFlux crashes the JVM if it detects blocks.
- B. Netty event loops process all request packets. If a handler thread blocks, Netty cannot process other TCP packages. Bypassing this requires offloading to a virtual thread scheduler using `.publishOn(Schedulers.fromExecutor(vtExecutor))`.
- C. Reactive streams do not compile on virtual threads.
- D. By scaling Netty threads to 100,000 platform threads.

*Answer*: **B**
- *Explanation*: The golden rule of WebFlux/Netty is: Never block the event loop. If a blocking JDBC driver is queried inside the loop, the loop is pinned. Offloading the blocking stage to virtual threads via `publishOn` releases Netty threads to accept incoming packages while the blocking call yields its carrier thread.

#### Question 6: Jakarta Concurrency Managed Executors
Under Jakarta Concurrency 3.1, what parameter is specified inside `@ManagedExecutorDefinition` to run CDI tasks on virtual threads?
- A. `type = ExecutorType.LIGHTWEIGHT`
- B. `virtual = true`
- C. `threadFactory = "virtual"`
- D. `isolation = CDI`

*Answer*: **B**
- *Explanation*: The `@ManagedExecutorDefinition` annotation (introduced in Jakarta EE 11) exposes the `virtual` attribute. Setting `virtual = true` tells the container to back this Managed Executor with virtual threads rather than a standard platform thread pool.

#### Question 7: Protecting Connection Pools via Semaphores
In a system handling 50,000 concurrent requests, what is the best practice to prevent connection pool exhaustion?
- A) Set `maximumPoolSize=50000` in HikariCP.
- B) Limit database access concurrency at the application layer using a `Semaphore`. Blocked virtual threads wait in memory with zero carrier thread pinning, protecting the database pool.
- C) Disable the connection pool and open raw connections on every request.
- D) Restart the database server periodically.

*Answer*: **B**
- *Explanation*: Setting the connection pool size to 50,000 will overwhelm the database server. The best practice is to throttle queries at the application layer using a `Semaphore` (or `RateLimitedJoiner`). The blocked virtual threads yield their carrier threads, keeping resource utilization low.

#### Question 8: ObjectMonitor Pinning in JDK 21
On JDK 21, what specific JVM structure prevents a virtual thread from unmounting from its carrier thread when blocked inside a synchronized block?
- A. ThreadLocal maps.
- B. The association of a JVM `ObjectMonitor` lock with the thread stack frame, which pins the virtual thread to the native carrier thread until the monitor is released.
- C. The CPU register cache.
- D. The native OS file descriptors.

*Answer*: **B**
- *Explanation*: In JDK 21, the JVM thread scheduler cannot unmount a virtual thread that is currently holding or acquiring a monitor lock. This monitor-stack linkage pins the virtual thread to its carrier thread, neutralizing Loom's scalability benefit until JEP 491 is applied.

#### Question 9: Spring @Async Wrapper Adaptations
How does Spring's `TaskExecutorAdapter` class integrate standard virtual thread executors with Spring's async proxy wrappers?
- A. It converts platform threads to virtual threads by modifying bytecode.
- B. It wraps standard Java `java.util.concurrent.Executor` instances (such as a virtual thread executor) to satisfy Spring's `AsyncTaskExecutor` interface contract.
- C. It intercepts database connection pools to apply semaphores.
- D. It acts as an HTTP proxy.

*Answer*: **B**
- *Explanation*: Spring's async subsystem expects beans implementing the `AsyncTaskExecutor` interface. `TaskExecutorAdapter` adapts standard JDK `Executor` instances (e.g. `Executors.newVirtualThreadPerTaskExecutor()`) to Spring's API framework, allowing async components to run on virtual threads.

#### Question 10: Quarkus CDI Context Propagation
How does Quarkus ensure that CDI request scopes (like transaction context or security credentials) are propagated to threads spawned under `@RunOnVirtualThread`?
- A) CDI contexts are global, so no propagation is required.
- B) Quarkus's integration handlers capture CDI request contexts at the request interceptor and propagate them to the virtual thread stack frame before executing the method.
- C) CDI request scopes are disabled on virtual threads.
- D) By replicating the CDI bean instances.

*Answer*: **B**
- *Explanation*: CDI request scopes are thread-bound. When offloading execution to a virtual thread, Quarkus intercepts the invocation, captures the active CDI request context, and propagates it to the target virtual thread stack frame, ensuring context availability.

#### Question 11: Pinning Diagnostic JFR Tracing
Which JFR event is monitored to detect carrier thread pinning duration in production environments?
- A) `jdk.ThreadPark`
- B) `jdk.VirtualThreadPinned`
- C) `jdk.VirtualThreadStarvation`
- D) `jdk.ThreadPinningException`

*Answer*: **B**
- *Explanation*: The `jdk.VirtualThreadPinned` event is recorded by the JVM whenever a virtual thread blocks while pinned to its carrier thread (due to monitor locks or native stack frames). Key attributes include `duration` and `stackTrace` to trace the pinning code block.

#### Question 12: Tomcat Acceptor Thread Dispatching
Under the virtual thread executor configuration, how does Tomcat's Acceptor thread dispatch incoming client socket connections?
- A. The Acceptor thread blocks until a carrier thread is free.
- B. The Acceptor thread accepts the connection socket and submits a task to the virtual thread executor, which spawns a new virtual thread to process the HTTP request immediately.
- C. The Acceptor thread processes the request inside its own thread context.
- D. By queueing the request in a SynchronousQueue.

*Answer*: **B**
- *Explanation*: Tomcat's architecture uses Acceptor threads to listen for TCP connections. Once accepted, the socket is dispatched to the protocol executor. When configured with virtual threads, the executor spawns a new virtual thread for the request, allowing the Acceptor to listen for more connections.

#### Question 13: Database Driver Locking Compatibility
Why do legacy JDBC drivers require refactoring to prevent carrier thread pinning on JDK 21 platforms?
- A) They are written in C, not Java.
- B) Their query acquisition wrappers utilize synchronized blocks to guarantee thread safety, which pins virtual threads to carrier threads during network I/O.
- C) They do not support connection pools.
- D) None of the above.

*Answer*: **B**
- *Explanation*: Legacy JDBC drivers wrap socket reads/writes in synchronized blocks for concurrency safety. On JDK 21, blocking inside a synchronized block pins the virtual thread, blocking the carrier thread. The fix is to upgrade the driver or replace synchronized blocks with `ReentrantLock`.

#### Question 14: Quarkus @Blocking vs @RunOnVirtualThread Annotations
In a Quarkus REST application, what is the operational difference between annotating an endpoint with `@Blocking` versus `@RunOnVirtualThread`?
- A. `@Blocking` runs the task inside the Netty event loop thread.
- B. `@Blocking` offloads the request to a standard, bounded platform thread pool (the Quarkus worker pool), while `@RunOnVirtualThread` executes the request on a newly spawned lightweight virtual thread, preserving the reactive event loop.
- C. `@RunOnVirtualThread` disables CDI context propagation.
- D. None of the above.

*Answer*: **B**
- *Explanation*: In Quarkus, `@Blocking` instructs the router to offload the request from the Vert.x event loop to a standard, bounded executor pool of platform threads. `@RunOnVirtualThread` instead offloads the request to a virtual thread executor, allowing massive scaling for blocking operations without event loop starvation or pool sizing limits.

#### Question 15: Database Deadlocks under JDBC Carrier Thread Pinning
On a JDK 21 runtime with a 4-core CPU (parallelism limit of 4 carrier threads), a virtual-thread-based service executes queries using a legacy driver containing synchronized blocks. Under a load of 1,000 concurrent writes, the application hangs. A thread dump shows all 4 carrier threads are in `PARKED` or `BLOCKED` states holding monitors. What is the name of this failure state?
- A. Garbage Collection deadlock.
- B. Carrier thread pool starvation deadlock, caused because all scheduler carrier threads are pinned to virtual threads waiting on JDBC network I/O, leaving no carrier threads available to execute the virtual threads that hold the database locks.
- C. Volatile bus saturation.
- D. None of the above.

*Answer*: **B**
- *Explanation*: If all available carrier threads (e.g. 4 threads on a 4-core machine) become pinned to virtual threads that are blocked waiting on downstream queries (like database sockets), the ForkJoinPool scheduler is completely starved. The JVM has no free carrier threads to execute the virtual threads that need to receive database packets or release lock permits, leading to a permanent deadlock.

#### Question 16: Spring Boot Async Executor Override Priority
When `spring.threads.virtual.enabled=true` is set, a developer declares a manual bean: `@Bean(name = "taskExecutor") public Executor customExecutor() { return Executors.newFixedThreadPool(10); }`. What is the execution behavior of `@Async` annotated methods?
- A. The methods execute on virtual threads because the global property takes precedence.
- B. Spring Boot's auto-configuration backs off because a custom bean named `"taskExecutor"` is explicitly defined. The async methods execute on the custom fixed pool of 10 platform threads.
- C. The program fails to compile.
- D. Spring Boot merges both pools.

*Answer*: **B**
- *Explanation*: Spring Boot's auto-configuration uses `@ConditionalOnMissingBean` policies. If a custom task executor bean named `"taskExecutor"` is defined, Spring Boot respects the developer's configuration and does not inject the virtual thread-backed `SimpleAsyncTaskExecutor`. The `@Async` tasks will run on the platform thread pool, overriding the global property for async methods.

#### Question 17: Spring WebFlux Netty Event Loop Bypass
Why is offloading blocking code in Spring WebFlux controllers to `Schedulers.fromExecutor(Executors.newVirtualThreadPerTaskExecutor())` superior to offloading to `Schedulers.boundedElastic()`?
- A. BoundedElastic does not support reactive streams.
- B. BoundedElastic uses a pool of platform threads. Under extreme load, the pool can experience thread exhaustion or create high context-switching overhead. Offloading to virtual threads allows spawning millions of unpooled, lightweight execution units with near-zero resource cost.
- C. BoundedElastic is deprecated.
- D. Virtual threads execute database queries faster.

*Answer*: **B**
- *Explanation*: Project Reactor's `boundedElastic()` scheduler uses a pool of platform threads (default maximum 10x number of CPU cores). Under heavy load, it can starve or saturate memory. Using a virtual thread-backed scheduler allows the application to handle high concurrency with low memory footprint, avoiding event loop starvation and pool sizing bottlenecks.

#### Question 18: HikariCP Connection Acquisition Throttling via Semaphores
When protecting a database connection pool from timeouts under a load of 20,000 concurrent virtual threads, what is the best practice for configuring the application-level Semaphore?
- A) Set the Semaphore permit count to 20,000.
- B) Set the Semaphore permit count slightly lower than or equal to the maximum connection pool size (e.g., 90% of HikariCP's `max-lifetime-pool`), ensuring that threads block in memory as lightweight virtual threads instead of queuing up at the connection pool driver.
- C) Disable the pool and use single connection instances.
- D) None of the above.

*Answer*: **B**
- *Explanation*: The Semaphore acts as a gatekeeper. By setting its permit count close to the database connection pool limit, virtual threads are throttled in the application layer. Blocked virtual threads yield their carrier threads, keeping resource usage low and preventing Hikari connection acquisition timeouts.

#### Question 19: Analysing VirtualThreadPinned JFR Events in Spring Boot
During a production run of a Spring Boot service, JFR captures several `jdk.VirtualThreadPinned` events. What action should the developer take to locate and resolve the issue?
- A) Set `spring.threads.virtual.enabled=false`.
- B) Analyze the stack trace of the event to locate the synchronized block causing the pinning, and refactor it to use `ReentrantLock` instead.
- C) Increase the Tomcat thread pool size.
- D) Restart the server.

*Answer*: **B**
- *Explanation*: The `VirtualThreadPinned` event includes the stack trace of the blocking call. By inspecting this stack trace in JDK Mission Control, developers can locate the class and method causing the pinning (often in legacy drivers or libraries) and replace the synchronized monitor lock with a `ReentrantLock`.

#### Question 20: Undertow vs Tomcat Protocol Executors
How does Undertow's protocol executor adaptation under Spring Boot 3.2+ differ from Tomcat's when `spring.threads.virtual.enabled=true` is enabled?
- A. Undertow disables HTTP/2 support.
- B. Both Tomcat and Undertow adapt their internal execution engines. Tomcat overrides its protocol executor to use `newVirtualThreadPerTaskExecutor()`, and Undertow replaces its worker threads with virtual-thread-based executors for request processing.
- C. Undertow does not support virtual threads.
- D. None of the above.

*Answer*: **B**
- *Explanation*: Spring Boot 3.2+ provides integrations for all major embedded servlet containers. Enabling virtual threads replaces Tomcat's protocol handlers and Undertow's request workers with virtual thread task executors, ensuring high request concurrency across both servlet engines.

---

## 7. Beginner-Friendly Concept: The Restaurant Analogy of Web Server Concurrency

To understand why modern web frameworks are integrating virtual threads, let us look at an office or restaurant analogy.

Imagine a popular restaurant processing dinner orders. Each order involves:
1. A customer placing an order with a waiter.
2. The waiter taking the order to the kitchen.
3. The kitchen preparing the food (simulating external database queries or downstream API calls).
4. The waiter delivering the food to the table.

Web frameworks handle these orders in three different ways:

### 1. The Traditional Servlet Model: Spring MVC / Tomcat (One Waiter Per Table)
In a traditional Spring Boot application without virtual threads:
- **The Waiters**: Platform Threads. Each waiter is assigned to exactly one table.
- **The Process**:
  - A waiter takes the customer's order and walks to the kitchen.
  - While the kitchen is cooking the food, the waiter stands outside the kitchen window, waiting. They cannot serve any other table.
  - If the restaurant only has 200 waiters, they can only serve 200 tables at the same time.
  - If a 201st table arrives, they must wait outside in a long queue (causing latency spikes), even if the kitchen is idle.
  - To serve more tables, the restaurant must hire more waiters, but waiters are expensive, take up space, and eat food (large thread stack overhead).

### 2. The Reactive Model: Spring WebFlux / Netty (The Event Loop Waiter)
To solve this, reactive programming changes the waiter's behavior:
- **The Process**:
  - The restaurant only hires 4 highly efficient waiters (Event Loop Threads, matching CPU cores).
  - A waiter takes Table 1's order, drops it off at the kitchen, and immediately turns around to take Table 2's order. They never stand around waiting.
  - When Table 1's food is cooked, the chef rings a bell (OS socket notification). The first available waiter grabs the plate and delivers it.
  - **The Catch**: This is highly efficient and scales to thousands of tables, but the waiters must *never* stop moving. If a customer asks the waiter to calculate a complex split bill (a blocking database query or long computation), and the waiter stands there calculating it for 10 seconds, the entire restaurant service freezes because there are only 4 waiters in the room. This is event loop starvation.

### 3. The Loom Model: Spring Boot + Virtual Threads (Desks with Self-Service Runners)
Project Loom combines the simplicity of the first model with the scalability of the second:
- **The Process**:
  - Each customer is given a direct intercom button to the kitchen (Virtual Thread). Every request runs independently.
  - The restaurant only has 4 physical food runners (Carrier platform threads).
  - When the kitchen finishes cooking, a food runner grabs the plate, runs to the table, drops it off, and runs back.
  - If a customer needs to wait, they wait at their table. They do not hold up a waiter or a runner.
  - This allows the restaurant to serve 100,000 tables simultaneously. The developer writes code as if they have their own dedicated waiter (simple, linear, synchronous code), but the underlying system shares the food runners automatically (M-to-N cooperative scheduling), giving you reactive scaling without the complexity of callback streams.

---

## 8. Spring Boot Tomcat vs. Spring WebFlux Event Loop Performance Comparison

With the introduction of virtual threads, developers often ask: *“Is Spring WebFlux and reactive programming still necessary, or can we build everything using Spring MVC and Virtual Threads?”*

To answer this, we must compare how both models perform under varying levels of concurrency.

#### The Benchmark Setup
Imagine a gateway service that receives client REST requests, calls a downstream payment service (which introduces a 100ms latency), and returns the payload. We compare three configurations:
1. **Tomcat Platform Pools**: Standard Spring Boot MVC with a default thread pool limit of 200 platform threads.
2. **Spring WebFlux (Reactive)**: A fully reactive service running on Netty with 8 event loop threads (matching CPU cores).
3. **Tomcat Virtual Threads**: Spring Boot MVC with virtual threads enabled (`spring.threads.virtual.enabled=true`).

---

#### Performance under Load

##### Phase 1: Low Concurrency (100 Concurrent Users)
- **Tomcat Platform**: Handles all 100 requests concurrently since the pool has 200 threads. Average response latency is **100ms**.
- **Spring WebFlux**: Offloads network waiting to the OS kernel. The 8 event loops easily handle the traffic. Average response latency is **100ms**.
- **Tomcat Virtual Threads**: Spawns 100 virtual threads on the heap. Average response latency is **100ms**.
- *Verdict*: All three systems perform identically.

##### Phase 2: Medium Concurrency (1,000 Concurrent Users)
- **Tomcat Platform**: The 200 threads are instantly saturated. The remaining 800 requests must wait in Tomcat's internal request queue.
  - **Latency jumps to ~500ms** due to queuing delays.
  - CPU usage remains low because threads are blocked waiting for sockets, but throughput is capped.
- **Spring WebFlux**: Netty event loops process incoming socket bytes asynchronously. Latency remains flat at **100ms**.
- **Tomcat Virtual Threads**: Tomcat spawns 1,000 virtual threads. They execute and immediately yield their carrier threads. Latency remains flat at **100ms**.
- *Verdict*: Reactive and Virtual Threads scale smoothly; Platform Threads experience severe queuing delays.

##### Phase 3: High Concurrency (10,000 Concurrent Users)
- **Tomcat Platform**: The queue overflows, resulting in socket connection timeouts, dropped requests, and high CPU usage due to context-switch thrashing. The application becomes unresponsive.
- **Spring WebFlux**: Latency remains flat at **100ms**. Netty event loops handle the connections efficiently. Memory usage remains stable at **~200MB**.
- **Tomcat Virtual Threads**: Tomcat spawns 10,000 virtual threads. All 10,000 block on network I/O, yielding carriers. Latency remains flat at **100ms**. Memory usage rises slightly to **~320MB** (allocating 10,000 heap stacks).
- *Verdict*: Both Reactive and Virtual Threads achieve identical scalability, but Virtual Threads do so using simple, sequential blocking code.

---

#### Summary of Mechanical Trade-Offs

| Metric | Tomcat Platform Pools | Spring WebFlux (Reactive) | Tomcat Virtual Threads |
| :--- | :--- | :--- | :--- |
| **Concurrency Ceiling** | Low (~200–500 tasks) | Extremely High (Millions) | Extremely High (Millions) |
| **Response Latency** | High under request queue | Flat, low latency | Flat, low latency |
| **Memory Footprint** | High (1MB per thread stack) | Extremely Low (~200MB) | Low (~300MB heap stack) |
| **Debugging and Logs** | Easy (Thread-bound) | Difficult (Lost traces) | Easy (Thread-bound) |
| **Coding Style** | Simple Imperative | Declarative (Streams) | Simple Imperative |

#### Architectural Recommendation
- Use **Tomcat Virtual Threads (Spring MVC)** for standard enterprise web applications, REST APIs, and CRUD microservices. It matches the scalability of WebFlux while keeping the programming model simple, readable, and easy to debug.
- Use **Spring WebFlux (Reactive)** when you are building streaming applications (such as WebSockets, Server-Sent Events, or real-time event brokers) where connection states are long-lived and require custom backpressure pipelines.
