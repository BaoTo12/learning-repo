# Chapter 6: API Gateway & Service Routing

In a microservices architecture, a single client request (such as displaying a user dashboard) might require calling multiple independent backend microservices. If client applications communicate directly with these services, they must handle complex routing, manage different authentication protocols, and make multiple network requests over slow mobile connections. This direct communication increases security exposure, network overhead, and client-side complexity.

This chapter covers the **API Gateway pattern**. We will analyze how a gateway acts as a single entry point to route requests, manage cross-cutting concerns (authentication, rate limiting, and request tracing), and compare the blocking **Netflix Zuul** proxy with the reactive, non-blocking **Spring Cloud Gateway**. Finally, we will configure manual and automated route mappings, build custom pre- and post-routing gateway filters to trace requests, and configure Redis-based rate limiting.

---

## Learning Objectives

By the end of this chapter, you will be able to:
1. Explain the architectural benefits of the API Gateway pattern over direct client-to-service communication.
2. Analyze the difference between blocking thread-pool models and reactive, non-blocking gateways.
3. Configure automated and manual route mappings in **Spring Cloud Gateway**.
4. Build custom pre-routing and post-routing **Gateway Filters** to generate and propagate correlation IDs.
5. Secure downstream services by propagating OAuth2 authorization headers through the gateway.
6. Configure Redis-based **Request Rate Limiting** to protect endpoints from overload.
7. Explain Spring Cloud Gateway Handler Mapping and Web Handler lifecycle routing.
8. Implement reactive JWT validation using Spring Security WebFlux at the gateway edge.
9. Define global custom JSON exception handlers for downstream microservice connection failures.
10. Configure Header Predicates to route requests dynamically for Canary rollouts.


---

## 6.1 The API Gateway Pattern

Without an API gateway, client applications must interact directly with the unique network endpoints of each microservice:

![Figure 6.1: Service topology without an API gateway](https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//47e368cf-85e5-4073-98f9-7f4002948ac7/markdown_3/imgs/img_in_image_box_139_1004_870_1162.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T09%3A47%3A38Z%2F-1%2F%2F8c45f97e1dcf341cd20b0a0bf53523ccc0cd1cd6b756158bc4c399f7f309c440)
*Figure 6.1: Direct client-to-service communication without an intermediary API gateway.*

This direct communication model leads to:
* **Tight Coupling**: Clients must know the host addresses, ports, and query parameters of all services. If a service is refactored, split, or relocated, client applications break.
* **Security Exposure**: Every microservice must expose a public IP address to accept client traffic, increasing the attack surface of the system.
* **Network Overhead**: The client must execute multiple sequential HTTP requests (e.g. fetching user data, then orders, then billing details) over slow mobile networks, increasing latency.
* **Redundant Logic**: Cross-cutting concerns such as user authentication, SSL termination, request logging, and rate limiting must be implemented in every service.

An **API Gateway** acts as a reverse proxy, standing between client applications and internal backend services:

![Figure 6.2: Service topology with an API gateway as a single entry point](https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//47e368cf-85e5-4073-98f9-7f4002948ac7/markdown_4/imgs/img_in_image_box_145_280_932_451.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T09%3A47%3A39Z%2F-1%2F%2Fc7632fefd32a14f446858f029d06a14fc58eb4e7681d8862f95c74425dedf1cf)
*Figure 6.2: All client requests flow through the API gateway, which routes calls to internal services.*

### Core Functions of an API Gateway:
* **Routing**: Maps public URL paths to internal microservice coordinates using service discovery.
* **Security**: Authenticates client credentials at the edge and passes token contexts downstream.
* **Request Aggregation**: Combines responses from multiple services into a single response payload, reducing client-side requests.
* **Rate Limiting**: Intercepts requests and enforces traffic limits to protect backend services from denial-of-service (DoS) attacks or traffic spikes.

---

## 6.2 Blocking vs. Non-Blocking Gateways: Netflix Zuul vs. Spring Cloud Gateway

Choosing the architecture of your API gateway affects system throughput and resource usage:

### Netflix Zuul 1.x (Blocking Servlet Engine)
Zuul 1.x uses a traditional **one-thread-per-request** blocking servlet model. 
* **Mechanism**: Each incoming HTTP request is assigned to a dedicated thread from a thread pool. The thread manages the entire request lifecycle, including blocking I/O calls to downstream services.
* **Limitations**: If a downstream service runs slowly (e.g. database locks or high CPU load), the assigned thread is blocked waiting for the response. Under high loads, this leads to thread pool exhaustion, which increases latency and causes gateway crashes.

### Spring Cloud Gateway (Reactive, Non-Blocking)
Built on Spring Boot 2.x, Spring WebFlux, and Project Reactor, it utilizes an asynchronous, non-blocking event-loop model.
* **Mechanism**: A small, fixed number of threads (typically matching the host's CPU core count) handle all requests. When a request is waiting for a downstream service, the event loop registers a callback and frees the thread to process other incoming requests. When the downstream service returns a response, a callback resumes the original request.
* **Benefits**: Handles thousands of concurrent connections with low memory and CPU overhead.

---

## 6.3 Configuring Routes in Spring Cloud Gateway

Spring Cloud Gateway maps routes based on **Predicates** and modifies requests/responses using **Filters**.

### Project Setup
Include the Spring Cloud Gateway starter, Actuator, Config Client, and Eureka client dependencies in the gateway's `pom.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    <parent>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-parent</artifactId>
        <version>2.5.4</version>
        <relativePath/>
    </parent>
    <groupId>com.ftgo</groupId>
    <artifactId>gateway-server</artifactId>
    <version>1.0.0-SNAPSHOT</version>
    <name>FTGO API Gateway Server</name>
    <description>API Gateway Server for FTGO Food Delivery System</description>

    <dependencies>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-actuator</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.cloud</groupId>
            <artifactId>spring-cloud-starter-config</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.cloud</groupId>
            <artifactId>spring-cloud-starter-gateway</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.cloud</groupId>
            <artifactId>spring-cloud-starter-netflix-eureka-client</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-test</artifactId>
            <scope>test</scope>
        </dependency>
    </dependencies>

    <dependencyManagement>
        <dependencies>
            <dependency>
                <groupId>org.springframework.cloud</groupId>
                <artifactId>spring-cloud-dependencies</artifactId>
                <version>2020.0.3</version>
                <type>pom</type>
                <scope>import</scope>
            </dependency>
        </dependencies>
    </dependencyManagement>
</project>
```

---

## 6.2.1 Spring Cloud Gateway Handler Architecture

To implement custom filters effectively, developers must understand the internal request processing pipeline of Spring Cloud Gateway. It uses a three-tier architecture to resolve and route client requests:

```
Client Request -> [ Gateway Handler Mapping ]
                             |
                             v
                  [ Gateway Web Handler ] -> Executes Filter Chain (Pre-filters)
                             |
                             v
                    [ Downstream Proxy ] -> Invokes Backend Microservice
                             |
                             v
                  [ Gateway Web Handler ] -> Executes Filter Chain (Post-filters)
                             |
                             v
Client Response <- [ Outbound response headers ]
```

1. **Gateway Handler Mapping**: Evaluates the request against the configured routes. If a matching route is found (based on path, headers, methods, etc.), it forwards the request to the Web Handler.
2. **Gateway Web Handler**: Manages the execution of the filter chain. The filter chain consists of global filters and route-specific filters. It executes all "Pre-filter" logic sequentially before forwarding the request.
3. **Downstream Proxy / Web Client**: Routes the mutated request to the target backend microservice.
4. **Post-filter chain**: Once the response is returned from the microservice, the Web Handler executes the "Post-filter" logic in reverse order, allowing filters to inspect or modify the outgoing response.

---

---

### Config Server Integration: `bootstrap.yml`
Set up the local `bootstrap.yml` to specify config server details:

```yaml
spring:
  application:
    name: gateway-server
  cloud:
    config:
      uri: http://localhost:8071
```

---

### Automated Route Mapping
The gateway can query a service discovery registry (like Eureka) to automatically map routes based on service application IDs:

```yaml
spring:
  cloud:
    gateway:
      discovery:
        locator:
          enabled: true # Enables dynamic service routing based on Eureka
          lowerCaseServiceId: true # Matches lowercase service IDs in path
```

With `discovery.locator.enabled` set to true, the gateway automatically routes requests to Eureka-registered services:
* A request to `http://localhost:8072/order-service/v1/restaurant/1/order` is routed to the service registered as `ORDER-SERVICE`.

---

### Manual Route Mapping
For fine-grained control, define route mappings manually inside `gateway-server.yml` hosted on the Config Server:

```yaml
server:
  port: 8072

eureka:
  instance:
    preferIpAddress: true
  client:
    registerWithEureka: true
    fetchRegistry: true
    serviceUrl:
      defaultZone: http://eurekaserver:8070/eureka/

spring:
  cloud:
    gateway:
      routes:
        # Route 1: order-service manual mapping
        - id: order-service
          uri: lb://order-service # lb:// indicates client-side load balancing via Eureka
          predicates:
            - Path=/order/** # Matches any path starting with /order/
          filters:
            # Strip the prefix '/order' from the path before routing downstream
            - StripPrefix=1 

        # Route 2: kitchen-service manual mapping
        - id: kitchen-service
          uri: lb://kitchen-service
          predicates:
            - Path=/kitchen/**
          filters:
            - StripPrefix=1
```

If a client sends a request to `http://localhost:8072/order/v1/restaurant/1/order`, the gateway strips the `/order` prefix and forwards the request to a healthy instance of `order-service` at `/v1/restaurant/1/order`.

---

## 6.4 Custom Gateway Filters

Filters intercept incoming requests and outgoing responses, allowing you to execute logic at the gateway boundary. We build these filters by implementing Spring Cloud Gateway's `GlobalFilter` interface.

We will build a pre-routing filter to trace requests across microservices. This filter checks if a correlation ID is present in the request headers; if not, it generates a new UUID and injects it into the headers.

```
 Client Request         TrackingFilter         Target Route         ResponseFilter
       |                      |                      |                     |
       |--- HTTP Request ---->|                      |                     |
       |    (Add Trace ID)    |                      |                     |
       |                      |--- Forward Request ->|                     |
       |                      |                      |--- Return Response -|
       |                      |                      |    (Collect Logs)   |
       |<------------------ Return HTTP Response --------------------------|
       |                    (Inject Trace ID)
```

---

### 1. The Filter Utility Class: `FilterUtils.java`
Create a helper class to read and modify HTTP headers:

```java
package com.ftgo.gateway.filters;

import org.springframework.http.HttpHeaders;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ServerWebExchange;
import java.util.List;

@Component
public class FilterUtils {

    public static final String CORRELATION_ID = "ftgo-correlation-id";
    public static final String AUTH_TOKEN     = "Authorization";
    public static final String USER_ID        = "ftgo-user-id";
    public static final String RESTAURANT_ID  = "ftgo-restaurant-id";

    public String getCorrelationId(HttpHeaders headers) {
        List<String> headerList = headers.get(CORRELATION_ID);
        if (headerList != null && !headerList.isEmpty()) {
            return headerList.get(0);
        }
        return null;
    }

    public ServerWebExchange setCorrelationId(ServerWebExchange exchange, String correlationId) {
        return this.setRequestHeader(exchange, CORRELATION_ID, correlationId);
    }

    public ServerWebExchange setRequestHeader(ServerWebExchange exchange, String name, String value) {
        return exchange.mutate()
                .request(exchange.getRequest().mutate().header(name, value).build())
                .build();
    }
}
```

---

### 2. The Tracking Pre-Filter: `TrackingFilter.java`
Create a global filter to intercept requests and check for correlation IDs:

```java
package com.ftgo.gateway.filters;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.cloud.gateway.filter.GatewayFilterChain;
import org.springframework.cloud.gateway.filter.GlobalFilter;
import org.springframework.core.annotation.Order;
import org.springframework.http.HttpHeaders;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ServerWebExchange;
import reactor.core.publisher.Mono;

import java.util.UUID;

@Order(1) // Executed first in the filter chain
@Component
public class TrackingFilter implements GlobalFilter {

    private static final Logger logger = LoggerFactory.getLogger(TrackingFilter.class);

    @Autowired
    private FilterUtils filterUtils;

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, GatewayFilterChain chain) {
        HttpHeaders requestHeaders = exchange.getRequest().getHeaders();
        String correlationId = filterUtils.getCorrelationId(requestHeaders);

        if (correlationId != null) {
            logger.debug("Correlation ID found in tracking filter: {}. ", correlationId);
        } else {
            correlationId = UUID.randomUUID().toString();
            exchange = filterUtils.setCorrelationId(exchange, correlationId);
            logger.debug("Generated Correlation ID in tracking filter: {}.", correlationId);
        }

        return chain.filter(exchange);
    }
}
```

---

### 3. The Response Post-Filter: `ResponseFilter.java`
We will build a post-filter to inject the correlation ID back into the HTTP response headers returned to the client:

```java
package com.ftgo.gateway.filters;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.cloud.gateway.filter.GlobalFilter;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpHeaders;
import reactor.core.publisher.Mono;

@Configuration
public class ResponseFilter {

    private static final Logger logger = LoggerFactory.getLogger(ResponseFilter.class);

    @Autowired
    private FilterUtils filterUtils;

    @Bean
    public GlobalFilter postGlobalFilter() {
        return (exchange, chain) -> chain.filter(exchange).then(Mono.fromRunnable(() -> {
            HttpHeaders requestHeaders = exchange.getRequest().getHeaders();
            String correlationId = filterUtils.getCorrelationId(requestHeaders);
            
            logger.debug("Injecting the correlation ID back to the outbound headers: {}.", correlationId);
            exchange.getResponse().getHeaders().add(FilterUtils.CORRELATION_ID, correlationId);
            logger.debug("Request path completed: {}", exchange.getRequest().getPath());
        }));
    }
}
```

---

## 6.5 Downstream Correlation Propagation (User Context)

When a call goes through the API Gateway, we must propagate the trace/correlation ID across all subsequent microservice requests executing within the transaction context:

```
  Client          Gateway            Order Service             Kitchen Service
    |                |                     |                           |
    |-- GET Order -->| (Generate Trace ID) |                           |
    |                |----- GET Order ---->| (Save ThreadLocal)        |
    |                |                     |----- GET Ticket --------->|
    |                |                     |      (Propagate Header)   |
```

To implement this context propagation pipeline, each microservice must include three classes: `UserContext`, `UserContextHolder`, and `UserContextFilter`.

### 1. Context Model: `UserContext.java`
This class holds the tracing values scraped from the request:

```java
package com.ftgo.order.utils;

import org.springframework.stereotype.Component;

@Component
public class UserContext {
    public static final String CORRELATION_ID = "ftgo-correlation-id";
    public static final String AUTH_TOKEN     = "Authorization";
    public static final String USER_ID        = "ftgo-user-id";
    public static final String RESTAURANT_ID  = "ftgo-restaurant-id";

    private String correlationId = "";
    private String authToken = "";
    private String userId = "";
    private String restaurantId = "";

    public String getCorrelationId() { return correlationId; }
    public void setCorrelationId(String correlationId) { this.correlationId = correlationId; }

    public String getAuthToken() { return authToken; }
    public void setAuthToken(String authToken) { this.authToken = authToken; }

    public String getUserId() { return userId; }
    public void setUserId(String userId) { this.userId = userId; }

    public String getRestaurantId() { return restaurantId; }
    public void setRestaurantId(String restaurantId) { this.restaurantId = restaurantId; }
}
```

---

### 2. Thread-Local Holder: `UserContextHolder.java`
Stores the request context inside a ThreadLocal variable, making it accessible to any method executed by the active thread:

```java
package com.ftgo.order.utils;

import org.springframework.util.Assert;

public class UserContextHolder {
    private static final ThreadLocal<UserContext> userContext = new ThreadLocal<>();

    public static final UserContext getContext() {
        UserContext context = userContext.get();
        if (context == null) {
            context = new UserContext();
            userContext.set(context);
        }
        return userContext.get();
    }

    public static final void setContext(UserContext context) {
        Assert.notNull(context, "Only non-null UserContext instances are permitted");
        userContext.set(context);
    }
}
```

---

### 3. Servlet Filter: `UserContextFilter.java`
Intercepts incoming HTTP requests inside each microservice to extract tracing headers and map them to `UserContextHolder`:

```java
package com.ftgo.order.utils;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;
import javax.servlet.*;
import javax.servlet.http.HttpServletRequest;

import java.io.IOException;

@Component
public class UserContextFilter implements Filter {
    private static final Logger logger = LoggerFactory.getLogger(UserContextFilter.class);

    @Override
    public void doFilter(ServletRequest request, ServletResponse response, FilterChain chain)
            throws IOException, ServletException {
        HttpServletRequest httpRequest = (HttpServletRequest) request;

        UserContextHolder.getContext().setCorrelationId(httpRequest.getHeader(UserContext.CORRELATION_ID));
        UserContextHolder.getContext().setUserId(httpRequest.getHeader(UserContext.USER_ID));
        UserContextHolder.getContext().setAuthToken(httpRequest.getHeader(UserContext.AUTH_TOKEN));
        UserContextHolder.getContext().setRestaurantId(httpRequest.getHeader(UserContext.RESTAURANT_ID));

        logger.debug("UserContextFilter Correlation ID: {}", UserContextHolder.getContext().getCorrelationId());
        chain.doFilter(request, response);
    }
}
```

---

### 4. Client Request Interceptor: `UserContextInterceptor.java`
Injects correlation headers into any outgoing HTTP request executed from a RestTemplate instance:

```java
package com.ftgo.order.utils;

import org.springframework.http.HttpRequest;
import org.springframework.http.client.ClientHttpRequestExecution;
import org.springframework.http.client.ClientHttpRequestInterceptor;
import org.springframework.http.client.ClientHttpResponse;
import java.io.IOException;

public class UserContextInterceptor implements ClientHttpRequestInterceptor {

    @Override
    public ClientHttpResponse intercept(HttpRequest request, byte[] body, ClientHttpRequestExecution execution)
            throws java.io.IOException {
        request.getHeaders().add(UserContext.CORRELATION_ID, UserContextHolder.getContext().getCorrelationId());
        request.getHeaders().add(UserContext.AUTH_TOKEN, UserContextHolder.getContext().getAuthToken());
        request.getHeaders().add(UserContext.USER_ID, UserContextHolder.getContext().getUserId());
        request.getHeaders().add(UserContext.RESTAURANT_ID, UserContextHolder.getContext().getRestaurantId());
        return execution.execute(request, body);
    }
}
```

Add this interceptor to the `RestTemplate` bean:

```java
@LoadBalanced
@Bean
public RestTemplate getRestTemplate() {
    RestTemplate template = new RestTemplate();
    java.util.List<ClientHttpRequestInterceptor> interceptors = template.getInterceptors();
    if (interceptors == null) {
        template.setInterceptors(java.util.Collections.singletonList(new UserContextInterceptor()));
    } else {
        interceptors.add(new UserContextInterceptor());
        template.setInterceptors(interceptors);
    }
    return template;
}
```

---

## 6.6 Request Rate Limiting

Rate limiting restricts the volume of requests sent to an API within a given window, preventing resource exhaustion. Spring Cloud Gateway integrates with **Redis** to enforce rate limiting using the **Token Bucket Algorithm**.

### 1. Configure Redis Rate Limiter: `application.yml`
Add the Redis rate limiter configurations inside the gateway route mapping:

```yaml
spring:
  redis:
    host: localhost
    port: 6379
  cloud:
    gateway:
      routes:
        - id: order-service
          uri: lb://order-service
          predicates:
            - Path=/order/**
          filters:
            - StripPrefix=1
            - name: RequestRateLimiter
              args:
                # Spring Expression Language (SpEL) pointing to a KeyResolver bean
                key-resolver: "#{@userKeyResolver}"
                # The number of tokens added to the bucket per second (average rate)
                redis-rate-limiter.replenishRate: 10
                # The maximum number of requests a client can make in a single second (burst capacity)
                redis-rate-limiter.burstCapacity: 20
```

---

### 2. Configure KeyResolver Bean
The `KeyResolver` determines the key used to group rate limits (e.g. rate limiting by client IP address, authenticated user ID, or client application ID).

Define the `KeyResolver` bean configuration:

```java
package com.ftgo.gateway.config;

import org.springframework.cloud.gateway.filter.ratelimit.KeyResolver;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import reactor.core.publisher.Mono;

@Configuration
public class RateLimiterConfig {

    @Bean
    public KeyResolver userKeyResolver() {
        // Rate limit clients based on their IP address
        return exchange -> Mono.just(
            exchange.getRequest().getRemoteAddress().getAddress().getHostAddress()
        );
    }
}
```

If a client exceeds the configured rate (10 requests/sec, with up to 20 requests in a burst), the gateway rejects the request and returns an HTTP status code **429 Too Many Requests**.

---

## 6.7 Gateway Security Integration with OAuth2 JWT Validation

In microservice architectures, the API Gateway is the ideal boundary to authorize requests, validate JSON Web Tokens (JWT), and prevent unauthenticated traffic from reaching backend subdomains.

Since Spring Cloud Gateway is built on **Spring WebFlux**, we configure security using reactive configurations:

### 6.7.1 Security Configuration: `GatewaySecurityConfig.java`
Create the configuration bean to enable the OAuth2 Resource Server and configure authorization scopes:

```java
package com.ftgo.gateway.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.web.reactive.EnableWebFluxSecurity;
import org.springframework.security.config.web.server.ServerHttpSecurity;
import org.springframework.security.web.server.SecurityWebFilterChain;

@Configuration
@EnableWebFluxSecurity
public class GatewaySecurityConfig {

    @Bean
    public SecurityWebFilterChain securityWebFilterChain(ServerHttpSecurity http) {
        http
            .csrf().disable() // Disable CSRF for stateless REST APIs
            .authorizeExchange()
            .pathMatchers("/order/v1/restaurant/*/order").hasAuthority("SCOPE_write:orders") // Restrict order writes
            .pathMatchers("/kitchen/v1/kitchen/**").hasAuthority("SCOPE_read:tickets")
            .anyExchange().authenticated() // All other requests require a valid token
            .and()
            .oauth2ResourceServer()
            .jwt(); // Configure token validation using JWKS
        return http.build();
    }
}
```

### 6.7.2 Propagating JWT Claims Downstream: `TokenPropagationFilter.java`
After verifying the JWT, the gateway extracts user information and injects it into outbound HTTP headers so downstream services (like `order-service`) do not have to parse the token again:

```java
package com.ftgo.gateway.filters;

import org.springframework.cloud.gateway.filter.GatewayFilterChain;
import org.springframework.cloud.gateway.filter.GlobalFilter;
import org.springframework.security.core.context.ReactiveSecurityContextHolder;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ServerWebExchange;
import reactor.core.publisher.Mono;

@Component
public class TokenPropagationFilter implements GlobalFilter {

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, GatewayFilterChain chain) {
        return ReactiveSecurityContextHolder.getContext()
            .map(securityContext -> securityContext.getAuthentication().getPrincipal())
            .cast(Jwt.class)
            .map(jwt -> {
                String userId = jwt.getSubject();
                // Inject the user ID extracted from JWT claims into outbound headers
                return exchange.mutate()
                    .request(exchange.getRequest().mutate()
                        .header(FilterUtils.USER_ID, userId)
                        .build())
                    .build();
            })
            .defaultIfEmpty(exchange)
            .flatMap(chain::filter);
    }
}
```

---

## 6.8 Global Custom Exception Handler Filter (JSON Error Format)

If a downstream service is down (e.g. `order-service` returns a connection exception), Spring Cloud Gateway returns a default HTML error page. To provide a clean developer experience, we override the default error handler to return structured JSON payloads:

### 6.8.1 Exception Handler: `GlobalGatewayExceptionHandler.java`
```java
package com.ftgo.gateway.exception;

import org.springframework.boot.web.reactive.error.ErrorWebExceptionHandler;
import org.springframework.core.annotation.Order;
import org.springframework.core.io.buffer.DataBuffer;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ServerWebExchange;
import reactor.core.publisher.Mono;

import java.nio.charset.StandardCharsets;
import java.time.LocalDateTime;

@Order(-1) // Mandatory order assignment to execute before default Spring Boot Error Web Handlers
@Component
public class GlobalGatewayExceptionHandler implements ErrorWebExceptionHandler {

    /**
     * Intercepts reactive exceptions thrown during the gateway routing lifecycle.
     * Overrides default whitelabel HTML error responses with structured JSON formats.
     */
    @Override
    public Mono<Void> handle(ServerWebExchange exchange, Throwable ex) {
        HttpStatus status = HttpStatus.INTERNAL_SERVER_ERROR;
        String message = "Internal Gateway Error";

        // Map Spring Cloud Gateway specific routing failures to appropriate HTTP statuses
        if (ex instanceof org.springframework.cloud.gateway.support.NotFoundException) {
            status = HttpStatus.NOT_FOUND;
            message = "Service Endpoint Not Found";
        } else if (ex instanceof java.net.ConnectException) {
            // Downstream microservices connection refused
            status = HttpStatus.SERVICE_UNAVAILABLE;
            message = "Downstream Microservice Offline";
        }

        // Set outgoing response headers
        exchange.getResponse().setStatusCode(status);
        exchange.getResponse().getHeaders().setContentType(MediaType.APPLICATION_JSON);

        // Format custom error JSON payload matching standard enterprise schemas
        String errorJson = String.format(
            "{\"timestamp\":\"%s\",\"status\":%d,\"error\":\"%s\",\"message\":\"%s\",\"path\":\"%s\"}",
            LocalDateTime.now(), status.value(), status.getReasonPhrase(), message, exchange.getRequest().getPath()
        );

        // Convert JSON payload to byte arrays using UTF-8 encoding
        byte[] bytes = errorJson.getBytes(StandardCharsets.UTF_8);
        
        // Wrap bytes in WebFlux DataBuffer segment
        DataBuffer buffer = exchange.getResponse().bufferFactory().wrap(bytes);
        
        // Write buffer stream directly back to client
        return exchange.getResponse().writeWith(Mono.just(buffer));
    }
}
```

---

## 6.9 Blue-Green Deployment Routing using Header Predicates

To implement canary rollouts or blue-green updates, the API Gateway can inspect incoming request headers and route traffic dynamically to different target clusters without changes to the client application code.

### 6.9.1 Configuring Header Predicates in YAML
Below is the route configuration inside `gateway-server.yml` mapping requests containing a specific version header to a canary deployment:

```yaml
spring:
  cloud:
    gateway:
      routes:
        # Route 1: Canary Deployments (V2 Version)
        - id: order-service-v2
          uri: lb://order-service-v2
          predicates:
            - Path=/order/**
            - Header=X-Version, v2 # Match requests containing header 'X-Version: v2'
          filters:
            - StripPrefix=1

        # Route 2: Default Production Deployment (V1 Version)
        - id: order-service-v1
          uri: lb://order-service
          predicates:
            - Path=/order/**
          filters:
            - StripPrefix=1
```

Using this setup:
* Standard requests to `/order/v1/restaurant/1/order` default to the stable `order-service` cluster.
* Beta-testing client requests sending the header `X-Version: v2` are intercepted and routed to the `order-service-v2` cluster, enabling safe canary testing in production.

---

## Chapter Summary

* An **API Gateway** serves as a reverse proxy to route requests, protect endpoints, and manage cross-cutting concerns (authentication, request tracing, rate limiting).
* Traditional gateways (Zuul 1.x) use a **blocking one-thread-per-request** model. Modern gateways (Spring Cloud Gateway) use a **reactive, non-blocking** event loop that handles high concurrency with minimal resource overhead.
* Spring Cloud Gateway supports **automated routing** via Eureka and **manual routing** using predicates and filters.
* **Gateway Filters** intercept requests and responses to perform actions like generating and propagating correlation IDs for request tracing.
* Downstream tracing context is managed using `UserContext` thread-local variables, mapping header parameters to thread boundaries, and injecting headers into outgoing `RestTemplate` calls using Spring interceptors.
* **Rate limiting** is enforced at the gateway boundary using a **Redis Rate Limiter** to monitor request rates and prevent resource exhaustion.
* Security is centralized at the gateway boundary using reactive **Spring Security WebFlux** filters that validate incoming OAuth2 JWT tokens before routing them downstream.
* Tracing headers and user context claims are extracted from JWT payloads and propagated to downstream services via global filters like `TokenPropagationFilter`.
* Downstream connection failures and route timeouts are intercepted using a custom `ErrorWebExceptionHandler` bean to return formatted JSON error payloads.
* Adaptive canary deployments and blue-green updates are supported at the routing layer by configuring **Header Predicates** to match client-specific header markers dynamically.

