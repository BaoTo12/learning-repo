# Chapter 25: Integration-Testing & ShrinkWrap Deployments

In a microservices architecture, integration testing validates that a service can communicate correctly with its external peers, databases, and network adapters. While unit tests isolate logic using mocks and component tests bundle a single service in a container with mocked outbound calls, integration testing verifies the real network transport boundaries, database serialization layers, and third-party protocol converters.

This chapter covers the design and technical implementation of **Integration-Testing and ShrinkWrap Deployments** in Java. We will analyze integration testing schemas, write robust persistence tests using the **Arquillian Persistence Extension (APE)**, and configure **NoSQLUnit** to execute integration tests against NoSQL datastores. We will configure multi-deployment scenarios to test service-to-service communication, define execution sequences, and customize Maven build scripts. Finally, we will write complete, production-grade integration test listings for the Gamer application, verifying database repository operations and external REST API gateways.

---

## Learning Objectives

By the end of this chapter, you will be able to:
1. Explain the purpose of integration testing and map the microservice layers that require integration validation.
2. Differentiate integration testing from unit and component testing.
3. Design predictable database integration tests by enforcing data isolation and lifecycle purges.
4. Implement declarative and programmatic database seeding using APE (Arquillian Persistence Extension).
5. Build and execute NoSQL database integration tests using NoSQLUnit and MongoDB.
6. Configure multi-deployment archives in Arquillian to test service-to-service communication loops.
7. Apply `@OperateOnDeployment` and `@InSequence` to control multi-deployment test contexts.
8. Resolve complex external gateway APIs during testing without invoking production systems.
9. Configure Maven dependencies and build adapters for advanced integration test environments.

---

## 25.1 Integration Testing in Microservices

The primary goal of integration testing in a microservices architecture is to verify the communication between the service and external components (like relational databases, caches, messaging queues, or remote REST APIs) without testing the internal logic of those external components.

### 25.1.1 Modules Communication
An integration test exercises the interfaces and data contracts between modules. Unlike a unit test, it involves calling at least one target class and executing the real network call or database query to verify that data is serialized and transmitted correctly:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//7beaed2e-af04-48e5-843b-3f811fd16bc2/markdown_1/imgs/img_in_image_box_202_424_749_608.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A21%3A50Z%2F-1%2F%2F14caa4fb4ec3b6ff81af30234d92319ed1918e8b57b3dd7b598c6dd71c31d31c" alt="Image" width="51%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 5.1 Integration tests involving different modules</div> </div>

As shown in Figure 5.1, integration tests verify that Module A and Module B communicate correctly across their shared interface.

---

### 25.1.2 Microservice Subsystem Schema
In a microservices context, the integration test executes inside the service container and communicates with a real external dependency (like a database or mock API gateway) over network ports:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//7beaed2e-af04-48e5-843b-3f811fd16bc2/markdown_1/imgs/img_in_image_box_201_1083_949_1186.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A21%3A50Z%2F-1%2F%2F447f3b05a155bc351937a640bf67c0ea3a3f7deb784e91682455ea298aa731df" alt="Image" width="70%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 5.2 Integration test schema with an external component</div> </div>

As shown in Figure 5.2, the subsystem under test (e.g. your service code inside a container) sends requests to and receives responses from the external component over a real network socket.

---

### 25.1.3 Microservice Anatomy Boundaries
We do not need to integration-test every class in a microservice. We focus integration tests on the components that cross the service boundary. In the diagram below, these integration boundaries are highlighted:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//7beaed2e-af04-48e5-843b-3f811fd16bc2/markdown_2/imgs/img_in_image_box_181_512_706_1019.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A21%3A51Z%2F-1%2F%2F11786cf9a6e9fea5451ac412c92c0df97f1660d33430c224e3063b5f77841d75" alt="Image" width="49%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 5.3 Layers to write integration tests for in a microservice architecture</div> </div>

As illustrated in Figure 5.3, we target three main integration areas:
* **The Gateway Component Layer**: Verifies that outbound API client calls construct and transmit HTTP requests correctly.
* **The Resource Component Layer**: Verifies that REST endpoints parse incoming HTTP requests and return correct headers and payload structures.
* **The Database Repositories**: Verifies that SQL/NoSQL entities map correctly and execute queries against the database without errors.

---

## 25.2 Database Integration: The Risk of Shared State

Relational database integration tests suffer from a common anti-pattern: **Shared State Mutation**. If tests run against a persistent database without isolation, their execution order can cause false results.

Consider a repository test containing two methods: `shouldFindAllGames()` and `shouldInsertGame()`. If the test runner executes `shouldInsertGame()` first, it inserts a record into the database. When `shouldFindAllGames()` executes next, it reads this newly inserted record, changing its expected count and failing the assertion:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//7beaed2e-af04-48e5-843b-3f811fd16bc2/markdown_4/imgs/img_in_image_box_183_418_908_828.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A21%3A52Z%2F-1%2F%2F06bb11290720589d508ca1a8fc3868f4efb0a02373f2eeaa4af464f399ec8528" alt="Image" width="68%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 5.4 Failing test execution due to order dependencies</div> </div>

Conversely, if the runner executes the query test first, the DB is empty, the count assertion matches, and all tests pass. This is a **false-positive** scenario, as the test suite is fragile and will fail if the execution order changes:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//1dea7bae-83f1-4d88-88bd-7ac92470a7de/markdown_0/imgs/img_in_image_box_203_126_925_499.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A21%3A50Z%2F-1%2F%2F9f5dd0494670d6cb039a87a91038e468dfcbeb5761f6032032f5aa5d1d21b174" alt="Image" width="67%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 5.5 Successful test execution (False Positive) depending on order</div> </div>

### Enforcing Lifecycle Isolation
To solve this, we must reset the database to a known state before each test executes. We do this by purging previous mutations and seeding the database with a static, predictable dataset:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//1dea7bae-83f1-4d88-88bd-7ac92470a7de/markdown_0/imgs/img_in_image_box_765_574_944_927.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A21%3A50Z%2F-1%2F%2Fe19beb815ebc28a49e398b4500925fa70d130d969fd1be74f60e227af69976c8" alt="Image" width="16%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 5.6 Lifecycle of a safe persistence test</div> </div>

As shown in Figure 5.6, the database lifecycle consists of three phases:
1. **Purge**: Delete all existing rows in target tables before running a test.
2. **Seed**: Insert the specific data rows needed for the test.
3. **Execute**: Run the test assertions.

---

## 25.3 Relational Database Testing with APE

The **Arquillian Persistence Extension (APE)** automates this database lifecycle, allowing developers to define datasets and assert database states declaratively.

### 25.3.1 Declarative APE Structure
APE integrates with Arquillian using metadata annotations:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//1dea7bae-83f1-4d88-88bd-7ac92470a7de/markdown_1/imgs/img_in_image_box_128_223_937_665.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A21%3A51Z%2F-1%2F%2Fd713675d5836468becce890e27efc0367ff3012f56b46a5913f051cf8f5a1f78" alt="Image" width="76%" /></div>

The `@UsingDataSet` annotation seeds the database from a file (e.g. YAML, XML, or JSON), while `@ShouldMatchDataSet` asserts that the database contents match the expected dataset after the test executes.

---

### 25.3.2 APE Lifecycle and Sequence Mappings
The diagram below shows the sequence of events when executing a test with APE:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//1dea7bae-83f1-4d88-88bd-7ac92470a7de/markdown_2/imgs/img_in_image_box_194_529_755_1209.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A21%3A52Z%2F-1%2F%2F5eedd2139768ca6d1460b1d097f45d20ebcd23604ed10abccd729e995e8163de" alt="Image" width="52%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 5.7 Arquillian Persistence Extension lifecycle</div> </div>

As shown in the sequence mapping:
1. **Container Startup**: Arquillian boots the server and deploys the ShrinkWrap archive.
2. **Transaction Hook**: The extension opens a transaction on the target database datasource.
3. **Data Seeding**: APE parses the target dataset and executes SQL inserts.
4. **Test Run**: JUnit executes the test method assertions.
5. **State Assertion**: APE queries the database and verifies it matches the `@ShouldMatchDataSet` file.
6. **Cleanup**: APE deletes all rows in the seeded tables.

---

## 25.4 NoSQL Database Integration Testing: NoSQLUnit

Relational databases use standard SQL and ACID transactions. However, many microservices use NoSQL datastores (like MongoDB, Redis, or Cassandra) that do not support standard SQL or JDBC transactions.

To run integration tests against NoSQL datastores, we use **NoSQLUnit**. NoSQLUnit provides a lifecycle engine similar to APE, allowing developers to seed and verify NoSQL datastores using YAML or JSON datasets.

### 25.4.1 Defining a MongoDB Dataset (`datasets/comments.json`)
For MongoDB, datasets are defined using JSON structures mapping collections and documents:

```json
{
  "comments": [
    {
      "id": 1,
      "gameId": 123,
      "author": "Peter",
      "text": "Great game!"
    },
    {
      "id": 2,
      "gameId": 123,
      "author": "Alice",
      "text": "Too hard."
    }
  ]
}
```

---

### 25.4.2 Writing a NoSQL Integration Test (`CommentsNoSqlTest.java`)
This test class uses the `@ShouldMatchDataSet` annotation from NoSQLUnit to assert that a document was successfully inserted into a local MongoDB instance:

```java
package com.ftgo.game.repository;

import com.lordofthejars.nosqlunit.annotation.ShouldMatchDataSet;
import com.lordofthejars.nosqlunit.annotation.UsingDataSet;
import com.lordofthejars.nosqlunit.mongodb.MongoDbRule;
import org.junit.Rule;
import org.junit.Test;
import org.mongodb.morphia.Datastore;
import org.mongodb.morphia.Morphia;
import com.mongodb.MongoClient;

import static com.lordofthejars.nosqlunit.mongodb.MongoDbConfigurationBuilder.mongoDb;
import static org.assertj.core.api.Assertions.assertThat;

public class CommentsNoSqlTest {

    // Configure the local MongoDB Rule adapter
    @Rule
    public MongoDbRule mongoDbRule = new MongoDbRule(mongoDb().databaseName("comments-db").build());

    @Test
    @UsingDataSet(locations = "datasets/comments.json", loadStrategy = com.lordofthejars.nosqlunit.core.LoadStrategyEnum.CLEAN_INSERT)
    public void shouldQuerySeededNoSqlDocuments() {
        MongoClient mongoClient = new MongoClient("localhost", 27017);
        Morphia morphia = new Morphia();
        Datastore datastore = morphia.createDatastore(mongoClient, "comments-db");

        long count = datastore.createQuery(Comment.class).count();
        assertThat(count).isEqualTo(2);
    }

    @Test
    @UsingDataSet(locations = "datasets/comments.json", loadStrategy = com.lordofthejars.nosqlunit.core.LoadStrategyEnum.CLEAN_INSERT)
    @ShouldMatchDataSet(location = "datasets/expected-comments.json")
    public void shouldPersistNewCommentDocument() {
        MongoClient mongoClient = new MongoClient("localhost", 27017);
        Morphia morphia = new Morphia();
        Datastore datastore = morphia.createDatastore(mongoClient, "comments-db");

        Comment newComment = new Comment();
        newComment.setId(3);
        newComment.setGameId(123);
        newComment.setAuthor("Bob");
        newComment.setText("Must play.");

        datastore.save(newComment);
    }
}
```

---

## 25.5 Multi-Deployment Integration Testing

In advanced integration scenarios, we must verify that service-to-service calls (e.g. Service A invoking a REST endpoint on Service B) succeed over HTTP.

By default, Arquillian deploys a single archive. However, we can define **multiple deployments** inside a single test class and direct test methods to run against specific deployment contexts using `@OperateOnDeployment`.

```
                    [ Arquillian Test Runner ]
                      /                  \
   (Deploys Web Archive 1)            (Deploys Web Archive 2)
                    /                      \
          v                                  v
[ Service A (orders.war) ] ===(REST Call)===> [ Service B (comments.war) ]
```

---

### 25.5.1 Multi-Deployment Structure
We define multiple `@Deployment` methods, each with a unique `name` attribute:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//17925e97-3bd9-4748-b77f-1947b85ba9f0/markdown_1/imgs/img_in_image_box_117_811_895_1122.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A21%3A53Z%2F-1%2F%2F13dd165179560ee2a97318a81d2a15fa5c47f5e8858a4499fb08cc32888d4dad" alt="Image" width="73%" /></div>

As shown in the multi-deployment schema, two separate web archives are deployed to the container. Test methods can then target either archive using the `@OperateOnDeployment` annotation.

---

### 25.5.2 Multi-Deployment Integration Code (`MultiDeploymentIntegrationTest.java`)
This test class deploys two distinct WAR files (`orders` and `comments`) and verifies their communication:

```java
package com.ftgo.game.integration;

import org.jboss.arquillian.container.test.api.Deployment;
import org.jboss.arquillian.container.test.api.OperateOnDeployment;
import org.jboss.arquillian.junit5.ArquillianExtension;
import org.jboss.arquillian.test.api.ArquillianResource;
import org.jboss.shrinkwrap.api.ShrinkWrap;
import org.jboss.shrinkwrap.api.spec.WebArchive;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;

import javax.ws.rs.client.ClientBuilder;
import javax.ws.rs.core.Response;
import java.net.URL;

import static org.assertj.core.api.Assertions.assertThat;

@ExtendWith(ArquillianExtension.class)
public class MultiDeploymentIntegrationTest {

    // 1. Define Deployment A (Orders Service)
    @Deployment(name = "orders-service", order = 1)
    public static WebArchive createOrdersDeployment() {
        return ShrinkWrap.create(WebArchive.class, "orders.war")
                .addClasses(OrdersResource.class, OrdersApplication.class);
    }

    // 2. Define Deployment B (Comments Service)
    @Deployment(name = "comments-service", order = 2)
    public static WebArchive createCommentsDeployment() {
        return ShrinkWrap.create(WebArchive.class, "comments.war")
                .addClasses(CommentsResource.class, CommentsApplication.class);
    }

    // 3. Inject deployment URLs
    @ArquillianResource
    @OperateOnDeployment("orders-service")
    private URL ordersUrl;

    @ArquillianResource
    @OperateOnDeployment("comments-service")
    private URL commentsUrl;

    @Test
    @OperateOnDeployment("orders-service") // Run test in the context of the Orders service
    public void ordersServiceShouldQueryCommentsServiceSuccessfully() {
        // Query the orders endpoint, which internally queries the comments service url
        String targetUrl = ordersUrl.toString() + "api/orders/123/comments";
        
        Response response = ClientBuilder.newClient()
                .target(targetUrl)
                .request()
                .get();

        assertThat(response.getStatus()).isEqualTo(Response.Status.OK.getStatusCode());
    }
}
```

---

## 25.6 Advanced Postman Integration: API Boundary Testing

To run black-box integration tests against REST resource boundaries, developers often write Postman collections. Postman allows designing REST requests, asserting status codes and payloads, and chain-executing requests using environment variables.

To integrate Postman tests into our Java build lifecycle, we export the Postman collections as JSON files and run them using **Newman** (Postman's CLI runner) inside our integration tests.

### 25.6.1 Exporting a Postman Collection
Export the collection from the Postman UI as a JSON file (`postman/gamer_collection.json`):

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//cde4d08e-36f1-45be-9925-93ff3bb7f4c4/markdown_1/imgs/img_in_image_box_125_107_950_526.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A21%3A51Z%2F-1%2F%2F11dc88641881f05fe273f19e75e45b8316ee15bdc4522e1384e1e6394139493f" alt="Image" width="77%" /></div>

As shown in Figure 5.8, collections can be exported from Postman as JSON files.

---

### 25.6.2 Running Newman from a Java Integration Test (`NewmanIntegrationTest.java`)
This test runs after the Arquillian container boots. It executes Newman as a process, passing the target deployment URL dynamically:

```java
package com.ftgo.game.integration;

import org.jboss.arquillian.container.test.api.Deployment;
import org.jboss.arquillian.junit5.ArquillianExtension;
import org.jboss.arquillian.test.api.ArquillianResource;
import org.jboss.shrinkwrap.api.ShrinkWrap;
import org.jboss.shrinkwrap.api.spec.WebArchive;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.URL;

import static org.assertj.core.api.Assertions.assertThat;

@ExtendWith(ArquillianExtension.class)
public class NewmanIntegrationTest {

    @Deployment(testable = false)
    public static WebArchive createDeployment() {
        return ShrinkWrap.create(WebArchive.class, "gamer-app.war")
                .addClasses(GamesResource.class, GamesApplication.class);
    }

    @ArquillianResource
    private URL baseUrl;

    @Test
    public void executePostmanCollectionUsingNewman() throws Exception {
        // Build the Newman command line process
        ProcessBuilder pb = new ProcessBuilder(
                "newman", "run", "src/test/resources/postman/gamer_collection.json",
                "--env-var", "baseUrl=" + baseUrl.toString()
        );
        
        pb.redirectErrorStream(true);
        Process process = pb.start();

        // Print Newman CLI output to system logs
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(process.getInputStream()))) {
            String line;
            while ((line = reader.readLine()) != null) {
                System.out.println(line);
            }
        }

        int exitCode = process.waitFor();
        // Newman returns 0 if all Postman assertions passed
        assertThat(exitCode).isEqualTo(0);
    }
}
```

---

## 25.7 Advanced Integration Scenarios for the Gamer Application

To demonstrate integration testing in practice, we write the integration suite for the **Gamer Application's Comments System**. 

The system contains:
1. **`Comments` Repository**: Manages user comment records in the database.
2. **`CommentsGateway`**: Calls an external remote HTTP comments API.

---

### 25.7.1 Testing the `Comments` Repository
We write an integration test for `Comments.java` using APE, verifying that queries return correct values when the database is seeded.

#### The Target Class: `Comments.java`
```java
package com.ftgo.comment.repository;

import com.ftgo.comment.entity.Comment;
import javax.ejb.Stateless;
import javax.persistence.EntityManager;
import javax.persistence.PersistenceContext;
import java.util.List;

@Stateless
public class Comments {

    @PersistenceContext(unitName = "GamerPU")
    private EntityManager em;

    public void addComment(Comment comment) {
        if (comment == null) {
            throw new IllegalArgumentException("Comment cannot be null!");
        }
        em.persist(comment);
    }

    public List<Comment> getCommentsForGame(Long gameId) {
        return em.createQuery("SELECT c FROM Comment c WHERE c.gameId = :gameId", Comment.class)
                .setParameter("gameId", gameId)
                .getResultList();
    }
}
```

#### The Integration Test: `CommentsRepositoryTest.java`
```java
package com.ftgo.comment.repository;

import com.ftgo.comment.entity.Comment;
import org.jboss.arquillian.container.test.api.Deployment;
import org.jboss.arquillian.junit5.ArquillianExtension;
import org.jboss.arquillian.persistence.Cleanup;
import org.jboss.arquillian.persistence.UsingDataSet;
import org.jboss.shrinkwrap.api.ShrinkWrap;
import org.jboss.shrinkwrap.api.spec.WebArchive;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;

import javax.inject.Inject;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

@ExtendWith(ArquillianExtension.class)
@Cleanup // Clear database after running test
public class CommentsRepositoryTest {

    @Deployment
    public static WebArchive createDeployment() {
        return ShrinkWrap.create(WebArchive.class, "comments-repo-test.war")
                .addClasses(Comment.class, Comments.class)
                .addAsResource("META-INF/persistence.xml", "META-INF/persistence.xml");
    }

    @Inject
    private Comments commentsRepository;

    @Test
    @UsingDataSet("datasets/comments.yml") // Seed database before running test
    public void shouldReturnCommentsForGameId() {
        // When
        List<Comment> results = commentsRepository.getCommentsForGame(123L);

        // Then
        assertThat(results)
                .isNotNull()
                .hasSize(2)
                .extracting("author")
                .containsExactlyInAnyOrder("Peter", "Alice");
    }

    @Test
    @UsingDataSet("datasets/comments.yml")
    public void shouldSaveNewCommentSuccessfully() {
        // Given
        Comment comment = new Comment();
        comment.setId(3L);
        comment.setGameId(123L);
        comment.setAuthor("Bob");
        comment.setText("Must play.");

        // When
        commentsRepository.addComment(comment);

        // Then
        List<Comment> results = commentsRepository.getCommentsForGame(123L);
        assertThat(results).hasSize(3);
    }
}
```

---

### 25.7.2 Testing the `CommentsGateway` Component
The `CommentsGateway` makes outbound HTTP calls to a remote comments API. We write an integration test using **Hoverfly** to capture and mock these HTTP requests.

#### The Target Class: `CommentsGateway.java`
```java
package com.ftgo.comment.gateway;

import com.ftgo.comment.entity.Comment;
import org.springframework.web.client.RestTemplate;
import java.util.Arrays;
import java.util.List;

public class CommentsGateway {

    private final RestTemplate restTemplate;
    private final String commentsApiUrl;

    public CommentsGateway(RestTemplate restTemplate, String commentsApiUrl) {
        this.restTemplate = restTemplate;
        this.commentsApiUrl = commentsApiUrl;
    }

    /**
     * Resolves comments for a game from a remote HTTP API.
     * @param gameId target game.
     * @return list of comments.
     */
    public List<Comment> fetchComments(Long gameId) {
        String url = commentsApiUrl + "/comments?gameId=" + gameId;
        Comment[] response = restTemplate.getForObject(url, Comment[class]);
        
        if (response == null) {
            throw new IllegalStateException("Failed to retrieve comments from remote API!");
        }
        return Arrays.asList(response);
    }
}
```

#### The Integration Test: `CommentsGatewayTest.java`
```java
package com.ftgo.comment.gateway;

import com.ftgo.comment.entity.Comment;
import io.specto.hoverfly.junit.rule.HoverflyRule;
import org.junit.ClassRule;
import org.junit.Test;
import org.springframework.web.client.RestTemplate;
import java.util.List;

import static io.specto.hoverfly.junit.core.SimulationSource.dsl;
import static io.specto.hoverfly.junit.dsl.HoverflyDsl.service;
import static io.specto.hoverfly.junit.dsl.ResponseCreators.success;
import static org.assertj.core.api.Assertions.assertThat;

public class CommentsGatewayTest {

    private static final String MOCK_URL = "http://www.gamer-comments.com";

    // Configure Hoverfly to intercept and mock outgoing HTTP calls to the comments API
    @ClassRule
    public static HoverflyRule hoverflyRule = HoverflyRule.inSimulationMode(dsl(
            service(MOCK_URL)
                    .get("/comments")
                    .queryParam("gameId", "123")
                    .willReturn(success("[{\"id\": 1, \"gameId\": 123, \"author\": \"Peter\", \"text\": \"Nice!\"}]", "application/json"))
    ));

    @Test
    public void shouldRetrieveCommentsFromGatewayUsingHoverflyInterception() {
        // Given
        CommentsGateway gateway = new CommentsGateway(new RestTemplate(), MOCK_URL);

        // When
        List<Comment> results = gateway.fetchComments(123L);

        // Then
        assertThat(results)
                .isNotNull()
                .hasSize(1);
        assertThat(results.get(0).getAuthor()).isEqualTo("Peter");
        assertThat(results.get(0).getText()).isEqualTo("Nice!");
    }
}
```

---

## 25.8 Summary of Integration Testing Controls

This table summarizes the configurations, classes, and annotations used to establish integration-testing boundaries:

| Testing Vector | Integration Resource / Config | Main Implementation Target | Scope Location |
| :--- | :--- | :--- | :--- |
| **Relational Database Seeding** | `@UsingDataSet` / APE | Seeds the database before running tests. | Test Method |
| **Relational Database Verification** | `@ShouldMatchDataSet` / APE | Asserts database state matches expected datasets. | Test Method |
| **NoSQL Database Isolation** | `MongoDbRule` / NoSQLUnit | Resets MongoDB to a clean state before running tests. | Test Class |
| **Multi-Deployment Context** | `@Deployment(name = "name")` | Compiles and deploys multiple WARs to the container. | Static Method |
| **Context Selection** | `@OperateOnDeployment` | Directs the test method to execute against a specific WAR. | Test Method |
| **Execution Sequence** | `@InSequence(order)` | Defines the execution order of test methods. | Test Method |
| **API Proxy Interception** | `HoverflyRule` | Intercepts and mocks outbound REST client queries. | Test Class |
| **Black-box Boundary Check** | `Newman` / Postman | Runs exported Postman collection assertions against a container. | Test Method |

---

## Chapter Summary

* Integration testing verifies that a microservice communicates correctly with its external peers, databases, and network adapters.
* Relational database integration tests suffer from shared state mutation. We resolve this by purging and seeding the database to a known state before each test.
* The **Arquillian Persistence Extension (APE)** automates database seeding and state checks using `@UsingDataSet` and `@ShouldMatchDataSet`.
* **NoSQLUnit** provides a lifecycle engine similar to APE to seed and verify NoSQL datastores (like MongoDB).
* Arquillian supports **multi-deployment** testing, allowing developers to deploy multiple WARs to the container and target them using `@OperateOnDeployment`.
* Outgoing HTTP API queries can be intercepted and mocked using **Hoverfly**, allowing gateways to be tested without making real network requests.
* Postman collections can be exported as JSON files and executed from Java tests using the **Newman CLI process** to run black-box API assertions.
---

## 25.6 Production-Grade FTGO Order Reviews Integration Test Suite

In this section, we present the complete, production-grade integration test suite for the **review-service** in the **FTGO Order Reviews** system. We implement relational database integration tests using **APE (Arquillian Persistence Extension)** with `@UsingDataSet` seeding, and MongoDB integration tests using the **NoSQLUnit** MongoDB extension.

---

### Scenario A: Relational Database Integration Test using APE
We test the JPA-based persistence layer of the reviews service. We use APE to clean the database and seed it with a known dataset before replaying database operations.

#### 1. The Seed Dataset: `src/test/resources/datasets/reviews-seed.yml`
```yaml
ORDER_REVIEW:
  - id: 100
    orderId: 999
    reviewerName: "Alice"
    reviewText: "Phenomenal pizza, highly recommend!"
    rating: 5
  - id: 101
    orderId: 888
    reviewerName: "Bob"
    reviewText: "Cold salad, slow delivery."
    rating: 2
```

#### 2. The Persistence Integration Test: `OrderReviewsPersistenceTest.java`
```java
package com.ftgo.review.repository;

import com.ftgo.review.entity.OrderReview;
import org.jboss.arquillian.container.test.api.Deployment;
import org.jboss.arquillian.junit5.ArquillianExtension;
import org.jboss.arquillian.persistence.Cleanup;
import org.jboss.arquillian.persistence.CleanupStrategy;
import org.jboss.arquillian.persistence.UsingDataSet;
import org.jboss.shrinkwrap.api.ShrinkWrap;
import org.jboss.shrinkwrap.api.spec.WebArchive;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;

import javax.inject.Inject;
import javax.persistence.EntityManager;
import javax.persistence.PersistenceContext;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;

@ExtendWith(ArquillianExtension.class)
@Cleanup(phase = Cleanup.Phase.BEFORE, strategy = CleanupStrategy.USED_TABLES) // Clean database tables before each run
public class OrderReviewsPersistenceTest {

    @Deployment
    public static WebArchive createDeployment() {
        return ShrinkWrap.create(WebArchive.class, "reviews-persistence-test.war")
                .addClasses(OrderReview.class, OrderReviewsRepository.class)
                .addAsResource("META-INF/persistence.xml", "META-INF/persistence.xml");
    }

    @Inject
    private OrderReviewsRepository repository;

    @PersistenceContext
    private EntityManager entityManager;

    @Test
    @UsingDataSet("datasets/reviews-seed.yml") // Seed database using APE
    public void shouldFindAllSeededReviewsForOrder() {
        // When
        Optional<OrderReview> review1 = repository.findReviewById(100L);
        Optional<OrderReview> review2 = repository.findReviewById(101L);

        // Then
        assertThat(review1).isPresent();
        assertThat(review1.get().getReviewerName()).isEqualTo("Alice");
        assertThat(review1.get().getRating()).isEqualTo(5);

        assertThat(review2).isPresent();
        assertThat(review2.get().getReviewerName()).isEqualTo("Bob");
        assertThat(review2.get().getRating()).isEqualTo(2);
    }

    @Test
    @UsingDataSet("datasets/reviews-seed.yml")
    public void shouldPersistNewReview() {
        // Given
        OrderReview newReview = new OrderReview(102L, 777L, "Charlie", "Amazing pasta!", 5);

        // When
        repository.create(newReview);
        
        // Then
        OrderReview persisted = entityManager.find(OrderReview.class, 102L);
        assertThat(persisted).isNotNull();
        assertThat(persisted.getReviewText()).isEqualTo("Amazing pasta!");
        assertThat(persisted.getOrderId()).isEqualTo(777L);
    }
}
```

---

### Scenario B: MongoDB Integration Test using NoSQLUnit
For high-performance collections, reviews are also indexed in MongoDB. We verify database CRUD operations on MongoDB collections using **NoSQLUnit MongoDB** rule seeding.

#### 1. The Seed Collection Dataset: `src/test/resources/datasets/reviews.json`
```json
{
  "reviews": [
    {
      "id": 200,
      "orderId": 999,
      "reviewerName": "Alice",
      "reviewText": "Awesome salad",
      "rating": 5,
      "foodImages": ["salad.jpg"],
      "reviewTags": ["Healthy"]
    },
    {
      "id": 201,
      "orderId": 888,
      "reviewerName": "Bob",
      "reviewText": "Cold soup",
      "rating": 2,
      "foodImages": ["soup.jpg"],
      "reviewTags": ["Disappointed"]
    }
  ]
}
```

#### 2. The MongoDB Repository Class: `OrderReviewsMongoRepository.java`
```java
package com.ftgo.review.repository;

import com.ftgo.review.entity.OrderReview;
import com.mongodb.client.MongoCollection;
import com.mongodb.client.MongoDatabase;
import com.mongodb.client.model.Filters;
import org.bson.Document;
import java.util.ArrayList;
import java.util.List;

public class OrderReviewsMongoRepository {

    private final MongoCollection<Document> collection;

    public OrderReviewsMongoRepository(MongoDatabase database) {
        this.collection = database.getCollection("reviews");
    }

    public void saveReview(OrderReview review) {
        Document doc = new Document("id", review.getId())
                .append("orderId", review.getOrderId())
                .append("reviewerName", review.getReviewerName())
                .append("reviewText", review.getReviewText())
                .append("rating", review.getRating())
                .append("foodImages", review.getFoodImages())
                .append("reviewTags", review.getReviewTags());
        
        collection.insertOne(doc);
    }

    public List<OrderReview> findReviewsByOrderId(Long orderId) {
        List<OrderReview> results = new ArrayList<>();
        for (Document doc : collection.find(Filters.eq("orderId", orderId))) {
            OrderReview review = new OrderReview();
            review.setId(doc.getLong("id"));
            review.setOrderId(doc.getLong("orderId"));
            review.setReviewerName(doc.getString("reviewerName"));
            review.setReviewText(doc.getString("reviewText"));
            review.setRating(doc.getInteger("rating"));
            
            List<String> images = (List<String>) doc.get("foodImages");
            if (images != null) review.getFoodImages().addAll(images);
            
            List<String> tags = (List<String>) doc.get("reviewTags");
            if (tags != null) review.getReviewTags().addAll(tags);
            
            results.add(review);
        }
        return results;
    }
}
```

#### 3. The MongoDB Integration Test: `OrderReviewsMongoTest.java`
```java
package com.ftgo.review.repository;

import com.ftgo.review.entity.OrderReview;
import com.lordofthejars.nosqlunit.annotation.UsingDataSet;
import com.lordofthejars.nosqlunit.mongodb.MongoDbRule;
import com.mongodb.client.MongoClient;
import com.mongodb.client.MongoClients;
import com.mongodb.client.MongoDatabase;
import org.junit.Rule;
import org.junit.Test;
import java.util.List;

import static com.lordofthejars.nosqlunit.mongodb.MongoDbRule.MongoDbRuleBuilder.newMongoDbRule;
import static org.assertj.core.api.Assertions.assertThat;

public class OrderReviewsMongoTest {

    private static final String DATABASE_NAME = "reviews-db";

    // 1. Configure the NoSQLUnit MongoDB rule pointing to our local test Mongo container
    @Rule
    public MongoDbRule mongoDbRule = newMongoDbRule().defaultEmbeddedMongoDb(DATABASE_NAME);

    @Test
    @UsingDataSet(locations = "/datasets/reviews.json", loadStrategy = com.lordofthejars.nosqlunit.core.LoadStrategyActive.CLEAN_INSERT)
    public void shouldQueryReviewsFromMongoCollection() {
        // Given
        MongoClient mongoClient = MongoClients.create("mongodb://localhost:27017");
        MongoDatabase database = mongoClient.getDatabase(DATABASE_NAME);
        OrderReviewsMongoRepository repo = new OrderReviewsMongoRepository(database);

        // When
        List<OrderReview> reviews = repo.findReviewsByOrderId(999L);

        // Then
        assertThat(reviews).hasSize(1);
        OrderReview review = reviews.get(0);
        assertThat(review.getReviewerName()).isEqualTo("Alice");
        assertThat(review.getReviewText()).isEqualTo("Awesome salad");
        assertThat(review.getFoodImages()).containsExactly("salad.jpg");
        assertThat(review.getReviewTags()).containsExactly("Healthy");
        
        mongoClient.close();
    }
}
```
