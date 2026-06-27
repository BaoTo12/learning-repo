# Chapter 22: Automated Security Testing and DevSecOps

In previous chapters, we configured multiple security patterns across our microservice architecture, including Mutual TLS (mTLS), Edge token delegation via Keycloak, JWT context propagation, and container runtime sandboxing. However, in modern agile teams, code is committed, reviewed, and deployed continuously. Relying on manual code audits or periodic security reviews is insufficient to guarantee that security postures do not regress.

To achieve continuous security verification, we must automate security validation by shifting security checks left in our software development lifecycle. This is known as the **DevSecOps** methodology. Security validation should run automatically inside our Continuous Integration (CI) and Continuous Deployment (CD) pipelines. This chapter focuses on integrating automated security scanning into Java microservice pipelines. We will detail the OWASP API Security Top 10 vulnerabilities, configure Static Application Security Testing (SAST) using SonarQube, automate dependency scanning using OWASP Dependency-Check (Software Composition Analysis), write a declarative multi-stage Jenkinsfile pipeline, automate Dynamic Application Security Testing (DAST) using OWASP Zed Attack Proxy (ZAP), script custom ZAP API interactions, configure multi-module Maven SCA policies, trace Keycloak JWT ZAP interceptors, write mock Spring Security MVC unit assertions, automate container image scans using Trivy, contrast base images CVE footprints, configure `.trivyignore` files, and establish a workflow to manage false positives and triage vulnerability findings. Finally, we will write a custom JUnit/ArchUnit security compiler rule to enforce HTTP verb safety at compile time and a Git pre-commit security hook.

---

## Learning Objectives

By the end of this chapter, you will be able to:
1. Explain the DevSecOps philosophy and describe the difference between SAST, DAST, and SCA.
2. Analyze the OWASP API Security Top 10 vulnerabilities in the context of Java microservices.
3. Configure a local Dockerized SonarQube instance and execute static security scans on Spring Boot applications.
4. Configure exclusion properties and quality gates for SonarQube scans inside Maven `pom.xml` files.
5. Detect and fix HTTP verb exposure vulnerabilities arising from unconstrained `@RequestMapping` annotations.
6. Integrate the OWASP Dependency-Check Maven plugin to identify vulnerabilities in third-party library dependencies.
7. Configure CVSS threshold rules to fail Maven builds when critical security vulnerabilities are introduced.
8. Configure multi-module Maven parent POM structures to enforce dependency scanning across all subservices.
9. Set up Jenkins in a Docker container and configure integrations with local container sockets and host filesystems.
10. Write a declarative Jenkinsfile executing parallel build stages, static scans, quality gates, Trivy container scans, and packaging steps.
11. Differentiate between passive and active security scanning in web applications and microservice endpoints.
12. Configure and run OWASP Zed Attack Proxy (ZAP) to execute dynamic penetration tests against running microservices.
13. Script custom Python validation wrappers to automate ZAP scans via the ZAP API client library.
14. Write Keycloak JWT header interceptors in Javascript for OWASP ZAP session management.
15. Program Spring Boot `@WebMvcTest` unit cases Mocking JWT roles to verify security filter logic locally.
16. Write custom ArchUnit tests to statically verify that controllers do not expose unconstrained `@RequestMapping` annotations.
17. Contrast Alpine vs. Debian base image CVE footprints and configure `.trivyignore` files.
18. Automate pre-commit security validations locally by implementing shell-based Git pre-commit hooks.
19. Establish vulnerability suppression files and triage strategies to minimize development overhead from false positives.

---

## 22.1 Shifting Security Left: SAST, DAST, and SCA

In standard waterfall development, security verification was executed at the end of the development cycle during a manual penetration testing phase. If vulnerabilities were identified, fixing them at this late stage required significant code changes and delayed deployment schedules.

According to software engineering metrics (such as the research documented by Laura Bell et al.), the cost to repair a software defect increases exponentially as the code moves from design to implementation, testing, and production:

```
[ Repair Cost ]
     ^
     |                                          * (Production: 100x cost)
     |                                         /
     |                                        /
     |                                       /
     |                                      * (Testing: 15x cost)
     |                                     /
     |                                    /
     |                  * (Build: 5x cost)
     |                 /
     |   * (Code: 1x) /
     +---+------------+---------------------+----------------------------> [ Phase ]
```

To minimize remediation overhead, DevSecOps shifts security testing to the left of the lifecycle, executing security scans during the code, build, and integration testing phases. This is achieved using three complementary automation strategies:

1. **Static Application Security Testing (SAST)**: Analyzes the application's source code files without executing them. SAST scans identify coding patterns that introduce vulnerabilities, such as SQL injections, unvalidated user input, and insecure request mappings.
2. **Software Composition Analysis (SCA)**: Scans third-party libraries and frameworks (e.g., Maven or Gradle dependencies) to check them against databases of known vulnerabilities (CVEs). Since microservices frequently rely on open-source frameworks, SCA prevents the introduction of vulnerable transitive dependencies.
3. **Dynamic Application Security Testing (DAST)**: Tests the application in its running state by sending malicious payloads, checking input boundaries, and analyzing HTTP responses. DAST tools simulate attacker behaviors from the outside, finding runtime misconfigurations and cross-site scripting vulnerabilities.

---

## 22.2 The OWASP API Security Top 10

Microservices expose data and actions through APIs. The Open Web Application Security Project (OWASP) maintains a dedicated classification of the top ten vulnerabilities that target web APIs:

### 1. Broken Object-Level Authorization (BOLA)
BOLA occurs when an API endpoint exposes an identifier (ID) of an object (e.g., `/api/orders/{id}`) but fails to verify if the authenticated client has permission to access that specific object.
* **Vulnerable Example**:
  ```http
  GET /api/orders/9987 HTTP/1.1
  Authorization: Bearer <Access Token for Customer A>
  ```
  If Customer A receives the order details for Customer B (order ID 9987), the endpoint is vulnerable to BOLA.
* **Mitigation**: Avoid exposing database sequential auto-incrementing integer IDs. Use cryptographically random Universally Unique Identifiers (UUIDs) and validate ownership on every access query:
  ```java
  @GetMapping("/orders/{orderId}")
  public OrderResponse getOrder(@PathVariable UUID orderId, @AuthenticationPrincipal Jwt principal) {
      Order order = orderRepository.findById(orderId)
          .orElseThrow(() -> new OrderNotFoundException());
      
      // Enforce owner verification
      if (!order.getCustomerId().equals(principal.getClaim("user_id"))) {
          throw new AccessDeniedException("Unauthorized order query");
      }
      return order.toResponse();
  }
  ```

This authorization check needs to happen for every API request, preventing unauthorized data exfiltration:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//d545c83a-d85b-4db6-aaa4-fb0c20275fa9/markdown_4/imgs/img_in_image_box_132_290_942_734.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A20%3A32Z%2F-1%2F%2Fc488dcc36f800443a4c0e0c2b6876446c4cd301138ca0626f8a74886b597807c" alt="Image" width="76%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 13.1 A client application under an attack could exploit the broken object-level authorization vulnerability in an API to retrieve one user's details with an access token that belongs to another user.</div> </div>

---

### 2. Broken User Authentication
Occurs when user authentication is weakly implemented or bypassed. This includes accepting unsigned JWT tokens, failing to validate token expiration, or allowing predictable token generation.
* **Mitigation**: Use standard OAuth 2.0 / OpenID Connect frameworks. Configure API Gateways or sidecar proxies to strictly validate the signature (`alg`), issuer (`iss`), audience (`aud`), and expiration time (`exp`) of tokens against a trusted Identity Provider.

---

### 3. Excessive Data Exposure
Occurs when APIs return complete domain objects in the JSON payload, relying on the client-side user interface to filter and display the fields. Attackers can bypass the UI and inspect the raw HTTP response to retrieve sensitive fields.
* **Vulnerable Example**:
  ```java
  @GetMapping("/users/{id}")
  public User getUser(@PathVariable String id) {
      return userRepository.findById(id); // Returns internal User object containing password hash
  }
  ```
* **Mitigation**: Never return internal database entity objects directly. Construct tailored Data Transfer Objects (DTOs) that prunes data down to the fields required by the client:
  ```java
  @GetMapping("/users/{id}")
  public UserDto getUserPruned(@PathVariable String id) {
      User user = userRepository.findById(id);
      return new UserDto(user.getId(), user.getDisplayName(), user.getEmail());
  }
  ```

---

### 4. Lack of Resources and Rate Limiting
Occurs when APIs do not restrict the rate of incoming requests or fail to limit payload and query parameters. This exposes microservices to denial-of-service (DoS) attacks.
* **Mitigation**: Enforce payload limits on requests and utilize rate-limiting filters on API gateways to throttle traffic based on IP address or client ID.

---

### 5. Broken Function-Level Authorization
Occurs when an API checks authorization at the entry point (e.g., verifying user login) but fails to restrict specific HTTP verbs or operations based on user roles.
* **Vulnerable Example**: A regular user has access to `GET /api/users` and is able to call `DELETE /api/users/{id}` because the gateway verifies authentication but does not check operation-level roles.
* **Mitigation**: Bind specific roles or OAuth scopes to specific HTTP verbs:
  ```java
  @DeleteMapping("/users/{id}")
  @PreAuthorize("hasAuthority('SCOPE_admin')")
  public ResponseEntity<?> deleteUser(@PathVariable String id) {
      userRepository.deleteById(id);
      return ResponseEntity.ok().build();
  }
  ```

---

### 6. Mass Assignment
Occurs when APIs automatically bind client JSON parameters directly to internal Java domain object properties without filtering. This allows clients to modify fields they should not have access to (e.g., setting `"isAdmin": true`).
* **Mitigation**: Use separate incoming request DTOs instead of binding directly to JPA Entities:
  ```java
  // Secure binding pattern
  @PutMapping("/profile")
  public ResponseEntity<?> updateProfile(@RequestBody ProfileUpdateRequest request, @AuthenticationPrincipal Jwt jwt) {
      User user = userRepository.findById(jwt.getClaim("user_id"));
      user.setDisplayName(request.getDisplayName()); // Only bind allowed properties
      userRepository.save(user);
      return ResponseEntity.ok().build();
  }
  ```

---

### 7. Security Misconfiguration
Includes exposing verbose stack traces in error responses, enabling permissive Cross-Origin Resource Sharing (CORS) configurations (`*`), or failing to disable plaintext HTTP listeners in production.
* **Mitigation**: Define a custom `@ControllerAdvice` to catch exceptions globally and sanitize error details before sending responses, implementing the exception shielding pattern:
  ```java
  @ControllerAdvice
  public class GlobalExceptionHandler {
      @ExceptionHandler(Exception.class)
      public ResponseEntity<ErrorResponse> handleGenericException(Exception ex) {
          // Log verbose details internally
          logger.error("Internal service error:", ex);
          // Return standardized error code to the client
          return ResponseEntity.status(500)
              .body(new ErrorResponse("ERR-500", "An unexpected internal error occurred. Please contact support."));
      }
  }
  ```

---

### 8. Injection
Injection vulnerabilities arise when user-supplied inputs are passed directly to system interpreters (SQL, NoSQL, LDAP, OS command line) without validation or sanitization.
* **Mitigation**: Use parameterized database queries (like Spring Data JPA methods) instead of concatenating raw SQL strings. Perform input validation on all controller parameters using Jakarta Validation annotations:
  ```java
  public interface UserRepository extends JpaRepository<User, String> {
      // JPA automatically parameterizes this query, preventing SQL injection
      @Query("SELECT u FROM User u WHERE u.displayName = :name")
      List<User> findByName(@Param("name") String name);
  }
  ```

---

### 9. Improper Assets Management
Occurs when multiple versions of an API are deployed (e.g., deprecated v1 APIs) and left unpatched under the radar.
* **Mitigation**: Document APIs using OpenAPI (Swagger) specifications. Establish a retirement process for old APIs and ensure deprecated endpoints are deleted.

---

### 10. Insufficient Logging and Monitoring
Failing to log failed authentication attempts, authorization denials, or application errors. This prevents security teams from detecting active attacks or diagnosing data breaches.
* **Mitigation**: Log all authentication events, failed authorization attempts, and input sanitization failures with structured user context, and forward them to centralized log managers (such as OpenSearch).

---

## 22.3 Static Application Security Testing (SAST) with SonarQube

SonarQube is a static analysis platform used to identify security hotspots, code bugs, and style violations across codebases.

```
[ Developer Code Commit ] ==> [ Maven SonarQube Scanner ] ==> [ SonarQube Server Dashboard ]
                                                                      |
                                                            (Vulnerabilities Flagged)
                                                                      |
                                                                      v
                                                           [ Build Allowed / Blocked ]
```

### 1. Deploying SonarQube Locally
We launch a SonarQube server locally inside a Docker container:
```bash
docker run -d --name sonarqube-dev -p 9000:9000 sonarqube:community
```

Once initialized, log in to the interface at `http://localhost:9000` (default credentials: `admin/admin`) and generate an API access token.

---

### 2. Configuring Maven Settings (`settings.xml`)
To enable Maven to connect to the local SonarQube instance, define the server details inside your local Maven configuration file (`$USER_HOME/.m2/settings.xml`):

```xml
<settings>
    <pluginGroups>
        <pluginGroup>org.sonarsource.scanner.maven</pluginGroup>
    </pluginGroups>
    <profiles>
        <profile>
            <id>sonar</id>
            <activation>
                <activeByDefault>true</activeByDefault>
            </activation>
            <properties>
                <sonar.host.url>http://localhost:9000</sonar.host.url>
                <sonar.token>sqp_your_generated_sonarqube_token_here</sonar.token>
            </properties>
        </profile>
    </profiles>
</settings>
```

After executing a project scan, the quality metrics and bugs are visualized in detail on the SonarQube dashboard:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//8e16a9fc-d392-4e04-93d2-6f687a60c7f4/markdown_2/imgs/img_in_image_box_131_109_949_465.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A20%3A31Z%2F-1%2F%2Fc6745e499c04e5c5cb5e2b7ad1467b3ee380bd9af812ea8a0910a9afe8a4b74a" alt="Image" width="77%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 13.2 The SonarQube page shows the scan results of a project.</div> </div>

---

### 3. Exclusions and Quality Gates inside `pom.xml`
To configure SonarQube properties, exclusions (such as database migrations or auto-generated MapStruct codes), and threshold criteria directly inside the microservice `pom.xml`:

```xml
<properties>
    <sonar.java.coveragePlugin>jacoco</sonar.java.coveragePlugin>
    <sonar.dynamicAnalysis>reuseReports</sonar.dynamicAnalysis>
    <!-- Exclude auto-generated or non-critical folders -->
    <sonar.exclusions>
        **/db/migration/*.sql,
        **/generated/**,
        **/dto/**,
        **/*Application.java
    </sonar.exclusions>
    <!-- Exclude test files from code coverage metrics -->
    <sonar.coverage.exclusions>
        **/*Test.java,
        **/config/**
    </sonar.coverage.exclusions>
</properties>
```

---

### 4. Case Study: Mitigating HTTP Verb Exposure
A common security misconfiguration in Spring MVC is using the generic `@RequestMapping` annotation without specifying the allowed HTTP methods:

```java
package com.ftgo.payment.controller;

import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class PaymentsController {

    // Vulnerable mapping: implicitly binds to GET, POST, PUT, DELETE, PATCH, etc.
    @RequestMapping("/payment")
    public String processPayment() {
        return "Payment processed successfully";
    }
}
```

When we run a scan on this code using the SonarQube scanner plugin:
```bash
mvn clean verify sonar:sonar
```

SonarQube flags this as a **Security Hotspot**:
> "RequestMapping method should explicitly specify HTTP request methods. Unconstrained request mappings expose the application endpoints to unintended HTTP verbs (e.g., executing a POST operation using a GET request)."

To resolve this issue, replace the generic mapping with a specific verb annotation (e.g., `@PostMapping`):

```java
package com.ftgo.payment.controller;

import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class PaymentsController {

    // Secured mapping: explicitly binds only to HTTP POST
    @PostMapping("/payment")
    public String processPayment() {
        return "Payment processed successfully";
    }
}
```

Rerunning `mvn clean verify sonar:sonar` updates the dashboard and clears the vulnerability flag.

---

## 22.4 Software Composition Analysis (SCA) for Multi-Module POMs

In multi-module Java architectures, Software Composition Analysis must be defined centrally inside the parent `pom.xml` under `<pluginManagement>`. This ensures all submodules run scans using a consistent CVSS fail threshold.

### 1. Multi-Module Parent configuration (`pom.xml`)
```xml
<project>
    <groupId>com.ftgo</groupId>
    <artifactId>ftgo-parent</artifactId>
    <version>1.0.0</version>
    <packaging>pom</packaging>

    <build>
        <pluginManagement>
            <plugins>
                <plugin>
                    <groupId>org.owasp</groupId>
                    <artifactId>dependency-check-maven</artifactId>
                    <version>8.4.0</version>
                    <configuration>
                        <failBuildOnCVSS>7.0</failBuildOnCVSS>
                        <!-- Configure a local database mirror to prevent NVD API rate-limits in CI -->
                        <dataDirectory>/var/jenkins_home/dependency-check-data</dataDirectory>
                        <autoUpdate>true</autoUpdate>
                        <formats>
                            <format>HTML</format>
                            <format>JSON</format>
                        </formats>
                    </configuration>
                </plugin>
            </plugins>
        </pluginManagement>
    </build>
</project>
```

Run the dependency check command from the root folder:
```bash
mvn dependency-check:check
```

If the scanner identifies any library version containing a vulnerability with a Common Vulnerability Scoring System (CVSS) score of 7.0 or higher, the build fails, preventing the deployment of vulnerable code.

---

## 22.5 Continuous Integration Pipeline Automation with Jenkins

To ensure these scans run on every code commit, we automate the build pipeline using a **Jenkinsfile**.

We launch a Jenkins server configured with access to the host's Docker socket, allowing Jenkins to spin up transient Docker containers for build stages:

```bash
docker run -d --name jenkins-blueocean \
  -p 7070:8080 -p 50000:50000 \
  -v jenkins-data:/var/jenkins_home \
  -v /var/run/docker.sock:/var/run/docker.sock \
  jenkinsci/blueocean
```

Integrating scans early in the pipeline guarantees that vulnerabilities are caught before package build completion:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//8e16a9fc-d392-4e04-93d2-6f687a60c7f4/markdown_3/imgs/img_in_image_box_112_998_931_1117.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A20%3A32Z%2F-1%2F%2F03cd11b873a9c9ed400c64311b2948f569747a374a1d1227e35d3e6c13f3a7b9" alt="Image" width="77%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 13.3 In this Jenkins build pipeline, the first step is to perform a code scan by using SonarQube and then to start the build process.</div> </div>

---

### 1. Setting up SonarQube in Jenkins
1. Go to **Manage Jenkins** -> **Configure System**.
2. Locate the **SonarQube Servers** section and click **Add SonarQube**.
3. Name the installation `SonarScanner` and set the Server URL to `http://host.docker.internal:9000` (allowing container-to-host connectivity).

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//e6447deb-1fb3-48af-9683-80748c8a6cb0/markdown_1/imgs/img_in_image_box_196_104_836_480.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A20%3A49Z%2F-1%2F%2F45992086434121f2b1f4c379480535ba03653003d230d7eeb163e4450ab264c3" alt="Image" width="60%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 13.4 The Manage Jenkins page lets you install plugins for Jenkins.</div> </div>

4. Tick **Enable Injection of SonarQube Server Configuration as Build Environment Variables**.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//e6447deb-1fb3-48af-9683-80748c8a6cb0/markdown_1/imgs/img_in_image_box_132_664_947_888.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A20%3A49Z%2F-1%2F%2F4f250af80decf0cb5c3dfa8b92a5739ff59eaf3678567b9b83643c00cd77d92f" alt="Image" width="76%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 13.5 To set up the SonarQube plugin on Jenkins for the examples in this section, use host.docker.internal as the SonarQube host URL to connect to a port on the host machine where the Jenkins Docker container is running.</div> </div>

5. Save changes.

---

### 2. Declarative Jenkins Pipeline Configuration (`Jenkinsfile`)
To configure the pipeline run, create a new item inside the Jenkins dashboard and select the pipeline definition format:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//e6447deb-1fb3-48af-9683-80748c8a6cb0/markdown_2/imgs/img_in_image_box_185_112_915_346.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A20%3A50Z%2F-1%2F%2F2fc98681926f6063dfb0b763923be9d589671b2d61a7734a772262f21905c6a4" alt="Image" width="68%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 13.6 To create a Jenkins pipeline for our project, provide a name for the pipeline and then click the Pipeline option. Proceed by clicking the OK button at the bottom left.</div> </div>

Point the pipeline definition source to Git to load our dynamic configuration scripts:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//e6447deb-1fb3-48af-9683-80748c8a6cb0/markdown_2/imgs/img_in_image_box_185_642_925_1154.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A20%3A50Z%2F-1%2F%2F1d3088ba372692aa66eb075ca21cff3417eaad7783f357cb0b13cb0ae27078c4" alt="Image" width="69%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 13.7 In the Jenkins pipeline configuration, note that the path to the repository URL has been provided. Provide details as shown here and proceed by clicking the Save button at the bottom left.</div> </div>

This pipeline script executes SCA dependency scans, static analysis (SAST), Quality Gate verification, container scans using Trivy, and packages the microservice inside a Maven container:

```groovy
pipeline {
    agent {
        docker {
            image 'maven:3.8.6-openjdk-11'
            // Mount the local host's Maven repository directory to cache dependencies
            args '-v /var/jenkins_home/.m2:/root/.m2'
        }
    }
    
    stages {
        stage('Software Composition Analysis') {
            steps {
                echo 'Scanning third-party libraries for CVE vulnerabilities...'
                // Run OWASP Dependency Check
                sh 'mvn org.owasp:dependency-check-maven:check -DfailBuildOnCVSS=7.0'
            }
        }
        
        stage('SonarQube Static Analysis') {
            steps {
                echo 'Running static code scan with SonarQube...'
                // Inject the SonarQube server configuration from Jenkins system settings
                withSonarQubeEnv('SonarScanner') {
                    sh 'mvn clean verify sonar:sonar'
                }
            }
        }

        stage('Quality Gate Verification') {
            steps {
                echo 'Verifying quality gates...'
                // Wait for the SonarQube background processing task to return the quality status
                timeout(time: 5, unit: 'MINUTES') {
                    waitForQualityGate abortPipeline: true
                }
            }
        }

        stage('Compile and Package') {
            steps {
                echo 'Packaging application binary...'
                sh 'mvn -B -DskipTests clean package'
            }
        }

        stage('Container Image Scan') {
            steps {
                echo 'Building and scanning container image using Trivy...'
                sh 'docker build -t ftgo/payment-service:${BUILD_NUMBER} .'
                // Fail the build if critical or high vulnerabilities are discovered in the base OS layer
                sh 'trivy image --severity HIGH,CRITICAL --exit-code 1 ftgo/payment-service:${BUILD_NUMBER}'
            }
        }
    }
}
```

Once the pipeline build completes successfully, Jenkins displays the build execution outcomes:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//e6447deb-1fb3-48af-9683-80748c8a6cb0/markdown_4/imgs/img_in_image_box_111_542_931_664.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A20%3A51Z%2F-1%2F%2Fdad734aaabd3fbca8f920a66ba675cc6203c6446241d5494d9c2d85919f19ecc" alt="Image" width="77%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 13.8 After the build is successful, this progress bar shows the result of your SonarQube scan.</div> </div>

---

## 22.6 Dynamic Application Security Testing (DAST) with OWASP ZAP

Static analysis tool findings are validated by testing the application in its running state using **OWASP Zed Attack Proxy (ZAP)**. ZAP acts as an intercepting proxy, analyzing request and response flows to identify vulnerabilities.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//74b93a0f-27b9-40e0-9726-327e64cb4098/markdown_0/imgs/img_in_image_box_203_573_889_720.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A20%3A30Z%2F-1%2F%2Fae401a862d2608d773ea00c3c1988d324951b8eaaaab7a35f62e6ceb9add98ed" alt="Image" width="64%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 13.9 OWASP ZAP acts as a proxy between the web browser and the web application. It intercepts all request and response exchanges between the two.</div> </div>

### 1. Passive Scanning vs. Active Scanning
* **Passive Scanning**: ZAP inspects outgoing responses from the running microservice without modifying client payloads. It identifies configuration issues, such as missing HTTP security headers (`X-Frame-Options`, `Content-Security-Policy`, `X-Content-Type-Options`).
* **Active Scanning**: ZAP sends custom attack payloads (e.g., SQL injection sequences, XSS scripts, path traversal attempts) directly to the API endpoints to verify input validation controls. Active scans should only run in isolated QA or staging environments to prevent data corruption.

---

### 2. Deploying a Target App (order-service)
For testing, deploy the `order-service` microservice:
```bash
java -jar order-service-1.0.0.jar --server.port=8081 --server.address=localhost
```

Upon launching the ZAP UI, configure ZAP settings to start a non-persisted test session:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//74b93a0f-27b9-40e0-9726-327e64cb4098/markdown_1/imgs/img_in_image_box_186_568_766_888.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A20%3A31Z%2F-1%2F%2Fc712776d0a85655ee4cab994c3930f3fc78507d6a31c31a6c9df44e7a9776961" alt="Image" width="54%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 13.10 The ZAP start screen asks whether to persist the ZAP session. The exercises in this section don't require you to persist the session.</div> </div>

---

### 3. Automating Headless DAST Scans in pipelines
We automate DAST scans inside our build pipelines using a headless Dockerized ZAP instance. We trigger scans using the automated scan function exposed on ZAP interface:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//74b93a0f-27b9-40e0-9726-327e64cb4098/markdown_2/imgs/img_in_image_box_133_827_943_1140.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A20%3A31Z%2F-1%2F%2F90507af2a08822dcaf0104f195aa99bd936536d0c8a6209955a99ede7a74cda8" alt="Image" width="76%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 13.11 On the ZAP Welcome page, click the Automated Scan option to perform an automated scan on the order-service application.</div> </div>

Configure target ports and select drivers for web automation spiders:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//74b93a0f-27b9-40e0-9726-327e64cb4098/markdown_3/imgs/img_in_image_box_115_262_929_565.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A20%3A32Z%2F-1%2F%2F95f7c9ec58083ef6a8ce42a30f9acbeecb817346d13a83aed7302fb148a5eb37" alt="Image" width="76%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 13.12 Use the Automated Scan screen in ZAP to obtain details of the order-service application and attack using Firefox.</div> </div>


Run ZAP against the target API host and export the findings as a structured security report:
```bash
docker run -t owasp/zap2docker-stable zap-api-scan.py \
  -t http://host.docker.internal:8081/v3/api-docs \
  -f openapi \
  -r zap_security_report.html
```

---

### 4. Custom DAST Automation Scripting using the ZAP API
To orchestrate dynamic tests programmatically, we write a Python script (`zap_scanner.py`) utilizing the `python-owasp-zap-v2.4` library client. This script accesses ZAP over a proxy, runs the spider, initiates active scanning, polls the task status, and exports the vulnerabilities report:

```python
import time
from zapv2 import ZAPv2

# Define target and ZAP proxy settings
target = 'http://host.docker.internal:8081'
zap_proxy = 'http://localhost:8090'
zap_api_key = 'sec_api_key_102030'

# Initialize ZAP client
zap = ZAPv2(proxies={'http': zap_proxy, 'https': zap_proxy}, apikey=zap_api_key)

print(f'Starting spider scan on: {target}')
spider_id = zap.spider.scan(target)


# Poll spider until completion
while int(zap.spider.status(spider_id)) < 100:
    print(f'Spider progress: {zap.spider.status(spider_id)}%')
    time.sleep(2)
print('Spider scan complete.')

print(f'Initiating active scan on target: {target}')
ascan_id = zap.ascan.scan(target)

# Poll active scanner until completion
while int(zap.ascan.status(ascan_id)) < 100:
    print(f'Active scan progress: {zap.ascan.status(ascan_id)}%')
    time.sleep(5)
print('Active scan complete.')

# Retrieve and log discovered alerts
alerts = zap.core.alerts(baseurl=target)
print(f'Discovered {len(alerts)} security alerts.')
for alert in alerts:
    print(f"[{alert['risk']}] {alert['alert']} (Parameter: {alert['param']})")
```

For applications that run authenticated loops, select ZAP's manual explorer option to launch browser sessions recording target interactions:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//74b93a0f-27b9-40e0-9726-327e64cb4098/markdown_4/imgs/img_in_image_box_130_111_948_399.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A20%3A32Z%2F-1%2F%2F63cc768b06f79eaffcf8a23b17008cb37ef9a24d16a7e59ae44b07ba0ad80555" alt="Image" width="77%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 13.13 On the Manual Explore screen in ZAP, provide the details as shown here and then click the Launch Browser button.</div> </div>

Accessing the target exposes the application lessons page:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//74b93a0f-27b9-40e0-9726-327e64cb4098/markdown_4/imgs/img_in_image_box_128_737_951_1151.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A20%3A33Z%2F-1%2F%2F157fcc8cbc814f326bb9d154770059ed94c96c24d2cc0a08260dd21f27129b12" alt="Image" width="77%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 13.14 On the WebGoat home page, various tutorials are navigable from the lefthand menu.</div> </div>

Navigating to the Cross Site Scripting page:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//014873ec-df03-477c-bc32-dbc3f00d6e64/markdown_0/imgs/img_in_image_box_177_213_932_567.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A20%3A31Z%2F-1%2F%2Facd533dd7b30745b4ffad7929dbbcf5a921a3f39469ca18f4f7209cbf3eae4d9" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 13.15 On the Cross Site Scripting page, you can learn all about XSS attacks and how to prevent them.</div> </div>

Step 7 in this tutorial contains a shopping cart checkout form that is vulnerable to reflected XSS:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//014873ec-df03-477c-bc32-dbc3f00d6e64/markdown_0/imgs/img_in_image_box_179_836_777_1155.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A20%3A31Z%2F-1%2F%2Fd7e29efe927e517efc0f05357f351c59f0709d31f658724c6a4afaeb21f8f4c8" alt="Image" width="56%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 13.16 On the shopping cart form that's vulnerable to reflected XSS attacks, click the Purchase button to make ZAP detect the vulnerability.</div> </div>

Interacting with this form lets ZAP intercept request payloads, scanning them actively and flagging vulnerabilities inside the ZAP UI's Alerts section:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//014873ec-df03-477c-bc32-dbc3f00d6e64/markdown_1/imgs/img_in_image_box_130_353_948_772.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A20%3A32Z%2F-1%2F%2Fc9eb51acdb5fb33a7d68d7f9c75f88a2901350fb301c9874101c232c234c9d75" alt="Image" width="77%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 13.17 ZAP reports an XSS vulnerability on the page: the area that prints out the credit card number is vulnerable.</div> </div>

Submitting Javascript payloads into the field displays popup alert boxes validating the vulnerability:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//014873ec-df03-477c-bc32-dbc3f00d6e64/markdown_2/imgs/img_in_image_box_119_112_645_416.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A20%3A33Z%2F-1%2F%2Fc9ee0d3038dd36f3fd11fbb732b5aef62e66c49c77d52fbac19d52a1f93997d2" alt="Image" width="49%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 13.18 The JavaScript pop up that appears when attempting the purchase. It's clear that the page tries to print the user input entered in the Credit Card Number field.</div> </div>

---

### 6. Keycloak OAuth2 JWT Interceptor Script for ZAP
To enable ZAP's active scanner to bypass authentication checks and scan protected API routes, deploy an HTTP Sender script in ZAP that fetches a JWT access token from Keycloak and dynamically inserts it as an authorization header in outgoing scan requests:

```javascript
// ZAP HTTP Sender script template to append Keycloak tokens dynamically
function sendingRequest(msg, initiator, helper) {
    // Check if Request has target domain
    if (msg.getRequestHeader().getHostName().equals("host.docker.internal")) {
        
        // Retrieve fresh token from Keycloak STS
        var token = getAccessToken();
        msg.getRequestHeader().setHeader("Authorization", "Bearer " + token);
    }
}

function getAccessToken() {
    var xhr = new java.net.URL("http://host.docker.internal:8080/auth/realms/spmia-realm/protocol/openid-connect/token").openConnection();
    xhr.setDoOutput(true);
    xhr.setRequestMethod("POST");
    xhr.setRequestProperty("Content-Type", "application/x-www-form-urlencoded");
    
    var params = "grant_type=password&client_id=payment-service&client_secret=secret123&username=peter&password=peter123";
    var os = xhr.getOutputStream();
    os.write(params.getBytes("UTF-8"));
    os.close();
    
    var br = new java.io.BufferedReader(new java.io.InputStreamReader(xhr.getInputStream()));
    var response = "";
    var line;
    while ((line = br.readLine()) != null) {
        response += line;
    }
    br.close();
    
    // Quick JSON parser to extract accessToken
    var json = JSON.parse(response);
    return json.access_token;
}

function responseReceived(msg, initiator, helper) {
    // No modifications needed on responses
}
```

---

## 22.7 Spring Boot MVC Security Unit Testing

In addition to static analyses, we write MVC integration test cases to ensure that our security configurations and role-based policies are evaluated locally.

The following test class (`PaymentsControllerSecurityTest`) uses **Spring Security Test** helpers to mock authenticated JWT tokens and verify endpoint routing outcomes:

```java
package com.ftgo.payment.security;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors;
import org.springframework.test.web.servlet.MockMvc;
import com.ftgo.payment.controller.PaymentsController;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(PaymentsController.class)
public class PaymentsControllerSecurityTest {

    @Autowired
    private MockMvc mockMvc;

    @Test
    public void anonymousRequestsShouldBeRejectedWithUnauthorized() throws Exception {
        mockMvc.perform(post("/payment")
                .content("{\"amount\": 100.00}"))
                .andExpect(status().isUnauthorized()); // Verify filter rejects anonymous calls
    }

    @Test
    public void requestsWithAdminScopeShouldBeAllowed() throws Exception {
        mockMvc.perform(post("/payment")
                .with(SecurityMockMvcRequestPostProcessors.jwt()
                        .jwt(jwt -> jwt.claim("scope", "admin"))) // Mock admin scope JWT
                .content("{\"amount\": 100.00}"))
                .andExpect(status().isOk());
    }

    @Test
    public void requestsWithUserScopeShouldBeForbidden() throws Exception {
        mockMvc.perform(post("/payment")
                .with(SecurityMockMvcRequestPostProcessors.jwt()
                        .jwt(jwt -> jwt.claim("scope", "user"))) // Mock regular user scope
                .content("{\"amount\": 100.00}"))
                .andExpect(status().isForbidden()); // Verify role block works
    }
}
```

---

## 22.8 Custom ArchUnit Tests for Static RequestMapping Security

To enforce secure coding standards at compile time, we write custom **ArchUnit** tests. This test automatically scans the classpath and fails the build if a developer attempts to add a generic `@RequestMapping` annotation without explicitly setting the HTTP verb parameters:

```java
package com.ftgo.payment.security;

import com.tngtech.archunit.core.domain.JavaClasses;
import com.tngtech.archunit.core.domain.JavaMethod;
import com.tngtech.archunit.core.importer.ClassFileImporter;
import com.tngtech.archunit.core.importer.ImportOption;
import org.junit.jupiter.api.Test;
import org.springframework.web.bind.annotation.RequestMapping;
import java.util.Arrays;
import static org.assertj.core.api.Assertions.assertThat;

public class ControllerSecurityRuleTest {

    @Test
    public void controllersMustNotUseUnconstrainedRequestMapping() {
        JavaClasses importedClasses = new ClassFileImporter()
                .withImportOption(ImportOption.Predefined.DO_NOT_INCLUDE_TESTS)
                .importPackages("com.ftgo.payment");

        for (com.tngtech.archunit.core.domain.JavaClass clazz : importedClasses) {
            // Check if class is a controller
            if (clazz.isAnnotatedWith("org.springframework.web.bind.annotation.RestController") ||
                clazz.isAnnotatedWith("org.springframework.stereotype.Controller")) {
                
                for (JavaMethod method : clazz.getMethods()) {
                    if (method.isAnnotatedWith(RequestMapping.class)) {
                        RequestMapping annotation = method.getAnnotationOfType(RequestMapping.class);
                        
                        // Fail if RequestMapping has no methods specified (implicitly exposing all verbs)
                        assertThat(annotation.method())
                            .withFailMessage("Controller method %s.%s uses a generic @RequestMapping without specifying HTTP verbs. Replace it with @PostMapping or add method constraints.",
                                    clazz.getName(), method.getName())
                            .isNotEmpty();
                    }
                }
            }
        }
    }
}
```

---

## 22.9 Hardened Docker Base Images and Trivy Ignores

To run container image security checks successfully, we must minimize our base image vulnerabilities:

* **Standard Debian Base (`openjdk:11`)**: Contains hundreds of system tools (packages, curl, shell utilities). A standard Trivy scan flags up to 120 CVEs, mostly in libraries unassociated with our running Java JAR.
* **Hardened Alpine Base (`eclipse-temurin:11-jre-alpine`)**: Possesses a minimal system footprint. A Trivy scan flags almost 0 CVEs.

```dockerfile
# Hardened multi-stage Dockerfile
FROM maven:3.8.6-openjdk-11-slim AS builder
WORKDIR /app
COPY . .
RUN mvn package -DskipTests

FROM eclipse-temurin:11-jre-alpine
RUN addgroup -S appgroup && adduser -S appuser -G appgroup
USER appuser
COPY --from=builder /app/target/*.jar app.jar
ENTRYPOINT ["java", "-jar", "/app.jar"]
```

If Trivy discovers upstream base-layer CVEs that are unfixable, add a `.trivyignore` file to the root of the project to skip them and prevent build failures:
```
# Suppress known unfixable CVEs
CVE-2023-10203
CVE-2023-40506
```

---

## 22.10 Local pre-commit Git Validation Hook

To prevent insecure configurations from being pushed to the remote repository, we establish a local pre-commit Git hook inside our repository (`.git/hooks/pre-commit`):

```bash
#!/bin/sh

echo "Executing pre-commit local security gates..."

# 1. Run the ControllerSecurityRuleTest to verify HTTP verb safety
mvn test -Dtest=ControllerSecurityRuleTest
if [ $? -ne 0 ]; then
    echo "[SECURITY FAILURE] RequestMapping constraints violated. Commit aborted."
    exit 1
fi

# 2. Check for accidentally hardcoded secrets
git diff --cached | grep -E "(password|client_secret|private_key|token)\s*=\s*['\"][A-Za-z0-9+/]{10,}['\"]"
if [ $? -eq 0 ]; then
    echo "[SECURITY WARNING] Potential hardcoded credentials discovered in staged changes. Commit aborted."
    exit 1
fi

echo "All pre-commit gates passed."
exit 0
```

Deploy the hook script:
```bash
chmod +x .git/hooks/pre-commit
```

---

## 22.11 Managing False Positives and Triage

Static and dynamic analysis tools frequently report false positives, which can slow down deployment schedules. To manage findings efficiently:

### 1. Dependency-Check Vulnerability Suppression
If a third-party library dependency is flagged with a CVE that does not affect our application (e.g., a vulnerability in an unused class), configure a suppression file (`dependency-check-suppression.xml`):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<suppressions xmlns="https://jeremylong.github.io/DependencyCheck/dependency-check-suppression.1.3.xsd">
    <suppress>
        <notes>Suppress false positive CVE-2023-9999 for spring-webmvc in our payment microservice.</notes>
        <packageUrl regex="true">^pkg:maven/org\.springframework/spring\-webmvc@.*$</packageUrl>
        <cve>CVE-2023-9999</cve>
    </suppress>
</suppressions>
```

Reference this file inside the Maven plugin configuration:
```xml
<configuration>
    <suppressionFiles>
        <suppressionFile>${project.basedir}/dependency-check-suppression.xml</suppressionFile>
    </suppressionFiles>
</configuration>
```

---

### 2. SonarQube Hotspot Resolution
For SAST findings, developers review security hotspots inside the SonarQube dashboard. If a finding is deemed safe (e.g., encryption keys are handled by cloud providers), mark the finding as **"Safe"** or **"Acknowledged"** within the SonarQube UI. This configuration is persisted across subsequent pipeline builds.

---

## Chapter Summary

* **DevSecOps** integrates automated security testing inside the software delivery pipeline, executing verification checks early in the development lifecycle.
* **Static Application Security Testing (SAST)** analyzes source code files for vulnerabilities (such as missing HTTP verb constraints) without executing the code.
* **Software Composition Analysis (SCA)** scans third-party library frameworks to prevent vulnerable dependencies from entering the deployment artifact.
* **Declarative Jenkinsfiles** automate the build pipeline, executing SCA checks, SAST analyses, Quality Gate checks, Trivy container scans, and compilation steps on every commit.
* **Dynamic Application Security Testing (DAST)** tests running applications. **Passive Scans** verify header configurations, while **Active Scans** send security payloads to test endpoint boundaries.
* Authenticated DAST scans are executed by configuring context xml parameters and supplying login credentials to ZAP engines.
* Custom Python scripts orchestrate dynamic active security scans by polling ZAP proxy APIs.
* Interceptor Javascript helper files fetch OAuth tokens dynamically to scan JWT-protected API routes.
* Spring Security Test frameworks allow developers to mock JWT scopes and verify role constraints locally.
* **ArchUnit** tests are added to Java suites to programmatically enforce HTTP verb mapping constraints at compile time.
* Hardened Alpine base images minimize Docker vulnerability footprints, while `.trivyignore` files suppress unfixable base-layer issues.
* **Git pre-commit hooks** run ArchUnit tests and search for hardcoded secrets before allowing commits.
* False positives are managed using dependency-check suppression xml files and updating finding states in the SonarQube dashboard.
