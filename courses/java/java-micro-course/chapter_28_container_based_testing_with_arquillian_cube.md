# Chapter 28: Container-Based Testing with Arquillian Cube

Unit and component tests verify code using mock networks and databases, but they cannot prove that an application will execute correctly inside a real containerized environment. In production, microservices are packaged as Docker images and run inside containers (like Docker or Kubernetes). If your local JVM environment has different settings, library versions, or network paths than your production containers, your local tests will pass while your production deployment fails.

To bridge this gap, the JBoss team developed **Arquillian Cube**. Instead of deploying code to a pre-configured local application server, Arquillian Cube communicates with a Docker daemon or Kubernetes cluster to build, launch, and manage the lifecycle of real containers dynamically during test runs. This chapter covers the technical design and implementation of **Container-Based Testing with Arquillian Cube**. We will compare virtual machines and containers, analyze the Cube execution lifecycle, write containerized JUnit tests using Docker Compose configuration files, implement the Page Object Pattern for in-container browser automation, parallelize test suites, and write Kubernetes deployment verifications.

---

## Learning Objectives

By the end of this chapter, you will be able to:
1. Explain the architectural differences between virtual machines (VMs) and Docker containers.
2. Outline the lifecycle of Arquillian Cube container management.
3. Configure the `arquillian.xml` configuration file to establish communication with local or remote Docker hosts.
4. Define multi-container runtimes using standard Docker Compose configuration files (`docker-compose.yml`).
5. Write Arquillian Cube integration tests that deploy web archives to containerized application servers.
6. Configure random dynamic port binding and resolve container endpoint addresses programmatically.
7. Automate browser testing inside containers using Drone, Graphene, and VNC recording nodes.
8. Apply the Container-Objects pattern to decouple container configurations from test classes.
9. Integrate Arquillian Cube with Kubernetes to verify pod deployments, service routing, and environment health.

---

## 28.1 Virtual Machines vs. Containers: The Docker Architecture

Before implementing containerized tests, it is critical to understand the underlying infrastructure differences between virtual machines and containers:

<table border="1" style="margin: auto; width: 80%; text-align: center; border-collapse: collapse;">
  <thead>
    <tr style="background: #f2f2f2;">
      <th>Virtual Machine (VM) Architecture</th>
      <th>Docker Container Architecture</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>
        <div style="padding: 10px;">
          <strong>App 1 | App 2 | App 3</strong><br/>
          Bins/Libs | Bins/Libs | Bins/Libs<br/>
          Guest OS | Guest OS | Guest OS<br/>
          <hr/>
          Hypervisor (Type 1 or 2)<br/>
          Host Operating System<br/>
          Physical Infrastructure
        </div>
      </td>
      <td>
        <div style="padding: 10px;">
          <strong>App 1 | App 2 | App 3</strong><br/>
          Bins/Libs | Bins/Libs | Bins/Libs<br/>
          <hr/>
          <strong>Docker Engine</strong> (Shared kernel)<br/>
          Host Operating System<br/>
          Physical Infrastructure
        </div>
      </td>
    </tr>
  </tbody>
</table>

<div style="text-align: center; margin-top: 10px;">
  <div style="text-align: center;">Figure 8.1 Virtual machine vs. container virtualization models</div>
</div>

As illustrated in Figure 8.1, virtual machines require a guest operating system for each individual application stack. Docker containers run directly on the host operating system's kernel, sharing system resources and making them lightweight, fast to boot, and highly portable.

---

### 28.1.1 The Docker Client-Daemon Interface
The Docker platform operates as a client-server architecture:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//f77635b3-75f5-40e6-8f8d-abf96f856cd7/markdown_2/imgs/img_in_image_box_183_603_866_879.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A22%3A28Z%2F-1%2F%2Fc638b0af57ddf9cb4944bbc219a2a94f6837826d95eeb775b9ade7cf246d27aa" alt="Image" width="64%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 8.2 Docker client, host daemon, and registry architecture</div> </div>

As mapped in Figure 8.2, the Docker Client communicates with the Docker Host daemon. When building or running containers, the host daemon downloads missing parent images from the remote Docker Registry (such as Docker Hub) and instantiates them locally.

---

## 28.2 The Arquillian Cube Lifecycle

During a test run, Arquillian Cube automates the management of your containerized environment:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//bdabaae2-ff5a-48ef-8e9c-bf671a79b793/markdown_1/imgs/img_in_image_box_190_780_685_995.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A21%3A52Z%2F-1%2F%2Ffcc3208ec4fc89f9028a981a4743d7a880b9c3542de63bf398e1ad4711668303" alt="Image" width="46%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 8.4 Arquillian Cube container lifecycle steps</div> </div>

As shown in Figure 8.4, the lifecycle follows a strict sequence:
1. **Read Configuration**: Arquillian Cube reads your container definitions from `arquillian.xml` or a Docker Compose file (`docker-compose.yml`).
2. **Boot Containers**: It issues commands to the Docker host to start all defined containers in the correct order.
3. **Await Health Check**: It monitors the containers (checking port availability or HTTP endpoints) to ensure the services are fully booted.
4. **Execute Tests**: The JUnit runner executes the tests against the running containers.
5. **Shut Down**: It stops and deletes all started containers, leaving the host system clean.

---

## 28.3 Build Configuration (`pom.xml`)

Add the Arquillian Cube BOM and dependencies to your project's Maven configuration file:

```xml
<dependencyManagement>
    <dependencies>
        <dependency>
            <groupId>org.arquillian.cube</groupId>
            <artifactId>arquillian-cube-bom</artifactId>
            <version>1.18.0</version>
            <type>pom</type>
            <scope>import</scope>
        </dependency>
    </dependencies>
</dependencyManagement>

<dependencies>
    <!-- Arquillian Cube Docker Container Controller -->
    <dependency>
        <groupId>org.arquillian.cube</groupId>
        <artifactId>arquillian-cube-docker</artifactId>
        <scope>test</scope>
    </dependency>
    <!-- Docker Compose extension -->
    <dependency>
        <groupId>org.arquillian.cube</groupId>
        <artifactId>arquillian-cube-docker-compose</artifactId>
        <scope>test</scope>
    </dependency>
</dependencies>
```

---

## 28.4 Multi-Container Coordination: Docker Compose Setup

Instead of manually defining container parameters in Java, Arquillian Cube reads standard Docker Compose files. This section details how to verify the **Comments Service** by booting a PostgreSQL database container and an Apache TomEE application server container concurrently.

### 28.4.1 The Docker Compose File (`docker-compose.yml`)
```yaml
version: '3.8'

services:
  # Database container dependency
  postgres-db:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: secretpassword
      POSTGRES_DB: comments_db
    exposedPorts:
      - "5432/tcp"

  # Backend application server container
  comments-server:
    image: tomee:8-jre11-webprofile
    depends_on:
      - postgres-db
    exposedPorts:
      - "8080/tcp"
```

---

### 28.4.2 Configuring `arquillian.xml`
We configure the Arquillian extension to read our Docker Compose file and enable communication with the local Docker daemon:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<arquillian xmlns="http://jboss.org/schema/arquillian"
            xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
            xsi:schemaLocation="http://jboss.org/schema/arquillian 
            http://jboss.org/schema/arquillian/arquillian_3_0.xsd">

    <!-- Configure Arquillian Cube Docker Extension -->
    <extension qualifier="docker">
        <property name="serverUri">tcp://localhost:2375</property>
        <!-- Specify the location of the Docker Compose file -->
        <property name="dockerComposeFile">src/test/resources/docker-compose.yml</property>
        <property name="definitionFormat">COMPOSE</property>
    </extension>
</arquillian>
```

---

### 28.4.3 The Containerized Integration Test Case
The test class uses `@Cube` annotations to inject the container's IP address and port dynamically. This resolves issues with static port conflicts during concurrent CI pipeline runs:

```java
package com.ftgo.comment.boundary;

import org.arquillian.cube.CubeController;
import org.arquillian.cube.CubeIp;
import org.arquillian.cube.HostPort;
import org.jboss.arquillian.junit5.ArquillianExtension;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;

import javax.inject.Inject;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;

import static org.assertj.core.api.Assertions.assertThat;

@ExtendWith(ArquillianExtension.class)
public class ContainerCommentsIntegrationTest {

    // 1. Inject the controller to manage the container lifecycles programmatically if needed
    @Inject
    private CubeController cubeController;

    // 2. Inject the dynamic IP address of the running comments-server container
    @Inject
    @CubeIp(cubeName = "comments-server")
    private String serverIp;

    // 3. Inject the dynamic host port bound to container port 8080
    @Inject
    @HostPort(cubeName = "comments-server", port = 8080)
    private int boundPort;

    @Test
    public void shouldReceiveSuccessfulResponseFromContainerServer() throws Exception {
        // Construct the dynamic endpoint URL resolved during container boot
        String targetUrl = "http://" + serverIp + ":" + boundPort + "/comments-service/health";
        
        HttpClient client = HttpClient.newHttpClient();
        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(targetUrl))
                .GET()
                .build();

        HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());

        // Verify container responds with HTTP Status 200 OK
        assertThat(response.statusCode()).isEqualTo(200);
        assertThat(response.body()).contains("HEALTHY");
    }
}
```

---

## 28.5 In-Container UI Automation with Drone and Graphene

Arquillian Cube integrates with Drone and Graphene to automate UI testing. Because the browser and the web application run inside containers, they run on the same virtual network, eliminating host-routing issues:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//d08ba1a1-7ffb-4ef4-8069-3fdaa0fe9b26/markdown_0/imgs/img_in_image_box_189_106_717_390.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A22%3A18Z%2F-1%2F%2Fe0859e297b9a689c84c84f1c79c04658a178d8f210d26761bcb7c23a7e7906b0" alt="Image" width="49%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 8.5 Integrated Arquillian extension ecosystem</div> </div>

As mapped in Figure 8.5, Arquillian Cube boots the application containers, Drone launches the browser node, and Graphene executes user actions against the page objects.

### 28.5.1 Recording Browser Sessions using VNC
When running E2E tests in a headless CI environment, debugging failures is difficult. Arquillian Cube resolves this by allowing you to run a VNC sidecar container alongside your browser node. The VNC node records the browser session and exports it as an MP4 video file:

```xml
<!-- Enable VNC video recording in arquillian.xml -->
<extension qualifier="docker">
    <property name="videoRecording">true</property>
    <property name="videoOutputFolder">target/recordings</property>
</extension>
```

---

## 28.6 The Container-Objects Pattern

Declaring database, cache, or message broker container configurations directly inside `arquillian.xml` can make it verbose and hard to maintain across multiple projects.

The **Container-Object Pattern** solves this by encapsulating container parameters in a reusable Java class. Test classes can then boot containers programmatically using a fluent DSL API:

```java
package com.ftgo.comment.container;

import org.arquillian.cube.container.object.Cube;
import org.arquillian.cube.container.object.Image;
import org.arquillian.cube.container.object.Port;

@Cube("comments-database")
@Image("postgres:15-alpine")
public class CommentsPostgresContainer {

    @Port(5432)
    private int port;

    public int getExposedPort() {
        return this.port;
    }
    
    public String getJdbcUrl() {
        return "jdbc:postgresql://localhost:" + port + "/comments_db";
    }
}
```

By encapsulating the container logic in a class, test classes remain clean and decoupled:

```java
@ExtendWith(ArquillianExtension.class)
public class DatabaseRepositoryTest {

    // Instantiates and boots the container dynamically before running tests
    @Cube
    private CommentsPostgresContainer database;

    @Test
    public void shouldConnectToPostgresContainer() {
        String url = database.getJdbcUrl();
        assertThat(url).isNotBlank();
    }
}
```

---

## 28.7 Deployment Verification on Kubernetes

As applications scale, they transition from Docker Compose to **Kubernetes** orchestrations. Arquillian Cube supports deploying and verifying resources directly on a Kubernetes cluster:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//b26c00c5-8496-4d9e-a522-e9f6bf4166da/markdown_4/imgs/img_in_image_box_187_353_721_624.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A21%3A54Z%2F-1%2F%2B8e717ff3357154d8d338c662342af2d846a719fa021d58ee98f44afc4429ba19" alt="Image" width="50%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 8.7 Kubernetes namespace, service, and pod deployment layers</div> </div>

As shown in Figure 8.7, Kubernetes structures deployments into Namespaces containing Services, which route traffic to replicas of underlying Pods.

---

### 28.7.1 The Kubernetes Verification Lifecycle
Arquillian Cube automates deploying manifests and running assertions on the cluster:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//d3ee5637-3a93-48ab-891b-e4adab510531/markdown_0/imgs/img_in_image_box_201_427_781_784.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A21%3A52Z%2F-1%2F%2F5b3c0f1fc37bf9df7f84d90533f3fe1bc2e688a8f26c44c0b39a1af2c69cc36c" alt="Image" width="54%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 8.8 Kubernetes integration lifecycle</div> </div>

As shown in Figure 8.8, the integration lifecycle follows a clear path:
1. **Initialize client**: Reads the local `~/.kube/config` to connect to the cluster.
2. **Apply manifest**: Deploys the resources defined in your `kubernetes.json` or `kubernetes.yaml` files.
3. **Await pod availability**: Blocks execution until all pods report a status of `Running` and are ready to receive traffic.
4. **Assert cluster state**: Runs the test assertions (e.g. validating pod counts, service routing, and configuration maps).
5. **Undeploy resources**: Deletes the deployed resources to clean up the cluster.

---

### 28.7.2 Writing a Kubernetes Test Case
This test class uses the `@KubernetesTest` annotation to inject the Kubernetes client and verify pod resources dynamically:

```java
package com.ftgo.comment.k8s;

import io.fabric8.kubernetes.client.KubernetesClient;
import io.fabric8.kubernetes.api.model.PodList;
import org.arquillian.cube.kubernetes.annotations.KubernetesTest;
import org.jboss.arquillian.junit5.ArquillianExtension;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;

import javax.inject.Inject;

import static org.assertj.core.api.Assertions.assertThat;

@ExtendWith(ArquillianExtension.class)
@KubernetesTest // Boots the Kubernetes environment and deploys target manifests
public class CommentsKubernetesDeploymentTest {

    // 1. Inject the Fabric8 Kubernetes Client
    @Inject
    private KubernetesClient client;

    @Test
    public void shouldDeployCommentsServicePods() {
        // Retrieve the list of active pods inside the test namespace
        PodList list = client.pods().inNamespace("test-env").list();
        
        // Assert that the pods are deployed and running
        assertThat(list.getItems()).isNotEmpty();
        
        list.getItems().forEach(pod -> {
            assertThat(pod.getMetadata().getName()).contains("comments-service");
            assertThat(pod.getStatus().getPhase()).isEqualTo("Running");
        });
    }
}
```

---

## 28.8 Parallelizing Container-Based Tests

Running containerized tests sequentially can slow down CI/CD pipelines, especially when booting heavy application servers. To speed up execution, Arquillian Cube supports **Parallel Test Execution**.

### 1. The Dynamic Container Asterisk (*) Operator
To run tests in parallel, each execution thread must launch isolated containers with unique names to prevent port and name conflicts on the shared Docker daemon. Cube supports this using the asterisk (`*`) wildcard suffix operator inside the Docker Compose file:

```yaml
version: '3.8'

services:
  # Adding * tells Cube to append a random UUID to the container name at startup
  video-service-container*:
    image: ftgo/video-service:latest
    exposedPorts:
      - "8080/tcp"
```

When parallel test threads run, Cube generates dynamic container names (e.g. `video-service-container_a3f9`, `video-service-container_e8b1`) and dynamically binds separate host ports for each thread, keeping execution isolated.

---

## 28.9 Testing the Dockerfile Configuration for the Video Service

Before publishing a microservice image, you should test the **Dockerfile** itself to ensure that file permissions, entrypoint scripts, and dependencies are configured correctly.

Arquillian Cube allows you to build an image from a local Dockerfile dynamically before launching it for the test run:

### 1. The Video Service Dockerfile (`src/main/docker/Dockerfile`)
```dockerfile
FROM openjdk:11-jre-slim
EXPOSE 8080
COPY target/video-service.jar /app/video-service.jar
ENTRYPOINT ["java", "-Djava.security.egd=file:/dev/./urandom", "-jar", "/app/video-service.jar"]
```

### 2. Building the Image Dynamically in the Compose file
Instead of pulling a static image tag, we configure the Compose file to build the image from our local source directory:

```yaml
version: '3.8'

services:
  video-service-test:
    build:
      context: ../../../
      dockerfile: src/main/docker/Dockerfile
    exposedPorts:
      - "8080/tcp"
```

When the test runs, Cube automatically executes the Docker build step, compiles the image, boots the container, runs the test assertions, and cleans up the generated image.

---

## 28.10 Integrating Arquillian Cube with Contract Testing (Algeron)

In Chapter 26, we wrote contract tests using **Arquillian Algeron**. When validating the provider side, we deployed our test archives to application servers running locally.

By combining Arquillian Cube with Algeron, we can verify provider contracts against a real containerized server.

### 1. Booting the Provider in a Docker Container
The test class uses both the `@Provider` contract annotation and the `@Cube` container annotations:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//0086e463-2a70-4032-8b1f-e83b5af80df2/markdown_1/imgs/img_in_image_box_179_255_876_659.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A22%3A22Z%2F-1%2F%2Fa635398b81cfc1c613f54b728701706d681aef95ac9030da9b62866255b20320" alt="Image" width="65%" /></div>

As illustrated, the Pact runner communicates directly with the containerized provider instance to verify contract expectations:

```java
package com.ftgo.comment.contract;

import org.arquillian.cube.CubeIp;
import org.arquillian.cube.HostPort;
import org.jboss.arquillian.junit5.ArquillianExtension;
import org.jboss.arquillian.pact.provider.api.Provider;
import org.jboss.arquillian.pact.provider.api.PactFolder;
import org.jboss.arquillian.pact.provider.api.verification.PactVerification;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;

import javax.inject.Inject;

@ExtendWith(ArquillianExtension.class)
@Provider("comments-service")
@PactFolder("target/pacts")
public class ContainerPactProviderTest {

    // Inject dynamic container IP address
    @Inject
    @CubeIp(cubeName = "comments-server")
    private String serverIp;

    // Inject dynamic host port bound to container port 8080
    @Inject
    @HostPort(cubeName = "comments-server", port = 8080)
    private int boundPort;

    @Test
    @PactVerification
    public void verifyPactsAgainstContainerInstance() {
        // Pact replays all contracts against http://${serverIp}:${boundPort}
    }
}
```

---

## 28.11 Managing Container Port Resolution Programmatically

During end-to-end container test runs, microservices need to locate one another over the network. If ports are resolved dynamically, we cannot hardcode endpoint URLs (like `http://localhost:8080`) in our configurations.

Arquillian Cube provides a **Port Resolution API** to query dynamic port mappings programmatically during the execution phase:

```java
package com.ftgo.video.util;

import org.arquillian.cube.docker.impl.client.config.CubeContainer;
import org.arquillian.cube.docker.impl.client.config.PortBinding;
import java.util.Collection;

public class PortResolver {

    /**
     * Resolves the external host port mapped to a container port dynamically.
     * @param container Target container config instance
     * @param internalPort Container port
     * @return Bound host port.
     */
    public static int getHostPort(CubeContainer container, int internalPort) {
        Collection<PortBinding> bindings = container.getPortBindings();
        for (PortBinding binding : bindings) {
            if (binding.getExposedPort().getPort() == internalPort) {
                return binding.getBoundPort().getPort();
            }
        }
        throw new IllegalArgumentException("Internal port " + internalPort + " not bound.");
    }
}
---

## 28.12 OpenShift Deployment Verification

In enterprise environments, Kubernetes is often run as Red Hat **OpenShift**. OpenShift extends Kubernetes with security constraints, build configs, and deployment routes.

Arquillian Cube provides native integration to verify OpenShift deployments using the OpenShift client:

### 1. Declaring OpenShift Dependencies (`pom.xml`)
```xml
<dependency>
    <groupId>org.arquillian.cube</groupId>
    <artifactId>arquillian-cube-openshift</artifactId>
    <scope>test</scope>
</dependency>
```

### 2. Writing an OpenShift Verification Test (`CommentsOpenShiftDeploymentTest.java`)
This test injects the OpenShift Client to verify deployment routes and project contexts dynamically:

```java
package com.ftgo.comment.openshift;

import io.fabric8.openshift.client.OpenShiftClient;
import io.fabric8.openshift.api.model.Route;
import org.arquillian.cube.openshift.impl.client.OpenShiftSuiteListener;
import org.arquillian.cube.kubernetes.annotations.KubernetesTest;
import org.jboss.arquillian.junit5.ArquillianExtension;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;

import javax.inject.Inject;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

@ExtendWith(ArquillianExtension.class)
@KubernetesTest // Cube openshift extension builds on top of the kubernetes listener
public class CommentsOpenShiftDeploymentTest {

    // 1. Inject the OpenShift Client
    @Inject
    private OpenShiftClient osClient;

    @Test
    public void shouldExposeHttpRouteForCommentsService() {
        // Retrieve routes inside the target OpenShift project namespace
        List<Route> routes = osClient.routes().inNamespace("gamer-prod").list().getItems();
        
        // Assert that the public ingress route is configured correctly
        assertThat(routes).isNotEmpty();
        
        Route targetRoute = routes.stream()
                .filter(r -> r.getMetadata().getName().equals("comments-route"))
                .findFirst()
                .orElse(null);
                
        assertThat(targetRoute).isNotNull();
        // Verify public hostname target is exposed
        assertThat(targetRoute.getSpec().getHost()).contains("openshift.apps");
        assertThat(targetRoute.getSpec().getTo().getName()).isEqualTo("comments-service");
    }
}
```



---

## 28.13 Managing Docker Networks and DNS Contexts

When coordinating multi-container deployments using Docker Compose, Arquillian Cube creates a dedicated, isolated **Docker network bridge**.

Each service within the compose file is registered with the network's internal DNS server, allowing containers to resolve peer microservices using their service name (e.g. `http://comments-server:8080`) rather than IP addresses:

```
[ bridge-network: tomee-network ]
  |--> comments-server (resolves via internal DNS)
  |--> postgres-db (resolves via internal DNS)
```

### 1. Declaring Networks in Docker Compose
We map networks explicitly inside the compose file to enforce isolation:

```yaml
version: '3.8'

services:
  postgres-db:
    image: postgres:15-alpine
    networks:
      - gamer-net
    exposedPorts:
      - "5432/tcp"

  comments-server:
    image: tomee:8-jre11-webprofile
    networks:
      - gamer-net
    environment:
      DATABASE_URL: jdbc:postgresql://postgres-db:5432/comments_db
    depends_on:
      - postgres-db
    exposedPorts:
      - "8080/tcp"

networks:
  gamer-net:
    driver: bridge
```

### 2. Resolving Entropy Issues inside Containers
Java applications running inside containerized JREs can suffer from slow startup times due to blockages in cryptographically secure random number generators (using `/dev/random`).

We resolve this by configuring the JVM's entropy source to `/dev/urandom` inside the compose environment variables:

```yaml
  comments-server:
    image: tomee:8-jre11-webprofile
    environment:
      - JAVA_OPTS=-Djava.security.egd=file:/dev/./urandom
```

---

## 28.14 Writing the CommentsResource REST API Endpoint class

To complete our E2E verification loop, we examine the REST controller class deployed inside the containerized WildFly or TomEE application servers.

This controller exposes the endpoints queried by the Selenium WebDriver tests:

```java
package com.ftgo.comment.boundary;

import com.ftgo.comment.entity.Comment;
import com.ftgo.comment.repository.CommentsRepository;

import javax.inject.Inject;
import javax.ws.rs.*;
import javax.ws.rs.core.MediaType;
import javax.ws.rs.core.Response;
import java.util.List;

@Path("/comments")
@Produces(MediaType.APPLICATION_JSON)
@Consumes(MediaType.APPLICATION_JSON)
public class CommentsResource {

    @Inject
    private CommentsRepository repository;

    @GET
    public List<Comment> getComments(@QueryParam("gameId") Long gameId) {
        if (gameId == null) {
            throw new BadRequestException("Query parameter gameId is required.");
        }
        return repository.getCommentsForGame(gameId);
    }

    @POST
    public Response addComment(Comment comment) {
        if (comment == null || comment.getAuthor() == null || comment.getText() == null) {
            return Response.status(Response.Status.BAD_REQUEST)
                    .entity("Invalid comment payload.")
                    .build();
        }
        repository.addComment(comment);
        return Response.status(Response.Status.CREATED).build();
    }
}
```

---

---

## 28.15 Kubernetes YAML Manifest Definition

To understand how Arquillian Cube interacts with Kubernetes during test runs, we examine the deployment manifest configuration file (`kubernetes.yaml`) loaded by the `@KubernetesTest` runner.

This file outlines the services and replica parameters deployed to the cluster namespace:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: comments-service
  namespace: test-env
  labels:
    app: comments-service
spec:
  ports:
    - port: 8080
      targetPort: 8080
      protocol: TCP
  selector:
    app: comments-service
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: comments-service
  namespace: test-env
  labels:
    app: comments-service
spec:
  replicas: 2
  selector:
    matchLabels:
      app: comments-service
  template:
    metadata:
      labels:
        app: comments-service
    spec:
      containers:
        - name: comments-service-node
          image: ftgo/comments-service:latest
          imagePullPolicy: IfNotPresent
          ports:
            - containerPort: 8080
          readinessProbe:
            httpGet:
              path: /comments-service/health
              port: 8080
            initialDelaySeconds: 5
            periodSeconds: 5
```

---

---

## 28.16 Understanding Kubernetes Services and Ingress Routing

In the Kubernetes manifest schema defined in section 28.15, we declared both a `Service` and a `Deployment`.

It is important to understand the routing mechanics verified by Arquillian Cube:
* **Deployment**: Launches a specified number of Pod replicas (in our case, `replicas: 2`) and monitors their health. Pods are assigned dynamic internal IP addresses when they boot, meaning they are transient and cannot be targeted directly.
* **Service**: Creates a stable IP address and DNS name (`comments-service`) that load-balances traffic across the Pod replicas.
* **Ingress**: Exposes HTTP and HTTPS routes from outside the cluster to services within the cluster. During test runs, Arquillian Cube can query the Ingress controller to resolve public domain configurations.

```
[ Ingress Controller ] ===(HTTP Route)===> [ Comments Service ] ===(Load Balances)===> [ Pod Replica 1 | Pod Replica 2 ]
```

By verifying both services and deployments, we ensure that DNS routing tables, ports, and selectors are aligned before pushing to production.

---

## 28.17 Summary of Container-Based Testing Controls

This table summarizes the configurations, annotations, and classes used to establish container-based tests:

| Testing Vector | Container Resource / Config | Main Implementation Target | Scope Location |
| :--- | :--- | :--- | :--- |
| **Compose Integration** | `arquillian.xml` format | Binds the test runner to a specific Docker Compose layout. | Test Resources |
| **Container Controller**| `CubeController` | Manages container lifecycles programmatically. | Test Fields |
| **Address Resolver** | `@CubeIp(name)` | Resolves the container's dynamic IP address. | Test Fields |
| **Port Mapper** | `@HostPort(name, port)` | Maps the container port to the dynamic host port. | Test Fields |
| **Remote Server URI** | `serverUri` | Binds the Docker client to a remote daemon socket. | Test Resources |
| **Browser Recording** | `videoRecording: true` | Exports browser interactions as VNC videos. | Test Resources |
| **Pattern Decoupling** | `@Cube` / `@Image` class | Encapsulates container parameters in reusable classes. | Class Definition |
| **Kubernetes Injection**| `KubernetesClient` | Manages resource deployments and cluster assertions. | Test Fields |
| **Manifest Deployment**| `@KubernetesTest` | Deploys manifest configuration files dynamically. | Test Class |

---

## Chapter Summary

* Running tests in local JVM environments can hide bugs caused by setting differences, library version mismatches, or network paths in production containers.
* **Arquillian Cube** solves this by communicating with your Docker daemon or Kubernetes cluster to manage container lifecycles dynamically during test runs.
* Docker containers run directly on the host operating system's kernel, making them lightweight compared to virtual machines.
* Cube reads standard **Docker Compose** files to coordinate multi-container runtimes.
* Dynamic ports and IP addresses are injected into tests using `@CubeIp` and `@HostPort` annotations, preventing port conflicts in CI environments.
* In-container browser testing is supported by running the browser inside a container, with options to record the session using VNC.
* The **Container-Objects Pattern** encapsulates container configurations in reusable Java classes.
* **Kubernetes integration** allows deploying manifests (`kubernetes.json`) and running assertions against the cluster state using the Fabric8 client.
---

## 28.8 Production-Grade FTGO Order Reviews Containerized Integration Tests

In this section, we present the complete, production-grade containerized integration test suite for the **review-service** in the **FTGO Order Reviews** system. We deploy a multi-container environment using **Arquillian Cube** to control a dynamic Docker Compose lifecycle, binding container ports dynamically to prevent port collisions in local and CI runtimes.

```
+-------------------------------------------------------------------------+
|                         ARQUILLIAN CUBE TEST ENVIRONMENT                |
+-------------------------------------------------------------------------+
|                                                                         |
|   [ JUnit Test Runner JVM ]                                             |
|              |                                                          |
|              +---(checks status & injects ports)---> [ Docker Daemon ]   |
|              |                                              |           |
|              v (executes JAX-RS HTTP client requests)        v (boots)   |
|     +------------------+                        +-------------------+   |
|     |  review-service  | ===(JDBC Postgres)===> |     review-db     |   |
|     |   (Tomcat WAR)   |                        |  (PostgreSQL DB)  |   |
|     +------------------+                        +-------------------+   |
|                                                                         |
+-------------------------------------------------------------------------+
```

---

### Scenario: Multi-Container Setup with Database and Backend APIs
We run our JAX-RS reviews service containerized alongside a dedicated PostgreSQL database container. Arquillian Cube spins up both services, links their network interfaces, and injects the dynamic host ports into our JUnit test class so we can run verification scripts.

#### 1. The Multi-Container Orchestration Manifest: `src/test/resources/docker-compose.yml`
```yaml
version: '3.8'

services:
  review-db:
    image: postgres:15-alpine
    container_name: review-db
    environment:
      POSTGRES_DB: reviewdb
      POSTGRES_USER: ftgo_user
      POSTGRES_PASSWORD: secure_password
    ports:
      - "5432" # Let Docker allocate a random dynamic port on the host
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ftgo_user -d reviewdb"]
      interval: 5s
      timeout: 5s
      retries: 5

  review-service:
    image: ftgo/review-service:latest
    container_name: review-service
    depends_on:
      review-db:
        condition: service_healthy
    ports:
      - "8080" # Let Docker allocate a random dynamic port on the host
    environment:
      - DB_URL=jdbc:postgresql://review-db:5432/reviewdb
      - DB_USERNAME=ftgo_user
      - DB_PASSWORD=secure_password
      - MANAGED_EXECUTOR_THREADS=4
```

---

#### 2. The Containerized Integration Test Suite: `OrderReviewsContainerTest.java`
This test uses Arquillian Cube to configure the compose stack and inject dynamic port bindings to execute client integration calls.

```java
package com.ftgo.review.integration;

import com.ftgo.review.entity.OrderReview;
import org.arquillian.cube.CubeIp;
import org.arquillian.cube.HostPort;
import org.jboss.arquillian.junit5.ArquillianExtension;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.springframework.http.ResponseEntity;
import org.springframework.web.client.RestTemplate;

import java.net.URI;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

@ExtendWith(ArquillianExtension.class)
public class OrderReviewsContainerTest {

    // 1. Inject the dynamically resolved IP address of the review-service container
    @CubeIp(containerName = "review-service")
    private String reviewServiceIp;

    // 2. Inject the dynamically mapped host port matching internal Tomcat port 8080
    @HostPort(containerName = "review-service", value = 8080)
    private int reviewServiceMappedPort;

    private RestTemplate restTemplate;
    private String apiBaseUrl;

    @BeforeEach
    public void setUp() {
        this.restTemplate = new RestTemplate();
        // Construct the dynamic connection endpoint address
        this.apiBaseUrl = "http://" + reviewServiceIp + ":" + reviewServiceMappedPort + "/reviewsservice/reviews";
    }

    @Test
    public void shouldPersistAndRetrieveReviewsFromContainerizedEnvironment() {
        // Step 1: Query initial reviews for order 999 (should be empty)
        String queryUrl = apiBaseUrl + "?orderId=999";
        ResponseEntity<OrderReview[]> initialResponse = restTemplate.getForEntity(queryUrl, OrderReview[].class);
        
        assertThat(initialResponse.getStatusCodeValue()).isEqualTo(200);
        assertThat(initialResponse.getBody()).isEmpty();

        // Step 2: Post a new review payload to the containerized service
        OrderReview review = new OrderReview();
        review.setId(100L);
        review.setOrderId(999L);
        review.setReviewerName("Alice");
        review.setReviewText("The burger was outstanding!");
        review.setRating(5);

        ResponseEntity<OrderReview> postResponse = restTemplate.postForEntity(apiBaseUrl, review, OrderReview.class);
        
        assertThat(postResponse.getStatusCodeValue()).isEqualTo(200);
        assertThat(postResponse.getBody()).isNotNull();
        assertThat(postResponse.getBody().getReviewText()).isEqualTo("The burger was outstanding!");

        // Step 3: Re-query reviews for order 999 to confirm DB persistence
        ResponseEntity<OrderReview[]> finalResponse = restTemplate.getForEntity(queryUrl, OrderReview[].class);
        
        assertThat(finalResponse.getStatusCodeValue()).isEqualTo(200);
        assertThat(finalResponse.getBody()).hasSize(1);
        
        OrderReview persisted = finalResponse.getBody()[0];
        assertThat(persisted.getReviewerName()).isEqualTo("Alice");
        assertThat(persisted.getRating()).isEqualTo(5);
    }

    @Test
    public void shouldReturnBadRequestWhenSubmittingInvalidRating() {
        // Given: payload with rating of 6 (violates validation rules)
        OrderReview invalidReview = new OrderReview();
        invalidReview.setId(101L);
        invalidReview.setOrderId(999L);
        invalidReview.setReviewerName("Bob");
        invalidReview.setReviewText("Terrible");
        invalidReview.setRating(6); // Invalid rating

        // When & Then
        try {
            restTemplate.postForEntity(apiBaseUrl, invalidReview, Map.class);
            org.junit.jupiter.api.Assertions.fail("Expected HTTP client exception due to invalid rating!");
        } catch (org.springframework.web.client.HttpClientErrorException e) {
            assertThat(e.getRawStatusCode()).isEqualTo(400);
            assertThat(e.getResponseBodyAsString()).contains("Rating must be between 1 and 5!");
        }
    }
}
```
