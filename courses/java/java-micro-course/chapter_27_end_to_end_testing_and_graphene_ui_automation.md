# Chapter 27: End-to-End Testing & Graphene UI Automation

While unit, component, and integration tests validate the isolated layers of a microservice, they do not verify the complete user journey. End-to-End (E2E) testing validates the entire application stack from the user interface (UI) to the underlying databases and external network gateways. E2E tests ensure that all microservices coordinate successfully, database schemas align, network routes are open, and Javascript clients render pages correctly.

This chapter covers the design and implementation of **End-to-End Testing and Graphene UI Automation** in Java. We will compare **Vertical** (white-box element validation) and **Horizontal** (black-box journey transitions) E2E testing strategies. We will configure **Arquillian Drone** and **Graphene 2** to automate web browser lifecycles, and analyze the **Page Object Pattern** to write decoupled, maintainable test code. We will resolve Cross-Origin Resource Sharing (CORS) issues in multi-container setups, configure browser drivers, and write a complete E2E test suite that automates a web browser to post and verify user reviews on our Gamer Web Application.

---

## Learning Objectives

By the end of this chapter, you will be able to:
1. Explain the role of end-to-end (E2E) testing within a comprehensive testing pyramid.
2. Differentiate between vertical E2E tests and horizontal E2E tests.
3. Configure Arquillian Drone to manage Selenium WebDriver lifecycles automatically.
4. Implement Arquillian Graphene 2 to handle AJAX synchronization and wait guards.
5. Apply the Page Object Pattern to decouple UI element selectors from test assertions.
6. Design reusable UI widgets using Graphene Page Fragments.
7. Configure Maven dependencies and browser drivers (ChromeDriver) for headless test runs.
8. Resolve browser CORS (Cross-Origin Resource Sharing) restrictions in multi-deployment environments.
9. Write E2E test suites that deploy multiple microservices and automate browser-based user interactions.

---

## 27.1 End-to-End Testing Techniques: Vertical vs. Horizontal

End-to-end tests simulate real user actions against the application. We classify E2E tests into two main patterns based on their testing scope:

### 27.1.1 Vertical Tests
A vertical test is a white-box testing technique that targets a single view or page. It verifies that all UI elements are rendered correctly based on user roles, permissions, or system states. It checks the "vertical" stack of that specific view: from the HTML elements down to the database constraints:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//7db1f0c5-ddf5-4f56-881d-732fe1b00974/markdown_1/imgs/img_in_image_box_498_478_933_623.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A21%3A52Z%2F-1%2F%2F7c700466162f1f7b890ebed77aeee62b28a7829a6b2ad07f203e24473b145074" alt="Image" width="40%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 7.1 A simple white-box vertical test</div> </div>

As shown in Figure 7.1, vertical testing validates that all sub-components of a page render correctly in isolation.

---

### 27.1.2 Horizontal Tests
A horizontal test is a journey-based testing technique. It checks the flow of the application from left to right, verifying the transitions from one view to the next as the user completes a task (e.g. logging in, searching for a game, submitting a comment, and verifying it appears in the list):

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//7db1f0c5-ddf5-4f56-881d-732fe1b00974/markdown_1/imgs/img_in_image_box_182_980_644_1132.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A21%3A52Z%2F-1%2F%2F6f86e75f71e5d7a1937edca4bbd477f0a6bdca6088f994c965b631298bb8236f" alt="Image" width="43%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 7.2 A black- and white-box horizontal test</div> </div>

As shown in Figure 7.2, horizontal testing follows the user path across multiple distinct views to verify that transitions succeed.

---

## 26.2 E2E UI Automation: Drone and Graphene

Automating UI tests requires driving a real browser engine (like Chrome or Firefox). In Java, the standard tool is **Selenium WebDriver**. However, raw Selenium code has major drawbacks:
1. **Lifecycle Boilerplate**: You must manually locate browser binaries, start the driver process, configure capabilities, and shut down the browser at the end of the test.
2. **Brittle AJAX Waits**: Modern UIs load data asynchronously using AJAX. If a test attempts to click an element before the Javascript page load completes, Selenium throws a `NoSuchElementException`. Developers resort to thread sleeps (`Thread.sleep(3000)`), which slows down the test suite and causes flakiness.

The Arquillian ecosystem solves these issues using two extensions: **Drone** and **Graphene 2**.

### 26.2.1 Arquillian Drone
Drone manages the lifecycle of the browser driver. It automatically reads configuration, downloads browser binaries, boots the driver before the test, injects it into the test class using the `@Drone` annotation, and stops the process when tests complete:

```java
@Drone
private WebDriver browser; // Injected automatically by Drone
```

---

### 26.2.2 Arquillian Graphene 2
Graphene wraps Selenium to simplify AJAX synchronization and UI element lookup. It introduces **Request Guards** that block test execution until AJAX or HTTP calls complete:

* **`guardHttp(element).click()`**: Blocks execution until the HTTP request triggered by the click completes and the page reloads.
* **`guardAjax(element).click()`**: Blocks execution until the AJAX call triggered by the click completes and the DOM is updated.

This eliminates sleep hacks, making tests fast and robust:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//0e316b7d-4af2-44af-82f8-ccae259b3231/markdown_3/imgs/img_in_image_box_114_337_929_714.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A22%3A12Z%2F-1%2F%2F439cad987325b901d207981ce2b3a326e636dcf51ad32c6c3096eb8d44479343" alt="Image" width="76%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 7.3 UI automation execution lifecycle</div> </div>

As mapped in Figure 7.3:
1. Graphene loads the browser session.
2. The user initiates a click event guarded by Graphene.
3. The browser sends the request.
4. Graphene intercepts and monitors the response state.
5. Once DOM updates stabilize, Graphene returns control to the test runner.

---

## 27.3 Maven Configuration (`pom.xml`)

To use Graphene and Drone, include the following dependencies and configurations in your Maven POM:

```xml
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    <groupId>com.ftgo</groupId>
    <artifactId>gamer-e2e-testing</artifactId>
    <version>1.0.0</version>

    <properties>
        <maven.compiler.source>11</maven.compiler.source>
        <maven.compiler.target>11</maven.compiler.target>
        <version.arquillian_bom>1.7.0.Alpha10</version.arquillian_bom>
        <version.arquillian_drone>2.5.5</version.arquillian_drone>
        <version.arquillian_graphene>2.5.0</version.arquillian_graphene>
    </properties>

    <dependencyManagement>
        <dependencies>
            <dependency>
                <groupId>org.jboss.arquillian</groupId>
                <artifactId>arquillian-bom</artifactId>
                <version>${version.arquillian_bom}</version>
                <type>pom</type>
                <scope>import</scope>
            </dependency>
            <dependency>
                <groupId>org.jboss.arquillian.extension</groupId>
                <artifactId>arquillian-drone-bom</artifactId>
                <version>${version.arquillian_drone}</version>
                <type>pom</type>
                <scope>import</scope>
            </dependency>
        </dependencies>
    </dependencyManagement>

    <dependencies>
        <!-- JUnit 5 Extension -->
        <dependency>
            <groupId>org.junit.jupiter</groupId>
            <artifactId>junit-jupiter-api</artifactId>
            <version>5.9.2</version>
            <scope>test</scope>
        </dependency>
        <dependency>
            <groupId>org.junit.jupiter</groupId>
            <artifactId>junit-jupiter-engine</artifactId>
            <version>5.9.2</version>
            <scope>test</scope>
        </dependency>
        <dependency>
            <groupId>org.jboss.arquillian.junit5</groupId>
            <artifactId>arquillian-junit5-container</artifactId>
            <scope>test</scope>
        </dependency>

        <!-- Drone Extension WebDriver -->
        <dependency>
            <groupId>org.jboss.arquillian.extension</groupId>
            <artifactId>arquillian-drone-webdriver-depchain</artifactId>
            <type>pom</type>
            <scope>test</scope>
        </dependency>

        <!-- Graphene Extension -->
        <dependency>
            <groupId>org.jboss.arquillian.graphene</groupId>
            <artifactId>graphene-webdriver</artifactId>
            <version>${version.arquillian_graphene}</version>
            <type>pom</type>
            <scope>test</scope>
        </dependency>

        <!-- ChromeDriver manager dependency to resolve chrome binaries -->
        <dependency>
            <groupId>io.github.bonigarcia</groupId>
            <artifactId>webdrivermanager</artifactId>
            <version>5.3.2</version>
            <scope>test</scope>
        </dependency>
    </dependencies>
</project>
```

---

## 27.4 The Page Object Pattern and Page Fragments

Writing E2E tests where selectors (like `id="submit-btn"`) are hardcoded directly in the test methods creates fragile tests. If the UI designer modifies the HTML structure (e.g. changing an ID to a class name), all tests referencing that element will fail.

The **Page Object Pattern** resolves this by modeling the UI as a Java class. The test methods interact only with the Page Object's Java methods (like `submitComment()`), shielding the test assertions from HTML structure changes.

```
[ GamerAppEndToEndTest ]
          | (calls Java methods)
          v
[ Page Object: GamerDashboardPage ]
    - Locates elements (@FindBy)
    - Exposes user actions (submitComment)
          | (contains widgets)
          v
[ Page Fragment: CommentsSectionFragment ]
    - Models the comments list table
```

### 27.4.1 Page Fragments
If a UI widget (like a comments list table or a navigation menu) is reused across multiple views, we represent it as a **Page Fragment** in Graphene. This allows us to reuse the widget configuration across multiple Page Objects.

#### The Page Fragment: `CommentsSectionFragment.java`
This class wraps the comments table UI element:

```java
package com.ftgo.game.ui.fragment;

import org.openqa.selenium.WebElement;
import org.openqa.selenium.support.FindBy;
import java.util.List;
import java.util.stream.Collectors;

public class CommentsSectionFragment {

    @FindBy(tagName = "table")
    private WebElement commentsTable;

    @FindBy(css = "tr.comment-row")
    private List<WebElement> commentRows;

    /**
     * Reads all authors from the rendered comments list.
     * @return List of author names.
     */
    public List<String> getCommentAuthors() {
        return commentRows.stream()
                .map(row -> row.getAttribute("data-author"))
                .collect(Collectors.toList());
    }

    /**
     * Reads all text values from the comments list.
     * @return List of comment messages.
     */
    public List<String> getCommentTexts() {
        return commentRows.stream()
                .map(row -> row.getAttribute("data-text"))
                .collect(Collectors.toList());
    }
}
```

---

### 27.4.2 The Page Object: `GamerDashboardPage.java`
This class models the dashboard view, mapping elements and injecting the `CommentsSectionFragment`:

```java
package com.ftgo.game.ui.page;

import com.ftgo.game.ui.fragment.CommentsSectionFragment;
import org.jboss.arquillian.graphene.Graphene;
import org.jboss.arquillian.graphene.page.Location;
import org.openqa.selenium.WebElement;
import org.openqa.selenium.support.FindBy;

import static org.jboss.arquillian.graphene.Graphene.guardAjax;

@Location("index.html") // Defines target page URL routing path
public class GamerDashboardPage {

    @FindBy(id = "comment-author")
    private WebElement authorInput;

    @FindBy(id = "comment-text")
    private WebElement commentInput;

    @FindBy(id = "submit-comment-btn")
    private WebElement submitButton;

    // Inject the Comments list widget as a nested page fragment
    @FindBy(id = "comments-list-section")
    private CommentsSectionFragment commentsSection;

    /**
     * Submits a comment. Uses Graphene's AJAX guard to block until the request completes.
     * @param author Author name
     * @param text Comment text
     */
    public void submitComment(String author, String text) {
        authorInput.clear();
        authorInput.sendKeys(author);
        
        commentInput.clear();
        commentInput.sendKeys(text);

        // Guard the submit button click using guardAjax
        guardAjax(submitButton).click();
    }

    public CommentsSectionFragment getCommentsSection() {
        return this.commentsSection;
    }
}
```

---

## 27.5 Enabling CORS in Java Backend Containers

In a split microservices architecture, the static frontend application (e.g. HTML, Javascript) is hosted on a separate port or container than the backend REST API gateway. During E2E test runs, the browser's default security model blocks the frontend Javascript from calling the backend REST endpoints, throwing a CORS error:

```
[ Web Browser (localhost:8080) ] ===(invokes AJAX)===> [ Backend REST API (localhost:8181) ]
                                                               |
                                                 (Blocked: CORS validation failed)
```

To resolve this, we write a JAX-RS / Jakarta REST filter on the backend microservice to append the required Cross-Origin Resource Sharing headers to every response:

#### The CORS Filter: `CorsResponseFilter.java`
```java
package com.ftgo.comment.filter;

import javax.ws.rs.container.ContainerRequestContext;
import javax.ws.rs.container.ContainerResponseContext;
import javax.ws.rs.container.ContainerResponseFilter;
import javax.ws.rs.ext.Provider;
import java.io.IOException;

@Provider // Register this filter with the JAX-RS runtime
public class CorsResponseFilter implements ContainerResponseFilter {

    @Override
    public void filter(ContainerRequestContext requestContext, ContainerResponseContext responseContext) throws IOException {
        // Append CORS headers to allow browser scripts to access endpoints
        responseContext.getHeaders().add("Access-Control-Allow-Origin", "*");
        responseContext.getHeaders().add("Access-Control-Allow-Headers", "origin, content-type, accept, authorization");
        responseContext.getHeaders().add("Access-Control-Allow-Credentials", "true");
        responseContext.getHeaders().add("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS, HEAD");
    }
}
```

---

## 27.6 Complete End-to-End E2E Test Implementation

This section provides the complete code listings for our E2E test case. We configure a **multi-deployment** setup:
1. **`gamerwebapp.war`**: Contains the frontend HTML and Javascript code.
2. **`commentsservice.war`**: Contains the JAX-RS backend database REST API.

We configure the container adapters in `arquillian.xml` using container groups to deploy both web archives concurrently:

#### The E2E Test Suite: `GamerAppEndToEndTest.java`
```java
package com.ftgo.game.ui;

import com.ftgo.comment.entity.Comment;
import com.ftgo.comment.filter.CorsResponseFilter;
import com.ftgo.comment.repository.CommentsRepository;
import com.ftgo.comment.boundary.CommentsResource;
import com.ftgo.game.ui.page.GamerDashboardPage;
import io.github.bonigarcia.wdm.WebDriverManager;
import org.jboss.arquillian.container.test.api.Deployment;
import org.jboss.arquillian.container.test.api.TargetsContainer;
import org.jboss.arquillian.drone.api.annotation.Drone;
import org.jboss.arquillian.graphene.page.InitialPage;
import org.jboss.arquillian.junit5.ArquillianExtension;
import org.jboss.shrinkwrap.api.ShrinkWrap;
import org.jboss.shrinkwrap.api.spec.WebArchive;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.openqa.selenium.WebDriver;

import static org.assertj.core.api.Assertions.assertThat;

@ExtendWith(ArquillianExtension.class)
public class GamerAppEndToEndTest {

    // 1. Resolve browser driver binaries before executing tests
    @BeforeAll
    public static void setupWebDriver() {
        WebDriverManager.chromedriver().setup();
    }

    // 2. Build and target the static frontend web deployment
    @Deployment(name = "frontend-deployment")
    @TargetsContainer("tomcat-frontend")
    public static WebArchive createFrontendDeployment() {
        return ShrinkWrap.create(WebArchive.class, "gamerwebapp.war")
                // Add static html/js resources to the root of the archive
                .addAsWebResource(new java.io.File("src/main/webapp/index.html"), "index.html")
                .addAsWebResource(new java.io.File("src/main/webapp/app.js"), "app.js");
    }

    // 3. Build and target the REST comments backend deployment
    @Deployment(name = "backend-deployment")
    @TargetsContainer("tomcat-backend")
    public static WebArchive createBackendDeployment() {
        return ShrinkWrap.create(WebArchive.class, "commentsservice.war")
                .addClasses(Comment.class, CommentsRepository.class, CommentsResource.class, CorsResponseFilter.class)
                .addAsResource("META-INF/persistence.xml", "META-INF/persistence.xml");
    }

    // 4. Inject the Drone WebBrowser instance
    @Drone
    private WebDriver browser;

    @Test
    public void shouldPostCommentAndDisplayInUiList(@InitialPage GamerDashboardPage dashboardPage) {
        // Given: The dashboardPage is initialized and loaded by Graphene automatically
        
        // When: We fill out the comments form and click the submit button
        dashboardPage.submitComment("Alice Cooper", "End-to-end testing with Graphene works!");

        // Then: Read the comments section widget page fragment and verify the comment was updated in the DOM
        assertThat(dashboardPage.getCommentsSection().getCommentAuthors())
                .contains("Alice Cooper");

        assertThat(dashboardPage.getCommentsSection().getCommentTexts())
                .contains("End-to-end testing with Graphene works!");
    }
}
```

---

## 27.7 Overriding E2E Configurations in `arquillian.xml`

To configure Drone to boot Google Chrome in **headless** mode (which is required to execute tests in server environments without graphical monitors), configure the `arquillian.xml` file as follows:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<arquillian xmlns="http://jboss.org/schema/arquillian"
            xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
            xsi:schemaLocation="http://jboss.org/schema/arquillian 
            http://jboss.org/schema/arquillian/arquillian_3_0.xsd">

    <!-- Define the container group containing both frontend and backend Tomcats -->
    <group qualifier="tomee-cluster">
        <container qualifier="tomcat-frontend">
            <configuration>
                <property name="bindHttpPort">8080</property>
            </configuration>
        </container>
        <container qualifier="tomcat-backend">
            <configuration>
                <property name="bindHttpPort">8181</property>
            </configuration>
        </container>
    </group>

    <!-- Configure the Drone WebBrowser driver -->
    <extension qualifier="webdriver">
        <property name="browser">chrome</property>
        <!-- Pass headless command line arguments to the Chrome binary -->
        <property name="chromeArguments">--headless --disable-gpu --window-size=1200,800</property>
    </extension>
</arquillian>
```

---

## 27.8 Summary of E2E Testing Controls

This table summarizes the configurations, annotations, and classes used to establish end-to-end UI tests:

| Testing Vector | E2E Resource / Config | Main Implementation Target | Scope Location |
| :--- | :--- | :--- | :--- |
| **Browser Injection** | `@Drone WebDriver` | Drone manages the startup, initialization, and shutdown of the browser. | Test Fields |
| **Browser Configurations** | `arquillian.xml` extension | Configures head/headless mode, window size, and timeouts. | Test Resources |
| **Page URL Routing** | `@Location("index.html")` | Directs the browser session to a specific page. | Page Object |
| **Element Mapping** | `@FindBy(css = "...")` | Locates HTML elements inside the browser DOM. | Page Object / Fragment |
| **AJAX request guard** | `guardAjax(button).click()` | Blocks execution until AJAX calls complete. | Page Object |
| **HTTP request guard** | `guardHttp(button).click()` | Blocks execution until HTTP reloads complete. | Page Object |
| **Multi-Deployment target**| `@TargetsContainer` | Directs archives to be deployed to specific Tomcat containers. | Static Method |
| **Pre-run Driver Manager** | `WebDriverManager.setup()` | Downloads correct chromedriver binaries before execution. | Setup Method |
| **Browser CORS filter** | `CorsResponseFilter` | Appends response headers to prevent browser blocks. | Backend App |

---

## Chapter Summary

* End-to-End (E2E) testing validates the entire system stack (from the UI down to the databases and external integrations) to ensure all components align.
* **Vertical E2E tests** check element configurations on a single page, while **Horizontal E2E tests** verify multi-page user journeys.
* **Arquillian Drone** manages the WebDriver lifecycle, injecting browser instances into tests using the `@Drone` annotation.
* **Graphene 2** wraps Selenium WebDriver to handle AJAX and HTTP synchronization using wait guards (like `guardAjax`).
* The **Page Object Pattern** decouples HTML structure from test methods. Test code interacts only with Java helper methods.
* **Page Fragments** represent reusable UI widgets (like a comments table) across multiple page objects.
* We configure a **CORS response filter** on the backend microservice to allow the separate frontend microservice to make HTTP calls during testing.
* Headless browser execution (required for CI pipelines) is configured in `arquillian.xml` by passing arguments (like `--headless`) to Chrome.
* Multi-deployment setups are configured in `arquillian.xml` using container groups, allowing the frontend and backend archives to run concurrently.
---

## 27.8 Production-Grade FTGO Order Reviews End-to-End Test Suite

In this section, we present the complete, production-grade end-to-end (E2E) testing and UI automation suite for the **FTGO Order Reviews** system. We build Page Objects and Page Fragments to represent the dashboard page and reviews table widget, configure CORS filter rules, and execute a multi-deployment test using **Arquillian Drone** and **Graphene 2** driving a headless web browser.

```
[ GamerAppEndToEndTest ]
          | (calls Java methods)
          v
[ Page Object: OrderReviewsDashboardPage ]
    - Locates elements (@FindBy)
    - Exposes user actions (submitReview)
          | (contains widgets)
          v
[ Page Fragment: ReviewsSectionFragment ]
    - Models the reviews list rows
```

---

### Scenario: Browser-Based Order Review Submission Journey
We automate a user journey where a customer logs into the FTGO dashboard, queries reviews for their recent order, writes a new review with a rating, and submits it. We verify that the review appears in the list table dynamically.

#### 1. The Page Fragment: `ReviewsSectionFragment.java`
This fragment encapsulates the reviews list section widget, making it reusable across different page objects.

```java
package com.ftgo.review.ui.fragment;

import org.openqa.selenium.WebElement;
import org.openqa.selenium.support.FindBy;
import java.util.List;
import java.util.stream.Collectors;

public class ReviewsSectionFragment {

    @FindBy(tagName = "table")
    private WebElement reviewsTable;

    @FindBy(css = "tr.review-row")
    private List<WebElement> reviewRows;

    /**
     * Reads all reviewer names from the rendered reviews list.
     * @return List of reviewer names.
     */
    public List<String> getReviewerNames() {
        return reviewRows.stream()
                .map(row -> row.getAttribute("data-reviewer"))
                .collect(Collectors.toList());
    }

    /**
     * Reads all text values from the reviews list.
     * @return List of review messages.
     */
    public List<String> getReviewTexts() {
        return reviewRows.stream()
                .map(row -> row.getAttribute("data-text"))
                .collect(Collectors.toList());
    }
}
```

---

#### 2. The Dashboard Page Object: `OrderReviewsDashboardPage.java`
This class models the dashboard view where users input reviews. It uses Graphene guards to handle AJAX synchronization.

```java
package com.ftgo.review.ui.page;

import com.ftgo.review.ui.fragment.ReviewsSectionFragment;
import org.jboss.arquillian.graphene.page.Location;
import org.openqa.selenium.WebElement;
import org.openqa.selenium.support.FindBy;

import static org.jboss.arquillian.graphene.Graphene.guardAjax;

@Location("index.html")
public class OrderReviewsDashboardPage {

    @FindBy(id = "reviewer-name")
    private WebElement reviewerInput;

    @FindBy(id = "review-text")
    private WebElement reviewTextFormatter;

    @FindBy(id = "review-rating")
    private WebElement ratingSelector;

    @FindBy(id = "submit-review-btn")
    private WebElement submitButton;

    // Inject our custom reviews table widget as a nested page fragment
    @FindBy(id = "reviews-list-section")
    private ReviewsSectionFragment reviewsSection;

    /**
     * Fills out the review form and clicks the submit button, guarding the AJAX response.
     * @param reviewer reviewer name.
     * @param text review message text.
     * @param rating review score rating.
     */
    public void submitReview(String reviewer, String text, int rating) {
        reviewerInput.clear();
        reviewerInput.sendKeys(reviewer);
        
        reviewTextFormatter.clear();
        reviewTextFormatter.sendKeys(text);

        ratingSelector.clear();
        ratingSelector.sendKeys(String.valueOf(rating));

        // Use Graphene's AJAX guard to block until the table updates
        guardAjax(submitButton).click();
    }

    public ReviewsSectionFragment getReviewsSection() {
        return this.reviewsSection;
    }
}
```

---

#### 3. The Login Page Object: `OrderReviewsLoginPage.java`
This page object represents the security gate, using HTTP guards to wait for browser page reloads.

```java
package com.ftgo.review.ui.page;

import org.jboss.arquillian.graphene.page.Location;
import org.openqa.selenium.WebElement;
import org.openqa.selenium.support.FindBy;

import static org.jboss.arquillian.graphene.Graphene.guardHttp;

@Location("login.html")
public class OrderReviewsLoginPage {

    @FindBy(id = "username")
    private WebElement usernameField;

    @FindBy(id = "password")
    private WebElement passwordField;

    @FindBy(id = "login-btn")
    private WebElement loginButton;

    /**
     * Executes the login form submit, blocking execution until the HTTP redirection completes.
     * @param user username.
     * @param pass password.
     */
    public void executeLogin(String user, String pass) {
        usernameField.clear();
        usernameField.sendKeys(user);
        
        passwordField.clear();
        passwordField.sendKeys(pass);

        // Guard the HTTP redirect request click
        guardHttp(loginButton).click();
    }
}
```

---

#### 4. The Multi-Deployment E2E Runner: `OrderReviewsAppEndToEndTest.java`
We configure a containerized test deploying both the frontend static assets and the JAX-RS backend microservice concurrently, using Drone to drive the automated Chrome browser.

```java
package com.ftgo.review.ui;

import com.ftgo.review.ui.page.OrderReviewsDashboardPage;
import com.ftgo.review.ui.page.OrderReviewsLoginPage;
import org.jboss.arquillian.container.test.api.Deployment;
import org.jboss.arquillian.container.test.api.TargetsContainer;
import org.jboss.arquillian.drone.api.annotation.Drone;
import org.jboss.arquillian.graphene.page.Page;
import org.jboss.arquillian.junit5.ArquillianExtension;
import org.jboss.shrinkwrap.api.ShrinkWrap;
import org.jboss.shrinkwrap.api.spec.WebArchive;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.openqa.selenium.WebDriver;

import java.net.URL;

import static org.assertj.core.api.Assertions.assertThat;

@ExtendWith(ArquillianExtension.class)
public class OrderReviewsAppEndToEndTest {

    // 1. Deploy the frontend WAR containing HTML assets to Tomcat Port 8080
    @Deployment(name = "frontend", testable = false)
    @TargetsContainer("tomcat-frontend")
    public static WebArchive createFrontendDeployment() {
        return ShrinkWrap.create(WebArchive.class, "reviews-frontend.war")
                .addAsWebResource(new java.io.File("src/main/webapp/index.html"), "index.html")
                .addAsWebResource(new java.io.File("src/main/webapp/login.html"), "login.html")
                .addAsWebResource(new java.io.File("src/main/webapp/app.js"), "app.js");
    }

    // 2. Deploy the JAX-RS backend REST API WAR to Tomcat Port 8181
    @Deployment(name = "backend", testable = false)
    @TargetsContainer("tomcat-backend")
    public static WebArchive createBackendDeployment() {
        return ShrinkWrap.create(WebArchive.class, "reviews-backend.war")
                .addPackage("com.ftgo.review.boundary")
                .addPackage("com.ftgo.review.service")
                .addPackage("com.ftgo.review.entity")
                .addPackage("com.ftgo.review.repository")
                .addAsResource("META-INF/persistence.xml", "META-INF/persistence.xml");
    }

    // 3. Inject Drone managed WebDriver
    @Drone
    private WebDriver browser;

    // 4. Inject Graphene Page Objects
    @Page
    private OrderReviewsLoginPage loginPage;

    @Page
    private OrderReviewsDashboardPage dashboardPage;

    @Test
    public void shouldExecuteLoginAndCreateNewReviewSuccessfully() {
        // Step 1: Browse to login page
        browser.get("http://localhost:8080/reviews-frontend/login.html");

        // Step 2: Log in (forces HTTP redirect)
        loginPage.executeLogin("ftgo_customer", "secure_password");

        // Step 3: Write a review (forces AJAX reload)
        dashboardPage.submitReview("Alice", "Amazing pizza, hot and tasty!", 5);

        // Step 4: Verify the review appeared in the fragment list table
        assertThat(dashboardPage.getReviewsSection().getReviewerNames()).contains("Alice");
        assertThat(dashboardPage.getReviewsSection().getReviewTexts()).contains("Amazing pizza, hot and tasty!");
    }
}
```

---

#### 5. Static Frontend Assets for E2E DOM Targets
To ensure selectors align with elements, we outline the HTML views and Javascript controllers.

##### The Index Page: `src/main/webapp/index.html`
```html
<!DOCTYPE html>
<html>
<head>
    <title>FTGO Order Reviews Dashboard</title>
</head>
<body>
    <h1>Order Reviews</h1>
    <div id="reviews-list-section">
        <table>
            <thead>
                <tr>
                    <th>Reviewer</th>
                    <th>Message</th>
                    <th>Rating</th>
                </tr>
            </thead>
            <tbody id="reviews-table-body">
                <!-- Seeded reviews inserted here dynamically -->
            </tbody>
        </table>
    </div>

    <h2>Write a Review</h2>
    <form id="review-form">
        <input type="text" id="reviewer-name" placeholder="Your Name" required /><br/>
        <textarea id="review-text" placeholder="Your Review" required></textarea><br/>
        <input type="number" id="review-rating" min="1" max="5" required /><br/>
        <button type="button" id="submit-review-btn">Submit Review</button>
    </form>

    <script src="app.js"></script>
</body>
</html>
```

##### The Javascript Controller: `src/main/webapp/app.js`
```javascript
document.addEventListener("DOMContentLoaded", function() {
    const backendUrl = "http://localhost:8181/reviews-backend/reviewsservice/reviews";

    // Load initial reviews
    fetch(backendUrl + "?orderId=999")
        .then(response => response.json())
        .then(reviews => {
            const tableBody = document.getElementById("reviews-table-body");
            reviews.forEach(review => {
                const row = document.createElement("tr");
                row.className = "review-row";
                row.setAttribute("data-reviewer", review.reviewerName);
                row.setAttribute("data-text", review.reviewText);
                row.innerHTML = `<td>${review.reviewerName}</td><td>${review.reviewText}</td><td>${review.rating}</td>`;
                tableBody.appendChild(row);
            });
        });

    // Form submit AJAX logic
    document.getElementById("submit-review-btn").addEventListener("click", function() {
        const reviewer = document.getElementById("reviewer-name").value;
        const text = document.getElementById("review-text").value;
        const rating = parseInt(document.getElementById("review-rating").value);

        const payload = {
            id: Date.now(),
            orderId: 999,
            reviewerName: reviewer,
            reviewText: text,
            rating: rating
        };

        fetch(backendUrl, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        })
        .then(response => {
            if (response.ok) {
                // Update reviews list table inline
                const tableBody = document.getElementById("reviews-table-body");
                const row = document.createElement("tr");
                row.className = "review-row";
                row.setAttribute("data-reviewer", reviewer);
                row.setAttribute("data-text", text);
                row.innerHTML = `<td>${reviewer}</td><td>${text}</td><td>${rating}</td>`;
                tableBody.appendChild(row);
            }
        });
    });
});
```
