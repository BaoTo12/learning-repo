# Chapter 3: Local Development Basics: Spring Boot, Docker, and the 12-Factor App

Decomposing a business domain into service contracts is an architectural exercise. However, translating those designs into a running, scalable system requires a concrete set of tools and development methodologies. Modern microservices must be built for elasticity, environment portability, and ease of orchestration.

This chapter details the technical foundation for developing microservices locally. We will introduce **Spring Boot** and analyze the anatomy of a Java microservice. We will examine the **12-Factor App methodology** and see how its rules are mapped to Spring Boot and Docker. Finally, we will configure an optimized multi-stage **Dockerfile** following industry best practices and orchestrate our service dependencies locally using **Docker Compose**.

---

## Learning Objectives

By the end of this chapter, you will be able to:
1. Explain the role of Spring Boot in eliminating enterprise Java boilerplate and application server deployments.
2. Bootstrap a Spring Boot project skeleton and explain its directory layout.
3. Manage configuration parameters using custom properties files and environment-specific profiles.
4. Map all twelve guidelines of the **Twelve-Factor App** manifesto directly to Java and containerized environments.
5. Identify the structural differences between Virtual Machines (VMs) and Docker containers.
6. Design a secure, optimized multi-stage **Dockerfile** utilizing Spring Boot's dependency layering.
7. Write a **Docker Compose** manifest to orchestrate a microservice alongside backing databases (PostgreSQL) and caching engines (Redis).

---

## 3.1 Intro to Spring Boot and Java Microservice Anatomy

For years, enterprise Java applications were deployed to heavy, external Application Servers (like WebSphere, WebLogic, or full JBoss installations). Development cycles were slow, configurations required verbose XML files, and scaling meant duplicating massive server runtimes.

**Spring Boot** revolutionized this landscape by adopting a **microservices-first philosophy**:
* **Embedded Web Container**: Spring Boot packages a lightweight web server (Apache Tomcat by default, though Jetty or Undertow can be configured) directly inside the executable application JAR. There is no need to deploy to an external application server.
* **Auto-Configuration**: Spring Boot analyzes your classpath dependencies. If it detects a database driver (e.g., PostgreSQL) and Spring Data JPA on the classpath, it automatically configures a database connection pool (`DataSource`) without requiring manual setup.
* **Starters**: Opinionated dependency descriptors that group related libraries together. For example, `spring-boot-starter-web` pulls in Tomcat, Spring MVC, Jackson (for JSON serialization), and validation libraries in one declaration.
* **Production-Ready Features**: Includes health endpoints, metrics collection (Micrometer), and externalized configurations via the **Spring Boot Actuator** library.

---

### The Anatomy of a Bootstrap Class
Every Spring Boot application is driven by a single bootstrap entry-point class annotated with `@SpringBootApplication`:

```java
package com.ftgo.order;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class OrderServiceApplication {
    public static void main(String[] args) {
        // Starts the Spring container, boots Tomcat, and initializes configuration scans
        SpringApplication.run(OrderServiceApplication.class, args);
    }
}
```

* **`@SpringBootApplication`**: Under the hood, this is a meta-annotation that combines:
  1. `@SpringBootConfiguration`: Declares the class as a source of bean definitions.
  2. `@EnableAutoConfiguration`: Tells Spring Boot to automatically configure beans based on classpath dependencies.
  3. `@ComponentScan`: Tells Spring to scan the package of this bootstrap class (and all sub-packages) for classes annotated with `@Component`, `@Service`, `@Repository`, or `@RestController`, and load them into the application context.

---

## 3.2 Setting Up a Spring Boot Project Skeleton

We can create a new Spring Boot microservice skeleton using **Spring Initializr** (accessible via [start.spring.io](https://start.spring.io/)). It provides a web-based UI and REST API to specify the build tool, Java version, and starters.

![Figure 3.1: Specifying dependency starters in Spring Initializr](https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//96c88d46-c089-4a8f-a57f-a56c53fde3a6/markdown_2/imgs/img_in_image_box_138_109_930_700.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T09%3A47%3A36Z%2F-1%2F%2Fc4293cb192c8b8bef45cc99475661165769a6bca1cd880998afc96f0baee095d)
*Figure 3.1: Specifying dependency starters in Spring Initializr. For a standard REST microservice, we select Web, Lombok, and Actuator.*

![Figure 3.2: Specifying package metadata in Spring Initializr](https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//96c88d46-c089-4a8f-a57f-a56c53fde3a6/markdown_2/imgs/img_in_image_box_137_800_931_1142.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T09%3A47%3A37Z%2F-1%2F%2Ff154e76527ae832e4e4809194fb27590c16be425a74ccbb8190ec1e45acfdc6f)
*Figure 3.2: Specifying package metadata, packaging type (JAR), and Java version in Spring Initializr.*

### The Directory Layout
Once downloaded and extracted, a standard Maven-based Spring Boot project follows a structured package layout:

```
order-service/
├── pom.xml
└── src/
    ├── main/
    │   ├── java/
    │   │   └── com/
    │   │       └── ftgo/
    │   │           └── order/
    │   │               ├── OrderServiceApplication.java
    │   │               ├── controller/
    │   │               ├── domain/
    │   │               ├── repository/
    │   │               └── service/
    │   └── resources/
    │       ├── application.yml
    │       ├── bootstrap.yml
    │       └── templates/
    └── test/
        └── java/
            └── com/
                └── ftgo/
                    └── order/
                        └── OrderServiceApplicationTests.java
```

* **`pom.xml`**: The Maven build file defining dependencies, plugins, and properties.
* **`src/main/java/`**: Holds the Java source files organized by functional packages (controllers, models, services, repositories).
* **`src/main/resources/`**: Holds non-Java resources, static files, and application property configurations.

  * `bootstrap.yml`: Loaded during the initial bootstrap context setup, typically used to point the service to an external configuration server.
  * `application.yml`: Contains the core configuration settings for the service (database connection strings, ports, security parameters).

---

## 3.3 Managing Configuration Properties and Profiles

To build flexible, cloud-native services, you must externalize configurations so the application can run in different environments without code modifications. We configure these properties inside `application.yml` using hierarchical blocks.

### The Configuration File: `application.yml`
```yaml
server:
  port: 8080 # Port on which the embedded Tomcat server will listen

spring:
  application:
    name: licensing-service # Service ID used for service discovery
  profiles:
    active: dev # Default active configuration profile
  datasource:
    hikari:
      connection-timeout: 20000
      maximum-pool-size: 5

# Custom configuration variables mapped to Java classes
example:
  property: "Default Configuration Value"
```

---

### Environment-Specific Profiles
We define environment-specific overrides by creating dedicated profile files (e.g., `application-dev.yml`, `application-prod.yml`):

#### Development Profile: `application-dev.yml`
```yaml
server:
  port: 8080

spring:
  datasource:
    url: jdbc:postgresql://localhost:5432/legendary_dev
    username: dev_user
    password: dev_password
    driver-class-name: org.postgresql.Driver

example:
  property: "Development Configuration Value"
```

#### Production Profile: `application-prod.yml`
```yaml
server:
  port: 80 # Production services bind to standard HTTP port

spring:
  datasource:
    url: jdbc:postgresql://prod-db-cluster:5432/legendary_prod
    username: prod_admin
    password: ${PROD_DB_PASSWORD} # Password injected via environment variable
    driver-class-name: org.postgresql.Driver

example:
  property: "Production Configuration Value"
```

To run the application with a specific profile, pass the active profile command-line argument:
```bash
java -jar -Dspring.profiles.active=prod licensing-service-1.0.0.jar
```

---

## 3.4 Mapping the 12-Factor App Manifesto to Java and Containerized Environments

The **Twelve-Factor App** is a methodology for building software-as-a-service (SaaS) applications that are portable, elastic, and scalable. Here is how these 12 factors map directly to Spring Boot and containerized environments:

### 1. Codebase
* *Rule*: One codebase tracked in revision control (like Git), many deploys.
* *Java Mapping*: Maintain a single Git repository for each microservice. Use Maven multi-module projects to manage clean separation of modules.

### 2. Dependencies
* *Rule*: Explicitly declare and isolate dependencies. Never rely on implicit system libraries.
* *Java Mapping*: Declare all dependencies inside the `pom.xml`. The compiled application must run inside an isolated JVM classpath. Never copy external JARs manually into runtime libraries.

### 3. Config
* *Rule*: Store configuration in the environment.
* *Java Mapping*: Read configuration values using Spring's `@Value` annotation mapping to environment variables or command-line overrides. Bind production credentials to environment variables injected at container runtime:
  ```java
  @Value("${DATABASE_PASSWORD}")
  private String dbPassword;
  ```

### 4. Backing Services
* *Rule*: Treat backing services (databases, caches, message brokers) as attached resources.
* *Java Mapping*: Connect to PostgreSQL, Redis, or Kafka using pluggable URIs and credentials defined in external configuration parameters. The service should be able to switch from a local PostgreSQL database to an Amazon RDS database by modifying the connection string without code changes.

### 5. Build, Release, Run
* *Rule*: Strictly separate build and run stages.
* *Java Mapping*:
  1. *Build Stage*: Maven compiles the source code and packages it into an executable JAR.
  2. *Release Stage*: Combine the JAR with environment-specific configurations inside a Docker image, tagged with a unique version (e.g., `licensing-service:v1.0.2`).
  3. *Run Stage*: Execute the container image in the target execution environment.

### 6. Processes
* *Rule*: Run the app as one or more stateless, share-nothing processes.
* *Java Mapping*: Microservices must not store user session data or state in local memory or on the local filesystem. Store persistent state in shared databases (like PostgreSQL) or distributed caches (like Redis).

### 7. Port Binding
* *Rule*: Export services via port binding.
* *Java Mapping*: The microservice embeds its own web server (Tomcat), binding directly to a port (e.g., `8080`). The container engine maps this internal port to the host port, exposing the service to the network without external server routing.

### 8. Concurrency
* *Rule*: Scale out via the process model.
* *Java Mapping*: Scale application capacity horizontally by running multiple identical copies of the microservice container in parallel, rather than increasing thread counts inside a single JVM.

### 9. Disposability
* *Rule*: Maximize robustness with fast startup and graceful shutdown.
* *Java Mapping*: Ensure the service starts quickly (typically under 10 seconds). Configure Spring Boot to handle termination signals (`SIGTERM`) gracefully by finishing active requests before shutting down:
  ```yaml
  server:
    shutdown: graceful
  spring:
    lifecycle:
      timeout-per-shutdown-phase: 20s
  ```

### 10. Dev/Prod Parity
* *Rule*: Keep development, staging, and production environments as similar as possible.
* *Java Mapping*: Use containerization (Docker) to execute the exact same runtime stack (OS, JRE version, dependencies) locally as in production. Avoid using an H2 database locally if you use PostgreSQL in production.

### 11. Logs
* *Rule*: Treat logs as event streams.
* *Java Mapping*: Configure Java logging frameworks (logback, log4j2) to write log statements directly to the console (`stdout`/`stderr`). The container runtime environment intercepts these console streams and forwards them to a centralized log aggregator (like Splunk or the ELK stack).

### 12. Admin Processes
* *Rule*: Run admin/management tasks as one-off processes.
* *Java Mapping*: Run database schema migrations (using Flyway or Liquibase) as independent, ephemeral container commands executed before starting the main application server, rather than running them inside the long-running application process.

---

## 3.5 Docker Containers vs. Virtual Machines

Before containerizing our Spring Boot service, we must understand the core architectural differences between Virtual Machines (VMs) and Docker Containers:

```
      +-------------------------+             +-------------------------+
      |    Virtual Machines     |             |    Docker Containers    |
      +-------------------------+             +-------------------------+
      |  App 1  |  App 2  |App 3|             |  App 1  |  App 2  |App 3|
      +---------+---------+-----+             +---------+---------+-----+
      | Guest OS| Guest OS|Guest|             | Libs/Bin| Libs/Bin|Libs |
      +---------+---------+-----+             +-------------------------+
      |        Hypervisor       |             |      Docker Engine      |
      +-------------------------+             +-------------------------+
      |        Host OS          |             |      Host OS / Kernel   |
      +-------------------------+             +-------------------------+
      |        Hardware         |             |      Hardware           |
      +-------------------------+             +-------------------------+
```

### Virtual Machine (VM)
* **Architecture**: A hypervisor partitions physical hardware to create virtual machines. Each VM requires its own complete copy of a Guest Operating System (guest OS), which includes virtualized drivers, system libraries, and the application runtime.
* **Footprint**: Extremely large (often gigabytes per VM).
* **Performance**: Slow boot times (minutes) because the guest OS must undergo a complete boot sequence.
* **Resource Cost**: High overhead, as CPU and RAM are allocated to run multiple operating system kernels.

### Docker Container
* **Architecture**: Containers run directly on the host machine's operating system kernel, utilizing Linux kernel namespaces and control groups (cgroups) for isolation. Containers package only the application binary, system dependencies, and runtime libraries.
* **Footprint**: Lightweight (megabytes).
* **Performance**: Starts in milliseconds because it runs as a standard isolated process on the host.
* **Resource Cost**: Minimal overhead, maximizing resource density on the host hardware.

### 3.5.1 Detailed VM vs. Container Comparison Matrix

| Virtualization Metric | Virtual Machines (VMs) | Docker Containers |
| :--- | :--- | :--- |
| **Isolation Boundary** | Hardware-level hypervisor virtualization. | OS Kernel-level process isolation. |
| **Guest OS Required** | Yes. Each VM boots a full guest operating system. | No. Containers share the host kernel. |
| **Startup Time** | Minutes (cold boot sequence of guest OS). | Milliseconds (process initialization). |
| **Image Size** | 10 GB - 50 GB (including full OS disks). | 50 MB - 500 MB (only app runtime and binaries). |
| **Memory Consumption** | High (pre-allocated static memory reservations). | Low (dynamic memory consumption on demand). |
| **Portability** | Bound to hypervisor platforms (ESXi, Hyper-V, KVM). | Highly portable across any OS running Docker. |
| **Process Namespaces** | Isolated within the guest OS scheduling scope. | Isolated via Linux namespaces (PID, Mount, Net). |
| **Resource Limits** | Managed statically by hypervisor controls. | Enforced dynamically via Linux control groups (cgroups). |

---


## 3.6 Multi-Stage Dockerfile Configuration

A naive Dockerfile copies the entire project directory, executes Maven tests, compiles the code inside the container, and runs the application. This approach results in large container images containing compile-time libraries (JDK, Maven plugins) and source code files, creating security risks and deployment overhead.

To solve this, we use a **Multi-Stage Build**. This pattern uses a compilation stage to generate the JAR and an execution stage to run it, keeping the final container image lightweight. We also utilize Spring Boot's dependency layering to maximize Docker's layer cache hits:

```
+------------------------------------+
| Stage 1: Build & Extract Layers    | -> Downloads dependencies, compiles code,
+------------------------------------+    and splits JAR into layers.
                 |
                 v
+------------------------------------+
| Stage 2: Runtime Container Image   | -> Copies only the extracted layer folders.
+------------------------------------+    If code changes, only the application
                                          layer is rebuilt, speeding up updates.
```

### Layered JAR Extraction Command
Spring Boot JARs can be split into layers using the layertools tool:
```bash
java -Djarmode=layertools -jar application.jar extract
```
This extracts the JAR into four directories:
1. `dependencies/`: External dependency libraries.
2. `spring-boot-loader/`: Spring Boot bootstrap classes.
3. `snapshot-dependencies/`: Snapshots of external dependencies.
4. `application/`: Application code and resources.

---

### The Optimized Multi-Stage `Dockerfile`
Create the following `Dockerfile` in the module directory (`order-service/Dockerfile`):

```dockerfile
# Stage 1: Build the application and extract JAR layers
FROM maven:3.8.2-openjdk-11-slim AS builder
WORKDIR /build

# Copy the pom.xml and download project dependencies to cache them
COPY pom.xml .
RUN mvn dependency:go-offline -B

# Copy the source code and compile the executable JAR
COPY src ./src
RUN mvn clean package -DskipTests

# Extract the JAR layers using the Spring Boot layertools tool
WORKDIR /build/target
RUN java -Djarmode=layertools -jar order-service-1.0.0-SNAPSHOT.jar extract

# Stage 2: Build the final runtime container
FROM openjdk:11-jre-slim
WORKDIR /app

# Create a non-privileged system user for security hardening
RUN groupadd -r spring && useradd -r -g spring spring
USER spring:spring

# Copy the extracted layers from the builder stage
COPY --from=builder /build/target/dependencies/ ./
COPY --from=builder /build/target/spring-boot-loader/ ./
COPY --from=builder /build/target/snapshot-dependencies/ ./
COPY --from=builder /build/target/application/ ./

# Expose the application port
EXPOSE 8081

# Run the application using the Spring Boot jar launcher class
ENTRYPOINT ["java", "org.springframework.boot.loader.JarLauncher"]
```

#### Key Benefits of this Configuration:
* **Minimal Image Size**: Uses `openjdk:11-jre-slim`, which contains only the JRE, reducing the container footprint.
* **Layer Caching**: Docker caches the `dependencies/` layer. When application code changes, Docker only rebuilds the small `application/` layer, speeding up container build times.
* **Security Hardening**: Runs the application as a non-privileged user (`spring`), preventing root-level access if the container is compromised.

---

## 3.5.1 Console and File Rolling Logging Configuration (`logback-spring.xml`)

In cloud-native microservices, log aggregation systems (such as ELK or Splunk) expect logs to be sent to standard output (stdout) as structured JSON streams. Below is the complete template `logback-spring.xml` file, which is placed in the `src/main/resources/` directory to configure standard logging formats:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<configuration>
    <include resource="org/springframework/boot/logging/logback/defaults.xml"/>

    <property name="LOG_FILE" value="${LOG_FILE:-${LOG_PATH:-${LOG_TEMP:-${java.io.tmpdir:-/tmp}}}/order-service.log}"/>

    <!-- 1. Console Appender for Local Development (Readable Text Format) -->
    <appender name="CONSOLE" class="ch.qos.logback.core.ConsoleAppender">
        <encoder>
            <pattern>%clr(%d{yyyy-MM-dd HH:mm:ss.SSS}){faint} %clr(${LOG_LEVEL_PATTERN:-%5p}) %clr(${PID:- }){magenta} %clr(---){faint} %clr([%15.15t]){faint} %clr(%-40.40logger{39}){cyan} %clr(:){faint} %m%n${LOG_EXCEPTION_CONVERSION_WORD:-%wEx}</pattern>
        </encoder>
    </appender>

    <!-- 2. Rolling File Appender for local debug collections -->
    <appender name="FILE" class="ch.qos.logback.core.rolling.RollingFileAppender">
        <file>${LOG_FILE}</file>
        <rollingPolicy class="ch.qos.logback.core.rolling.SizeAndTimeBasedRollingPolicy">
            <fileNamePattern>${LOG_FILE}.%d{yyyy-MM-dd}.%i.gz</fileNamePattern>
            <maxFileSize>10MB</maxFileSize>
            <maxHistory>7</maxHistory>
            <totalSizeCap>100MB</totalSizeCap>
        </rollingPolicy>
        <encoder>
            <pattern>%d{yyyy-MM-dd HH:mm:ss.SSS} ${LOG_LEVEL_PATTERN:-%5p} ${PID:- } --- [%t] %-40.40logger{39} : %m%n${LOG_EXCEPTION_CONVERSION_WORD:-%wEx}</pattern>
        </encoder>
    </appender>

    <!-- Application Log Level Configurations -->
    <logger name="com.ftgo.order" level="DEBUG"/>
    <logger name="org.springframework.web" level="INFO"/>
    <logger name="org.hibernate.SQL" level="INFO"/>

    <root level="INFO">
        <appender-ref ref="CONSOLE"/>
        <appender-ref ref="FILE"/>
    </root>
</configuration>
```

---


---

## 3.7 Orchestrating Backing Services with Docker Compose

During local development, a microservice must connect to its backing services (databases, caches). We use **Docker Compose** to orchestrate these containers, creating a local network where the service can communicate with PostgreSQL and Redis.

### The Orchestration Manifest: `docker-compose.yml`
Create the following file in the parent project directory (`docker-compose.yml`):

```yaml
version: '3.8'

services:
  # 1. PostgreSQL Database Container (Multiple Databases for Order & Kitchen Services)
  postgres:
    image: postgres:13-alpine
    container_name: ftgo_postgres
    environment:
      POSTGRES_USER: ftgo_user
      POSTGRES_PASSWORD: ftgo_password
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
      # Injects a script to initialize separate 'order_db' and 'kitchen_db' databases on startup
      - ./init-db.sql:/docker-entrypoint-initdb.d/init-db.sql
    networks:
      - ftgo-network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ftgo_user"]
      interval: 5s
      timeout: 5s
      retries: 5

  # 2. Redis Cache Container (Query caching for Order view lookups)
  redis:
    image: redis:6.2-alpine
    container_name: ftgo_redis
    ports:
      - "6379:6379"
    networks:
      - ftgo-network
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5

  # 3. Zookeeper Container (Coordinates Kafka brokers)
  zookeeper:
    image: confluentinc/cp-zookeeper:6.1.1
    container_name: ftgo_zookeeper
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181
      ZOOKEEPER_TICK_TIME: 2000
    networks:
      - ftgo-network

  # 4. Kafka Message Broker Container (Event streaming across subdomains)
  kafka:
    image: confluentinc/cp-kafka:6.1.1
    container_name: ftgo_kafka
    ports:
      - "9092:9092"
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9092,PLAINTEXT_HOST://localhost:29092
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: PLAINTEXT:PLAINTEXT,PLAINTEXT_HOST:PLAINTEXT
      KAFKA_INTER_BROKER_LISTENER_NAME: PLAINTEXT
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
    depends_on:
      - zookeeper
    networks:
      - ftgo-network
    healthcheck:
      test: ["CMD", "kafka-topics", "--bootstrap-server", "localhost:9092", "--list"]
      interval: 10s
      timeout: 5s
      retries: 5

  # 5. FTGO Order Service Application Container
  order-service:
    build:
      context: ./order-service
      dockerfile: Dockerfile
    image: ftgo/order-service:latest
    container_name: order_service_app
    ports:
      - "8081:8081"
    environment:
      SPRING_PROFILES_ACTIVE: dev
      SPRING_DATASOURCE_URL: jdbc:postgresql://postgres:5432/order_db
      SPRING_DATASOURCE_USERNAME: ftgo_user
      SPRING_DATASOURCE_PASSWORD: ftgo_password
      SPRING_KAFKA_BOOTSTRAP_SERVERS: kafka:9092
      SPRING_REDIS_HOST: redis
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      kafka:
        condition: service_healthy
    networks:
      - ftgo-network

  # 6. FTGO Kitchen Service Application Container
  kitchen-service:
    build:
      context: ./kitchen-service
      dockerfile: Dockerfile
    image: ftgo/kitchen-service:latest
    container_name: kitchen_service_app
    ports:
      - "8082:8082"
    environment:
      SPRING_PROFILES_ACTIVE: dev
      SPRING_DATASOURCE_URL: jdbc:postgresql://postgres:5432/kitchen_db
      SPRING_DATASOURCE_USERNAME: ftgo_user
      SPRING_DATASOURCE_PASSWORD: ftgo_password
      SPRING_KAFKA_BOOTSTRAP_SERVERS: kafka:9092
    depends_on:
      postgres:
        condition: service_healthy
      kafka:
        condition: service_healthy
    networks:
      - ftgo-network

volumes:
  pgdata:

networks:
  ftgo-network:
    driver: bridge
```

---

## 3.8 Production-Grade Spring Boot application.yml Configuration

In accordance with the Twelve-Factor App principles, configurations must be externalized. Below is the complete template `application.yml` for the `order-service`, configured to fetch secrets from environment variables with fallback profiles:

```yaml
server:
  port: 8081
  shutdown: graceful # Enable graceful shutdown to finish in-flight requests

spring:
  application:
    name: order-service
  profiles:
    active: ${SPRING_PROFILES_ACTIVE:dev} # Set default profile to dev

  # Database Connection Pooling Configuration (HikariCP)
  datasource:
    url: ${SPRING_DATASOURCE_URL:jdbc:postgresql://localhost:5432/order_db}
    username: ${SPRING_DATASOURCE_USERNAME:ftgo_user}
    password: ${SPRING_DATASOURCE_PASSWORD:ftgo_password}
    driver-class-name: org.postgresql.Driver
    hikari:
      maximum-pool-size: ${HIKARI_MAX_POOL_SIZE:10}
      minimum-idle: 2
      idle-timeout: 30000
      connection-timeout: 20000
      max-lifetime: 1800000
      pool-name: FTGOOrderServicePool

  # JPA & Hibernate Configurations
  jpa:
    database-platform: org.hibernate.dialect.PostgreSQLDialect
    hibernate:
      ddl-auto: update
    show-sql: false
    properties:
      hibernate:
        format_sql: true
        jdbc.batch_size: 25

  # Kafka Client Configurations
  kafka:
    bootstrap-servers: ${SPRING_KAFKA_BOOTSTRAP_SERVERS:localhost:29092}
    producer:
      key-serializer: org.apache.kafka.common.serialization.StringSerializer
      value-serializer: org.springframework.kafka.support.serializer.JsonSerializer
      acks: all # Guarantee durability
    consumer:
      key-deserializer: org.apache.kafka.common.serialization.StringDeserializer
      value-deserializer: org.springframework.kafka.support.serializer.JsonDeserializer
      group-id: order-service-group
      auto-offset-reset: earliest

# Production Actuator Endpoint Exposure
management:
  endpoints:
    web:
      exposure:
        include: health,info,metrics,prometheus
  endpoint:
    health:
      show-details: always
      probes:
        enabled: true # Enable liveness and readiness probes for Kubernetes
```

---

## 3.9 Mapping the 12 Factors to Spring Boot and Docker

To create a cloud-native delivery setup, we map all guidelines of the **Twelve-Factor App** manifesto directly to our project parameters:

| Factor Guideline | Technical Mapping in Java / Spring Boot | Container / Docker Implementation |
| :--- | :--- | :--- |
| **1. Codebase** | Single repository tracked in Git; multiple module directories (`order-service`, `kitchen-service`). | Continuous Integration builds unique image hashes per branch commit. |
| **2. Dependencies** | Explicit dependencies declared in Maven `pom.xml`. No reliance on local system utilities. | Multi-Stage builds using `dependencies/` directory separation. |
| **3. Config** | Configuration stored in environment variables, injected using Spring properties interpolation `${VAR:fallback}`. | Injected using `environment:` lists in Docker Compose manifests. |
| **4. Backing Services** | Handled as resource bindings; local configs fetch database connections via URL hostnames. | Linked using local bridge networks (e.g. `postgres:5432/order_db`). |
| **5. Build, Release, Run** | Maven handles the `build` phase. Release bundles configure images. | Image tags separate configurations from the binary code. |
| **6. Processes** | App is stateless; shared transactions are persisted in PostgreSQL. | Scaling triggers spin up multiple identical container replicas. |
| **7. Port Binding** | Embedded Tomcat binds port `8081` internally. | Ports exposed publicly using port forwarding declarations. |
| **8. Concurrency** | Scaled horizontally by launching multiple JVM process containers. | Docker Compose replicas or Kubernetes Deployment pods handle scaling. |
| **9. Disposability** | Minimizes startup times; listens to SIGTERM for graceful shutdown. | Docker stops containers safely within a 10s grace limit. |
| **10. Dev/Prod Parity** | Local run uses matching database platforms (PostgreSQL container matching staging DBs). | Consistent base runtime image definitions across all stages. |
| **11. Logs** | Writes logs directly to stdout/stderr using standard console appenders. | Logging drivers capture stdout streams and aggregate to OpenSearch. |
| **12. Admin Processes** | Executed using independent administrative JVM runners or tasks. | Run tasks using `docker-compose exec` wrappers. |

---

### 3.9.1 Detailed Analysis of the Twelve-Factor Guidelines

#### 1. One Codebase, One App
There is a one-to-one correlation between a microservice and its code repository. If there are multiple repositories, it is a distributed system of independent apps, not a single cohesive microservice. In our FTGO project, `order-service` and `kitchen-service` are isolated modules, each mapping to its own deployment pipelines, ensuring that changes to the ordering logic do not force updates or deployments of the kitchen logic.

#### 2. Explicitly Declare and Isolate Dependencies
A microservice must never rely on the implicit existence of system tools or libraries on the host operating system. All dependencies must be declared explicitly. In Java, this is handled by Maven (`pom.xml`) or Gradle. In containerized environments, the Dockerfile isolates dependencies: we install the exact JDK runtime, copy target libraries, and avoid relying on host libraries.

#### 3. Store Configuration in the Environment
Strictly separate config (which changes across deployments like development, staging, production) from code (which remains constant). Code must never contain raw database passwords or hostnames. We configure Spring Boot to interpolate properties using environment values (`${SPRING_DATASOURCE_URL}`), letting the container platform inject secrets dynamically.

#### 4. Treat Backing Services as Attached Resources
A backing service is any service that the application consumes over the network, such as a database (PostgreSQL), message broker (Kafka), or caching store (Redis). To the application, local backing services and cloud-hosted SaaS services must be identical: they are accessed via dynamic resource URLs configuration settings, allowing seamless swaps without code changes.

#### 5. Strictly Separate Build, Release, and Run Stages
The deployment process must be split into three isolated steps:
* **Build**: Translates code into a compiler artifact (compiling Java classes to a JAR file via Maven).
* **Release**: Combines the build artifact with the active environment configuration (combining the JAR with environment variables in a container image).
* **Run**: Starts the container process in the target execution environment.

#### 6. Execute the App as One or More Stateless Processes
Twelve-Factor processes are stateless and share nothing. Any stateful data that needs to persist must be stored in a stateful backing service (PostgreSQL or Redis). This allows the application processes to be destroyed, rescheduled, or scaled without risk of data loss.

#### 7. Export Services via Port Binding
The microservice must be completely self-contained and expose its services by binding to a port. Spring Boot accomplishes this by embedding Apache Tomcat within the runner. The container exposes this port (e.g. `8081`) to the bridge network, making routing configurations simple.

#### 8. Scale Out via the Process Model
Microservices do not rely on threading systems internally to scale. Instead, they scale horizontally by running multiple independent stateless processes (horizontal scaling). The execution platform (Docker Compose or Kubernetes) clones the stateless containers to handle spikes in throughput.

#### 9. Maximize Robustness with Fast Startup and Graceful Shutdown
Processes must be disposable, meaning they can be started or stopped at a moment's notice. This facilitates fast elastic scaling and rapid deployment rollouts. We configure Spring Boot's `server.shutdown: graceful` profile to allow active transactions to finish before terminating.

#### 10. Keep Development, Staging, and Production as Similar as Possible
Minimize gaps between development and production environments:
* **Time gap**: Deploy code quickly (hours instead of weeks).
* **People gap**: Developers write code and coordinate its deployment.
* **Tool gap**: Use matching backing services locally (using a PostgreSQL container for local tests instead of relying on H2, avoiding SQL compatibility mismatches in production).

#### 11. Treat Logs as Event Streams
Applications must never manage their own log files. Instead, they write logs directly to the standard output (`stdout`). The execution environment captures these streams, processes them using log shippers (Fluentd), and routes them to Elasticsearch or OpenSearch.

#### 12. Run Admin Tasks as One-Off Processes
Administrative tasks (database schema migrations, cleanup scripts) must run as one-off processes in the same environment as the application. We execute migrations using tools like Liquibase or Flyway as initialization tasks before the main container boots.

---
### Command Guide for Docker Compose Operations

#### Start the orchestration environment
Runs the containers in the background:
```bash
docker-compose up -d
```

#### Build and update the microservice container
Rebuilds the microservice image if changes are made to the code:
```bash
docker-compose up -d --build order-service
```

#### Check container status
Lists running containers and their health status:
```bash
docker-compose ps
```

#### View application logs
Streams logs from the microservice container:
```bash
docker-compose logs -f order-service
```

#### View database logs
Streams logs from the PostgreSQL database container:
```bash
docker-compose logs -f postgres
```

#### View Kafka broker logs
Streams logs from the Kafka broker container:
```bash
docker-compose logs -f kafka
```

#### Inspect local bridge network settings
Inspects the container network details:
```bash
docker network inspect ftgo-microservices_ftgo-network
```

#### Inspect volume storage paths
Inspects physical storage path mappings:
```bash
docker volume inspect ftgo-microservices_pgdata
```

#### Stop and remove the orchestration environment
Stops the containers but preserves data volumes:
```bash
docker-compose down
```

#### Stop and remove the orchestration environment including volumes
Stops the containers and deletes all data volumes:
```bash
docker-compose down -v
```

---

## 3.10 Troubleshooting Local Docker Compose Environments

When running a complex multi-container ecosystem locally, developers frequently encounter runtime issues. Below is a diagnostic troubleshooting matrix for resolving common container anomalies:

### 3.10.1 Port Binding Collision
* **The Symptom**: Starting Docker Compose fails with: `Bind for 0.0.0.0:5432 failed: port is already allocated`.
* **The Cause**: A local instance of PostgreSQL is already running directly on the host machine and occupying port `5432`.
* **The Resolution**:
  * Identify and terminate the host process. On Windows:
    ```powershell
    netstat -ano | findstr 5432
    # Stop the local postgres service
    Stop-Service -Name postgresql*
    ```
  * Alternatively, map the container to an alternative host port in `docker-compose.yml` (e.g., `"5433:5432"`).

### 3.10.2 Database Initialization Race Conditions
* **The Symptom**: The `order-service` container crashes on startup with database connection timeouts: `Connection to postgres:5432 refused`.
* **The Cause**: The database container is running, but the internal PostgreSQL engine is still starting up and not yet ready to accept socket connections when the Spring Boot JVM starts.
* **The Resolution**:
  * Do not rely on basic `depends_on` which only tracks container startup. Ensure you are using the extended syntax with a `healthcheck` declaration:
    ```yaml
    depends_on:
      postgres:
        condition: service_healthy
    ```

### 3.10.3 Kafka Advertised Listener Mismatches
* **The Symptom**: Spring Boot is unable to send messages to Kafka, logging infinite connection retries: `Connection to localhost:29092 could not be established`.
* **The Cause**: Kafka clients inside the Docker network use different hostnames than clients outside the Docker network.
* **The Resolution**: Configure both internal and external listeners inside the broker environment properties:
  - `KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9092,PLAINTEXT_HOST://localhost:29092`
  - In-network containers connect via `kafka:9092`, while external host applications connect via `localhost:29092`.

---


---

## Chapter Summary

* **Spring Boot** simplifies enterprise Java by embedding web servers (Tomcat) directly inside the executable JAR, using opinions (starters), and providing auto-configuration.
* **Externalized configurations** map variables inside `application.yml` and use profiles (dev, prod) to adapt to different environments without changes to the code.
* The **Twelve-Factor App** manifesto defines best practices for cloud-native applications: codebase, dependencies, config, backing services, build/release/run separation, processes, port binding, concurrency, disposability, dev/prod parity, logs, and admin processes.
* **Virtual Machines** include guest operating systems and require hypervisors, resulting in a large footprint. **Docker Containers** share the host operating system kernel, making them lightweight and fast to boot.
* A **Multi-Stage Build** separates code compilation from container execution, keeping the production container footprint small.
* Spring Boot's **dependency layering** split (dependencies, spring-boot-loader, snapshot-dependencies, application) uses Docker's layer cache to speed up container build times.
* **Docker Compose** orchestrates services (like databases and caches) locally using bridge networks, port mappings, volumes, env parameters, and health checks.
