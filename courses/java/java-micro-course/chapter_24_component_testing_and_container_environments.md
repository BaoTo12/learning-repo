# Chapter 24: Component-Testing & Container Environments

In a microservices architecture, component testing acts as an intermediate testing boundary. While unit tests validate individual classes in isolation, they do not verify how those classes behave when packaged and executed inside an application container (like Spring Boot, Tomcat, or WildFly). Conversely, full integration and end-to-end tests verify the entire system but are slow, flaky, and require spinning up multiple microservices, networks, and databases.

Component testing solves this by testing a single microservice as a coherent "component," mocking all outbound network calls (such as external REST APIs and message brokers) but executing the service's internal components inside a real container runtime. This chapter covers component-testing Java microservices using the **Arquillian** framework and the **ShrinkWrap** deployment utility. We will analyze container execution modes (Embedded, Managed, Remote), configure Maven build scripts with container adapters, write declarative `arquillian.xml` configuration overrides, and use REST and Warp extensions. Finally, we will write a complete component test suite that packages a Spring Boot microservice, mocks remote APIs using **WireMock**, and executes assertions against a real, running container environment.

---

## Learning Objectives

By the end of this chapter, you will be able to:
1. Explain the purpose of component testing and how it differs from unit and integration testing.
2. Describe the architecture and lifecycle phases of the Arquillian test framework.
3. Contrast Embedded, Managed, and Remote container execution adapters.
4. Programmatically package microservice archives using ShrinkWrap (JAR, WAR, EAR).
5. Add classes, resources, packages, and manifest metadata to ShrinkWrap archives.
6. Resolve complex transitive dependencies dynamically using the ShrinkWrap Maven Resolver.
7. Configure Maven profiles to switch test execution across different target containers.
8. Customize container configurations using `arquillian.xml` parameter overrides.
9. Implement client-side and server-side assertions using Arquillian REST and Warp extensions.
10. Integrate WireMock within a containerized component test to mock outbound REST endpoints.
11. Deploy and run persistent database tests inside an Arquillian-managed container.

---

## 24.1 The Arquillian Test Framework

Arquillian is an integration and component testing framework for Java. Its core philosophy is to **bring the test to the runtime**, rather than trying to replicate container behavior in a mock environment. Instead of executing tests in a bare IDE JVM and mocking Java EE/Spring infrastructures, Arquillian manages the lifecycle of a real container, packages the application classes into a micro-archive, deploys it to the container, and runs the tests *inside* the container JVM.

### 24.1.1 The Component Test Lifecycle
The Arquillian test lifecycle is divided into six automated phases:

#### 1. Selecting the Container
The framework reads the classpath and configuration to determine which container adapter (e.g. WildFly, Tomcat, GlassFish, or Spring Boot) is active:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//94be17b0-729a-4252-89f3-d679ea1ad945/markdown_1/imgs/img_in_image_box_183_372_691_601.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A21%3A51Z%2F-1%2F%2F2008cf304c7f06605f247a634756c8c21d3da9ff8db268bc540327fbea220fb9" alt="Image" width="47%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 4.1 Selecting the test container</div> </div>

As shown in Figure 4.1, selecting the right container is the first step of the execution cycle.

#### 2. Activating the Container Environment
Arquillian either boots up a new local instance of the selected container or establishes a network socket connection to an already running remote instance:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//94be17b0-729a-4252-89f3-d679ea1ad945/markdown_1/imgs/img_in_image_box_772_691_861_885.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A21%3A51Z%2F-1%2F%2Ff5c3563160608482894ded226f6755a6df30211a184e18353fc24735a9c046f2" alt="Image" width="8%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 4.2 Activating the container environment</div> </div>

As shown in Figure 4.2, this phase manages the physical state of the server.

#### 3. Packaging and Deploying
Arquillian invokes the static `@Deployment` method inside the test class. This method uses the **ShrinkWrap** utility to define a minimal, custom archive (JAR, WAR, or EAR) containing only the classes and resources required for the test. Arquillian then deploys this archive to the running container:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//94be17b0-729a-4252-89f3-d679ea1ad945/markdown_1/imgs/img_in_image_box_183_1014_529_1208.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A21%3A52Z%2F-1%2F%2Fde2f428414e1ee8a38e595b3a65d41851ba5ab9454290322766f9ca266b7f591" alt="Image" width="32%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 4.3 Packaging the test application using ShrinkWrap, and deploying to the container</div> </div>

Figure 4.3 illustrates the assembly of the micro-deployment on the client side and its delivery to the container.

#### 4. Running the Tests In-Container
The tests are executed inside the container's JVM. If a test class is annotated to run in-container, Arquillian bypasses the default test execution and redirects commands to an in-container servlet or protocol handler. This allows the test class to leverage dependency injection (like CDI `@Inject` or Spring `@Autowired`) to reference live beans, datasources, and transactions directly:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//94be17b0-729a-4252-89f3-d679ea1ad945/markdown_2/imgs/img_in_image_box_199_105_564_343.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A21%3A52Z%2F-1%2F%2Fb4aea55a7020263a66746ccc8a3e83e8bb41812f16293e2e0f50b4f040d5d4ef" alt="Image" width="34%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 4.4 The deployed test application runs in the container.</div> </div>

As shown in Figure 4.4, the container hosts both the application components and the test case executing assertions.

#### 5. Capturing and Returning Results
The results of the test assertions (success, failure stack traces, execution times) are collected by the in-container runner, serialized, and sent back to the client JVM over HTTP or JMX. The local IDE or build engine displays the results as standard test reports:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//94be17b0-729a-4252-89f3-d679ea1ad945/markdown_2/imgs/img_in_image_box_672_455_949_690.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A21%3A52Z%2F-1%2F%2F94e4dcc5492b15a7067293f76f09e3e0066aa6f2b86e4059e56257b61ce5f073" alt="Image" width="26%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 4.5 Capturing the results and returning them to the test environment</div> </div>

As illustrated in Figure 4.5, this boundary serialization hides the complex networking behind the test results visualization.

#### 6. Cleaning Up Resources
Once execution completes, Arquillian undeploys the test archive. If a managed container was started, the framework commands it to shut down, releasing memory, port bindings, and database connections:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//94be17b0-729a-4252-89f3-d679ea1ad945/markdown_2/imgs/img_in_image_box_203_817_289_1009.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A21%3A52Z%2F-1%2F%2Fe69e757dbf289fddfe6343fb792abef96bb217574883fe9098691fd5bc7f6aca" alt="Image" width="8%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 4.6 Cleaning up resources and shutting down the container</div> </div>

Figure 4.6 illustrates the final step where resources are recycled and files cleaned.

---

### 24.1.2 Container Execution Modes
Arquillian supports three container modes, configured via dependencies and profiles:

| Container Mode | Execution Description | Best Use Case | Trade-offs |
| :--- | :--- | :--- | :--- |
| **Embedded** | The container runs as a library in the same JVM as the test runner. | Quick local developer checks. | Fast startup, but lacks classpath isolation; may behave differently from production. |
| **Managed** | Arquillian starts a separate container JVM process, deploys the code, and stops it after execution. | Continuous Integration (CI) pipelines. | High isolation and realism, but suffers from startup overhead (seconds to minutes). |
| **Remote** | Arquillian connects over the network to an already running container instance. | Fast local loops and remote debugging. | Instant test runs (no server startup), but requires manually managing the server's state. |

---

## 24.2 Declaring Deployments with @Deployment and ShrinkWrap

In standard integration testing, developers deploy their entire application artifact (e.g. a 150MB fat JAR). This is slow and introduces noise: a bug in an unrelated service can prevent the entire application from booting, failing your test.

Arquillian solves this using **ShrinkWrap**, a Java API that allows programmatically defining a minimal deployment archive. 

### 24.2.1 The `@Deployment` Method Structure
An Arquillian test class must declare a `public static` method annotated with `@Deployment` that returns a ShrinkWrap archive:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//94be17b0-729a-4252-89f3-d679ea1ad945/markdown_4/imgs/img_in_image_box_151_103_837_626.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A21%3A53Z%2F-1%2F%2F8505da27f28a001c92cd8aa4c55b2881bba94f3bf3dca9b9f5d5afc1a128685d" alt="Image" width="64%" /></div>

The `@Deployment` method defines the specific boundary of the test run, packaging only the classes, configurations, and libraries required to run the test in the container JVM.

---

### 24.2.2 Adding Content to the Archive
ShrinkWrap provides fluent APIs to assemble archives (`JavaArchive` for JARs, `WebArchive` for WARs, `EnterpriseArchive` for EARs). You can add files, resources, and dependencies to these archives:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//c17bced5-faaf-407b-b37a-f097a773a94e/markdown_2/imgs/img_in_image_box_180_463_761_943.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A21%3A53Z%2F-1%2F%2F1cc39f9f41fd012f9665a0b1d644793a125ef1670f26c91b185e2f82a0d1dfa3" alt="Image" width="54%" /></div>

As shown in the API methods list, you can add individual classes (`addClass`), arrays of classes (`addClasses`), packages (`addPackage`), or external libraries.

* **`addClass(Class<?> clazz)`**: Adds a single class to the archive.
* **`addClasses(Class<?>... classes)`**: Adds multiple classes.
* **`addPackage(Package pack)`**: Adds all classes in a package.
* **`addAsResource(String resourceName)`**: Copies a file from `src/main/resources` or `src/test/resources` into the root of the archive.
* **`addAsWebInfResource(String resourceName, String targetName)`**: Places configuration files (like `beans.xml` or `web.xml`) in a web archive's `WEB-INF/` directory.

---

### 24.2.3 Resolving Transitive Dependencies with Maven Resolver
If the classes in your archive rely on third-party libraries (like Jackson, Apache Commons, or Spring Security), they must be packaged inside the deployment. Rather than manually referencing individual jar paths, we use the **ShrinkWrap Maven Resolver** to resolve and load transitive dependencies directly from your project's `pom.xml`:

```java
// Dynamically resolve and import all dependencies in a specific Maven POM
File[] dependencies = Maven.resolver()
        .loadPomFromFile("pom.xml")
        .importCompileAndRuntimeDependencies()
        .resolve()
        .withTransitiveDependencies()
        .asFile();

WebArchive archive = ShrinkWrap.create(WebArchive.class, "test.war")
        .addClasses(GamerService.class, GameRepository.class)
        .addAsLibraries(dependencies);
```

---

## 24.3 Build-Script Configurations (Maven Profiles)

To run component tests against different container runtimes, we configure target adapters inside our build scripts. In Maven, we achieve this by defining **profiles** for each container. This allows developers to run tests locally using an embedded container, while the CI/CD pipeline executes them against a managed or remote container.

Here is a complete, production-grade Maven `pom.xml` configuration containing container adapters for both **WildFly Managed** and **Tomcat Embedded**:

```xml
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    <groupId>com.ftgo</groupId>
    <artifactId>gamer-component-testing</artifactId>
    <version>1.0.0</version>

    <properties>
        <maven.compiler.source>11</maven.compiler.source>
        <maven.compiler.target>11</maven.compiler.target>
        <version.arquillian_bom>1.7.0.Alpha10</version.arquillian_bom>
        <version.junit5>5.9.2</version.junit5>
        <version.shrinkwrap.resolver>3.1.4</version.shrinkwrap.resolver>
    </properties>

    <!-- Import Arquillian Dependency Management BOM -->
    <dependencyManagement>
        <dependencies>
            <dependency>
                <groupId>org.jboss.arquillian</groupId>
                <artifactId>arquillian-bom</artifactId>
                <version>${version.arquillian_bom}</version>
                <type>pom</type>
                <scope>import</scope>
            </dependency>
        </dependencies>
    </dependencyManagement>

    <dependencies>
        <!-- JUnit 5 API and Engine -->
        <dependency>
            <groupId>org.junit.jupiter</groupId>
            <artifactId>junit-jupiter-api</artifactId>
            <version>${version.junit5}</version>
            <scope>test</scope>
        </dependency>
        <dependency>
            <groupId>org.junit.jupiter</groupId>
            <artifactId>junit-jupiter-engine</artifactId>
            <version>${version.junit5}</version>
            <scope>test</scope>
        </dependency>

        <!-- Arquillian JUnit 5 Integration -->
        <dependency>
            <groupId>org.jboss.arquillian.junit5</groupId>
            <artifactId>arquillian-junit5-container</artifactId>
            <scope>test</scope>
        </dependency>

        <!-- ShrinkWrap Maven Resolver -->
        <dependency>
            <groupId>org.jboss.shrinkwrap.resolver</groupId>
            <artifactId>shrinkwrap-resolver-impl-maven</artifactId>
            <version>${version.shrinkwrap.resolver}</version>
            <scope>test</scope>
        </dependency>
    </dependencies>

    <profiles>
        <!-- Profile 1: WildFly Managed Container (Default) -->
        <profile>
            <id>wildfly-managed</id>
            <activation>
                <activeByDefault>true</activeByDefault>
            </activation>
            <dependencies>
                <dependency>
                    <groupId>org.wildfly.arquillian</groupId>
                    <artifactId>wildfly-arquillian-container-managed</artifactId>
                    <version>5.0.0.Alpha6</version>
                    <scope>test</scope>
                </dependency>
            </dependencies>
            <build>
                <plugins>
                    <plugin>
                        <groupId>org.apache.maven.plugins</groupId>
                        <artifactId>maven-dependency-plugin</artifactId>
                        <executions>
                            <execution>
                                <id>unpack-wildfly</id>
                                <phase>process-test-classes</phase>
                                <goals>
                                    <goal>unpack</goal>
                                </goals>
                                <configuration>
                                    <artifactItems>
                                        <artifactItem>
                                            <groupId>org.wildfly</groupId>
                                            <artifactId>wildfly-dist</artifactId>
                                            <version>26.1.1.Final</version>
                                            <type>zip</type>
                                            <outputDirectory>${project.build.directory}</outputDirectory>
                                        </artifactItem>
                                    </artifactItems>
                                </configuration>
                            </execution>
                        </executions>
                    </plugin>
                    <plugin>
                        <groupId>org.apache.maven.plugins</groupId>
                        <artifactId>maven-surefire-plugin</artifactId>
                        <version>3.0.0-M8</version>
                        <configuration>
                            <systemPropertyVariables>
                                <jboss.home>${project.build.directory}/wildfly-26.1.1.Final</jboss.home>
                            </systemPropertyVariables>
                        </configuration>
                    </plugin>
                </plugins>
            </build>
        </profile>

        <!-- Profile 2: Tomcat Embedded Container -->
        <profile>
            <id>tomcat-embedded</id>
            <dependencies>
                <dependency>
                    <groupId>org.jboss.arquillian.container</groupId>
                    <artifactId>arquillian-tomcat-embedded-8</artifactId>
                    <version>1.1.0.Final</version>
                    <scope>test</scope>
                </dependency>
                <dependency>
                    <groupId>org.apache.tomcat.embed</groupId>
                    <artifactId>tomcat-embed-core</artifactId>
                    <version>8.5.85</version>
                    <scope>test</scope>
                </dependency>
                <dependency>
                    <groupId>org.apache.tomcat.embed</groupId>
                    <artifactId>tomcat-embed-jasper</artifactId>
                    <version>8.5.85</version>
                    <scope>test</scope>
                </dependency>
            </dependencies>
        </profile>
    </profiles>
</project>
```

To run your tests using the WildFly Managed container, execute:
```bash
mvn test -Pwildfly-managed
```

To switch runtimes and execute using the Tomcat Embedded container, run:
```bash
mvn test -Ptomcat-embedded
```

---

## 24.4 Overriding Configurations with arquillian.xml

Default container settings (like port bindings, management credentials, and startup timeouts) are pre-configured by the vendor adapter. To override these parameters, define an `arquillian.xml` file in your classpath (`src/test/resources/arquillian.xml`):

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//f0de0ed9-d17e-4f27-8bf6-c43ce39fbc5c/markdown_2/imgs/img_in_image_box_176_310_942_718.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A21%3A52Z%2F-1%2F%2F8656b321e3b35019da2ca894d4db925c3e0d88906a3c19fe7f822dd2932c8c91" alt="Image" width="72%" /></div>

The layout of `arquillian.xml` is structured into qualifiers that align with target container adapters on the classpath.

### Example: Custom Configuration (`arquillian.xml`)
This configuration file sets custom ports, management ports, and startup configurations:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<arquillian xmlns="http://jboss.org/schema/arquillian"
            xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
            xsi:schemaLocation="http://jboss.org/schema/arquillian 
            http://jboss.org/schema/arquillian/arquillian_3_0.xsd">

    <!-- Configuration for the WildFly Managed Container Profile -->
    <container qualifier="wildfly-managed">
        <configuration>
            <!-- Define the home directory of the unpacked WildFly server -->
            <property name="jbossHome">target/wildfly-26.1.1.Final</property>
            <!-- Bind WildFly to localhost -->
            <property name="managementAddress">127.0.0.1</property>
            <!-- Custom management port override -->
            <property name="managementPort">9990</property>
            <property name="username">admin</property>
            <property name="password">admin-password123!</property>
            <!-- Prevent test failures due to slow server startup -->
            <property name="startupTimeoutInSeconds">120</property>
        </configuration>
    </container>

    <!-- Configuration for the Tomcat Embedded Container Profile -->
    <container qualifier="tomcat-embedded">
        <configuration>
            <property name="bindAddress">127.0.0.1</property>
            <property name="bindHttpPort">8081</property>
            <property name="tomcatHome">target/tomcat-temp</property>
        </configuration>
    </container>
</arquillian>
```

---

## 24.5 Client and Server-Side Assertions (REST & Warp Extensions)

When testing REST microservices in Arquillian, you can run assertions in two ways:
1. **Client-Side (REST Client Extension)**: You execute HTTP requests from the client JVM against the container, validating the HTTP responses (status, body) like an external client.
2. **Server-Side (Warp Extension)**: You intercept a client request *inside* the container, executing assertions on internal server states (like CDI beans, JPA entities, or transaction flags) during the request execution.

### 24.5.1 The REST Client Extension
The REST Client extension injects the base deployment URL (`@ArquillianResource URL url`) and allows calling the REST endpoints using standard client libraries:

```java
package com.ftgo.game.boundary;

import org.jboss.arquillian.container.test.api.Deployment;
import org.jboss.arquillian.junit5.ArquillianExtension;
import org.jboss.arquillian.test.api.ArquillianResource;
import org.jboss.shrinkwrap.api.ShrinkWrap;
import org.jboss.shrinkwrap.api.spec.WebArchive;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;

import javax.ws.rs.client.Client;
import javax.ws.rs.client.ClientBuilder;
import javax.ws.rs.core.MediaType;
import javax.ws.rs.core.Response;
import java.net.URL;

import static org.assertj.core.api.Assertions.assertThat;

@ExtendWith(ArquillianExtension.class)
public class GamesResourceComponentTest {

    @Deployment(testable = false) // testable = false forces the test to run in client-mode
    public static WebArchive createDeployment() {
        return ShrinkWrap.create(WebArchive.class, "games-test.war")
                .addClasses(GamesResource.class, GamesApplication.class);
    }

    @ArquillianResource
    private URL deploymentUrl;

    @Test
    public void shouldReturnSuccessfulGameSearchResponse() {
        Client client = ClientBuilder.newClient();
        Response response = client.target(deploymentUrl.toString() + "api/games/123")
                .request(MediaType.APPLICATION_JSON)
                .get();

        assertThat(response.getStatus()).isEqualTo(Response.Status.OK.getStatusCode());
        String body = response.readEntity(String.class);
        assertThat(body).contains("id", "title");
    }
}
```

---

### 24.5.2 Server-Side Inspections with Warp
Warp intercepts HTTP requests and executes assertions inside the server's JVM. It allows validating database operations, transactions, and CDI contexts directly.

```java
package com.ftgo.game.boundary;

import org.jboss.arquillian.container.test.api.Deployment;
import org.jboss.arquillian.junit5.ArquillianExtension;
import org.jboss.arquillian.warp.Activity;
import org.jboss.arquillian.warp.Inspection;
import org.jboss.arquillian.warp.Warp;
import org.jboss.arquillian.warp.WarpTest;
import org.jboss.arquillian.warp.servlet.AfterServlet;
import org.jboss.shrinkwrap.api.ShrinkWrap;
import org.jboss.shrinkwrap.api.spec.WebArchive;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;

import javax.inject.Inject;
import javax.servlet.http.HttpServletRequest;
import javax.ws.rs.client.ClientBuilder;
import java.net.URL;

import static org.assertj.core.api.Assertions.assertThat;

@ExtendWith(ArquillianExtension.class)
@WarpTest // Activates Warp interception framework
public class GamesWarpComponentTest {

    @Deployment
    public static WebArchive createDeployment() {
        return ShrinkWrap.create(WebArchive.class, "warp-test.war")
                .addClasses(GamesResource.class, DatabaseAuditor.class);
    }

    @ArquillianResource
    private URL deploymentUrl;

    @Test
    public void shouldAuditRequestOnServerAfterApiCall() {
        Warp.initiate(new Activity() {
            @Override
            public void perform() {
                // Client-side call that triggers Warp interception
                ClientBuilder.newClient()
                        .target(deploymentUrl.toString() + "api/games/123")
                        .request()
                        .get();
            }
        }).inspect(new RequestAuditingInspection());
    }

    // This inspection class is serialized and executed INSIDE the container JVM
    private static class RequestAuditingInspection extends Inspection {
        private static final long serialVersionUID = 1L;

        @Inject
        private DatabaseAuditor auditor; // Inject server-side CDI bean

        @AfterServlet
        public void verifyDatabaseAuditLogs(HttpServletRequest request) {
            // Verify that request metadata was logged in the database cache
            assertThat(auditor.getLoggedRequestCount()).isGreaterThan(0);
        }
    }
}
```

---

## 24.6 Component Testing with Spring Boot & WireMock

In a microservices architecture, services communicate with external downstream APIs. When running component tests, we isolate our service under test by mocking these external HTTP calls.

We use **WireMock** to run a local mock HTTP server. We configure our service's outbound gateway (e.g. `YouTubeGateway`) to point to the WireMock server rather than the real production URL.

```
[ Test JVM Runner ] ===(configures)===> [ WireMock Server (Local Port) ]
        |                                       ^
(invokes client request)                        | (HTTP GET)
        |                                       |
        v                                       |
[ Arquillian Container: Web Application ] ======+
```

---

### 24.6.1 The Application Components

#### The Video Domain Entity: `GameVideo.java`
```java
package com.ftgo.game.entity;

public class GameVideo {
    private final String title;
    private final String embedUrl;

    public GameVideo(String title, String embedUrl) {
        this.title = title;
        this.embedUrl = embedUrl;
    }

    public String getTitle() { return title; }
    public String getEmbedUrl() { return embedUrl; }
}
```

#### The Outbound REST Gateway: `YouTubeGateway.java`
```java
package com.ftgo.game.gateway;

import com.ftgo.game.entity.GameVideo;
import org.springframework.web.client.RestTemplate;
import java.util.Map;

public class YouTubeGateway {

    private final RestTemplate restTemplate;
    private final String apiBaseUrl;

    public YouTubeGateway(RestTemplate restTemplate, String apiBaseUrl) {
        this.restTemplate = restTemplate;
        this.apiBaseUrl = apiBaseUrl;
    }

    /**
     * Resolves game video details from YouTube REST API.
     * @param videoId the target video ID.
     * @return GameVideo model mapping.
     */
    @SuppressWarnings("unchecked")
    public GameVideo fetchVideoDetails(String videoId) {
        String url = apiBaseUrl + "/videos/" + videoId;
        
        // Execute HTTP GET request
        Map<String, Object> response = restTemplate.getForObject(url, Map.class);
        
        if (response == null || !response.containsKey("title")) {
            throw new IllegalStateException("Failed to resolve video details from YouTube!");
        }

        String title = (String) response.get("title");
        String embedUrl = "https://www.youtube.com/embed/" + videoId;
        
        return new GameVideo(title, embedUrl);
    }
}
```

#### The Service Layer under Test: `GamerService.java`
```java
package com.ftgo.game.service;

import com.ftgo.game.entity.GameVideo;
import com.ftgo.game.gateway.YouTubeGateway;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class GamerService {

    private static final Logger logger = LoggerFactory.getLogger(GamerService.class);
    private final YouTubeGateway youtubeGateway;

    public GamerService(YouTubeGateway youtubeGateway) {
        this.youtubeGateway = youtubeGateway;
    }

    /**
     * Queries video details, applying fallback logs in case of service downtime.
     * @param videoId target video.
     * @return video info.
     */
    public GameVideo retrieveVideoInfo(String videoId) {
        logger.info("Resolving component video info for id: {}", videoId);
        try {
            return youtubeGateway.fetchVideoDetails(videoId);
        } catch (Exception e) {
            logger.warn("Outbound API failed. Returning cached placeholder.");
            return new GameVideo("Alternative Gameplay Video", "https://youtube.com/embed/placeholder");
        }
    }
}
```

---

### 24.6.2 The Component Test Suite (`GamerServiceComponentTest.java`)
This test class uses `@ExtendWith(ArquillianExtension.class)` to manage the container environment, ShrinkWrap to package the application, and WireMock to mock the external REST API:

```java
package com.ftgo.game.service;

import com.ftgo.game.entity.GameVideo;
import com.ftgo.game.gateway.YouTubeGateway;
import com.github.tomakehurst.wiremock.WireMockServer;
import org.jboss.arquillian.container.test.api.Deployment;
import org.jboss.arquillian.junit5.ArquillianExtension;
import org.jboss.shrinkwrap.api.ShrinkWrap;
import org.jboss.shrinkwrap.api.spec.WebArchive;
import org.jboss.shrinkwrap.resolver.api.maven.Maven;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.springframework.web.client.RestTemplate;

import java.io.File;

import static com.github.tomakehurst.wiremock.client.WireMock.*;
import static org.assertj.core.api.Assertions.assertThat;

@ExtendWith(ArquillianExtension.class)
public class GamerServiceComponentTest {

    private static final int WIREMOCK_PORT = 9090;
    private static WireMockServer wireMockServer;

    // 1. Set up the WireMock mock HTTP server to run on the host machine
    @BeforeAll
    public static void startWireMock() {
        wireMockServer = new WireMockServer(WIREMOCK_PORT);
        wireMockServer.start();
        configureFor("localhost", WIREMOCK_PORT);
    }

    @AfterAll
    public static void stopWireMock() {
        if (wireMockServer != null) {
            wireMockServer.stop();
        }
    }

    // 2. Define the static ShrinkWrap deployment package
    @Deployment
    public static WebArchive createDeployment() {
        // Resolve transitive dependencies (such as Spring Web Libraries) using the Maven Resolver
        File[] springDependencies = Maven.resolver()
                .loadPomFromFile("pom.xml")
                .resolve("org.springframework:spring-web:5.3.25")
                .withTransitiveDependencies()
                .asFile();

        return ShrinkWrap.create(WebArchive.class, "gamer-service-test.war")
                .addClasses(GamerService.class, YouTubeGateway.class, GameVideo.class)
                .addAsLibraries(springDependencies);
    }

    private GamerService gamerService;

    @BeforeEach
    public void setUp() {
        // Configure Gateway to point to the local WireMock instance
        String mockApiUrl = "http://localhost:" + WIREMOCK_PORT;
        YouTubeGateway gateway = new YouTubeGateway(new RestTemplate(), mockApiUrl);
        this.gamerService = new GamerService(gateway);
        
        // Reset WireMock mappings before each test
        wireMockServer.resetAll();
    }

    @Test
    public void shouldReturnFetchedVideoDetailsOnGatewaySuccess() {
        // Given: stub the external service endpoint
        stubFor(get(urlEqualTo("/videos/zelda-vid-1"))
                .willReturn(aResponse()
                        .withHeader("Content-Type", "application/json")
                        .withBody("{\"title\": \"The Legend Of Zelda Gameplay\", \"id\": \"zelda-vid-1\"}")
                        .withStatus(200)));

        // When
        GameVideo result = gamerService.retrieveVideoInfo("zelda-vid-1");

        // Then
        assertThat(result).isNotNull();
        assertThat(result.getTitle()).isEqualTo("The Legend Of Zelda Gameplay");
        assertThat(result.getEmbedUrl()).isEqualTo("https://www.youtube.com/embed/zelda-vid-1");

        // Verify that the container made exactly one HTTP request to the mock server
        verify(getRequestedFor(urlEqualTo("/videos/zelda-vid-1")));
    }

    @Test
    public void shouldReturnFallbackPlaceholderDetailsOnGatewayFailure() {
        // Given: stub the external server to return a 500 error
        stubFor(get(urlEqualTo("/videos/error-vid"))
                .willReturn(aResponse()
                        .withStatus(500)));

        // When
        GameVideo result = gamerService.retrieveVideoInfo("error-vid");

        // Then: verify that the application recovers using fallback logic
        assertThat(result).isNotNull();
        assertThat(result.getTitle()).isEqualTo("Alternative Gameplay Video");
        assertThat(result.getEmbedUrl()).isEqualTo("https://youtube.com/embed/placeholder");
        
        verify(getRequestedFor(urlEqualTo("/videos/error-vid")));
    }
}
```

---

## 24.7 Summary of Component Testing Control Configurations

This table summarizes the configurations, classes, and annotations used to establish component-testing boundaries:

| Testing Vector | Component Resource / Config | Main Implementation Target | Scope Location |
| :--- | :--- | :--- | :--- |
| **In-Container Orchestration** | `@ExtendWith(ArquillianExtension.class)` | Enables the Arquillian runtime and injector engine inside JUnit. | Test Class |
| **Micro-Deployment Packaging** | `@Deployment` / ShrinkWrap | Assembles minimal JAR or WAR archives programmatically. | Static Method |
| **Dependency Resolution** | `Maven.resolver()` | Resolves transitive dependencies from `pom.xml`. | Deployment Builder |
| **Environment Customization** | `arquillian.xml` | Overrides container adapter ports, startup configurations, and timeouts. | Test Resources |
| **HTTP client verification** | `@ArquillianResource URL` | Injects the runtime deployment URL for JAX-RS calls. | Test Fields |
| **Server Interception** | `@WarpTest` / `Warp.initiate()` | Runs assertions on database or CDI beans inside the container JVM. | Test Class & Assertions |
| **Mock API Gateway** | `WireMockServer` | Mocks external REST API endpoints during container execution. | Test Host Process |

---

## Chapter Summary

* Component testing validates a microservice as an isolated unit, mocking external network interfaces (APIs, brokers) but executing the service's internal components inside a real container environment.
* The **Arquillian** framework manages the lifecycle of the test container, handles deployment packaging, and executes tests directly inside the container JVM.
* **ShrinkWrap** allows developers to programmatically package minimal deployment archives (JARs, WARs, EARs) to keep test suites fast, focused, and isolated.
* The **ShrinkWrap Maven Resolver** reads `pom.xml` to dynamically package third-party dependencies into the test deployment.
* Maven profiles allow switching container adapters (Embedded, Managed, Remote) based on the execution context (e.g. local development vs CI pipelines).
* Custom container settings (like port bindings and management credentials) are defined using a `src/test/resources/arquillian.xml` file.
* **REST Client extensions** allow client-side validation of HTTP responses, while **Warp extensions** allow server-side validation of beans and database states.
* External microservices are mocked using **WireMock**, allowing gateways to be tested inside the container environment under both success and failure conditions.
---

## 24.8 Production-Grade FTGO Order Reviews Component Test Suite

In this section, we present the complete, production-grade component test suite for the **review-service** in the **FTGO Order Reviews** system. We package the service using a ShrinkWrap `.war` micro-deployment, resolve dependencies with the Maven Resolver, and mock external HTTP integrations using a local **WireMock** server.

```
[ Test JVM Runner ] ===(configures)===> [ WireMock Server (Local Port 9090) ]
        |                                                 ^
(invokes client request)                                  | (HTTP GET /reviews/images/{id})
        |                                                 |
        v                                                 |
[ Arquillian Container: Web Application ] ================+
```

---

### Scenario: Mocking Food Image Metadata API
Our `OrderReviewsService` interacts with an external CDN metadata service via `ReviewImageGateway` to check if uploaded images exist and retrieve their metadata. In component tests, we isolate our service under test by spinning up a local **WireMock** server to simulate success and failure responses from the external API.

#### 1. The Target Domain Model: `ReviewImageMetadata.java`
```java
package com.ftgo.review.entity;

public class ReviewImageMetadata {
    private final String imageId;
    private final String format;
    private final long sizeBytes;

    public ReviewImageMetadata(String imageId, String format, long sizeBytes) {
        this.imageId = imageId;
        this.format = format;
        this.sizeBytes = sizeBytes;
    }

    public String getImageId() { return imageId; }
    public String getFormat() { return format; }
    public long getSizeBytes() { return sizeBytes; }
}
```

#### 2. The Outbound REST Gateway: `ReviewImageGateway.java`
```java
package com.ftgo.review.gateway;

import com.ftgo.review.entity.ReviewImageMetadata;
import org.springframework.web.client.RestTemplate;
import java.util.Map;

public class ReviewImageGateway {

    private final RestTemplate restTemplate;
    private final String apiBaseUrl;

    public ReviewImageGateway(RestTemplate restTemplate, String apiBaseUrl) {
        this.restTemplate = restTemplate;
        this.apiBaseUrl = apiBaseUrl;
    }

    /**
     * Queries image details from external media storage REST API.
     * @param imageId target image.
     * @return ReviewImageMetadata mapping.
     */
    @SuppressWarnings("unchecked")
    public ReviewImageMetadata fetchImageDetails(String imageId) {
        String url = apiBaseUrl + "/reviews/images/" + imageId;
        
        // Execute HTTP GET request
        Map<String, Object> response = restTemplate.getForObject(url, Map.class);
        
        if (response == null || !response.containsKey("format")) {
            throw new IllegalStateException("Failed to resolve image details from CDN service!");
        }

        String format = (String) response.get("format");
        Number size = (Number) response.get("sizeBytes");
        
        return new ReviewImageMetadata(imageId, format, size.longValue());
    }
}
```

#### 3. The Core Business Service: `OrderReviewsService.java`
```java
package com.ftgo.review.service;

import com.ftgo.review.entity.ReviewImageMetadata;
import com.ftgo.review.gateway.ReviewImageGateway;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class OrderReviewsService {

    private static final Logger logger = LoggerFactory.getLogger(OrderReviewsService.class);
    private final ReviewImageGateway imageGateway;

    public OrderReviewsService(ReviewImageGateway imageGateway) {
        this.imageGateway = imageGateway;
    }

    /**
     * Resolves metadata for a review image, falling back to clean placeholders if CDN is offline.
     * @param imageId target image identifier.
     * @return image metadata.
     */
    public ReviewImageMetadata retrieveImageInfo(String imageId) {
        logger.info("Resolving image metadata for id: {}", imageId);
        try {
            return imageGateway.fetchImageDetails(imageId);
        } catch (Exception e) {
            logger.warn("Outbound CDN API failed. Returning safe metadata placeholder. Reason: {}", e.getMessage());
            return new ReviewImageMetadata(imageId, "JPEG", 1024L);
        }
    }
}
```

#### 4. The Component Test Suite: `OrderReviewsServiceComponentTest.java`
This test uses `@ExtendWith(ArquillianExtension.class)` to manage the container, ShrinkWrap to package the classes, and WireMock to simulate external HTTP responses.

```java
package com.ftgo.review.service;

import com.ftgo.review.entity.ReviewImageMetadata;
import com.ftgo.review.gateway.ReviewImageGateway;
import com.github.tomakehurst.wiremock.WireMockServer;
import org.jboss.arquillian.container.test.api.Deployment;
import org.jboss.arquillian.junit5.ArquillianExtension;
import org.jboss.shrinkwrap.api.ShrinkWrap;
import org.jboss.shrinkwrap.api.spec.WebArchive;
import org.jboss.shrinkwrap.resolver.api.maven.Maven;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.springframework.web.client.RestTemplate;

import java.io.File;

import static com.github.tomakehurst.wiremock.client.WireMock.*;
import static org.assertj.core.api.Assertions.assertThat;

@ExtendWith(ArquillianExtension.class)
public class OrderReviewsServiceComponentTest {

    private static final int WIREMOCK_PORT = 9090;
    private static WireMockServer wireMockServer;

    // 1. Boot up the WireMock server on localhost before executing tests
    @BeforeAll
    public static void startWireMock() {
        wireMockServer = new WireMockServer(WIREMOCK_PORT);
        wireMockServer.start();
        configureFor("localhost", WIREMOCK_PORT);
    }

    @AfterAll
    public static void stopWireMock() {
        if (wireMockServer != null) {
            wireMockServer.stop();
        }
    }

    // 2. Package the service inside a ShrinkWrap WAR archive
    @Deployment
    public static WebArchive createDeployment() {
        // Resolve Spring web dependencies dynamically using Maven resolver
        File[] webDependencies = Maven.resolver()
                .loadPomFromFile("pom.xml")
                .resolve("org.springframework:spring-web:5.3.25")
                .withTransitiveDependencies()
                .asFile();

        return ShrinkWrap.create(WebArchive.class, "review-service-test.war")
                .addClasses(OrderReviewsService.class, ReviewImageGateway.class, ReviewImageMetadata.class)
                .addAsLibraries(webDependencies);
    }

    private OrderReviewsService reviewsService;

    @BeforeEach
    public void setUp() {
        String mockApiUrl = "http://localhost:" + WIREMOCK_PORT;
        ReviewImageGateway gateway = new ReviewImageGateway(new RestTemplate(), mockApiUrl);
        this.reviewsService = new OrderReviewsService(gateway);
        
        // Reset mock server mapping endpoints before each run
        wireMockServer.resetAll();
    }

    @Test
    public void shouldReturnFetchedMetadataOnGatewaySuccess() {
        // Given
        stubFor(get(urlEqualTo("/reviews/images/salad_photo_1.png"))
                .willReturn(aResponse()
                        .withHeader("Content-Type", "application/json")
                        .withBody("{"imageId": "salad_photo_1.png", "format": "PNG", "sizeBytes": 204800}")
                        .withStatus(200)));

        // When
        ReviewImageMetadata result = reviewsService.retrieveImageInfo("salad_photo_1.png");

        // Then
        assertThat(result).isNotNull();
        assertThat(result.getFormat()).isEqualTo("PNG");
        assertThat(result.getSizeBytes()).isEqualTo(204800L);

        // Verify container dispatched the HTTP call successfully
        verify(getRequestedFor(urlEqualTo("/reviews/images/salad_photo_1.png")));
    }

    @Test
    public void shouldReturnFallbackPlaceholderMetadataOnGatewayFailure() {
        // Given: server throws a 500 server error
        stubFor(get(urlEqualTo("/reviews/images/error_photo.png"))
                .willReturn(aResponse()
                        .withStatus(500)));

        // When
        ReviewImageMetadata result = reviewsService.retrieveImageInfo("error_photo.png");

        // Then: verify fallback logic is invoked
        assertThat(result).isNotNull();
        assertThat(result.getFormat()).isEqualTo("JPEG");
        assertThat(result.getSizeBytes()).isEqualTo(1024L);
        
        verify(getRequestedFor(urlEqualTo("/reviews/images/error_photo.png")));
    }
}
```
