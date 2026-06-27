# Chapter 26: Consumer-Driven Contract Testing

In a monolithic application, when one module's API interface changes, the Java compiler immediately catches the breakage and fails the build. In a microservices architecture, however, services are deployed in separate runtimes and speak over network protocols (like HTTP/REST or AMQP). In this environment, if a provider service changes its JSON payload format (for example, renaming a field or changing a type), the compiler cannot detect it. If you deploy this change to production, the consumer microservices will fail at runtime, causing cascading system failures.

Historically, teams tried to solve this using end-to-end integration tests that deploy all microservices together. However, end-to-end tests are slow, flaky, expensive, and require massive environment coordination. **Consumer-Driven Contract Testing (CDCT)** solves this by allowing consumer services to define their exact API expectations in a "contract" file. The provider service then verifies itself against this contract in isolation, without boot-strapping the consumer services. This chapter covers consumer-driven contract testing in Java using **Pact** and **Arquillian Algeron**. We will write complete, copy-pasteable consumer and provider tests, configure Pact Brokers and Maven plugins, and analyze contract types and states.

---

## Learning Objectives

By the end of this chapter, you will be able to:
1. Explain the limitations of monolithic compiler checks and end-to-end integration tests in microservices.
2. Differentiate between Provider Contracts, Consumer Contracts, and Consumer-Driven Contracts.
3. Apply the Postel Law (Robustness Principle) to JSON payload parsing.
4. Set up the Pact JVM framework using JUnit 5 rules and Maven plugins.
5. Build dynamic request and response JSON payloads using `PactDslJsonBody` and matchers.
6. Verify contract assertions on the provider side using JUnit and Maven plugins.
7. Configure Pact States to set up database datasets before a contract interaction.
8. Integrate Pact with the Arquillian container ecosystem using the Arquillian Algeron extension.
9. Configure Pact Brokers to automate the publishing and retrieval of contract files within a CI/CD pipeline.

---

## 26.1 Understanding Contracts: Provider, Consumer, and Consumer-Driven

Every API interaction consists of a **Provider** (the service that exposes the API endpoints and produces the response data) and a **Consumer** (the service that calls the API and consumes the response data).

### 26.1.1 Monolithic vs. Microservice Runtimes
In a monolithic application, all modules reside in the same JVM. If Module B (Provider) changes a method signature, Module A (Consumer) will fail to compile:

```
[ Monolith JVM: Compile-Time Verification ]
Module A (Consumer) ===(Direct Method Invocation)===> Module B (Provider)
  ^                                                      |
  +------------------(Compiler validation detects error)-+
```

In a microservices architecture, each service resides in its own isolated runtime and JVM:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//c17e93a7-001b-4ff1-a0d0-41c0cc1069d4/markdown_0/imgs/img_in_image_box_183_621_913_1168.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A21%3A51Z%2F-1%2F%2F57fa0a42f864a02f6cda5091b0701ee541e03eaa4f31b93b64d0d089ee70be68" alt="Image" width="68%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 6.1 Big-picture overview of the example application</div> </div>

As shown in Figure 6.1, there is no shared JVM or compiler to catch API changes, meaning contract mismatches are only caught at runtime unless verified.

---

### 26.1.2 The Robustness Principle (Postel's Law)
Postel's Law states: *"Be conservative in what you do, be liberal in what you accept from others."* In microservice communication, this means a consumer should only validate the specific JSON fields it requires, and ignore any extra fields in the payload:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//c17e93a7-001b-4ff1-a0d0-41c0cc1069d4/markdown_1/imgs/img_in_image_box_637_538_944_854.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A21%3A51Z%2F-1%2F%2F3595e52129f4f576aa5dd164fc3e4add021dfbea953fa7eff7d74e44aa21fdf5" alt="Image" width="28%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 6.2 Data exchange between producer and consumer A</div> </div>

As shown in Figure 6.2, if a provider returns four fields, but Consumer A only reads `body` and `author`, it should ignore the other fields.

If a new Consumer B requires the provider to change its payload format (for example, nesting `author` inside a sub-object), this change can break Consumer A if Consumer A is not isolated:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//c17e93a7-001b-4ff1-a0d0-41c0cc1069d4/markdown_2/imgs/img_in_image_box_168_594_931_1170.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A21%3A52Z%2F-1%2F%2F02ecea3b0ffcfeaade1883bd87554749d884c9d8172e275640e71c7141bd5776" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 6.3 Data exchange between producer and consumers A and B</div> </div>

As illustrated in Figure 6.3, both consumers must be verified against the provider payload changes. If compatibility breaks, Consumer A fails:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//c17e93a7-001b-4ff1-a0d0-41c0cc1069d4/markdown_3/imgs/img_in_image_box_198_105_901_547.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A21%3A53Z%2F-1%2F%2F12e6b90f5335a81d1295c9090083b3785e8e7448f99e13f57cd5d5cce7de19af" alt="Image" width="66%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 6.4 Updated data-exchange scheme causing compatibility failure</div> </div>

Figure 6.4 shows that Consumer A fails to parse the new structure because it expected a flat string for `author`, while Consumer B succeeds.

---

### 26.1.3 The Cost of Catching Bugs Late
Finding contract breakages in production is extremely expensive, requiring rollbacks and emergency hotfixes. Contract testing shifts these checks to the left, catching mismatches in the build pipeline:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//c17e93a7-001b-4ff1-a0d0-41c0cc1069d4/markdown_4/imgs/img_in_chart_box_192_108_804_470.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A21%3A53Z%2F-1%2F%2Fa94cb16a5ca654c727db026ce05b03456514280b2788d867251076d09aef979e" alt="Image" width="57%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 6.5 Costs of fixing bugs in specific development phases</div> </div>

As illustrated in Figure 6.5, fixing a bug in production can cost up to 100 times more than catching it during the coding phase.

---

### 26.1.4 Contract Types
We classify contracts into three types based on who owns the contract:

#### 1. Provider Contracts
The provider team defines the API schemas (e.g. OpenAPI/Swagger documents) and publishes them. Consumers must adapt to what the provider offers:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//03bfe22b-5695-4a10-9a14-5e272cb78674/markdown_1/imgs/img_in_image_box_648_489_928_926.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A21%3A51Z%2F-1%2F%2Fa3abf5a32bc4791c6dc76828d2d21a37e2e6ebbe66f4c65368358935db6d823a" alt="Image" width="26%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 6.7 Provider contracts</div> </div>

Figure 6.7 illustrates that the provider owns the contract and exposes it to all consumers.

#### 2. Consumer Contracts
Each consumer team defines a contract file outlining exactly what data fields and endpoints they require from the provider:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//03bfe22b-5695-4a10-9a14-5e272cb78674/markdown_2/imgs/img_in_image_box_665_109_947_569.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A21%3A52Z%2F-1%2F%2F330b64b290a82f56adc4cb19b3dac4fdaf27cb133304f3959c43086cc4b0825c" alt="Image" width="26%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 6.8 Consumer contracts</div> </div>

As shown in Figure 6.8, a separate contract exists for each consumer-provider relationship.

#### 3. Consumer-Driven Contracts (Recommended)
A consumer-driven contract aggregates all individual consumer contracts. The provider verifies its API against this aggregated contract to ensure it satisfies all consumer requirements before releasing code:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//03bfe22b-5695-4a10-9a14-5e272cb78674/markdown_2/imgs/img_in_image_box_200_709_611_1197.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A21%3A52Z%2F-1%2F%2F8ce556e02e95b61c5ac0aa3b1d050ae79dafc40de13faef24fb14f2069ae1ce0" alt="Image" width="38%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 6.9 Consumer-driven contracts</div> </div>

Figure 6.9 shows that the provider aggregates all consumer contracts and validates itself against them.

---

## 26.2 The Pact Lifecycle

Pact is the industry-standard tool for consumer-driven contract testing. The Pact lifecycle is divided into five phases:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//b4dc3b18-997f-4211-afaf-701928d11c29/markdown_0/imgs/img_in_image_box_183_142_622_363.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A22%3A10Z%2F-1%2F%2F22ecd93f0b21beb3f6090ecbe13e1dcb06ab766feb108247bd959d493d70d19b" alt="Image" width="41%" /></div>

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//b4dc3b18-997f-4211-afaf-701928d11c29/markdown_0/imgs/img_in_image_box_182_438_621_664.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A22%3A10Z%2F-1%2F%2F56bf36db15ba52ed0e295cea21ea74da2d57138a4e692a33ea76ca9670142a2f" alt="Image" width="41%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 6.10 Pact lifecycle phases</div> </div>

As illustrated in Figure 6.10, the lifecycle flows as follows:
1. **Consumer Test**: The consumer writes a test using the Pact DSL. The test runs against a Pact-managed local mock server, verifying that the consumer handles the response correctly.
2. **Pact Generation**: When the consumer test passes, Pact serializes the expectations into a `.json` contract file (the "pact").
3. **Pact Publishing**: The consumer publishes this pact file to a centralized repository, known as the **Pact Broker**.
4. **Provider Verification**: The provider build downloads the pact from the Pact Broker, runs a local server, and replays all requests defined in the contract against it.
5. **Verification Reporting**: The provider sends the verification results back to the Pact Broker, indicating whether the provider satisfies the consumer's expectations.

---

## 26.3 Pact States: Setting Up Preconditions

A provider must be verified in isolation. However, to respond with a correct JSON payload, the provider may require specific database states (for example, verifying a query request requires that the target ID exists in the database).

We handle this using **Pact States**. When the consumer defines an interaction, it specifies a state description (e.g. `"A game with ID 123 exists"`). Before the provider replays that interaction, it runs a setup hook to insert the required database records:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//2047ee94-7a2e-4db5-bc3d-79c14ccfad06/markdown_3/imgs/img_in_image_box_183_105_911_377.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A22%3A14Z%2F-1%2F%2Ffce71044f2a24159ab7b6ede2269464c870b244ab2d9cceb7b08ca3575ad9b1b" alt="Image" width="68%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 6.11 Interactions between consumer and provider with state setups</div> </div>

As shown in Figure 6.11, the provider intercepts the request, runs the state setup function, executes the REST request, and cleans up the state.

---

## 26.4 Complete Pact JVM Implementation (Java)

This section provides complete, production-ready class listings for both the consumer and provider sides of the **Comments Service** contract test.

### 26.4.1 Build Configuration (`pom.xml`)
Add the following dependencies and plugins to your `pom.xml`:

```xml
<dependencies>
    <!-- JUnit 5 -->
    <dependency>
        <groupId>org.junit.jupiter</groupId>
        <artifactId>junit-jupiter-api</artifactId>
        <version>5.9.2</version>
        <scope>test</scope>
    </dependency>
    <!-- Pact Consumer Support -->
    <dependency>
        <groupId>au.com.dius.pact.consumer</groupId>
        <artifactId>junit5</artifactId>
        <version>4.5.3</version>
        <scope>test</scope>
    </dependency>
    <!-- Pact Provider Support -->
    <dependency>
        <groupId>au.com.dius.pact.provider</groupId>
        <artifactId>junit5</artifactId>
        <version>4.5.3</version>
        <scope>test</scope>
    </dependency>
</dependencies>

<build>
    <plugins>
        <!-- Pact Publish Plugin -->
        <plugin>
            <groupId>au.com.dius.pact.provider</groupId>
            <artifactId>maven</artifactId>
            <version>4.5.3</version>
            <configuration>
                <pactBrokerUrl>http://localhost:9292</pactBrokerUrl>
                <pactDirectory>target/pacts</pactDirectory>
            </configuration>
        </plugin>
    </plugins>
</build>
```

---

### 26.4.2 The Consumer Side (`CommentsConsumerTest.java`)
We write a consumer test for the `CommentsGateway` client. We use the Pact DSL to define our request and response expectations:

```java
package com.ftgo.comment.gateway;

import au.com.dius.pact.consumer.dsl.PactDslJsonBody;
import au.com.dius.pact.consumer.dsl.PactDslWithProvider;
import au.com.dius.pact.consumer.junit5.PactConsumerTestExt;
import au.com.dius.pact.consumer.junit5.PactTestFor;
import au.com.dius.pact.core.model.RequestResponsePact;
import au.com.dius.pact.core.model.annotations.Pact;
import com.ftgo.comment.entity.Comment;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.springframework.web.client.RestTemplate;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

@ExtendWith(PactConsumerTestExt.class)
@PactTestFor(providerName = "comments-service", hostInterface = "localhost", port = "8080")
public class CommentsConsumerTest {

    // 1. Define expectations using the Pact DSL
    @Pact(consumer = "gamer-app")
    public RequestResponsePact createCommentsPact(PactDslWithProvider builder) {
        
        // Define dynamic JSON body matcher
        PactDslJsonBody responseBody = new PactDslJsonBody()
                .minArrayLike("comments", 1)
                    .id("id")
                    .numberType("gameId", 123)
                    .stringType("author")
                    .stringType("text")
                .closeObject()
                .closeArray();

        return builder
                .given("Comments exist for game with ID 123")
                .uponReceiving("a request to retrieve comments for game 123")
                    .path("/comments")
                    .query("gameId=123")
                    .method("GET")
                .willRespondWith()
                    .status(200)
                    .body(responseBody)
                .toPact();
    }

    // 2. Execute the test against the mock server
    @Test
    @PactTestFor(pactMethod = "createCommentsPact")
    public void shouldRetrieveCommentsFromMockServer() {
        // Instantiate the gateway pointing to the Pact local mock server (localhost:8080)
        CommentsGateway gateway = new CommentsGateway(new RestTemplate(), "http://localhost:8080");

        List<Comment> results = gateway.fetchComments(123L);

        // Verify gateway parsed the mock response correctly
        assertThat(results).isNotEmpty();
        assertThat(results.get(0).getAuthor()).isNotBlank();
        assertThat(results.get(0).getText()).isNotBlank();
    }
}
```

---

### 26.4.3 The Provider Side (`CommentsProviderTest.java`)
We write a provider test to verify the `comments-service` API against the published contracts. We use `@State` annotations to set up database data before each interaction:

```java
package com.ftgo.comment.boundary;

import au.com.dius.pact.provider.junit5.HttpTestTarget;
import au.com.dius.pact.provider.junit5.PactVerificationContext;
import au.com.dius.pact.provider.junit5.PactVerificationInvocationContextProvider;
import au.com.dius.pact.provider.junitsupport.Provider;
import au.com.dius.pact.provider.junitsupport.State;
import au.com.dius.pact.provider.junitsupport.loader.PactFolder;
import com.ftgo.comment.entity.Comment;
import com.ftgo.comment.repository.CommentsRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.TestTemplate;
import org.junit.jupiter.api.extension.ExtendWith;

import javax.inject.Inject;

@Provider("comments-service")
@PactFolder("target/pacts") // Retrieve contract files from local directory
public class CommentsProviderTest {

    @Inject
    private CommentsRepository repository;

    @BeforeEach
    public void setUp(PactVerificationContext context) {
        // Direct Pact verification to our running provider server
        context.setTarget(new HttpTestTarget("localhost", 8080, "/"));
    }

    @TestTemplate
    @ExtendWith(PactVerificationInvocationContextProvider.class)
    public void verifyPact(PactVerificationContext context) {
        context.verifyInteraction();
    }

    // 3. Define the setup hook for the Pact state
    @State("Comments exist for game with ID 123")
    public void setupCommentsForGameId() {
        // Clean previous states
        repository.deleteAllComments();

        // Seed target data required for interaction
        Comment comment = new Comment();
        comment.setId(1L);
        comment.setGameId(123L);
        comment.setAuthor("Peter");
        comment.setText("Pact verification is awesome.");

        repository.addComment(comment);
    }
}
```

---

## 26.5 CDCT in Container Environments: Arquillian Algeron

The Pact JVM runner requires a running provider instance. In local development or CI, this means developers must manually start the server before running provider tests.

We solve this using **Arquillian Algeron**. Algeron integrates Pact with the Arquillian container ecosystem, automatically booting the container server, deploying the ShrinkWrap archive, replaying the contracts, and shutting it down:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//2047ee94-7a2e-4db5-bc3d-79c14ccfad06/markdown_2/imgs/img_in_image_box_155_107_972_343.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A22%3A12Z%2F-1%2F%2Fc3777db0840f50e4f795c68aa84016595dafc2de8b922b31959948184552aeff" alt="Image" width="76%" /></div>

Arquillian Algeron wraps Pact execution, automating deployment lifecycle hooks and publishing verification states to target brokers.

### 26.5.1 Algeron Provider Test (`AlgeronCommentsProviderTest.java`)
This test class uses `@Deployment` to build the archive, booting TomEE or WildFly to run the provider verification dynamically:

```java
package com.ftgo.comment.boundary;

import org.jboss.arquillian.container.test.api.Deployment;
import org.jboss.arquillian.junit5.ArquillianExtension;
import org.jboss.arquillian.junit5.annotations.InSequence;
import org.jboss.arquillian.pact.provider.api.Provider;
import org.jboss.arquillian.pact.provider.api.PactFolder;
import org.jboss.arquillian.pact.provider.api.verification.PactVerification;
import org.jboss.shrinkwrap.api.ShrinkWrap;
import org.jboss.shrinkwrap.api.spec.WebArchive;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;

@ExtendWith(ArquillianExtension.class)
@Provider("comments-service")
@PactFolder("pacts")
public class AlgeronCommentsProviderTest {

    // 1. Build and deploy the archive to the container automatically
    @Deployment
    public static WebArchive createDeployment() {
        return ShrinkWrap.create(WebArchive.class, "comments-provider.war")
                .addClasses(Comment.class, CommentsRepository.class, CommentsResource.class);
    }

    // 2. Algeron automatically runs verification against the deployed archive URL
    @Test
    @PactVerification
    public void verifyContracts() {
        // All pact interactions are fetched and verified against the container
    }
}
```

---

### 26.5.2 Algeron Lifecycle Mapping
The diagram below shows the sequence of events during an Algeron provider test run:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//2047ee94-7a2e-4db5-bc3d-79c14ccfad06/markdown_3/imgs/img_in_image_box_183_105_911_377.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A22%3A14Z%2F-1%2F%2Ffce71044f2a24159ab7b6ede2269464c870b244ab2d9cceb7b08ca3575ad9b1b" alt="Image" width="68%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 6.12 The Algeron contract testing lifecycle</div> </div>

As mapped in Figure 6.12:
1. Algeron boots MongoDB (if using NoSQL) and the application server (e.g. TomEE).
2. It deploys the comments service archive.
3. For each pact interaction, it checks for a `@State` annotation and runs it to populate database records.
4. It replays the HTTP requests defined in the contract against the container instance.
5. It undeploys the archive and shuts down the container.

---

## 26.6 Summary of Contract Testing Control Elements

This table summarizes the configurations, annotations, and classes used to establish consumer-driven contract testing:

| Testing Vector | Contract Resource / Config | Main Implementation Target | Scope Location |
| :--- | :--- | :--- | :--- |
| **Consumer Mock rule** | `PactProviderRule` | Manages mock HTTP server lifecycle and contract generation. | Test Class |
| **Pact Definition** | `@Pact(consumer, provider)` | Declares the contract expectations method. | Test Method |
| **JSON Payload DSL** | `PactDslJsonBody` | Builds dynamic JSON matchers and typings. | Pact Builder |
| **Provider Verification** | `@Provider("name")` | Binds the test class to a specific provider endpoint. | Test Class |
| **Local Contract Retrieval** | `@PactFolder("path")` | Reads pact contracts from local filesystem directories. | Test Class |
| **Pact Broker Retrieval** | `@PactBroker(host)` | Reads pact contracts from a centralized broker server. | Test Class |
| **Precondition State** | `@State("description")` | Declares database seeding setup hooks on the provider. | Test Method |
| **Container Integration** | `@PactVerification` / Algeron | Automatically boots containers to verify provider pacts. | Test Method |

---

## Chapter Summary

* In a microservices architecture, API contract breakages cannot be caught by the compiler because services reside in isolated runtimes.
* Consumer-Driven Contract Testing (CDCT) allows consumers to define their exact API expectations in a contract file, which the provider verifies in isolation.
* Postel's Law states that consumers should be liberal in what they accept, validating only the specific JSON fields they require.
* The **Pact** framework provides a DSL to build mock HTTP expectations on the consumer side, generating pact contract files automatically.
* Dynamic JSON expectations are defined using `PactDslJsonBody` to avoid fragile static value tests.
* On the provider side, Pact replays requests defined in the contract against a running instance of the provider.
* We configure **Pact States** using `@State` to seed database records before replaying specific contract interactions.
* **Arquillian Algeron** integrates Pact with the container ecosystem, automatically booting servers, deploying archives, and running provider contract validations.
---

## 26.7 Production-Grade FTGO Order Reviews Contract Test Suite

In this section, we present the complete, production-grade consumer-driven contract testing (CDCT) suite for the **FTGO Order Reviews** system. We implement the consumer-side test (for the gateway in `order-service` calling `/reviewsservice/reviews?orderId=999`), the provider-side verification test (for the `review-service`), and the container-integrated **Arquillian Algeron** provider test.

---

### Scenario: Gateway API Integration Contract
The `order-service` (consumer) invokes the `review-service` (provider) to retrieve review lists when displaying order details. We must establish a contract that ensures the provider returns the fields `id`, `orderId`, `reviewerName`, `reviewText`, and `rating` in the correct types.

#### 1. The Outbound REST Gateway: `OrderReviewsGateway.java` (order-service)
```java
package com.ftgo.order.gateway;

import com.ftgo.review.entity.OrderReview;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.util.UriComponentsBuilder;

import java.util.Arrays;
import java.util.List;

public class OrderReviewsGateway {

    private final RestTemplate restTemplate;
    private final String serviceUrl;

    public OrderReviewsGateway(RestTemplate restTemplate, String serviceUrl) {
        this.restTemplate = restTemplate;
        this.serviceUrl = serviceUrl;
    }

    /**
     * Fetches the reviews for a specific order.
     * @param orderId the order ID.
     * @return the list of reviews.
     */
    public List<OrderReview> fetchOrderReviews(Long orderId) {
        String url = UriComponentsBuilder.fromHttpUrl(serviceUrl)
                .path("/reviewsservice/reviews")
                .queryParam("orderId", orderId)
                .toUriString();

        OrderReview[] reviews = restTemplate.getForObject(url, OrderReview[].class);
        return Arrays.asList(reviews != null ? reviews : new OrderReview[0]);
    }
}
```

---

### 2. The Consumer Test: `OrderReviewsConsumerTest.java` (order-service)
We define our contract expectations using Pact DSL matchers and run a local consumer verification.

```java
package com.ftgo.order.gateway;

import au.com.dius.pact.consumer.dsl.PactDslJsonArray;
import au.com.dius.pact.consumer.dsl.PactDslJsonBody;
import au.com.dius.pact.consumer.dsl.PactDslWithProvider;
import au.com.dius.pact.consumer.junit5.PactConsumerTestExt;
import au.com.dius.pact.consumer.junit5.PactTestFor;
import au.com.dius.pact.core.model.RequestResponsePact;
import au.com.dius.pact.core.model.annotations.Pact;
import com.ftgo.review.entity.OrderReview;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.springframework.web.client.RestTemplate;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

@ExtendWith(PactConsumerTestExt.class)
@PactTestFor(providerName = "review-service", hostInterface = "localhost", port = "8080")
public class OrderReviewsConsumerTest {

    // 1. Declare contract expectations
    @Pact(consumer = "order-service")
    public RequestResponsePact createReviewsContract(PactDslWithProvider builder) {
        PactDslJsonBody responseBody = new PactDslJsonBody()
                .minArrayLike("reviews", 1)
                    .id("id")
                    .numberType("orderId", 999L)
                    .stringType("reviewerName", "Alice")
                    .stringType("reviewText", "Highly recommend!")
                    .integerType("rating", 5)
                .closeObject()
                .closeArray();

        return builder
                .given("Reviews exist for order 999")
                .uponReceiving("a request to retrieve reviews for order 999")
                    .path("/reviewsservice/reviews")
                    .query("orderId=999")
                    .method("GET")
                .willRespondWith()
                    .status(200)
                    .body(responseBody)
                .toPact();
    }

    // 2. Verify that the gateway can parse mock provider responses correctly
    @Test
    @PactTestFor(pactMethod = "createReviewsContract")
    public void shouldRetrieveReviewsFromMockServer() {
        OrderReviewsGateway gateway = new OrderReviewsGateway(new RestTemplate(), "http://localhost:8080");

        List<OrderReview> results = gateway.fetchOrderReviews(999L);

        assertThat(results).isNotEmpty();
        assertThat(results.get(0).getReviewerName()).isEqualTo("Alice");
        assertThat(results.get(0).getReviewText()).isEqualTo("Highly recommend!");
        assertThat(results.get(0).getRating()).isEqualTo(5);
    }
}
```

---

### 3. The Provider Test: `OrderReviewsProviderTest.java` (review-service)
We verify the real backend REST service against published contracts, running state setups before replaying interactions.

```java
package com.ftgo.review.boundary;

import au.com.dius.pact.provider.junit5.HttpTestTarget;
import au.com.dius.pact.provider.junit5.PactVerificationContext;
import au.com.dius.pact.provider.junit5.PactVerificationInvocationContextProvider;
import au.com.dius.pact.provider.junitsupport.Provider;
import au.com.dius.pact.provider.junitsupport.State;
import au.com.dius.pact.provider.junitsupport.loader.PactFolder;
import com.ftgo.review.entity.OrderReview;
import com.ftgo.review.repository.OrderReviewsRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.TestTemplate;
import org.junit.jupiter.api.extension.ExtendWith;

import javax.inject.Inject;

@Provider("review-service")
@PactFolder("target/pacts")
public class OrderReviewsProviderTest {

    @Inject
    private OrderReviewsRepository repository;

    @BeforeEach
    public void setUp(PactVerificationContext context) {
        context.setTarget(new HttpTestTarget("localhost", 8080, "/"));
    }

    @TestTemplate
    @ExtendWith(PactVerificationInvocationContextProvider.class)
    public void verifyPact(PactVerificationContext context) {
        context.verifyInteraction();
    }

    // Hook up database states before replaying interactions
    @State("Reviews exist for order 999")
    public void setupReviewsForOrder() {
        // Clean database tables
        repository.em.createQuery("DELETE FROM OrderReview").executeUpdate();

        // Seed reviews for order 999
        OrderReview review = new OrderReview();
        review.setId(100L);
        review.setOrderId(999L);
        review.setReviewerName("Alice");
        review.setReviewText("Highly recommend!");
        review.setRating(5);

        repository.create(review);
    }
}
```

---

### 4. Container Integration: `AlgeronOrderReviewsProviderTest.java`
We use **Arquillian Algeron** to deploy the WAR package, boot Tomcat, deploy states, and execute the contract verification automatically.

```java
package com.ftgo.review.boundary;

import com.ftgo.review.entity.OrderReview;
import com.ftgo.review.repository.OrderReviewsRepository;
import org.jboss.arquillian.container.test.api.Deployment;
import org.jboss.arquillian.junit5.ArquillianExtension;
import org.jboss.arquillian.pact.provider.api.Provider;
import org.jboss.arquillian.pact.provider.api.PactFolder;
import org.jboss.arquillian.pact.provider.api.verification.PactVerification;
import org.jboss.shrinkwrap.api.ShrinkWrap;
import org.jboss.shrinkwrap.api.spec.WebArchive;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;

@ExtendWith(ArquillianExtension.class)
@Provider("review-service")
@PactFolder("pacts")
public class AlgeronOrderReviewsProviderTest {

    @Deployment
    public static WebArchive createDeployment() {
        return ShrinkWrap.create(WebArchive.class, "reviews-provider.war")
                .addClasses(OrderReview.class, OrderReviewsRepository.class, OrderReviewsResource.class);
    }

    @Test
    @PactVerification
    public void verifyContracts() {
        // Algeron intercepts container deployment and runs verification against local broker files
    }
}
```
