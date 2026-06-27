# Chapter 29: Service Virtualization & API Emulation

Testing modern microservices requires communicating with numerous external dependencies, such as third-party payment processors, identity providers, and peer microservices. In development and staging environments, these dependencies are often unstable, slow, cost-prohibitive, or completely unavailable. While unit mocks isolate code inside the JVM, they do not verify real network transport, serialization layers, or client timeouts.

To address these limitations, we use **Service Virtualization**. Service Virtualization intercepts network traffic at the API boundary, emulating the HTTP/HTTPS behavior of external services without booting them. This chapter covers service virtualization using **Hoverfly**, a lightweight API emulation proxy. We will analyze Hoverfly execution modes, configure JVM proxy settings, handle SSL/TLS certificate interceptions, write advanced request matchers, and construct a complete resilient test suite for our Gamer Aggregator service that emulates network delays, error responses, and database updates.

---

## Learning Objectives

By the end of this chapter, you will be able to:
1. Explain the differences between unit mocking, containerized testing, and service virtualization.
2. Outline the benefits of service virtualization in removing external third-party API dependencies.
3. Configure Hoverfly to run in Capture, Simulate, Modify, Synthesize, and Spy modes.
4. Establish JVM proxy settings to intercept HTTP and HTTPS traffic cleanly.
5. Manage SSL/TLS certificate trust chains using Hoverfly custom CA certificates.
6. Write JUnit 5 test classes utilizing the Hoverfly Extension.
7. Build dynamic request matchers using globs, regular expressions, and payload body checkers.
8. Simulate network failures, latency, and HTTP status code errors to verify client resilience.
9. Implement Hoverfly simulation files to support headless integration testing in CI/CD pipelines.

---

## 29.1 What is Service Virtualization? Enterprise Mocking

Service virtualization is the process of simulating the API endpoints of a dependent service. While Java class mocking (e.g. Mockito) replaces a dependency inside the JVM, service virtualization acts as a mock at the **enterprise network layer**. It allows the target microservice to run unchanged, while all outbound network requests are intercepted and resolved by a local virtualized proxy:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//b06712ed-be74-4e52-8e15-c6632fb502ca/markdown_0/imgs/img_in_image_box_203_108_888_478.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A21%3A53Z%2F-1%2F%2Fc0be233cc1dcb93e1a4931962aaf5bef9e667322538be122d439e5b9f3add30f" alt="Image" width="64%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 9.1 Monolithic environment dependencies vs. virtualized microservice boundaries</div> </div>

As illustrated in Figure 9.1, instead of starting the target Service B and its downstream transitive dependencies (Services C and D), service virtualization replaces the entire network chain with a single virtualized responder.

---

### 29.1.1 Why and When to Use Service Virtualization
Service virtualization is preferred in the following scenarios:
1. **Unstable Staging Environments**: Staging servers are frequently redeployed, causing test runs to fail due to temporary network glitches.
2. **Third-Party Payment Gates**: Calling real API sandboxes (like Stripe or PayPal) is slow, rate-limited, and can incur costs.
3. **Negative Testing (Fault Injection)**: It is difficult to force a live external service to return a `503 Service Unavailable` or trigger a 10-second timeout to test your Hystrix or Resilience4j circuit breakers. Virtualization proxies make fault injection trivial.

---

## 29.2 Introducing Hoverfly Proxy

Hoverfly is an open-source API simulation tool written in Go. It operates as an HTTP/HTTPS proxy server:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//b06712ed-be74-4e52-8e15-c6632fb502ca/markdown_1/imgs/img_in_image_box_682_311_930_465.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A21%3A54Z%2F-1%2F%2Ff232058af3dcfd81b462a32d04050fc6515d5e3c3277b3ccce5fdbdcc9ea5170" alt="Image" width="23%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 9.2 Hoverfly proxy intercept schema</div> </div>

As shown in Figure 9.2, Hoverfly intercepts outbound HTTP requests, searches its database for a matching request pattern, and returns the pre-configured response without hitting the real network.

---

### 29.2.1 Hoverfly Modes of Operation

Hoverfly supports five core run modes:

#### 1. Capture Mode
Hoverfly intercepts real outbound requests, forwards them to the real target services, records the request-response pairs, and saves them to a local JSON file (the "simulation"):

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//b06712ed-be74-4e52-8e15-c6632fb502ca/markdown_2/imgs/img_in_image_box_201_106_616_339.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A21%3A54Z%2F-1%2F%2F5693bbdd5542ca2f5808ebb08310fd8e9a42a069297bdbdf19c4c91c010d4dd2" alt="Image" width="39%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 9.3 Hoverfly capture mode execution flow</div> </div>

As mapped in Figure 9.3, the client sends a request to Hoverfly, which forwards it to the external API, saves the response, and returns it to the client.

#### 2. Simulate Mode
Hoverfly reads a local simulation JSON file. All outbound requests are matched against the simulation records. If a match is found, Hoverfly returns the recorded response immediately. If no match is found, it returns an error:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//b06712ed-be74-4e52-8e15-c6632fb502ca/markdown_2/imgs/img_in_image_box_202_560_617_795.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A21%3A54Z%2F-1%2F%2F30a777524648cbb5be205c1a3fbf4c0bfdda11ea4e9400eb8d6c09c4c77e353d" alt="Image" width="39%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 9.4 Hoverfly simulate mode execution flow</div> </div>

As mapped in Figure 9.4, requests are intercepted and resolved locally without hitting the external network.

#### 3. Modify Mode
Hoverfly forwards requests to the real service, but passes the requests and responses through custom middleware scripts (written in Python, JavaScript, or bash) to alter payloads, headers, or inject latency on the fly.

#### 4. Synthesize Mode
Instead of reading a static simulation file, Hoverfly routes incoming requests directly to a middleware script, which generates the response payload programmatically.

#### 5. Spy Mode
Similar to a packet analyzer, Hoverfly forwards all traffic unchanged, but logs the request and response metadata for debugging.

---

## 29.3 JVM Proxy Configurations

Hoverfly intercepts traffic by configuring itself as the JVM proxy. When Hoverfly boots, it sets the following Java System Properties:

```properties
http.proxyHost=localhost
http.proxyPort=8500
https.proxyHost=localhost
https.proxyPort=8500
```

By default, Java's standard network library (`java.net.HttpURLConnection`), Apache HttpClient, and Spring `RestTemplate` honor these proxy settings automatically, routing all HTTP calls through Hoverfly on port 8500.

---

## 28.4 Maven Configurations (`pom.xml`)

To use Hoverfly in your Java test suite, add the Hoverfly Java library dependency to your `pom.xml`:

```xml
<dependencies>
    <!-- JUnit 5 API -->
    <dependency>
        <groupId>org.junit.jupiter</groupId>
        <artifactId>junit-jupiter-api</artifactId>
        <version>5.9.2</version>
        <scope>test</scope>
    </dependency>
    <!-- Hoverfly Java Integration -->
    <dependency>
        <groupId>io.specto</groupId>
        <artifactId>hoverfly-java-junit5</artifactId>
        <version>0.14.3</version>
        <scope>test</scope>
    </dependency>
</dependencies>
```

---

## 29.5 Trusting SSL/TLS HTTPS Interceptions

When a client application queries a secure HTTPS endpoint (e.g. `https://api.github.com`), the browser or Java client validates the server's SSL certificate.

Because Hoverfly intercepts these secure calls to act as the responder, it generates a dynamic certificate on the fly. The Java client will detect this as a Man-in-the-Middle (MitM) action and throw a `SSLHandshakeException` because it does not trust the Hoverfly certificate authority.

We resolve this by importing Hoverfly's custom CA certificate into the JVM truststore, or by configuring the Hoverfly JUnit extension to override the default JVM trust context automatically at startup:

```java
// Hoverfly Java automatically injects its root certificate into the JVM SSL truststore
@ExtendWith(HoverflyExtension.class)
public class SecureApiTest {
    // JVM will now trust Hoverfly HTTPS interception calls automatically
}
```

---

## 29.6 Gamer Aggregator Case Study

In the Gamer Application, the **Aggregator Service** orchestrates data aggregation, querying three separate microservices to construct a consolidated response for the end user:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//0e002590-1f95-4f08-87a5-8bffe471a6c8/markdown_1/imgs/img_in_image_box_199_107_794_537.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A21%3A53Z%2F-1%2F%2Fd08623432b5bd815ad50c23a3de0c1aa3c2f96c9ccf1fe69bbfe1be88736f674" alt="Image" width="56%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 9.5 Gamer Aggregator service data flow</div> </div>

As shown in Figure 9.5, when a client queries the dashboard, the Aggregator service makes asynchronous calls to the Video Service, Comments Service, and Ratings Service. We will write tests to emulate these backend service responses.

---

### 29.6.1 The Aggregator Client Gateway (`AggregatorGateway.java`)
This class queries the comments service REST API and uses Spring's `RestTemplate` to fetch the reviews:

```java
package com.ftgo.aggregator.gateway;

import com.ftgo.aggregator.dto.CommentDto;
import org.springframework.web.client.RestTemplate;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.HttpMethod;
import org.springframework.http.ResponseEntity;

import java.util.Collections;
import java.util.List;

public class AggregatorGateway {

    private final RestTemplate restTemplate;
    private final String commentsServiceUrl;

    public AggregatorGateway(RestTemplate restTemplate, String commentsServiceUrl) {
        this.restTemplate = restTemplate;
        this.commentsServiceUrl = commentsServiceUrl;
    }

    /**
     * Queries comments for a target game. Resolves with fallback values on request failure.
     * @param gameId Game identifier
     * @return List of comments.
     */
    public List<CommentDto> getCommentsForGame(Long gameId) {
        try {
            String url = commentsServiceUrl + "/comments?gameId=" + gameId;
            ResponseEntity<List<CommentDto>> response = restTemplate.exchange(
                    url,
                    HttpMethod.GET,
                    null,
                    new ParameterizedTypeReference<List<CommentDto>>() {}
            );
            return response.getBody();
        } catch (Exception e) {
            // Fallback recovery context on network failure
            return Collections.emptyList();
        }
    }
}
```

---

### 29.6.2 Writing the JUnit 5 Hoverfly Simulation Test (`AggregatorHoverflyTest.java`)
This test uses the `@ExtendWith(HoverflyExtension.class)` annotation to verify the gateway behavior. We configure Hoverfly to mock both successful responses and network failure states:

```java
package com.ftgo.aggregator;

import com.ftgo.aggregator.dto.CommentDto;
import com.ftgo.aggregator.gateway.AggregatorGateway;
import io.specto.hoverfly.junit.core.Hoverfly;
import io.specto.hoverfly.junit.core.HoverflyMode;
import io.specto.hoverfly.junit.core.model.DelaySettings;
import io.specto.hoverfly.junit5.HoverflyExtension;
import io.specto.hoverfly.junit5.api.HoverflyConfig;
import io.specto.hoverfly.junit5.api.HoverflyCore;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.springframework.web.client.RestTemplate;

import java.util.List;
import java.util.concurrent.TimeUnit;

import static io.specto.hoverfly.junit.core.SimulationSource.dsl;
import static io.specto.hoverfly.junit.core.dsl.HoverflyDsl.service;
import static io.specto.hoverfly.junit.core.dsl.ResponseCreators.badRequest;
import static io.specto.hoverfly.junit.core.dsl.ResponseCreators.success;
import static io.specto.hoverfly.junit.core.dsl.matchers.HoverflyMatchers.any;
import static io.specto.hoverfly.junit.core.dsl.matchers.HoverflyMatchers.equalsTo;
import static org.assertj.core.api.Assertions.assertThat;

@ExtendWith(HoverflyExtension.class)
@HoverflyCore(mode = HoverflyMode.SIMULATE, config = @HoverflyConfig(adminPort = 8888, proxyPort = 8500))
public class AggregatorHoverflyTest {

    private AggregatorGateway gateway;

    @BeforeEach
    public void setUp() {
        // Point target gateway client to the production url context
        this.gateway = new AggregatorGateway(new RestTemplate(), "http://www.gamer-app-comments.com");
    }

    @Test
    public void shouldReturnCommentsWhenServiceRespondsCorrectly(Hoverfly hoverfly) {
        // 1. Configure the Hoverfly simulation DSL programmatically
        hoverfly.simulate(dsl(
                service("http://www.gamer-app-comments.com")
                        .get("/comments")
                        .queryParam("gameId", 999)
                        .willReturn(success(
                                "[{\"id\":1,\"author\":\"John Doe\",\"text\":\"Virtualization is simple!\"}]",
                                "application/json"
                        ))
        ));

        // 2. Query the gateway
        List<CommentDto> comments = gateway.getCommentsForGame(999L);

        // 3. Verify assertions
        assertThat(comments).isNotEmpty();
        assertThat(comments.get(0).getAuthor()).isEqualTo("John Doe");
        assertThat(comments.get(0).getText()).contains("Virtualization");
    }

    @Test
    public void shouldReturnEmptyListWhenServiceReturnsBadRequest(Hoverfly hoverfly) {
        // 1. Configure Hoverfly to return a 400 Bad Request
        hoverfly.simulate(dsl(
                service("http://www.gamer-app-comments.com")
                        .get("/comments")
                        .queryParam("gameId", any())
                        .willReturn(badRequest())
        ));

        // 2. Query the gateway
        List<CommentDto> comments = gateway.getCommentsForGame(999L);

        // 3. Verify fallback context is triggered successfully
        assertThat(comments).isEmpty();
    }

    @Test
    public void shouldTriggerTimeoutFallbackWhenDelayExceedsLimit(Hoverfly hoverfly) {
        // 1. Configure Hoverfly to simulate a 3-second delay
        hoverfly.simulate(dsl(
                service("http://www.gamer-app-comments.com")
                        .get("/comments")
                        .queryParam("gameId", 999)
                        .willReturn(success(
                                "[{\"id\":2,\"author\":\"Timeout Tester\",\"text\":\"This should be delayed.\"}]",
                                "application/json"
                        ).withDelay(3, TimeUnit.SECONDS))
        ));

        // 2. Query the gateway
        List<CommentDto> comments = gateway.getCommentsForGame(999L);

        // 3. Verify that Hystrix fallback resolves empty list
        assertThat(comments).isEmpty();
    }
}
```

---

### 29.6.3 Writing a Hoverfly Capture Test (`AggregatorHoverflyCaptureTest.java`)
If you want to record the actual responses from a live environment to generate a simulation file, run Hoverfly in **Capture** mode:

```java
package com.ftgo.aggregator;

import com.ftgo.aggregator.dto.CommentDto;
import com.ftgo.aggregator.gateway.AggregatorGateway;
import io.specto.hoverfly.junit.core.Hoverfly;
import io.specto.hoverfly.junit.core.HoverflyMode;
import io.specto.hoverfly.junit5.HoverflyExtension;
import io.specto.hoverfly.junit5.api.HoverflyConfig;
import io.specto.hoverfly.junit5.api.HoverflyCore;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.springframework.web.client.RestTemplate;

import java.nio.file.Paths;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

@ExtendWith(HoverflyExtension.class)
@HoverflyCore(mode = HoverflyMode.CAPTURE, config = @HoverflyConfig(proxyPort = 8500))
public class AggregatorHoverflyCaptureTest {

    @Test
    public void captureRealCommentsApi(Hoverfly hoverfly) {
        // Point gateway to a live staging instance
        AggregatorGateway gateway = new AggregatorGateway(new RestTemplate(), "http://staging.gamer-comments.net");

        // Execute request to trigger Hoverfly interception and capture the response
        List<CommentDto> comments = gateway.getCommentsForGame(999L);

        assertThat(comments).isNotNull();

        // Save recorded interactions into a local JSON simulation file
        hoverfly.exportSimulation(Paths.get("src/test/resources/hoverfly/comments-api-simulation.json"));
    }
}
```

---

## 29.7 Customizing Request Matchers

To avoid brittle tests, you can use **Request Matchers** to dynamically match incoming request headers, query parameters, or payloads:

* **Exact Matcher**: Checks for an exact string match.
  `equalsTo("value")`
* **Wildcard Matcher**: Checks for any value.
  `any()`
* **Glob Matcher**: Matches wildcards, e.g. matching all sub-paths.
  `matches("*/comments/*")`
* **Regex Matcher**: Matches regular expressions.
  `startsWith("/comments/")`

```java
// Matcher DSL Example
service("http://api.payments.com")
    .post("/charge")
    // Match any request payload containing credit card details
    .body(equalsTo("{\"amount\":100}"))
    .header("Authorization", any())
    .willReturn(success());
```

---

## 29.8 Exported Hoverfly Simulation File Schema (`comments-api-simulation.json`)

When you export a simulation, Hoverfly writes the recorded request-response mappings to a JSON file. This file can then be committed to your repository and used for headless test runs in your CI/CD pipelines:

```json
{
  "data": {
    "pairs": [
      {
        "request": {
          "path": [
            {
              "matcher": "exact",
              "value": "/comments"
            }
          ],
          "method": [
            {
              "matcher": "exact",
              "value": "GET"
            }
          ],
          "destination": [
            {
              "matcher": "exact",
              "value": "www.gamer-app-comments.com"
            }
          ],
          "query": {
            "gameId": [
              {
                "matcher": "exact",
                "value": "999"
              }
            ]
          }
        },
        "response": {
          "status": 200,
          "body": "[{\"id\":1,\"author\":\"John Doe\",\"text\":\"Virtualization is simple!\"}]",
          "encodedBody": false,
          "headers": {
            "Content-Type": [
              "application/json"
            ]
          },
          "templated": false
        }
      }
    ],
    "globalActions": {
      "delays": []
    }
  },
  "meta": {
    "schemaVersion": "v5",
    "hoverflyVersion": "v1.4.3",
    "timeExported": "2026-06-27T09:41:00Z"
  }
}
```

---

---

## 29.9 Writing Custom Middleware: Hoverfly Modify Mode

As explained in section 29.2.1, **Modify mode** allows Hoverfly to intercept requests, forward them to the real service, and pass both the request and response objects through custom middleware scripts before returning the response to the client.

This is ideal to simulate custom latency injection, header mutations, or mock payload data modifications dynamically.

### 1. The Python Middleware Script (`latency_injector.py`)
Hoverfly communicates with middleware scripts using standard I/O (stdin/stdout). The script reads a JSON structure containing the request and response metadata, modifies it, and prints it back to stdout:

```python
#!/usr/bin/env python3
import sys
import json
import time
import random

def main():
    # 1. Read request/response JSON payload from Hoverfly via stdin
    data = json.loads(sys.stdin.read())

    # 2. Inspect request and inject custom behavior
    path = data['request'].get('path', '')
    
    if '/comments' in path:
        # Simulate network latency by sleeping between 1 and 3 seconds
        delay = random.uniform(1.0, 3.0)
        time.sleep(delay)

        # Modify response body if response exists
        if 'response' in data and data['response'] is not None:
            body_str = data['response'].get('body', '{}')
            try:
                body_json = json.loads(body_str)
                # Inject metadata into payload dynamically
                if isinstance(body_json, list):
                    for item in body_json:
                        item['latencyInjected'] = f"{delay:.2f}s"
                data['response']['body'] = json.dumps(body_json)
            except Exception:
                pass

    # 3. Print modified JSON structure back to Hoverfly via stdout
    sys.stdout.write(json.dumps(data))

if __name__ == '__main__':
    main()
```

To run Hoverfly with this middleware script locally, launch it from the command line:
```bash
hoverfly -mode modify -middleware "python3 src/test/resources/middleware/latency_injector.py"
```

---

## 29.10 Virtualizing Spring Cloud OpenFeign Clients

In Spring Boot microservices, developers often use **OpenFeign** instead of `RestTemplate` to write declarative REST clients.

Because Feign clients use custom HTTP client configurations (like Apache HttpClient or OkHttp) underneath, they bypass standard Java System JVM proxy settings unless explicitly configured.

To virtualize OpenFeign clients using Hoverfly, configure the Feign client to pass its calls through Hoverfly's proxy port:

### 1. The Custom Feign Configuration (`FeignHoverflyConfig.java`)
```java
package com.ftgo.aggregator.config;

import org.apache.http.HttpHost;
import org.apache.http.impl.client.CloseableHttpClient;
import org.apache.http.impl.client.HttpClients;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import feign.Client;

@Configuration
public class FeignHoverflyConfig {

    @Bean
    public Client feignClient() {
        // Build an Apache HttpClient pointing to the Hoverfly proxy
        HttpHost proxy = new HttpHost("localhost", 8500);
        CloseableHttpClient httpClient = HttpClients.custom()
                .setProxy(proxy)
                .build();
                
        // Wrap it inside Feign ApacheHttpClient wrapper
        return new feign.httpclient.ApacheHttpClient(httpClient);
    }
}
```

Then register this config inside your Feign interface definition:
```java
@FeignClient(name = "comments-service", url = "http://www.gamer-app-comments.com", configuration = FeignHoverflyConfig.class)
public interface CommentsFeignClient {
    // Declarative endpoints mapping
}
```

---

## 29.11 Programmatic SSL Trust Store Override in Java Clients

In section 29.5, we explained that Hoverfly intercepts HTTPS calls using dynamic certificates.

If you are writing a custom HTTP client that does not honor global trust configuration changes, you can override its SSL Context programmatically to trust Hoverfly's custom certificate trust chain:

```java
package com.ftgo.aggregator.util;

import org.apache.http.conn.ssl.NoopHostnameVerifier;
import org.apache.http.conn.ssl.TrustAllStrategy;
import org.apache.http.impl.client.CloseableHttpClient;
import org.apache.http.impl.client.HttpClients;
import org.apache.http.ssl.SSLContexts;

import javax.net.ssl.SSLContext;

public class SecureHttpClientBuilder {

    /**
     * Programmatically builds a secure http client trusting all Hoverfly MitM certificates.
     * @return Trusting HttpClient instance
     */
    public static CloseableHttpClient buildTrustingClient() throws Exception {
        SSLContext sslContext = SSLContexts.custom()
                // Trust self-signed certificates and custom CA roots
                .loadTrustMaterial(null, TrustAllStrategy.INSTANCE)
                .build();

        return HttpClients.custom()
                .setSSLContext(sslContext)
                // Disable hostname validation checks
                .setSSLHostnameVerifier(NoopHostnameVerifier.INSTANCE)
                .build();
    }
}
```

---

## 29.12 Running Hoverfly as a Kubernetes Sidecar Container

In a Kubernetes cluster, we can apply the **Sidecar Pattern** to run Hoverfly alongside our main application container inside the same Pod namespace.

This allows us to run E2E integration tests against the pod while Hoverfly intercepts all egress traffic:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: gamer-aggregator-pod
  namespace: test-env
spec:
  containers:
    # 1. Main Java microservice container
    - name: gamer-aggregator
      image: ftgo/gamer-aggregator:latest
      env:
        # Route outbound traffic through the sidecar container localhost port
        - name: HTTP_PROXY
          value: http://localhost:8500
        - name: HTTPS_PROXY
          value: http://localhost:8500
      ports:
        - containerPort: 8080

    # 2. Hoverfly Sidecar container
    - name: hoverfly-sidecar
      image: spectolabs/hoverfly:latest
      args:
        - -db
        - -mode
        - simulate
        - -import
        - /hoverfly/simulations/comments-api-simulation.json
      volumeMounts:
        - name: simulation-volume
          mountPath: /hoverfly/simulations
      ports:
        - containerPort: 8500
        - containerPort: 8888

  volumes:
    - name: simulation-volume
      configMap:
        name: comments-api-simulation-config
```

---

---

## 29.13 Comparative Analysis: WireMock vs. Hoverfly

When virtualizing APIs in Java microservices, developers often choose between **WireMock** and **Hoverfly**. While both tools simulate REST APIs, their architectures and interception patterns are fundamentally different:

<table border="1" style="margin: auto; width: 90%; text-align: center; border-collapse: collapse;">
  <thead>
    <tr style="background: #f2f2f2;">
      <th>Feature Axis</th>
      <th>WireMock Architecture</th>
      <th>Hoverfly Architecture</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><strong>Interception Model</strong></td>
      <td><strong>HTTP Server</strong>: Runs as a mock web server on a specific local port. Outbound client URLs must be redirected to point to WireMock.</td>
      <td><strong>HTTP/HTTPS Proxy</strong>: Intercepts all traffic passing through the JVM system proxy. Egress URLs remain unchanged.</td>
    </tr>
    <tr>
      <td><strong>Implementation Language</strong></td>
      <td>Java (runs inside the JVM or as an external Java process).</td>
      <td>Go (compiled binary, very low memory footprint and high throughput).</td>
    </tr>
    <tr>
      <td><strong>Capture Mechanics</strong></td>
      <td>Requires running a proxy server instance and manually saving mappings via Admin REST API.</td>
      <td>Native CLI support for Capture/Simulate mode toggling during runs.</td>
    </tr>
    <tr>
      <td><strong>HTTPS/SSL Interception</strong></td>
      <td>Requires generating custom Keystores for the mock server host.</td>
      <td>Automated Man-in-the-Middle certificate generation with client CA injection.</td>
    </tr>
  </tbody>
</table>

---

## 29.14 Advanced Request Matching using JSONPath

In section 29.7, we matching string query parameters. However, microservices POST requests often carry large, nested JSON bodies. To write flexible assertions without validating every character, Hoverfly supports **JSONPath Matchers**:

```java
import static io.specto.hoverfly.junit.core.dsl.matchers.HoverflyMatchers.matchesJsonPath;

// Matcher validating JSON structure dynamically
service("http://api.payments.com")
        .post("/charge")
        .body(matchesJsonPath("$.payment.creditCard.cardNumber")) // Verify field exists
        .body(matchesJsonPath("$.payment[?(@.amount > 0)]"))     // Verify value criteria
        .willReturn(success("{\"status\":\"APPROVED\"}", "application/json"));
```

---

## 29.15 Dynamic Simulation Loading from Classpath

In section 29.6.2, we configured Hoverfly using the `@HoverflyCore` annotation. To build complex test suites, you may need to load different simulation JSON files dynamically inside different test methods.

We can load simulations programmatically from the Java test classpath:

```java
package com.ftgo.aggregator;

import io.specto.hoverfly.junit.core.Hoverfly;
import io.specto.hoverfly.junit.core.SimulationSource;
import org.junit.jupiter.api.Test;

public class DynamicSimulationTest {

    @Test
    public void shouldVerifyUsingClasspathFile(Hoverfly hoverfly) {
        // Load simulation JSON resource dynamically from src/test/resources
        hoverfly.simulate(SimulationSource.classpath("hoverfly/comments-api-simulation.json"));
        
        // Execute HTTP calls against the virtualized target
    }
}
```

---

---

## 29.16 Advanced Hoverfly Simulation Matching Rules

In section 29.8, we reviewed the structure of the simulation JSON file exported by Hoverfly.

It is important to understand the hierarchy of matching rules used by the engine to resolve dynamic requests during E2E integration test runs:
* **Host Matcher**: Hoverfly first checks if the request's destination host matches the target service pattern.
* **Method Matcher**: Next, it matches the HTTP verb (such as `GET`, `POST`, or `PUT`).
* **Path Matcher**: It verifies the URI path. If you are using glob or regex matchers, it resolves the expressions.
* **Query Parameter Matcher**: It verifies that all query parameters specified in the matcher definition are present in the request.
* **Header Matcher**: It checks for required headers (like `Authorization` or `Content-Type`).
* **Body Matcher**: Finally, it evaluates the request body using exact checks or JSONPath expressions.

If a request fails to match *any* of the defined rule groups, Hoverfly throws a matching error, detailing which elements failed to align. This helps developers debug contract mismatches immediately.

---

---

## 29.18 Optimizing Hoverfly Performance for High-Throughput Tests

In high-concurrency environments (like running parallel integration test suites), the Hoverfly proxy can become a CPU bottleneck if logging and database operations are not optimized.

To maximize performance, configure Hoverfly using the following tuning options:
* **Disable Logging**: Logging every request-response match generates massive disk write operations. Disable logs inside the config to free CPU resources.
* **Enable In-Memory Simulation**: Hoverfly stores simulations in a local BoltDB file by default. Configure in-memory mode to avoid disk read latencies.
* **Manage Proxy Cache**: Cache response lookups to prevent parsing regex patterns on every query.

```java
// Hoverfly config optimized for concurrent execution
@HoverflyCore(
    mode = HoverflyMode.SIMULATE,
    config = @HoverflyConfig(
        proxyPort = 8500,
        adminPort = 8888,
        // Disable stdout logs
        disableLogging = true,
        // Store mappings in memory instead of BoltDB
        inMemory = true
    )
)
```

---

## 29.19 Summary of Hoverfly Service Virtualization Controls

This table summarizes the configurations, classes, and annotations used to establish service virtualization:

| Testing Vector | Virtualization Config / Property | Main Implementation Target | Scope Location |
| :--- | :--- | :--- | :--- |
| **Extension Boot** | `@ExtendWith(HoverflyExtension.class)` | Boots the local Hoverfly proxy process before the test run. | Test Class |
| **Hoverfly Instance** | `Hoverfly hoverfly` | Allows programmatically managing and exporting simulations. | Test Parameter |
| **Simulate Configuration**| `@HoverflyCore(mode = SIMULATE)` | Sets Hoverfly to simulate APIs using recorded files. | Test Class |
| **Capture Configuration** | `@HoverflyCore(mode = CAPTURE)` | Sets Hoverfly to capture live API calls. | Test Class |
| **Port Binding** | `@HoverflyConfig(proxyPort)` | Configures the local proxy port (defaults to 8500). | Test Class |
| **Mock DSL Service** | `service(destination)` | Declares the mock destination host. | Test Method |
| **Exact Matcher** | `equalsTo(value)` | Matches query parameters or headers exactly. | Test Method |
| **Wildcard Matcher** | `any()` | Matches any input parameter value. | Test Method |
| **Delay Setting** | `withDelay(time, unit)` | Injects latency to test client timeout fallbacks. | Test Method |
| **SSL Interception** | trustStore configurations | Trusts the Hoverfly CA cert to support secure HTTPS calls. | Test Configuration |

---

## Chapter Summary

* Service Virtualization simulates dependent API endpoints, allowing you to test microservices without booting their external dependencies.
* Service Virtualization acts as an enterprise network mock, verifying HTTP serialization layers, client timeouts, and network exceptions.
* **Hoverfly** is a lightweight Go proxy that intercepts outbound HTTP and HTTPS requests.
* Hoverfly supports **Capture mode** to record live API calls, and **Simulate mode** to serve recorded responses.
* **Modify mode** uses middleware scripts to alter request-response payloads or inject network latency.
* Outgoing requests are intercepted by configuring Hoverfly as the JVM system proxy (`http.proxyHost=localhost`).
* Hoverfly intercepts secure HTTPS calls by generating certificates on the fly. You must configure the Java client to trust Hoverfly's root CA certificate.
* We write **Request Matchers** using regular expressions or wildcards (`any()`) to avoid fragile static value tests.
* Exported Hoverfly simulation JSON files can be committed to your repository and used to support offline, headless test runs in CI/CD pipelines.
* Running Hoverfly as a Kubernetes sidecar container allows us to apply service virtualization dynamically inside cluster pods.
---

## 29.8 Production-Grade FTGO Order Reviews API Emulation Suite

In this section, we present the complete, production-grade service virtualization integration test suite for the **review-service** in the **FTGO Order Reviews** system. We write an API emulation test using **Hoverfly** (via the Hoverfly JUnit 5 Extension) to simulate positive and negative responses from external services, mapping custom response headers, bodies, latency delays, and connection timeouts dynamically.

```
                  +-----------------------------------+
                  |      WIRED HOVERFLY EMULATION     |
                  +-----------------+-----------------+
                                    |
            +-----------------------+-----------------------+
            | (Intercepts HTTP outbound GET/POST calls)     |
            v                                               v
[ OrderReviewsService ]                               [ Hoverfly Core ]
  - Makes outbound payment calls                        - Inspects URL rules
  - Configures retry & timeout properties               - Simulates canned responses / delay
```

---

### Scenario: Emulating Outbound Payment Authorization Gateway
Our `review-service` includes logic to reward consumers with discount credits when they write a positive review (e.g., a rating of 5). To authorize these credits, the service must execute a REST HTTP call to an external payment processor `/payments/authorize`. We use Hoverfly to emulate this payment provider to verify the service behaves correctly under success, client error, and network timeout conditions.

#### 1. The Virtualized Integration Test Suite: `OrderReviewsHoverflyTest.java`
This test uses Hoverfly's JUnit 5 configuration rules to emulate target APIs.

```java
package com.ftgo.review.integration;

import io.specto.hoverfly.junit.core.Hoverfly;
import io.specto.hoverfly.junit.core.HoverflyMode;
import io.specto.hoverfly.junit.core.model.RequestFieldMatcher;
import io.specto.hoverfly.junit5.HoverflyExtension;
import io.specto.hoverfly.junit5.api.HoverflyConfig;
import io.specto.hoverfly.junit5.api.HoverflyCore;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.client.HttpServerErrorException;
import org.springframework.web.client.RestTemplate;

import java.util.Collections;
import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.TimeUnit;

import static io.specto.hoverfly.junit.core.SimulationSource.dsl;
import static io.specto.hoverfly.junit.core.dsl.HoverflyDsl.service;
import static io.specto.hoverfly.junit.core.dsl.ResponseCreators.*;
import static org.assertj.core.api.Assertions.assertThat;

@ExtendWith(HoverflyExtension.class)
@HoverflyCore(mode = HoverflyMode.SIMULATE, config = @HoverflyConfig(adminPort = 8888, proxyPort = 8500))
public class OrderReviewsHoverflyTest {

    private RestTemplate restTemplate;
    private String paymentServiceUrl;

    @BeforeEach
    public void setUp(Hoverfly hoverfly) {
        this.restTemplate = new RestTemplate();
        this.paymentServiceUrl = "http://www.ftgo-payment-gateway.com";

        // Program Hoverfly simulation rules dynamically using the Java DSL API
        hoverfly.simulate(dsl(
                // 1. Success Path: Valid credit mapping returns 200 OK
                service(paymentServiceUrl)
                        .post("/payments/authorize")
                        .header("Content-Type", "application/json")
                        .body("{"orderId":999,"rewardCredits":10}")
                        .willReturn(success("{"status":"AUTHORIZED","transactionId":"tx_999123"}", "application/json"))

                // 2. Client Failure Path: Rating check throws 400 Bad Request
                .post("/payments/authorize")
                        .header("Content-Type", "application/json")
                        .body("{"orderId":999,"rewardCredits":-1}") // Negative credits error
                        .willReturn(badRequest().withBody("{"error":"Invalid reward credit amount"}"))

                // 3. Network Latency & Timeout Path: Simulating a slow gateway response
                .post("/payments/authorize")
                        .header("Content-Type", "application/json")
                        .body("{"orderId":888,"rewardCredits":10}")
                        .willReturn(success("{"status":"DELAYED_SUCCESS"}", "application/json")
                                .withDelay(5, TimeUnit.SECONDS)) // Introduce a 5-second sleep response
        ));
    }

    @Test
    public void shouldReturnSuccessfulAuthorizationOnValidRequest() {
        // Given
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        
        Map<String, Object> payload = new HashMap<>();
        payload.put("orderId", 999);
        payload.put("rewardCredits", 10);
        
        HttpEntity<Map<String, Object>> request = new HttpEntity<>(payload, headers);

        // When
        ResponseEntity<Map> response = restTemplate.postForEntity(paymentServiceUrl + "/payments/authorize", request, Map.class);

        // Then
        assertThat(response.getStatusCodeValue()).isEqualTo(200);
        assertThat(response.getBody()).isNotNull();
        assertThat(response.getBody().get("status")).isEqualTo("AUTHORIZED");
        assertThat(response.getBody().get("transactionId")).isEqualTo("tx_999123");
    }

    @Test
    public void shouldReturnBadRequestWhenPostingInvalidRewardCredits() {
        // Given
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        
        Map<String, Object> payload = new HashMap<>();
        payload.put("orderId", 999);
        payload.put("rewardCredits", -1);
        
        HttpEntity<Map<String, Object>> request = new HttpEntity<>(payload, headers);

        // When & Then
        try {
            restTemplate.postForEntity(paymentServiceUrl + "/payments/authorize", request, Map.class);
            org.junit.jupiter.api.Assertions.fail("Expected HTTP client exception due to invalid credit payload!");
        } catch (org.springframework.web.client.HttpClientErrorException e) {
            assertThat(e.getRawStatusCode()).isEqualTo(400);
            assertThat(e.getResponseBodyAsString()).contains("Invalid reward credit amount");
        }
    }

    @Test
    public void shouldTriggerClientTimeoutWhenExternalPaymentGatewayIsSlow() {
        // Given: client configures a read timeout limit constraint of 2 seconds
        org.springframework.http.client.SimpleClientHttpRequestFactory requestFactory = 
                new org.springframework.http.client.SimpleClientHttpRequestFactory();
        requestFactory.setReadTimeout(2000); // 2-second timeout
        RestTemplate timeBoundTemplate = new RestTemplate(requestFactory);

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        
        Map<String, Object> payload = new HashMap<>();
        payload.put("orderId", 888);
        payload.put("rewardCredits", 10);
        
        HttpEntity<Map<String, Object>> request = new HttpEntity<>(payload, headers);

        // When & Then: verify read timeout exception is thrown (since Hoverfly delays 5 seconds)
        try {
            timeBoundTemplate.postForEntity(paymentServiceUrl + "/payments/authorize", request, Map.class);
            org.junit.jupiter.api.Assertions.fail("Expected transaction read timeout exception!");
        } catch (org.springframework.web.client.ResourceAccessException e) {
            assertThat(e.getMessage()).contains("Read timed out");
        }
    }
}
```
