# Chapter 23: Unit-Testing Microservices

In a microservices architecture, testing is one of the most critical aspects of the software development lifecycle. Because the system is decomposed into small, independent services communicating over network boundaries, validating the correctness of individual components before they are integrated into larger clusters is paramount. The testing pyramid suggests that unit tests should form the broad foundation of your test suite. They are fast to execute, run locally on a developer's machine without external dependencies, and pinpoint bugs to specific lines of code.

This chapter covers the implementation of high-performance, robust unit tests for Java microservices. We will analyze the trade-offs between **Sociable** and **Solitary** unit testing styles, define the roles of different **Test Doubles** (Dummies, Stubs, Spies, Mocks, and Fakes), and configure our testing framework using **JUnit 5**, **AssertJ**, and **Mockito**. We will write complete, production-grade Java class listings and tests for every architectural layer: utility helpers, rich domain models, JPA database repositories, service coordinators with external API integrations, and asynchronous JAX-RS resource controllers using thread pools and JAX-RS `AsyncResponse`. Finally, we will implement programmatic exception validation and analyze verification strategies to ensure code correctness.

---

## Learning Objectives

By the end of this chapter, you will be able to:
1. Explain the role of unit testing within a microservices testing strategy.
2. Differentiate between solitary unit testing and sociable unit testing.
3. Compare the five types of test doubles: Dummy, Stub, Spy, Mock, and Fake.
4. Configure Maven build scripts withJUnit 5, AssertJ, and Mockito dependencies.
5. Apply Given-When-Then test structures to improve readability.
6. Write sociable unit tests for utility and stateless controller components.
7. Implement functional interface mapping to inject collaborator logic into domain entities.
8. Mock JPA `EntityManager` calls using Mockito runners to test repository layers.
9. Implement behavior verification using Mockito's `verify()`, `times()`, and `never()`.
10. Test asynchronous JAX-RS REST resource endpoints using Mockito `@Captor` and `ArgumentCaptor`.
11. Test exception-throwing code paths and verify error propagation in service orchestrators.
12. Design tests that balance speed, isolation, and robustness.

---

## 23.1 Unit Testing Techniques: Sociable vs. Solitary

A unit test is designed to verify the behavior of a small, coherent piece of code (the "unit under test"), typically a single class. However, classes rarely exist in isolation; they interact with other classes (collaborators or dependencies) to fulfill their business requirements. How we handle these collaborators defines the two main styles of unit testing: **Sociable Unit Testing** and **Solitary Unit Testing**.

### 23.1.1 Sociable Unit Tests
In a sociable unit test, the unit under test is instantiated alongside its real, concrete collaborators. If the class under test calls a method on a dependency, the real code of that dependency is executed:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//5d057e00-737a-4efc-9687-d37960405908/markdown_3/imgs/img_in_image_box_203_106_762_213.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A21%3A52Z%2F-1%2F%2Ff0ae101dcf4a0ff1bc7f15a4a953064ff6c441602f215312739213f71f421fbf" alt="Image" width="52%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 3.1 Sociable unit test</div> </div>

As illustrated in Figure 3.1, the test class and the class under test form the core target, but the collaborator dependencies are real instances rather than mock configurations. 

#### Advantages:
* **True Behavior Validation**: Because real code is executed, sociable tests catch bugs caused by misunderstandings between the caller and the collaborator.
* **Low Refactoring Resistance**: If you refactor the internal implementation details of the collaborator (without changing its public API contract), the test continues to pass without modifications.

#### Disadvantages:
* **Cascading Failures**: A bug in a low-level utility class can cause hundreds of sociable tests across the entire codebase to fail, making it difficult to locate the root cause.
* **Complex Setup**: If the collaborator has its own dependencies (e.g. database connections, file system access), setting up a sociable test requires instantiating the entire dependency tree.

---

### 23.1.2 Solitary Unit Tests
In a solitary unit test, the unit under test is isolated from its real dependencies. Collaborators are replaced with **Test Doubles** (such as mocks or stubs) that mimic the behavior of the real objects:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//9f8da930-d850-454b-a1ab-8a06f7f6b344/markdown_1/imgs/img_in_image_box_184_367_745_476.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A21%3A50Z%2F-1%2F%2F4814596a81587866274578a0b6039f21c1662bafe0ad8ce22f406539652c33b6" alt="Image" width="52%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 3.2 Solitary unit test</div> </div>

As shown in Figure 3.2, the collaborators are replaced with test doubles, confining the execution scope strictly to the test class and the unit under test.

#### Advantages:
* **Isolated Failures**: If a test fails, you know the bug is located within the class under test.
* **Fast Execution**: Test doubles perform no complex calculations, network requests, or database queries, executing in milliseconds.
* **Easy Edge-Case Testing**: You can easily program test doubles to return empty values, throw exceptions, or simulate timeouts.

#### Disadvantages:
* **Mock Fragility**: Tests become tightly coupled to the implementation details of the class under test. If you change which method the class calls on a collaborator, the test fails, even if the business logic is correct.
* **False Security**: If a collaborator's API contract changes but you forget to update the corresponding mocks, the solitary unit tests will pass while the production code fails.

---

## 23.2 Test Doubles: Dummies, Stubs, Spies, Mocks, and Fakes

Gerard Meszaros coined the term **Test Double** to describe any object used to replace a real dependency in a test. Just as stunt doubles take the place of actors in dangerous movie scenes, test doubles stand in for real classes that are slow, insecure, or difficult to configure.

We categorize test doubles into five distinct patterns based on how they behave during test execution:

```
                  +-----------------------------------+
                  |            TEST DOUBLE            |
                  +-----------------+-----------------+
                                    |
     +-----------------+------------+------------+-----------------+
     v                 v                         v                 v
[ Dummy ]          [ Stub ]                   [ Spy ]           [ Mock ]
(Placeholder)      (Canned Response)          (Records Calls)   (Expectations)
                                                                   |
                                                                   v
                                                                [ Fake ]
                                                           (Lightweight Impl)
```

### 1. Dummy
A Dummy is an object passed into a method or constructor but never actually used or invoked. It exists solely to satisfy compiler requirements (such as method signatures or nullability checks):

```java
// Example: passing a dummy configuration object that is never read by the logging logic
GameConfiguration dummyConfig = new GameConfiguration() {
    @Override
    public String getEnvironment() {
        throw new UnsupportedOperationException("Dummy configuration should not be read!");
    }
};
LoggerService service = new LoggerService(dummyConfig);
service.log("Application started"); // The config is never read during this path
```

### 2. Stub
A Stub provides hardcoded, canned responses to method calls made during the test. It does not record how it was called, nor does it verify interactions; it simply feeds data to the class under test so the execution can proceed:

```java
// Example: a Stub repository that always returns a fixed game title
public class GameRepositoryStub implements GameRepository {
    @Override
    public Game findById(Long id) {
        Game game = new Game();
        game.setId(id);
        game.setTitle("Super Mario");
        return game;
    }
}
```

### 3. Spy
A Spy wraps a real dependency (or mimics it) and records details about the invocations made against it (such as arguments passed, return values, or how many times a method was called). It allows the test to verify side effects:

```java
// Example: a Spy that counts how many messages were dispatched
public class EmailServiceSpy implements EmailService {
    private int emailCount = 0;
    private String lastRecipient;

    @Override
    public void sendEmail(String recipient, String message) {
        this.emailCount++;
        this.lastRecipient = recipient;
    }

    public int getEmailCount() { return emailCount; }
    public String getLastRecipient() { return lastRecipient; }
}
```

### 4. Mock
A Mock is pre-programmed with expectations regarding the sequence of calls it should receive. It differs from a Stub because it actively verifies that the class under test behaves as expected:

```java
// Example: a mock verifying that the database transaction commit was invoked exactly once
public class TransactionMock implements TransactionManager {
    private boolean commitCalled = false;

    @Override
    public void commit() {
        this.commitCalled = true;
    }

    public void verify() {
        if (!commitCalled) {
            throw new AssertionError("Expected commit() to be called, but it was not!");
        }
    }
}
```

### 5. Fake
A Fake is a working implementation of a dependency, but it uses shortcuts that make it unsuitable for production environments (such as an in-memory H2 database replacing a production PostgreSQL instance, or a local Map replacing an external Redis cluster):

```java
// Example: a Fake user database using a HashMap
public class FakeUserRepository implements UserRepository {
    private final Map<Long, User> store = new HashMap<>();

    @Override
    public void save(User user) {
        store.put(user.getId(), user);
    }

    @Override
    public User findById(Long id) {
        return store.get(id);
    }
}
```

---

## 23.3 Unit Testing in Microservice Layers

A typical Java microservice is structured into multiple logical layers, each with specific testing requirements and patterns:

```
  [ Client Request ]
          |
          v
+-----------------------------+
|    Resource Controller      |  --> Endpoint definitions (HTTP, REST, JSON)
+--------------+--------------+      - Solitary testing with Mocks to verify status codes.
               |
               v
+-----------------------------+
|       Service Layer         |  --> Business orchestration & transactional rules
+--------------+--------------+      - Solitary testing to isolate external gateway APIs.
               |
               v
+-----------------------------+
|      Repository Layer       |  --> Database persistence operations (JPA)
+--------------+--------------+      - Mocking EntityManager or testing with lightweight databases.
               |
               v
+-----------------------------+
|        Domain Entity        |  --> Core rich domain logic (DDD Aggregates)
+-----------------------------+      - Sociable testing: verify state transformations.
```

### Resource and Service Component Layers
The **Resource Layer** (e.g. JAX-RS or Spring MVC Controllers) acts as the entry point for incoming HTTP requests. It handles path routing, content negotiation (XML/JSON deserialization), and request parameter validation. Tests here should verify that the correct HTTP status codes (200 OK, 400 Bad Request, 503 Service Unavailable) and payloads are returned. Mocks are heavily used here to simulate service layer responses.

The **Service Layer** orchestrates business processes. It retrieves data from repositories, calls external APIs, and applies business rules. Unit testing this layer requires mocking the database repositories and outbound gateways to focus entirely on conditional flows, calculations, and exception handling.

### Gateway Component
Gateways communicate with external microservices or third-party APIs. When testing gateways, solitary unit testing is preferred: we mock the underlying HTTP client (e.g., Spring `RestTemplate` or Apache `HttpClient`) to verify that the correct request payload, headers, and HTTP verbs are dispatched.

### Domain Component
Domain entities contain the core business models and data logic. Following DDD (Domain-Driven Design), entities should be "rich" models rather than simple, passive getters and setters. Because domain logic is self-contained and does not interact with infrastructure (databases, networks), **sociable testing** is the standard approach here.

### Repository Components
Repositories execute database CRUD operations. Since repository tests verify SQL mappings, database queries, and transaction state changes, writing pure unit tests with mocks offers little value. Instead, we use integration tests with in-memory database shims (like H2), or write mock tests that verify that database operations (like `merge` or `find`) are called in the expected order.

---

## 23.4 Testing Toolkit: JUnit 5, AssertJ, and Mockito

To build a high-performance unit testing suite, we leverage three industry-standard Java libraries:

1. **JUnit 5**: The orchestration framework. It manages the lifecycle of tests, runs them in parallel, and provides annotations to set up preconditions and tear down resources.
2. **AssertJ**: A fluent assertion library that replaces native JUnit assertions (`assertEquals`, `assertTrue`) with a readable, chainable API.
3. **Mockito**: A framework to generate mock implementations of interfaces and classes, stub method calls, and verify execution flows.

### Build Script Configuration (Maven `pom.xml`)
To integrate these frameworks, include the following configuration under the `<dependencies>` block:

```xml
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    <groupId>com.ftgo</groupId>
    <artifactId>gamer-app-testing</artifactId>
    <version>1.0.0</version>

    <properties>
        <maven.compiler.source>11</maven.compiler.source>
        <maven.compiler.target>11</maven.compiler.target>
        <junit.jupiter.version>5.9.2</junit.jupiter.version>
        <assertj.version>3.24.2</assertj.version>
        <mockito.version>5.2.0</mockito.version>
    </properties>

    <dependencies>
        <!-- JUnit 5 Engine and API -->
        <dependency>
            <groupId>org.junit.jupiter</groupId>
            <artifactId>junit-jupiter-api</artifactId>
            <version>${junit.jupiter.version}</version>
            <scope>test</scope>
        </dependency>
        <dependency>
            <groupId>org.junit.jupiter</groupId>
            <artifactId>junit-jupiter-engine</artifactId>
            <version>${junit.jupiter.version}</version>
            <scope>test</scope>
        </dependency>

        <!-- AssertJ Fluent Assertions -->
        <dependency>
            <groupId>org.assertj</groupId>
            <artifactId>assertj-core</artifactId>
            <version>${assertj.version}</version>
            <scope>test</scope>
        </dependency>

        <!-- Mockito Mocking Library -->
        <dependency>
            <groupId>org.mockito</groupId>
            <artifactId>mockito-core</artifactId>
            <version>${mockito.version}</version>
            <scope>test</scope>
        </dependency>
        
        <!-- Mockito JUnit 5 Extension -->
        <dependency>
            <groupId>org.mockito</groupId>
            <artifactId>mockito-junit-jupiter</artifactId>
            <version>${mockito.version}</version>
            <scope>test</scope>
        </dependency>

        <!-- JSON Processing API & Implementation for resource mock testing -->
        <dependency>
            <groupId>javax.json</groupId>
            <artifactId>javax.json-api</artifactId>
            <version>1.1.4</version>
        </dependency>
        <dependency>
            <groupId>org.glassfish</groupId>
            <artifactId>javax.json</artifactId>
            <version>1.1.4</version>
        </dependency>
    </dependencies>

    <build>
        <plugins>
            <!-- Maven Surefire Plugin to execute JUnit 5 tests -->
            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-surefire-plugin</artifactId>
                <version>3.0.0-M8</version>
            </plugin>
        </plugins>
    </build>
</project>
```

---

## 23.5 Exhaustive Testing Scenarios with Complete Code Listings

To demonstrate unit testing in practice, we will design and implement the test suite for the **Gamer App**, a microservice that aggregates video game records, user comment reviews, and YouTube video gameplay links.

```
+-------------------------------------------------------------+
|                         GAMER APP                           |
+-------------------------------------------------------------+
|                                                             |
|   [ JAX-RS Endpoint: GamesResource ] (Asynchronous Controller)
|                  |                                          |
|                  v                                          |
|   [ Coordinator: GamesService ] (Coordinates DB & IGDB API) |
|                  |                                          |
|         +--------+--------+                                 |
|         v                 v                                 |
|   [ GamesRepository ]  [ IgdbGateway ]                      |
|   (JPA persistence)    (External API)                       |
|                                                             |
+-------------------------------------------------------------+
```

---

### Scenario 1: Helper Utilities (Sociable Unit Test)
We begin with the `YouTubeVideoLinkCreator` helper utility. It compiles raw video identifier strings into embeddable HTML URL structures. Because this class has no side effects, static contexts, or network dependencies, we test it using a **sociable approach** (creating concrete instances without mocks).

#### The Target Class: `YouTubeVideoLinkCreator.java`
```java
package com.ftgo.video.controller;

import java.net.MalformedURLException;
import java.net.URI;
import java.net.URL;

public class YouTubeVideoLinkCreator {

    private static final String EMBED_URL = "https://www.youtube.com/embed/";

    /**
     * Builds a standardized YouTube embed link for a given video ID.
     * @param videoId the unique identifier for the video.
     * @return the formatted URL.
     * @throws IllegalArgumentException if the videoId is invalid or null.
     */
    public URL createEmbeddedUrl(final String videoId) {
        if (videoId == null || videoId.trim().isEmpty()) {
            throw new IllegalArgumentException("Video ID cannot be null or empty!");
        }
        
        try {
            return URI.create(EMBED_URL + videoId.trim()).toURL();
        } catch (final MalformedURLException e) {
            throw new IllegalArgumentException("Malformed URL resulted from video identifier: " + videoId, e);
        }
    }
}
```

#### The Unit Test: `YouTubeVideoLinkCreatorTest.java`
```java
package com.ftgo.video.controller;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import java.net.URL;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

public class YouTubeVideoLinkCreatorTest {

    private YouTubeVideoLinkCreator linkCreator;

    @BeforeEach
    public void setUp() {
        // Instantiate the concrete class before each test execution
        this.linkCreator = new YouTubeVideoLinkCreator();
    }

    @Test
    public void shouldReturnYouTubeEmbeddedUrlForGivenVideoId() {
        // Given
        String targetVideoId = "1234";

        // When
        URL resultUrl = linkCreator.createEmbeddedUrl(targetVideoId);

        // Then
        assertThat(resultUrl)
                .isNotNull()
                .hasProtocol("https")
                .hasHost("www.youtube.com")
                .hasPath("/embed/1234");
    }

    @Test
    public void shouldThrowIllegalArgumentExceptionWhenVideoIdIsEmpty() {
        // Given
        String emptyId = "";

        // When & Then
        assertThatThrownBy(() -> linkCreator.createEmbeddedUrl(emptyId))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("Video ID cannot be null or empty!");
    }

    @Test
    public void shouldThrowIllegalArgumentExceptionWhenVideoIdIsNull() {
        // Given
        String nullId = null;

        // When & Then
        assertThatThrownBy(() -> linkCreator.createEmbeddedUrl(nullId))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("Video ID cannot be null or empty!");
    }
}
```

---

### Scenario 2: Domain Entity Logic (Sociable Unit Test)
We test the `YouTubeLink` domain entity. It represents a video record linked to a game. It uses functional mapping to delegate URL generation to the `YouTubeVideoLinkCreator` collaborator.

#### The Target Class: `YouTubeLink.java`
```java
package com.ftgo.video.entity;

import java.net.URL;
import java.util.function.Function;

public class YouTubeLink {

    private final String videoId;
    private Function<String, URL> linkCreator;

    public YouTubeLink(final String videoId) {
        if (videoId == null || videoId.trim().isEmpty()) {
            throw new IllegalArgumentException("Video ID cannot be null or empty!");
        }
        this.videoId = videoId;
    }

    public void setYouTubeVideoLinkCreator(final Function<String, URL> linkCreator) {
        this.linkCreator = linkCreator;
    }

    public URL getEmbedUrl() {
        if (this.linkCreator == null) {
            throw new IllegalStateException("YouTubeVideoLinkCreator mapper has not been configured!");
        }
        return this.linkCreator.apply(this.videoId);
    }

    public String getVideoId() {
        return this.videoId;
    }
}
```

#### The Unit Test: `YouTubeLinkTest.java`
```java
package com.ftgo.video.entity;

import com.ftgo.video.controller.YouTubeVideoLinkCreator;
import org.junit.jupiter.api.Test;
import java.net.URL;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

public class YouTubeLinkTest {

    @Test
    public void shouldCalculateEmbedYouTubeLinkUsingRealCollaborator() {
        // Given
        YouTubeLink youtubeLink = new YouTubeLink("abcd");
        YouTubeVideoLinkCreator creator = new YouTubeVideoLinkCreator();

        // When - Injecting the real collaborator method as a functional parameter (Sociable style)
        youtubeLink.setYouTubeVideoLinkCreator(creator::createEmbeddedUrl);
        URL result = youtubeLink.getEmbedUrl();

        // Then
        assertThat(result)
                .isNotNull()
                .hasHost("www.youtube.com")
                .hasPath("/embed/abcd");
    }

    @Test
    public void shouldThrowIllegalStateExceptionWhenCollaboratorIsNotConfigured() {
        // Given
        YouTubeLink youtubeLink = new YouTubeLink("abcd");

        // When & Then
        assertThatThrownBy(youtubeLink::getEmbedUrl)
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("YouTubeVideoLinkCreator mapper has not been configured!");
    }
}
```

---

### Scenario 3: Repository Entity Manager (Solitary Test with Mockito)
We write a test for the `GamesRepository` persistence helper. This repository uses JPA's `EntityManager` to save and look up `Game` records. In unit tests, we stub the `EntityManager` to isolate the repository operations from real SQL engines.

#### The Target Class: `GamesRepository.java`
```java
package com.ftgo.game.repository;

import com.ftgo.game.entity.Game;
import java.util.Optional;

public class GamesRepository {

    public javax.persistence.EntityManager em;

    public Game create(final Game request) {
        if (request == null) {
            throw new IllegalArgumentException("Cannot save a null Game entity!");
        }
        return em.merge(request);
    }

    public Optional<Game> findGameById(final Long gameId) {
        if (gameId == null) {
            return Optional.empty();
        }
        
        Game game = em.find(Game.class, gameId);
        if (game != null) {
            // Force JPA lazy loading resolution for nested collections before detaching
            game.getReleaseDates().size();
            game.getPublishers().size();
            game.getDevelopers().size();
            em.detach(game);
        }
        return Optional.ofNullable(game);
    }
}
```

#### The Helper Entity Class: `Game.java`
```java
package com.ftgo.game.entity;

import java.util.ArrayList;
import java.util.List;
import java.util.Objects;

public class Game {
    private Long id;
    private String title;
    private String cover;
    
    private List<String> releaseDates = new ArrayList<>();
    private List<String> publishers = new ArrayList<>();
    private List<String> developers = new ArrayList<>();

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public String getTitle() { return title; }
    public void setTitle(String title) { this.title = title; }

    public String getCover() { return cover; }
    public void setCover(String cover) { this.cover = cover; }

    public List<String> getReleaseDates() { return releaseDates; }
    public List<String> getPublishers() { return publishers; }
    public List<String> getDevelopers() { return developers; }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (o == null || getClass() != o.getClass()) return false;
        Game game = (Game) o;
        return Objects.equals(id, game.id) && Objects.equals(title, game.title);
    }

    @Override
    public int hashCode() {
        return Objects.hash(id, title);
    }
}
```

#### The Unit Test: `GamesRepositoryTest.java`
```java
package com.ftgo.game.repository;

import com.ftgo.game.entity.Game;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
public class GamesRepositoryTest {

    private static final long TEST_GAME_ID = 123L;

    @Mock
    private javax.persistence.EntityManager entityManager;

    private GamesRepository gamesRepository;

    @BeforeEach
    public void setUp() {
        this.gamesRepository = new GamesRepository();
        this.gamesRepository.em = entityManager;
    }

    @Test
    public void shouldCreateAGameAndPersistSuccessfully() {
        // Given
        Game game = new Game();
        game.setId(TEST_GAME_ID);
        game.setTitle("Zelda");
        
        when(entityManager.merge(game)).thenReturn(game);

        // When
        Game result = gamesRepository.create(game);

        // Then
        assertThat(result).isNotNull();
        assertThat(result.getTitle()).isEqualTo("Zelda");
        verify(entityManager, times(1)).merge(game);
    }

    @Test
    public void shouldFindGameByIdAndTriggerLazyCollections() {
        // Given
        Game game = new Game();
        game.setId(TEST_GAME_ID);
        game.setTitle("Zelda");
        game.getReleaseDates().add("2026-06-27");
        game.getPublishers().add("Nintendo");
        game.getDevelopers().add("Nintendo EPD");

        when(entityManager.find(Game.class, TEST_GAME_ID)).thenReturn(game);

        // When
        Optional<Game> foundGame = gamesRepository.findGameById(TEST_GAME_ID);

        // Then
        assertThat(foundGame).isPresent();
        assertThat(foundGame.get()).isEqualTo(game);
        
        // Verify JPA lifecycle invocations on dependencies
        verify(entityManager, times(1)).find(Game.class, TEST_GAME_ID);
        verify(entityManager, times(1)).detach(game);
    }

    @Test
    public void shouldReturnEmptyOptionalIfGameIsNotFoundInDatabase() {
        // Given
        when(entityManager.find(Game.class, TEST_GAME_ID)).thenReturn(null);

        // When
        Optional<Game> result = gamesRepository.findGameById(TEST_GAME_ID);

        // Then
        assertThat(result).isEmpty();
        verify(entityManager, times(1)).find(Game.class, TEST_GAME_ID);
        verify(entityManager, never()).detach(any());
    }
}
```

---

### Scenario 4: Service Layer Business Logic (Solitary Test with Mockito)
We test the `GamesService` coordination layer. This service orchestrates game searches: it checks the database cache first, and if missing, calls `IgdbGateway` to retrieve the payload from the external IGDB api, builds a new `Game` entity, and saves it in the database.

We mock both `GamesRepository` and `IgdbGateway`. We write tests to verify:
1. **Cache Hits**: If the database contains the record, the external API is never called.
2. **Cache Misses**: The external API is called, and the new game is stored in the database.
3. **Exceptions**: Verifying error propagation if the external service fails.

#### The Target Class: `GamesService.java`
```java
package com.ftgo.game.service;

import com.ftgo.game.entity.Game;
import com.ftgo.game.repository.GamesRepository;
import com.ftgo.game.gateway.IgdbGateway;
import javax.json.JsonArray;
import java.io.IOException;
import java.util.Optional;

public class GamesService {

    public GamesRepository gamesRepository;
    public IgdbGateway igdbGateway;

    /**
     * Resolves a game by ID, pulling from database cache or fetching externally if missing.
     * @param gameId unique identifier.
     * @return the Game record.
     * @throws IOException if network gateway failure occurs.
     */
    public Game searchGameById(final Long gameId) throws IOException {
        Optional<Game> cachedGame = gamesRepository.findGameById(gameId);
        
        if (cachedGame.isPresent()) {
            return cachedGame.get();
        } else {
            // Cache Miss: Query external database and persist result
            JsonArray jsonPayload = igdbGateway.searchGameById(gameId);
            if (jsonPayload == null || jsonPayload.isEmpty()) {
                throw new IllegalArgumentException("Game not found in external IGDB API!");
            }
            
            Game game = parseFromJson(jsonPayload);
            gamesRepository.create(game);
            return game;
        }
    }

    private Game parseFromJson(JsonArray jsonArray) {
        Game game = new Game();
        javax.json.JsonObject obj = jsonArray.getJsonObject(0);
        game.setId((long) obj.getInt("id"));
        game.setTitle(obj.getString("title"));
        game.setCover(obj.getString("cover"));
        
        // Map details
        javax.json.JsonArray developers = obj.getJsonArray("developers");
        for (int i = 0; i < developers.size(); i++) {
            game.getDevelopers().add(developers.getString(i));
        }
        
        javax.json.JsonArray publishers = obj.getJsonArray("publishers");
        for (int i = 0; i < publishers.size(); i++) {
            game.getPublishers().add(publishers.getString(i));
        }

        javax.json.JsonArray releases = obj.getJsonArray("releaseDates");
        for (int i = 0; i < releases.size(); i++) {
            game.getReleaseDates().add(releases.getString(i));
        }
        
        return game;
    }
}
```

#### The Gateway Collaborator Class: `IgdbGateway.java`
```java
package com.ftgo.game.gateway;

import javax.json.JsonArray;
import java.io.IOException;

public interface IgdbGateway {
    JsonArray searchGameById(Long gameId) throws IOException;
}
```

#### The Unit Test: `GamesServiceTest.java`
```java
package com.ftgo.game.service;

import com.ftgo.game.entity.Game;
import com.ftgo.game.repository.GamesRepository;
import com.ftgo.game.gateway.IgdbGateway;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import javax.json.Json;
import javax.json.JsonArray;
import java.io.IOException;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
public class GamesServiceTest {

    private static final long TEST_ID = 123L;

    @Mock
    private GamesRepository repository;

    @Mock
    private IgdbGateway gateway;

    private GamesService service;

    @BeforeEach
    public void setUp() {
        this.service = new GamesService();
        this.service.gamesRepository = repository;
        this.service.igdbGateway = gateway;
    }

    @Test
    public void shouldReturnGameIfItIsCachedInInternalDatabase() throws IOException {
        // Given
        Game cachedGame = new Game();
        cachedGame.setId(TEST_ID);
        cachedGame.setTitle("Zelda: Ocarina of Time");
        
        when(repository.findGameById(TEST_ID)).thenReturn(Optional.of(cachedGame));

        // When
        Game result = service.searchGameById(TEST_ID);

        // Then
        assertThat(result).isNotNull();
        assertThat(result.getTitle()).isEqualTo("Zelda: Ocarina of Time");
        
        // Verify cache hits execute no external calls
        verify(repository, times(1)).findGameById(TEST_ID);
        verifyNoInteractions(gateway);
        verify(repository, never()).create(any());
    }

    @Test
    public void shouldReturnGameFromIgdbAndSaveInDatabaseOnCacheMiss() throws IOException {
        // Given
        when(repository.findGameById(TEST_ID)).thenReturn(Optional.empty());
        
        JsonArray mockPayload = Json.createArrayBuilder()
                .add(Json.createObjectBuilder()
                        .add("id", 123)
                        .add("title", "Battlefield 4")
                        .add("cover", "BF4Cover")
                        .add("developers", Json.createArrayBuilder().add("DICE"))
                        .add("publishers", Json.createArrayBuilder().add("EA"))
                        .add("releaseDates", Json.createArrayBuilder().add("2013-10-29")))
                .build();
        
        when(gateway.searchGameById(TEST_ID)).thenReturn(mockPayload);

        // When
        Game result = service.searchGameById(TEST_ID);

        // Then
        assertThat(result).isNotNull();
        assertThat(result.getTitle()).isEqualTo("Battlefield 4");
        assertThat(result.getDevelopers()).containsExactly("DICE");
        assertThat(result.getPublishers()).containsExactly("EA");

        // Verify gateway execution and database caching
        verify(repository, times(1)).findGameById(TEST_ID);
        verify(gateway, times(1)).searchGameById(TEST_ID);
        verify(repository, times(1)).create(result);
    }

    @Test
    public void shouldPropagateExceptionWhenGatewayGatewayFails() throws IOException {
        // Given
        when(repository.findGameById(TEST_ID)).thenReturn(Optional.empty());
        when(gateway.searchGameById(TEST_ID)).thenThrow(new IOException("Connection reset by peer"));

        // When & Then
        assertThatThrownBy(() -> service.searchGameById(TEST_ID))
                .isInstanceOf(IOException.class)
                .hasMessageContaining("Connection reset by peer");
                
        verify(repository, times(1)).findGameById(TEST_ID);
        verify(gateway, times(1)).searchGameById(TEST_ID);
        verify(repository, never()).create(any());
    }
}
```

---

### Scenario 5: JAX-RS Endpoint Layer (Solitary Test with ArgumentCaptor & ExecutorService)
Finally, we test the controller resource layer: `GamesResource`. This JAX-RS class handles query operations asynchronously. It offloads processing to an `ExecutorService` and suspends the HTTP connection using JAX-RS `AsyncResponse` until completion.

Because JAX-RS `Response` is a complex third-party class with private implementation details, we cannot easily verify it using a default `equals` assertion. Instead, we use Mockito's **ArgumentCaptor** (`@Captor`) to capture the response passed to `AsyncResponse.resume()`, allowing us to assert on its properties (like HTTP status family and JSON payloads).

#### The Target Class: `GamesResource.java`
```java
package com.ftgo.game.boundary;

import com.ftgo.game.service.GamesService;
import com.ftgo.game.entity.Game;
import javax.inject.Inject;
import javax.json.Json;
import javax.json.JsonArrayBuilder;
import javax.ws.rs.*;
import javax.ws.rs.container.AsyncResponse;
import javax.ws.rs.container.Suspended;
import javax.ws.rs.core.MediaType;
import javax.ws.rs.core.Response;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.TimeUnit;

@Path("/games")
public class GamesResource {

    @Inject
    public GamesService gamesService;

    @Inject
    public ExecutorService managedExecutorService;

    @GET
    @Path("/{id}")
    @Produces(MediaType.APPLICATION_JSON)
    public void getGameDetails(
            @Suspended final AsyncResponse asyncResponse,
            @PathParam("id") final Long gameId) {

        // 1. Configure the Timeout handler constraints on suspended connections
        asyncResponse.setTimeoutHandler(ar -> ar.resume(
                Response.status(Response.Status.SERVICE_UNAVAILABLE)
                        .entity("REQUEST_TIMEOUT_EXPIRED")
                        .type(MediaType.TEXT_PLAIN)
                        .build()
        ));
        asyncResponse.setTimeout(5, TimeUnit.SECONDS);

        // 2. Offload computational execution to thread pools
        managedExecutorService.submit(() -> {
            try {
                Game game = gamesService.searchGameById(gameId);
                
                // Map properties to JSON payload
                JsonArrayBuilder builder = Json.createArrayBuilder()
                        .add(Json.createObjectBuilder()
                                .add("id", game.getId())
                                .add("title", game.getTitle())
                                .add("cover", game.getCover()));
                
                Response successResponse = Response.ok(builder.build(), MediaType.APPLICATION_JSON).build();
                
                // Resume connections to return response payload to clients
                asyncResponse.resume(successResponse);
                
            } catch (final Throwable e) {
                // Resume with exception to let standard JAX-RS Exception Mappers resolve it
                asyncResponse.resume(Response.status(Response.Status.INTERNAL_SERVER_ERROR)
                        .entity(e.getMessage())
                        .build());
            }
        });
    }
}
```

#### The Unit Test: `GamesResourceTest.java`
```java
package com.ftgo.game.boundary;

import com.ftgo.game.entity.Game;
import com.ftgo.game.service.GamesService;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Captor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import javax.json.JsonArray;
import javax.ws.rs.container.AsyncResponse;
import javax.ws.rs.core.Response;
import java.io.IOException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
public class GamesResourceTest {

    private static final long TEST_GAME_ID = 555L;
    
    // Create a real Single Thread Executor pool to process tasks asynchronously
    private static ExecutorService realExecutorService;

    @Mock
    private GamesService gamesService;

    @Mock
    private AsyncResponse asyncResponse;

    @Captor
    private ArgumentCaptor<Response> responseCaptor;

    private GamesResource gamesResource;

    @BeforeAll
    public static void beforeAll() {
        realExecutorService = Executors.newSingleThreadExecutor();
    }

    @AfterAll
    public static void afterAll() {
        realExecutorService.shutdown();
    }

    @BeforeEach
    public void setUp() {
        this.gamesResource = new GamesResource();
        this.gamesResource.gamesService = gamesService;
        this.gamesResource.managedExecutorService = realExecutorService;
    }

    @Test
    public void restApiShouldSearchGamesAndReturnSuccessfulResponse() throws Exception {
        // Given
        Game mockGame = new Game();
        mockGame.setId(TEST_GAME_ID);
        mockGame.setTitle("Zelda II: The Adventure of Link");
        mockGame.setCover("Zelda2Cover");

        when(gamesService.searchGameById(TEST_GAME_ID)).thenReturn(mockGame);

        // When
        gamesResource.getGameDetails(asyncResponse, TEST_GAME_ID);
        
        // Wait up to 2 seconds for executor thread to finish task processing
        realExecutorService.awaitTermination(2, TimeUnit.SECONDS);

        // Then: Verify asyncResponse.resume() was called and capture the argument
        verify(asyncResponse, times(1)).resume(responseCaptor.capture());

        Response capturedResponse = responseCaptor.getValue();
        assertThat(capturedResponse).isNotNull();
        assertThat(capturedResponse.getStatus()).isEqualTo(Response.Status.OK.getStatusCode());
        
        // Verify return payload details
        JsonArray jsonEntity = (JsonArray) capturedResponse.getEntity();
        assertThat(jsonEntity).hasSize(1);
        assertThat(jsonEntity.getJsonObject(0).getString("title"))
                .isEqualTo("Zelda II: The Adventure of Link");
        assertThat(jsonEntity.getJsonObject(0).getString("cover"))
                .isEqualTo("Zelda2Cover");
    }

    @Test
    public void restApiShouldResumeWithInternalServerErrorStatusIfServiceFails() throws Exception {
        // Given
        when(gamesService.searchGameById(TEST_GAME_ID)).thenThrow(new RuntimeException("Database down!"));

        // When
        gamesResource.getGameDetails(asyncResponse, TEST_GAME_ID);
        realExecutorService.awaitTermination(2, TimeUnit.SECONDS);

        // Then
        verify(asyncResponse, times(1)).resume(responseCaptor.capture());
        
        Response capturedResponse = responseCaptor.getValue();
        assertThat(capturedResponse).isNotNull();
        assertThat(capturedResponse.getStatus()).isEqualTo(Response.Status.INTERNAL_SERVER_ERROR.getStatusCode());
        assertThat(capturedResponse.getEntity().toString()).contains("Database down!");
    }
}
```

---

## Chapter Summary

* Unit testing verifies small, isolated code modules (typically classes) and forms the foundation of a microservices testing suite.
* **Sociable unit tests** instantiate and run real collaborator implementations. They test behavior interactions accurately, but make failures harder to debug when lower-level classes break.
* **Solitary unit tests** replace dependencies with **Test Doubles** to isolate the class under test. They run in milliseconds, but can hide issues if API contracts change.
* Test doubles are classified into five patterns:
  1. **Dummy**: A placeholder object passed to satisfy signatures.
  2. **Stub**: An object providing canned responses to queries.
  3. **Spy**: An object that records arguments, execution counts, and parameters.
  4. **Mock**: An object pre-programmed with expected invocation patterns.
  5. **Fake**: A lightweight, simplified implementation (e.g. database in-memory).
* A rich test suite uses JUnit 5 for orchestration, AssertJ for readable assertions, and Mockito for mock creation and verification.
* We configure Maven build scripts to compile testing scopes by adding the `mockito-junit-jupiter` and `assertj-core` scopes under test dependencies.
* Rich domain entities are tested using sociable unit tests to verify state logic transitions without mock overhead.
* Repository components use Mockito extensions to stub `EntityManager` calls to avoid execution slowdowns.
* Business service orchestrators mock external gateways and databases, verifying execution paths using Mockito's `verify()`, `times()`, and `never()` methods.
* Asynchronous controller resource endpoints suspend incoming requests using JAX-RS `@Suspended AsyncResponse` parameters and run on background `ExecutorServices`.
* Complex HTTP JAX-RS `Response` validation is managed using Mockito's `@Captor` and `ArgumentCaptor` to capture async callback payloads.
---

## 23.6 Production-Grade FTGO Order Reviews Code Listings

In this section, we present the complete, production-grade unit testing suite aligned to the **FTGO Order Reviews** system (Consumer: `order-service`, Provider: `review-service`). This application manages customer reviews, ratings, and food images associated with specific delivery orders.

```
+-------------------------------------------------------------+
|                     FTGO ORDER REVIEWS                      |
+-------------------------------------------------------------+
|                                                             |
|   [ JAX-RS Endpoint: OrderReviewsResource ] (Async Control) |
|                  |                                          |
|                  v                                          |
|   [ Coordinator: OrderReviewsService ] (Cache & REST Gateway)|
|                  |                                          |
|         +--------+--------+                                 |
|         v                 v                                 |
|   [ OrderReviewsRepository ] [ ReviewsGateway ]             |
|   (JPA persistence)          (External REST API)            |
|                                                             |
+-------------------------------------------------------------+
```

---

### Scenario 1: Helper Utilities (Sociable Unit Test)
The `ReviewImageLinkCreator` helper utility parses raw image identifiers and constructs secure CDN URLs. Because this class has no side effects, database interactions, or network calls, we test it using a **sociable approach** (creating concrete instances without mocks).

#### The Target Class: `ReviewImageLinkCreator.java`
```java
package com.ftgo.review.controller;

import java.net.MalformedURLException;
import java.net.URI;
import java.net.URL;

public class ReviewImageLinkCreator {

    private static final String EMBED_URL = "https://cdn.ftgo.com/reviews/images/";

    /**
     * Builds a standardized CDN link for a given image ID.
     * @param imageId the unique identifier for the image.
     * @return the formatted URL.
     * @throws IllegalArgumentException if the imageId is invalid or null.
     */
    public URL createEmbeddedUrl(final String imageId) {
        if (imageId == null || imageId.trim().isEmpty()) {
            throw new IllegalArgumentException("Image ID cannot be null or empty!");
        }
        
        try {
            return URI.create(EMBED_URL + imageId.trim()).toURL();
        } catch (final MalformedURLException e) {
            throw new IllegalArgumentException("Malformed URL resulted from image identifier: " + imageId, e);
        }
    }
}
```

#### The Unit Test: `ReviewImageLinkCreatorTest.java`
```java
package com.ftgo.review.controller;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import java.net.URL;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

public class ReviewImageLinkCreatorTest {

    private ReviewImageLinkCreator linkCreator;

    @BeforeEach
    public void setUp() {
        this.linkCreator = new ReviewImageLinkCreator();
    }

    @Test
    public void shouldReturnCdnUrlForGivenImageId() {
        // Given
        String targetImageId = "salad_review_1.png";

        // When
        URL resultUrl = linkCreator.createEmbeddedUrl(targetImageId);

        // Then
        assertThat(resultUrl)
                .isNotNull()
                .hasProtocol("https")
                .hasHost("cdn.ftgo.com")
                .hasPath("/reviews/images/salad_review_1.png");
    }

    @Test
    public void shouldThrowIllegalArgumentExceptionWhenImageIdIsEmpty() {
        // Given
        String emptyId = "";

        // When & Then
        assertThatThrownBy(() -> linkCreator.createEmbeddedUrl(emptyId))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("Image ID cannot be null or empty!");
    }

    @Test
    public void shouldThrowIllegalArgumentExceptionWhenImageIdIsNull() {
        // Given
        String nullId = null;

        // When & Then
        assertThatThrownBy(() -> linkCreator.createEmbeddedUrl(nullId))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("Image ID cannot be null or empty!");
    }
}
```

---

### Scenario 2: Domain Entity Logic (Sociable Unit Test)
We test the `OrderReview` domain entity, which represents an order review with a list of food images. It uses functional mapping to delegate URL generation to the `ReviewImageLinkCreator` collaborator.

#### The Target Class: `OrderReview.java`
```java
package com.ftgo.review.entity;

import java.net.URL;
import java.util.ArrayList;
import java.util.List;
import java.util.Objects;
import java.util.function.Function;

public class OrderReview {

    private Long id;
    private Long orderId;
    private String reviewerName;
    private String reviewText;
    private int rating;
    private List<String> foodImages = new ArrayList<>();
    private List<String> reviewTags = new ArrayList<>();
    
    private Function<String, URL> linkCreator;

    public OrderReview() {}

    public OrderReview(Long id, Long orderId, String reviewerName, String reviewText, int rating) {
        if (rating < 1 || rating > 5) {
            throw new IllegalArgumentException("Rating must be between 1 and 5!");
        }
        this.id = id;
        this.orderId = orderId;
        this.reviewerName = reviewerName;
        this.reviewText = reviewText;
        this.rating = rating;
    }

    public void setLinkCreator(Function<String, URL> linkCreator) {
        this.linkCreator = linkCreator;
    }

    public List<URL> getFoodImageUrls() {
        if (this.linkCreator == null) {
            throw new IllegalStateException("LinkCreator mapper has not been configured!");
        }
        List<URL> urls = new ArrayList<>();
        for (String imgId : foodImages) {
            urls.add(this.linkCreator.apply(imgId));
        }
        return urls;
    }

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public Long getOrderId() { return orderId; }
    public void setOrderId(Long orderId) { this.orderId = orderId; }

    public String getReviewerName() { return reviewerName; }
    public void setReviewerName(String reviewerName) { this.reviewerName = reviewerName; }

    public String getReviewText() { return reviewText; }
    public void setReviewText(String reviewText) { this.reviewText = reviewText; }

    public int getRating() { return rating; }
    public void setRating(int rating) { this.rating = rating; }

    public List<String> getFoodImages() { return foodImages; }
    public List<String> getReviewTags() { return reviewTags; }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (o == null || getClass() != o.getClass()) return false;
        OrderReview that = (OrderReview) o;
        return Objects.equals(id, that.id) && Objects.equals(orderId, that.orderId);
    }

    @Override
    public int hashCode() {
        return Objects.hash(id, orderId);
    }
}
```

#### The Unit Test: `OrderReviewTest.java`
```java
package com.ftgo.review.entity;

import com.ftgo.review.controller.ReviewImageLinkCreator;
import org.junit.jupiter.api.Test;
import java.net.URL;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

public class OrderReviewTest {

    @Test
    public void shouldCalculateImageCdnUrlsUsingRealCollaborator() {
        // Given
        OrderReview review = new OrderReview(1L, 999L, "Alice", "Great food!", 5);
        review.getFoodImages().add("burger.png");
        ReviewImageLinkCreator creator = new ReviewImageLinkCreator();

        // When - Injecting the real collaborator method as a functional parameter (Sociable style)
        review.setLinkCreator(creator::createEmbeddedUrl);
        java.util.List<URL> result = review.getFoodImageUrls();

        // Then
        assertThat(result).hasSize(1);
        assertThat(result.get(0))
                .isNotNull()
                .hasHost("cdn.ftgo.com")
                .hasPath("/reviews/images/burger.png");
    }

    @Test
    public void shouldThrowIllegalStateExceptionWhenCollaboratorIsNotConfigured() {
        // Given
        OrderReview review = new OrderReview(1L, 999L, "Alice", "Great food!", 5);
        review.getFoodImages().add("burger.png");

        // When & Then
        assertThatThrownBy(review::getFoodImageUrls)
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("LinkCreator mapper has not been configured!");
    }

    @Test
    public void shouldThrowIllegalArgumentExceptionForInvalidRating() {
        // When & Then
        assertThatThrownBy(() -> new OrderReview(1L, 999L, "Alice", "Great food!", 6))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("Rating must be between 1 and 5!");
    }
}
```

---

### Scenario 3: Repository Entity Manager (Solitary Test with Mockito)
We test the `OrderReviewsRepository` using Mockito to stub JPA's `EntityManager`.

#### The Target Class: `OrderReviewsRepository.java`
```java
package com.ftgo.review.repository;

import com.ftgo.review.entity.OrderReview;
import java.util.Optional;

public class OrderReviewsRepository {

    public javax.persistence.EntityManager em;

    public OrderReview create(final OrderReview review) {
        if (review == null) {
            throw new IllegalArgumentException("Cannot save a null OrderReview entity!");
        }
        return em.merge(review);
    }

    public Optional<OrderReview> findReviewById(final Long reviewId) {
        if (reviewId == null) {
            return Optional.empty();
        }
        
        OrderReview review = em.find(OrderReview.class, reviewId);
        if (review != null) {
            // Force JPA lazy loading resolution for nested collections before detaching
            review.getFoodImages().size();
            review.getReviewTags().size();
            em.detach(review);
        }
        return Optional.ofNullable(review);
    }
}
```

#### The Unit Test: `OrderReviewsRepositoryTest.java`
```java
package com.ftgo.review.repository;

import com.ftgo.review.entity.OrderReview;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
public class OrderReviewsRepositoryTest {

    private static final long TEST_REVIEW_ID = 123L;

    @Mock
    private javax.persistence.EntityManager entityManager;

    private OrderReviewsRepository reviewsRepository;

    @BeforeEach
    public void setUp() {
        this.reviewsRepository = new OrderReviewsRepository();
        this.reviewsRepository.em = entityManager;
    }

    @Test
    public void shouldCreateReviewAndPersistSuccessfully() {
        // Given
        OrderReview review = new OrderReview(TEST_REVIEW_ID, 999L, "Bob", "Delicious pizza!", 5);
        when(entityManager.merge(review)).thenReturn(review);

        // When
        OrderReview result = reviewsRepository.create(review);

        // Then
        assertThat(result).isNotNull();
        assertThat(result.getReviewText()).isEqualTo("Delicious pizza!");
        verify(entityManager, times(1)).merge(review);
    }

    @Test
    public void shouldFindReviewByIdAndTriggerLazyCollections() {
        // Given
        OrderReview review = new OrderReview(TEST_REVIEW_ID, 999L, "Bob", "Delicious pizza!", 5);
        review.getFoodImages().add("pizza.png");
        review.getReviewTags().add("Italian");

        when(entityManager.find(OrderReview.class, TEST_REVIEW_ID)).thenReturn(review);

        // When
        Optional<OrderReview> foundReview = reviewsRepository.findReviewById(TEST_REVIEW_ID);

        // Then
        assertThat(foundReview).isPresent();
        assertThat(foundReview.get()).isEqualTo(review);
        
        // Verify JPA lifecycle invocations on dependencies
        verify(entityManager, times(1)).find(OrderReview.class, TEST_REVIEW_ID);
        verify(entityManager, times(1)).detach(review);
    }

    @Test
    public void shouldReturnEmptyOptionalIfReviewIsNotFoundInDatabase() {
        // Given
        when(entityManager.find(OrderReview.class, TEST_REVIEW_ID)).thenReturn(null);

        // When
        Optional<OrderReview> result = reviewsRepository.findReviewById(TEST_REVIEW_ID);

        // Then
        assertThat(result).isEmpty();
        verify(entityManager, times(1)).find(OrderReview.class, TEST_REVIEW_ID);
        verify(entityManager, never()).detach(any());
    }
}
```

---

### Scenario 4: Service Layer Business Logic (Solitary Test with Mockito)
We test the `OrderReviewsService` coordination layer. This service checks cache records, calling `ReviewsGateway` on cache misses.

#### The Target Class: `OrderReviewsService.java`
```java
package com.ftgo.review.service;

import com.ftgo.review.entity.OrderReview;
import com.ftgo.review.repository.OrderReviewsRepository;
import com.ftgo.review.gateway.ReviewsGateway;
import javax.json.JsonArray;
import java.io.IOException;
import java.util.Optional;

public class OrderReviewsService {

    public OrderReviewsRepository reviewsRepository;
    public ReviewsGateway reviewsGateway;

    /**
     * Resolves a review by ID, pulling from database cache or fetching externally if missing.
     * @param reviewId unique identifier.
     * @return the OrderReview record.
     * @throws IOException if network gateway failure occurs.
     */
    public OrderReview searchReviewById(final Long reviewId) throws IOException {
        Optional<OrderReview> cachedReview = reviewsRepository.findReviewById(reviewId);
        
        if (cachedReview.isPresent()) {
            return cachedReview.get();
        } else {
            // Cache Miss: Query external database and persist result
            JsonArray jsonPayload = reviewsGateway.searchReviewById(reviewId);
            if (jsonPayload == null || jsonPayload.isEmpty()) {
                throw new IllegalArgumentException("Review not found in external API!");
            }
            
            OrderReview review = parseFromJson(jsonPayload);
            reviewsRepository.create(review);
            return review;
        }
    }

    private OrderReview parseFromJson(JsonArray jsonArray) {
        OrderReview review = new OrderReview();
        javax.json.JsonObject obj = jsonArray.getJsonObject(0);
        review.setId((long) obj.getInt("id"));
        review.setOrderId((long) obj.getInt("orderId"));
        review.setReviewerName(obj.getString("reviewerName"));
        review.setReviewText(obj.getString("reviewText"));
        review.setRating(obj.getInt("rating"));
        
        // Map details
        javax.json.JsonArray images = obj.getJsonArray("foodImages");
        for (int i = 0; i < images.size(); i++) {
            review.getFoodImages().add(images.getString(i));
        }
        
        javax.json.JsonArray tags = obj.getJsonArray("reviewTags");
        for (int i = 0; i < tags.size(); i++) {
            review.getReviewTags().add(tags.getString(i));
        }
        
        return review;
    }
}
```

#### The Gateway Collaborator: `ReviewsGateway.java`
```java
package com.ftgo.review.gateway;

import javax.json.JsonArray;
import java.io.IOException;

public interface ReviewsGateway {
    JsonArray searchReviewById(Long reviewId) throws IOException;
}
```

#### The Unit Test: `OrderReviewsServiceTest.java`
```java
package com.ftgo.review.service;

import com.ftgo.review.entity.OrderReview;
import com.ftgo.review.repository.OrderReviewsRepository;
import com.ftgo.review.gateway.ReviewsGateway;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import javax.json.Json;
import javax.json.JsonArray;
import java.io.IOException;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
public class OrderReviewsServiceTest {

    private static final long TEST_ID = 123L;

    @Mock
    private OrderReviewsRepository repository;

    @Mock
    private ReviewsGateway gateway;

    private OrderReviewsService service;

    @BeforeEach
    public void setUp() {
        this.service = new OrderReviewsService();
        this.service.reviewsRepository = repository;
        this.service.reviewsGateway = gateway;
    }

    @Test
    public void shouldReturnReviewIfItIsCachedInInternalDatabase() throws IOException {
        // Given
        OrderReview cachedReview = new OrderReview();
        cachedReview.setId(TEST_ID);
        cachedReview.setReviewText("Excellent pasta!");
        
        when(repository.findReviewById(TEST_ID)).thenReturn(Optional.of(cachedReview));

        // When
        OrderReview result = service.searchReviewById(TEST_ID);

        // Then
        assertThat(result).isNotNull();
        assertThat(result.getReviewText()).isEqualTo("Excellent pasta!");
        
        // Verify cache hits execute no external calls
        verify(repository, times(1)).findReviewById(TEST_ID);
        verifyNoInteractions(gateway);
        verify(repository, never()).create(any());
    }

    @Test
    public void shouldReturnReviewFromGatewayAndSaveInDatabaseOnCacheMiss() throws IOException {
        // Given
        when(repository.findReviewById(TEST_ID)).thenReturn(Optional.empty());
        
        JsonArray mockPayload = Json.createArrayBuilder()
                .add(Json.createObjectBuilder()
                        .add("id", 123)
                        .add("orderId", 999)
                        .add("reviewerName", "Alice")
                        .add("reviewText", "Delightful salad")
                        .add("rating", 5)
                        .add("foodImages", Json.createArrayBuilder().add("salad.jpg"))
                        .add("reviewTags", Json.createArrayBuilder().add("Healthy")))
                .build();
        
        when(gateway.searchReviewById(TEST_ID)).thenReturn(mockPayload);

        // When
        OrderReview result = service.searchReviewById(TEST_ID);

        // Then
        assertThat(result).isNotNull();
        assertThat(result.getReviewText()).isEqualTo("Delightful salad");
        assertThat(result.getFoodImages()).containsExactly("salad.jpg");
        assertThat(result.getReviewTags()).containsExactly("Healthy");

        // Verify gateway execution and database caching
        verify(repository, times(1)).findReviewById(TEST_ID);
        verify(gateway, times(1)).searchReviewById(TEST_ID);
        verify(repository, times(1)).create(result);
    }

    @Test
    public void shouldPropagateExceptionWhenGatewayGatewayFails() throws IOException {
        // Given
        when(repository.findReviewById(TEST_ID)).thenReturn(Optional.empty());
        when(gateway.searchReviewById(TEST_ID)).thenThrow(new IOException("Connection reset by peer"));

        // When & Then
        assertThatThrownBy(() -> service.searchReviewById(TEST_ID))
                .isInstanceOf(IOException.class)
                .hasMessageContaining("Connection reset by peer");
                
        verify(repository, times(1)).findReviewById(TEST_ID);
        verify(gateway, times(1)).searchReviewById(TEST_ID);
        verify(repository, never()).create(any());
    }
}
```

---

### Scenario 5: JAX-RS Endpoint Layer (Solitary Test with ArgumentCaptor & ExecutorService)
We test the JAX-RS asynchronous gateway controller `OrderReviewsResource` using `ArgumentCaptor`.

#### The Target Class: `OrderReviewsResource.java`
```java
package com.ftgo.review.boundary;

import com.ftgo.review.service.OrderReviewsService;
import com.ftgo.review.entity.OrderReview;
import javax.inject.Inject;
import javax.json.Json;
import javax.json.JsonArrayBuilder;
import javax.ws.rs.*;
import javax.ws.rs.container.AsyncResponse;
import javax.ws.rs.container.Suspended;
import javax.ws.rs.core.MediaType;
import javax.ws.rs.core.Response;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.TimeUnit;

@Path("/order-reviews")
public class OrderReviewsResource {

    @Inject
    public OrderReviewsService reviewsService;

    @Inject
    public ExecutorService managedExecutorService;

    @GET
    @Path("/{id}")
    @Produces(MediaType.APPLICATION_JSON)
    public void getReviewDetails(
            @Suspended final AsyncResponse asyncResponse,
            @PathParam("id") final Long reviewId) {

        // 1. Configure the Timeout handler constraints on suspended connections
        asyncResponse.setTimeoutHandler(ar -> ar.resume(
                Response.status(Response.Status.SERVICE_UNAVAILABLE)
                        .entity("REQUEST_TIMEOUT_EXPIRED")
                        .type(MediaType.TEXT_PLAIN)
                        .build()
        ));
        asyncResponse.setTimeout(5, TimeUnit.SECONDS);

        // 2. Offload computational execution to thread pools
        managedExecutorService.submit(() -> {
            try {
                OrderReview review = reviewsService.searchReviewById(reviewId);
                
                // Map properties to JSON payload
                JsonArrayBuilder builder = Json.createArrayBuilder()
                        .add(Json.createObjectBuilder()
                                .add("id", review.getId())
                                .add("orderId", review.getOrderId())
                                .add("reviewerName", review.getReviewerName())
                                .add("reviewText", review.getReviewText())
                                .add("rating", review.getRating()));
                
                Response successResponse = Response.ok(builder.build(), MediaType.APPLICATION_JSON).build();
                
                // Resume connections to return response payload to clients
                asyncResponse.resume(successResponse);
                
            } catch (final Throwable e) {
                // Resume with exception to let standard JAX-RS Exception Mappers resolve it
                asyncResponse.resume(Response.status(Response.Status.INTERNAL_SERVER_ERROR)
                        .entity(e.getMessage())
                        .build());
            }
        });
    }
}
```

#### The Unit Test: `OrderReviewsResourceTest.java`
```java
package com.ftgo.review.boundary;

import com.ftgo.review.entity.OrderReview;
import com.ftgo.review.service.OrderReviewsService;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Captor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import javax.json.JsonArray;
import javax.ws.rs.container.AsyncResponse;
import javax.ws.rs.core.Response;
import java.io.IOException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
public class OrderReviewsResourceTest {

    private static final long TEST_REVIEW_ID = 555L;
    
    private static ExecutorService realExecutorService;

    @Mock
    private OrderReviewsService reviewsService;

    @Mock
    private AsyncResponse asyncResponse;

    @Captor
    private ArgumentCaptor<Response> responseCaptor;

    private OrderReviewsResource reviewsResource;

    @BeforeAll
    public static void beforeAll() {
        realExecutorService = Executors.newSingleThreadExecutor();
    }

    @AfterAll
    public static void afterAll() {
        realExecutorService.shutdown();
    }

    @BeforeEach
    public void setUp() {
        this.reviewsResource = new OrderReviewsResource();
        this.reviewsResource.reviewsService = reviewsService;
        this.reviewsResource.managedExecutorService = realExecutorService;
    }

    @Test
    public void restApiShouldSearchReviewsAndReturnSuccessfulResponse() throws Exception {
        // Given
        OrderReview mockReview = new OrderReview();
        mockReview.setId(TEST_REVIEW_ID);
        mockReview.setOrderId(999L);
        mockReview.setReviewerName("John Doe");
        mockReview.setReviewText("Phenomenal pizza!");
        mockReview.setRating(5);

        when(reviewsService.searchReviewById(TEST_REVIEW_ID)).thenReturn(mockReview);

        // When
        reviewsResource.getReviewDetails(asyncResponse, TEST_REVIEW_ID);
        
        // Wait up to 2 seconds for executor thread to finish task processing
        realExecutorService.awaitTermination(2, TimeUnit.SECONDS);

        // Then: Verify asyncResponse.resume() was called and capture the argument
        verify(asyncResponse, times(1)).resume(responseCaptor.capture());

        Response capturedResponse = responseCaptor.getValue();
        assertThat(capturedResponse).isNotNull();
        assertThat(capturedResponse.getStatus()).isEqualTo(Response.Status.OK.getStatusCode());
        
        // Verify return payload details
        JsonArray jsonEntity = (JsonArray) capturedResponse.getEntity();
        assertThat(jsonEntity).hasSize(1);
        assertThat(jsonEntity.getJsonObject(0).getString("reviewText"))
                .isEqualTo("Phenomenal pizza!");
        assertThat(jsonEntity.getJsonObject(0).getString("reviewerName"))
                .isEqualTo("John Doe");
    }

    @Test
    public void restApiShouldResumeWithInternalServerErrorStatusIfServiceFails() throws Exception {
        // Given
        when(reviewsService.searchReviewById(TEST_REVIEW_ID)).thenThrow(new RuntimeException("Database down!"));

        // When
        reviewsResource.getReviewDetails(asyncResponse, TEST_REVIEW_ID);
        realExecutorService.awaitTermination(2, TimeUnit.SECONDS);

        // Then
        verify(asyncResponse, times(1)).resume(responseCaptor.capture());
        
        Response capturedResponse = responseCaptor.getValue();
        assertThat(capturedResponse).isNotNull();
        assertThat(capturedResponse.getStatus()).isEqualTo(Response.Status.INTERNAL_SERVER_ERROR.getStatusCode());
        assertThat(capturedResponse.getEntity().toString()).contains("Database down!");
    }
}
```
