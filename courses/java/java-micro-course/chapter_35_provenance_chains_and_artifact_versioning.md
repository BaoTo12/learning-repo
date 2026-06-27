# Chapter 35: Provenance Chains & Artifact Versioning

A continuous delivery platform can deploy software across multiple clouds at high velocity. However, unless you can trace every running application instance back to its source code change and transitive dependencies, your platform lacks **Provenance**. When a critical security vulnerability (such as a Zero-day exploit) is announced, SREs must quickly identify which running microservices are affected and trace them back to their corresponding source code lines.

This chapter covers the technical design and implementation of artifact provenance chains. We will build queryable stateful asset inventories, outline the limitations of GitOps systems in tracking deployed states, analyze release versioning requirements across Docker registries and Maven artifact repositories, extract transitive dependencies metadata, construct abstract syntax trees (ASTs) using **OpenRewrite** to audit source code usage, and resolve version misalignment conflicts under dynamic constraints.

---

## Learning Objectives

By the end of this chapter, you will be able to:
1. Explain the concept of a software provenance chain and trace it from a code change to production.
2. Apply SLSA (Source Levels for Software Artifacts) principles to secure the build pipeline.
3. Verify signed metadata provenance using cryptographically secure signatures.
4. Build queryable stateful asset inventories that span multiple cloud providers.
5. Compare the limitations of GitOps status tracking against real-time active polling.
6. Manage immutable release versioning schemes using unique Git commit tags.
7. Explain why Docker image tags are mutable and configure pipelines to resolve expected artifacts by cryptographic digests.
8. Compare SPDX and CycloneDX Software Bill of Materials (SBOM) schema standards.
9. Generate a complete SPDX-compliant SBOM JSON file for a microservice.
10. Extract and audit first-level and transitive dependencies metadata from JVM applications.
11. Configure the CycloneDX Maven plugin to compile Software Bills of Materials (SBOMs).
12. Write custom OpenRewrite Abstract Syntax Tree (AST) recipes to automate security upgrades.
13. Execute a step-by-step SRE zero-day vulnerability triage run.
14. Diagnose and resolve dependency version misalignments caused by dynamic version constraints.
15. Configure explicit dependency resolutions in Maven and Gradle to align dynamic versions.
16. Implement signed artifact provenance using Sigstore and Cosign keys.
17. Configure the CycloneDX Gradle plugin inside build scripts.
18. Configure OWASP Dependency-Check Maven plug-ins to scan for CVEs at build-time.
19. Declare an in-toto formatted Build Provenance Attestation metadata schema.
20. Configure Snyk CLI scans inside pipeline scripts to block vulnerable libraries.
21. Write a Trivy docker image verification shell script that audits security context before CD deployment.
22. Configure OWASP Dependency-Check suppression rules using XML definitions to filter false positives.
23. Write a GitHub Actions workflow automating SBOM compilation, signing, and publication.

---

## 35.1 The Provenance Chain: Code Change to Production

A **Provenance Chain** maps every running production binary back to the exact code changes and build processes that produced it.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//a16c43a0-af8d-4c7b-b2b3-99e6c5e542ed/markdown_1/imgs/img_in_image_box_141_723_864_936.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A43Z%2F-1%2F%2De4f96acd261a3c7195d488ab245cd51feb059e4bedb8934035718adf1015d4f" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 35.1 The provenance chain mapping code modifications to active deployments</div> </div>

To establish a complete provenance chain:
1. **Source Code**: Every code change is tracked in Git, tagged with a unique commit hash.
2. **Build Stage**: The CI system compiles the code and generates a binary with metadata containing the commit hash, build number, and build time.
3. **Artifact Repository**: The binary is versioned and stored in an artifact repository (e.g. Maven Central, Docker Registry).
4. **Deploy Stage**: The CD system (Spinnaker) parses the artifact metadata and deploys it, tagging the cloud resources (Auto Scaling Groups, Kubernetes ReplicaSets) with the corresponding version descriptors.

---

## 35.2 The Stateful Asset Inventory

To query the state of running workloads, SREs maintain a queryable **Stateful Asset Inventory**:

```java
// Java code to retrieve all currently running deployed assets across clouds
List<ServerGroup> runningAssets = delivery.getApplications()
    .flatMap(application -> application.getClusters())
    .flatMap(cluster -> cluster.getServerGroups())
    .collect(Collectors.toList());

class Application {
    private String name;
    private List<Cluster> clusters;
    public Stream<Cluster> getClusters() { return clusters.stream(); }
}
class Cluster {
    private List<ServerGroup> serverGroups;
    public Stream<ServerGroup> getServerGroups() { return serverGroups.stream(); }
}
```

By querying this inventory, platform teams can determine the exact deployment target of any code version in real time.

---

## 35.3 GitOps Monitoring: Limitations and Solutions

GitOps uses operators (like ArgoCD or Flux) to sync the active cluster state with a declared configuration repository. While GitOps is an exceptional pattern, SREs must understand its limitations for status tracking:

* **Lack of Real-Time Status**: A GitOps operator tells you if the *desired state matches the Git state*, but it does not run real-time health checks on downstream database connections or third-party APIs.
* **Cascading Outages**: If an operator detects a configuration drift, it will automatically redeploy resources. If the drift was caused by a database migration failure, the automatic redeployment loop can trigger a cascading outage across dependencies.
* **Latency Drift**: ArgoCD relies on a sync loop (typically 3 minutes). Under load spikes, this lag can delay critical security rollbacks.

To mitigate these, platform teams combine GitOps with active real-time polling engines and readiness probes to confirm application health before resolving sync loops.

---

## 35.4 Supply Chain Security and SLSA

Software supply chain security has become a paramount concern for enterprise engineering. Attackers no longer target the production runtime exclusively; instead, they compromise the build pipelines (like the SolarWinds compromise) or inject malicious transitive dependencies (like Log4Shell).

To address this, platform teams adopt the **SLSA (Supply chain Levels for Software Artifacts)** framework. SLSA defines four levels of security:

### 35.4.1 SLSA Level 1: Documented Provenance
Requires a documented build process that outputs a provenance metadata record showing how the artifact was created. It must include the build source, build entry point, and list of dependencies.

### 35.4.2 SLSA Level 2: Tamper-Resistant Provenance
Requires version control, a hosted build service, and signed provenance data that prevents tampering. The build service must generate the provenance metadata in a way that developers cannot modify it, and sign it using a secure cryptographic key (e.g. Sigstore Cosign).

### 35.4.3 SLSA Level 3: Hermetic Build Environment
Requires an isolated, ephemeral build environment, ensuring the build run is reproducible and hermetic. The builder has no external internet access during execution, preventing it from downloading unverified external dependencies at compile-time that could inject malware.

### 35.4.4 SLSA Level 4: Complete Verification
Requires two-person code reviews and hermetic hermetization of all transitive dependencies. Every dependency must have signed SLSA L3 provenance verified before execution.

---

## 35.5 Release Versioning and Cryptographic Digests

When deploying containers, using generic or mutable tags (like `latest`, `staging`, or `v1`) introduces severe operational risks. If a developer overwrites the `v1` tag in the registry with a new build, two pods in the same cluster might run different code versions depending on when their container runtime pulled the image.

To guarantee immutability, continuous delivery systems route deployments using **Cryptographic Digests** (SHA-256):

```yaml
# Imperative deployment using mutable tag
image: ftgo/review-service:v1

# Production-grade deployment using immutable SHA-256 digest
image: ftgo/review-service@sha256:8f418b76c8c4e09f58ec4e1f7d58ecfd3b8a3b8a1f7d58ecfd3b8a3b8a1f7d58
```

By specifying the cryptographic hash, the container runtime guarantees that the exact same binary is executed across all replica pods.

---

## 35.6 Signed Artifact Provenance: Sigstore & Cosign

To verify that deployed container digests actually originated from the secure enterprise build pipeline rather than an unauthorized developer system, platform teams enforce signed artifact verification using **Sigstore Cosign**.

### 1. Generating Keys and Signing the Image in CI
The build pipeline compiles the reviews container image and signs the generated digest:
```bash
# Generate keypair on the secure runner (secured via KMS or ephemeral secrets)
cosign generate-key-pair k8s://ftgo-system/cosign-key

# Sign the image digest directly in the registry
cosign sign --key k8s://ftgo-system/cosign-key ftgo/review-service@sha256:8f418b76c8c4e09f58ec4e1f7d58ecfd3b8a3b8a1f7d58ecfd3b8a3b8a1f7d58
```

### 2. Validating Signed Images in Kubernetes
We install a Sigstore admission controller (like Kyverno or Cosign Policy Controller) inside the cluster that blocks any pod deployment if its image digest signature cannot be validated against the public key:
```yaml
apiVersion: policy.sigstore.dev/v1alpha1
kind: ClusterImagePolicy
metadata:
  name: enforce-signed-reviews
spec:
  images:
    - glob: "ftgo/review-service@sha256:*"
  authorities:
    - key:
        secretRef:
          name: cosign-public-key
          namespace: ftgo-system
```

---

## 35.7 In-Toto Build Provenance Attestation Metadata

In addition to signing the container image, modern secure pipelines output an **in-toto provenance attestation**. This document describes the exact inputs, build environment, and executed steps, sealed with a cryptographic signature. SRE systems parse this document at deploy-time to verify SLSA build compliance.

### The in-toto Provenance Attestation JSON: `provenance.attestation.json`
```json
{
  "_type": "https://in-toto.io/Statement/v0.1",
  "subject": [
    {
      "name": "ftgo/review-service",
      "digest": {
        "sha256": "8f418b76c8c4e09f58ec4e1f7d58ecfd3b8a3b8a1f7d58ecfd3b8a3b8a1f7d58"
      }
    }
  ],
  "predicateType": "https://slsa.dev/provenance/v0.2",
  "predicate": {
    "builder": {
      "id": "https://jenkins.ftgo-platform.com/GCPBuilder"
    },
    "buildType": "https://jenkins.ftgo-platform.com/Jenkinsfile@v1",
    "invocation": {
      "configSource": {
        "uri": "https://github.com/ftgo-platform/review-service.git",
        "digest": {
          "sha1": "3c983a5e8c2f1b4da3f8e91e58ea1f584ecd5c8a"
        },
        "entryPoint": "Jenkinsfile"
      },
      "parameters": {
        "build_number": "104"
      }
    },
    "environment": {
      "executor_id": "pod-maven-runner-j892",
      "architecture": "amd64"
    },
    "materials": [
      {
        "uri": "https://github.com/ftgo-platform/review-service.git",
        "digest": {
          "sha1": "3c983a5e8c2f1b4da3f8e91e58ea1f584ecd5c8a"
        }
      },
      {
        "uri": "pkg:maven/org.postgresql/postgresql@42.6.0",
        "digest": {
          "sha256": "8f418b76c8c4e09f58ec4e1f7d58ecfd3b8a3b8a1f7d58ecfd3b8a3b8a1f7d58"
        }
      }
    ]
  }
}
```

---

## 35.8 SBOM Standards: SPDX vs. CycloneDX

A **Software Bill of Materials (SBOM)** is a structured inventory of all software components, licensing metadata, and transitive dependencies that compose an application. SREs leverage SBOMs to scan for vulnerabilities (CVEs) during deployment gates. Two primary schema standards exist:

| Dimension | SPDX (Software Package Data Exchange) | CycloneDX |
| :--- | :--- | :--- |
| **Origin** | Linux Foundation (ISO standard). | OWASP Foundation. |
| **Primary Focus** | Licensing compliance, intellectual property audit. | Security vulnerability scanning, supply chain risk. |
| **Data Format** | Tag-value files, RDF, JSON, YAML, XML. | JSON, XML, Protocol Buffers. |
| **Dependency Graphs**| Verbose, highly detailed relationships. | Lightweight, direct component hierarchy mapping. |

For microservice environments, **CycloneDX** has emerged as the preferred format due to its lightweight JSON structure, speed of generation inside build profiles, and seamless integration with vulnerability scanners like Trivy, Grype, or dependency-track.

---

## 35.9 OpenRewrite and Abstract Syntax Trees (ASTs)

When dependencies must be updated across hundreds of microservices (e.g., upgrading Log4j due to a CVE), manual refactoring is slow and error-prone. Platform teams automate this using **OpenRewrite**.

OpenRewrite parses Java source files into an **Abstract Syntax Tree (AST)** (specifically a Lossless Semantic Tree or LST) that retains all code formatting, spacing, and comments. The tool runs declarative refactoring recipes on the LST and writes the modified code back to disk:

```
[ Java Code ] ──► (Parse) ──► [ Lossless Semantic Tree (LST) ]
                                            │
                                            ▼ (Apply Rewrite Recipe)
[ Refactored Code ] ◄── (Print) ◄── [ Mutated LST ]
```

For example, a platform recipe can parse all `pom.xml` files in the organization, detect transitively imported vulnerabilities, and rewrite dependency declarations to secure versions automatically.

---

## 35.10 Dependency Misalignments and Conflict Resolution

Microservices often import shared libraries (e.g. common domain models or authentication helpers). If Service A imports version `1.1` of a utility library, and Service B imports version `1.2`, a third service aggregating them may face **Dependency Misalignment**.

In Maven, dependency conflicts are resolved using the **Nearest Wins** strategy: the dependency closest to the root of the project's dependency tree is selected. This can lead to runtime errors:

```
[ App ] ──► [ Library A: v1.0 ] ──► [ Log4j: v2.15 ]  (Nearest: selected)
[ App ] ──► [ Library B: v2.0 ] ──► [ Log4j: v2.17 ]
```

If the JVM picks the older `v2.15` package, it may expose a vulnerability or trigger a `NoSuchMethodError` if Library B calls a method only present in `v2.17`. To resolve this under dynamic constraints, platform teams enforce strict parent POMs and dependency management blocks that lock transitive dependency versions explicitly.

---

## 35.11 Overriding Transitive Dependencies: Maven vs. Gradle

To resolve these conflicts, developers must declare explicit version rules within the build file to override secondary dependencies.

### 1. Maven Dependency Management Override
In Maven, we use the `<dependencyManagement>` tag. This locks the version of any transitive dependency that appears in the child graph:
```xml
<dependencyManagement>
    <dependencies>
        <!-- Lock Log4j transitive imports to a secure version -->
        <dependency>
            <groupId>org.apache.logging.log4j</groupId>
            <artifactId>log4j-core</artifactId>
            <version>2.17.1</version>
        </dependency>
    </dependencies>
</dependencyManagement>
```

### 2. Gradle Resolution Strategy Override
In Gradle, conflicts are overridden programmatically using the `resolutionStrategy` hook inside the `build.gradle` file:
```groovy
configurations.all {
    resolutionStrategy {
        // Enforce a specific version of a transitive dependency
        force 'org.apache.logging.log4j:log4j-core:2.17.1'
        
        // Fail the build immediately if any version conflict is detected
        failOnVersionConflict()
    }
}
```

---

## 35.12 Production-Grade CycloneDX SBOM Maven Configuration

To satisfy SLSA requirements and generate an SBOM automatically during the compile stage, the platform team configures the **CycloneDX Maven Plugin** in the `pom.xml` build profiles of the **review-service**.

The plugin generates a detailed inventory containing all direct imports (such as Spring Boot starter frameworks) and transitive dependencies (like database drivers and logging libraries).

### 1. POM Build Profile: `pom.xml`
```xml
<project>
    <!-- ... Core Project Coordinates ... -->
    
    <profiles>
        <!-- Profile compiles SBOM during package lifecycle -->
        <profile>
            <id>cyclonedx-sbom</id>
            <activation>
                <activeByDefault>true</activeByDefault>
            </activation>
            <build>
                <plugins>
                    <plugin>
                        <groupId>org.cyclonedx</groupId>
                        <artifactId>cyclonedx-maven-plugin</artifactId>
                        <version>2.7.9</version>
                        <executions>
                            <execution>
                                <phase>package</phase>
                                <goals>
                                    <goal>makeAggregateBom</goal>
                                </goals>
                            </execution>
                        </executions>
                        <configuration>
                            <projectType>library</projectType>
                            <schemaVersion>1.4</schemaVersion>
                            <includeBomSerialNumber>true</includeBomSerialNumber>
                            <includeComponentVersion>true</includeComponentVersion>
                            <includeLicenseText>false</includeLicenseText>
                            <outputFormat>all</outputFormat> <!-- Compiles both JSON and XML -->
                            <outputName>bom</outputName>
                            <excludeArtifactIds>
                                <!-- Expose only production dependencies by removing test libs -->
                                <excludeArtifactId>junit-jupiter</excludeArtifactId>
                                <excludeArtifactId>mockito-core</excludeArtifactId>
                            </excludeArtifactIds>
                        </configuration>
                    </plugin>
                </plugins>
            </build>
        </profile>
    </profiles>
</project>
```

---

### 2. Generated CycloneDX SBOM Metadata JSON: `bom.json`
During compile execution, the plugin writes `target/bom.json`. Below is the serialized representation mapping direct dependencies:

```json
{
  "bomFormat": "CycloneDX",
  "specVersion": "1.4",
  "serialNumber": "urn:uuid:68e27c1b-e5f8-4e42-901e-d4c5c8f8b8a3",
  "version": 1,
  "metadata": {
    "timestamp": "2026-06-27T08:16:00Z",
    "tools": [
      {
        "vendor": "OWASP",
        "name": "cyclonedx-maven-plugin",
        "version": "2.7.9"
      }
    ],
    "component": {
      "group": "com.ftgo",
      "name": "review-service",
      "version": "1.2.0",
      "type": "library"
    }
  },
  "components": [
    {
      "group": "org.springframework.boot",
      "name": "spring-boot-starter-web",
      "version": "3.1.2",
      "type": "library",
      "hashes": [
        {
          "alg": "SHA-256",
          "content": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        }
      ],
      "licenses": [
        {
          "license": {
            "id": "Apache-2.0"
          }
        }
      ],
      "purl": "pkg:maven/org.springframework.boot/spring-boot-starter-web@3.1.2"
    },
    {
      "group": "org.postgresql",
      "name": "postgresql",
      "version": "42.6.0",
      "type": "library",
      "hashes": [
        {
          "alg": "SHA-256",
          "content": "8f418b76c8c4e09f58ec4e1f7d58ecfd3b8a3b8a1f7d58ecfd3b8a3b8a1f7d58"
        }
      ],
      "purl": "pkg:maven/org.postgresql/postgresql@42.6.0"
    }
  ],
  "dependencies": [
    {
      "ref": "pkg:maven/com.ftgo/review-service@1.2.0",
      "dependsOn": [
        "pkg:maven/org.springframework.boot/spring-boot-starter-web@3.1.2",
        "pkg:maven/org.postgresql/postgresql@42.6.0"
      ]
    }
  ]
}
```

---

## 35.13 CycloneDX Gradle Build Script Configuration: `build.gradle`

For projects using the Gradle build system, the platform team configures the equivalent CycloneDX Gradle plugin to automate SBOM generation during packaging tasks.

```groovy
plugins {
    id 'java'
    id 'org.springframework.boot' version '3.1.2'
    id 'io.spring.dependency-management' version '1.1.0'
    id 'org.cyclonedx.bom' version '4.7.1'
}

group = 'com.ftgo'
version = '1.2.0'
sourceCompatibility = '17'

repositories {
    mavenCentral()
    maven {
        url "https://artifactory.ftgo.com/artifactory/maven-releases"
    }
}

dependencies {
    implementation 'org.springframework.boot:spring-boot-starter-web'
    implementation 'org.postgresql:postgresql:42.6.0'
    testImplementation 'org.springframework.boot:spring-boot-starter-test'
}

cyclonedxBom {
    includeConfigs = ["runtimeClasspath"]
    skipConfigs = ["compileClasspath", "testCompileClasspath"]
    projectType = "application"
    schemaVersion = "1.4"
    destination = file("build/reports")
    outputName = "bom"
    outputFormat = "json"
}
```

---

## 35.14 Production-Grade CVE Scan Configuration: OWASP Dependency-Check

To prevent deployment of vulnerable transitive packages, the build pipeline runs the **OWASP Dependency-Check Maven Plugin** to scan dependencies against the NVD database during the verify phase. The build fails if any dependency contains a CVSS score $\ge 7.0$.

```xml
<plugin>
    <groupId>org.owasp</groupId>
    <artifactId>dependency-check-maven</artifactId>
    <version>8.3.1</version>
    <executions>
        <execution>
            <phase>verify</phase>
            <goals>
                <goal>check</goal>
            </goals>
        </execution>
    </executions>
    <configuration>
        <failBuildOnCVSS>7.0</failBuildOnCVSS>
        <format>ALL</format>
        <outputDirectory>${project.build.directory}/dependency-check-reports</outputDirectory>
        <suppressionFile>${project.basedir}/dependency-check-suppressions.xml</suppressionFile>
    </configuration>
</plugin>
```

---

## 35.15 CVE Scan Suppression Rules: `dependency-check-suppressions.xml`

To prevent false positives from blocking deployment, SRE teams maintain a strict suppresion manifest. Below is the XML configuration suppressing CVE warnings that do not impact the microservice context.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<suppressions xmlns="https://jeremylong.github.io/DependencyCheck/dependency-suppression.1.3.xsd">
    <suppress>
        <notes><![CDATA[
            Suppress false positive for postgresql driver which is isolated within Namespace network controls.
        ]]></notes>
        <packageUrl regex="true">^pkg:maven/org\.postgresql/postgresql@.*$</packageUrl>
        <cve>CVE-2022-31197</cve>
    </suppress>
</suppressions>
```

---

## 35.16 Production-Grade SPDX SBOM Schema Configuration

To provide complete compatibility across security systems that require the **SPDX (Software Package Data Exchange)** format, the platform team maps the equivalent SPDX JSON structure. SPDX organizes SBOM components under the `packages` list, binding relationships explicitly using relationship descriptors.

### The SPDX Document JSON Schema: `bom-spdx.json`
```json
{
  "spdxVersion": "SPDX-2.3",
  "dataLicense": "CC0-1.0",
  "SPDXID": "SPDXRef-DOCUMENT",
  "name": "review-service-dependencies",
  "documentNamespace": "https://ftgo.com/spdx/review-service-1.2.0-urn:uuid:89a2e7c1",
  "creationInfo": {
    "creators": [
      "Tool: Maven-SPDX-Plugin-v1.0",
      "Organization: FTGO Platform Engineering"
    ],
    "created": "2026-06-27T08:16:00Z"
  },
  "packages": [
    {
      "name": "review-service",
      "SPDXID": "SPDXRef-Package-review-service-1.2.0",
      "versionInfo": "1.2.0",
      "downloadLocation": "NOASSERTION",
      "filesAnalyzed": false,
      "licenseConformed": "NOASSERTION",
      "licenseDeclared": "Apache-2.0",
      "copyrightText": "NOASSERTION",
      "checksums": [
        {
          "algorithm": "SHA256",
          "checksumValue": "9a3e2a7b8e1f584ecfd3b8a3b8a1f7d58ecfd3b8a3b8a1f7d58ecfd3b8a3b8a1"
        }
      ]
    },
    {
      "name": "spring-boot-starter-web",
      "SPDXID": "SPDXRef-Package-spring-boot-starter-web-3.1.2",
      "versionInfo": "3.1.2",
      "downloadLocation": "NOASSERTION",
      "filesAnalyzed": false,
      "licenseConformed": "NOASSERTION",
      "licenseDeclared": "Apache-2.0",
      "copyrightText": "NOASSERTION",
      "checksums": [
        {
          "algorithm": "SHA256",
          "checksumValue": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        }
      ]
    }
  ],
  "relationships": [
    {
      "spdxElementId": "SPDXRef-DOCUMENT",
      "relationshipType": "DESCRIBES",
      "relatedSpdxElement": "SPDXRef-Package-review-service-1.2.0"
    },
    {
      "spdxElementId": "SPDXRef-Package-review-service-1.2.0",
      "relationshipType": "DEPENDS_ON",
      "relatedSpdxElement": "SPDXRef-Package-spring-boot-starter-web-3.1.2"
    }
  ]
}
```

---

## 35.17 Automated Security Migration Rules: OpenRewrite Configuration

To execute secure dependency upgrades in place, the platform team writes custom **OpenRewrite Recipes** that match vulnerability signatures in source abstract syntax trees (ASTs) and execute replacements automatically.

### The OpenRewrite Declarative Upgrade Recipe: `rewrite-vulnerability-upgrade.yaml`
```yaml
type: specs.openrewrite.org/v1beta/recipe
name: com.ftgo.review.UpgradeSecureDependencies
displayName: Upgrade Vulnerable Dependencies for FTGO reviews-service
description: Upgrade Postgres JDBC driver and Spring Web modules to patched versions.
recipeList:
  - org.openrewrite.maven.UpgradeDependencyVersion:
      groupId: org.postgresql
      artifactId: postgresql
      newVersion: 42.6.0
  - org.openrewrite.maven.UpgradeDependencyVersion:
      groupId: org.springframework.boot
      artifactId: spring-boot-starter-web
      newVersion: 3.1.2
  - org.openrewrite.java.ChangePackage:
      oldPackageName: javax.servlet
      newPackageName: jakarta.servlet
      recursive: true
```

---

## 35.18 Programmatic AST Transformation in Java

To show how OpenRewrite operates on AST nodes dynamically, the platform team compiles a custom Java refactoring script using the OpenRewrite API. Below is the Java compiler plugin script that replaces vulnerable imports programmatically.

```java
package com.ftgo.platform.rewrite;

import org.openrewrite.ExecutionContext;
import org.openrewrite.Recipe;
import org.openrewrite.TreeVisitor;
import org.openrewrite.java.JavaIsoVisitor;
import org.openrewrite.java.tree.J;

public class UpgradeDependencyRecipe extends Recipe {

    @Override
    public String getDisplayName() {
        return "Upgrade import namespace to Jakarta Servlet";
    }

    @Override
    public String getDescription() {
        return "Relocates legacy javax.servlet package namespaces to modern jakarta.servlet.";
    }

    @Override
    protected TreeVisitor<?, ExecutionContext> getVisitor() {
        return new JavaIsoVisitor<ExecutionContext>() {
            @Override
            public J.Import visitImport(J.Import _import, ExecutionContext ctx) {
                J.Import imp = super.visitImport(_import, ctx);
                // Locate the target semantic tree node matching the package namespace
                if (imp.getFieldName().startsWith("javax.servlet")) {
                    String newFieldName = imp.getFieldName().replace("javax.servlet", "jakarta.servlet");
                    imp = imp.withFieldName(imp.getFieldName().withName(newFieldName));
                }
                return imp;
            }
        };
    }
}
```

---

## 35.19 Snyk CLI Scan Stage Configuration

To audit software packages against the Snyk vulnerability database, the platform integration script executes the scanner CLI during build stages, outputting JSON records to the platform security dashboard.

```bash
#!/bin/bash
# Pipeline script executing Snyk dependency audit
set -e

echo "Starting Snyk Vulnerability Scan..."
snyk auth "${SNYK_TOKEN}"

# Scan dependencies and fail the build if high severity CVEs exist
snyk test --json-file-output=snyk-report.json || snyk_exit_code=$?

if [ ${snyk_exit_code} -ne 0 ]; then
    echo "Snyk detected high severity vulnerabilities! Checking suppression rules..."
    # Check if suppression override allows temporary exemptions
    snyk ignore --file=.snyk
else
    echo "Snyk security scans passed successfully."
fi
```

---

## 35.20 Container Security Gate: Trivy Image Scanner

In addition to dependencies auditing, the platform runs **Trivy** to scan the compiled container filesystem. Trivy audits the base OS libraries (alpine/debian packages) and detects configuration anomalies, blocking the CD pipeline from deploying insecure containers.

### Trivy Container Security Scan Script: `validate_image_security.sh`
```bash
#!/bin/sh
set -e

TARGET_IMAGE="ftgo/review-service:latest"

echo "Auditing container filesystem using Trivy..."
trivy image --severity HIGH,CRITICAL --no-progress --exit-code 1 "${TARGET_IMAGE}"

echo "Validating non-root container configuration..."
IS_ROOT=$(docker inspect -f '{{.Config.User}}' "${TARGET_IMAGE}")

if [ -z "${IS_ROOT}" ] || [ "${IS_ROOT}" = "root" ] || [ "${IS_ROOT}" = "0" ]; then
    echo "[CRITICAL SECURITY FAILURE] Container image configures execution as root! Blocking deployment."
    exit 1
else
    echo "Container security verification passed. Image runs under non-privileged UID: ${IS_ROOT}."
fi
```

---

## 35.21 GitHub Actions SBOM Automation Workflow

To demonstrate a modern deployment pipeline context, we configure a declarative **GitHub Actions Workflow** that automatically builds the reviews application, compiles the CycloneDX SBOM, signs the SBOM using Cosign, and publishes it as a release asset.

```yaml
name: Generate and Sign SBOM

on:
  push:
    branches:
      - main

jobs:
  sbom-pipeline:
    runs-on: ubuntu-latest
    permissions:
      contents: write
      id-token: write

    steps:
      - name: Checkout Source Code
        uses: actions/checkout@v3

      - name: Setup JDK 17
        uses: actions/setup-java@v3
        with:
          java-version: '17'
          distribution: 'temurin'
          cache: 'maven'

      - name: Compile and Package with CycloneDX SBOM
        run: mvn clean package -B

      - name: Install Cosign CLI
        uses: sigstore/cosign-installer@v3.1.1

      - name: Write Signature using Keyless Signing
        run: |
          cosign sign-blob --yes             --output-signature target/bom.json.sig             --output-certificate target/bom.json.pem             target/bom.json

      - name: Upload SBOM Release Asset
        uses: softprops/action-gh-release@v1
        with:
          files: |
            target/bom.json
            target/bom.json.sig
            target/bom.json.pem
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

---

## 35.22 Step-by-Step SRE Zero-Day Vulnerability Triage Run

When a zero-day vulnerability (e.g. a remote code execution vulnerability in a core package) is declared, the SRE team implements the following triage run:

```
+---------------------------------------------------------------------------------+
|                       SRE ZERO-DAY TRIAGE AUTOMATED RUN                         |
+---------------------------------------------------------------------------------+
|                                                                                 |
|   1. Query Stateful Asset Inventory ────────► Identify running service pods    |
|   2. Parse Deployed Component Digest ───────► Match against vulnerable hashes    |
|   3. Run OpenRewrite AST Mutator ───────────► Rewrite pom.xml dependency tags   |
|   4. Deploy Patched Container Digest ───────► Confirm SLO and verify active logs|
|                                                                                 |
+---------------------------------------------------------------------------------+
```

### Step 1: Scan active cluster deployments using standard inventory commands
We retrieve the active container image digests running across production namespaces:
```bash
kubectl get pods --all-namespaces -o jsonpath="{range .items[*]}{.metadata.namespace}{\"\\t\"}{.metadata.name}{\"\\t\"}{.spec.containers[*].image}{\"\\n\"}{end}"
```

### Step 2: Fetch and verify the CycloneDX SBOM targets
We extract the target service's compiled SBOM from our artifact storage using `curl`:
```bash
curl -s https://artifactory.ftgo.com/sbom-store/review-service/1.2.0/bom.json | jq '.components[] | select(.name=="postgresql")'
```

### Step 3: Mutate vulnerable code bases with OpenRewrite
If a match is found, we run the OpenRewrite Maven plugin goal directly in the project directory, mutating the source abstract syntax tree:
```bash
mvn rewrite:run -Drewrite.recipeArtifactCoordinates=com.ftgo.platform:rewrite-recipes:latest -DactiveRecipes=com.ftgo.review.UpgradeSecureDependencies
```

### Step 4: Build and Deploy the secure cryptographic digest
We compile the updated code, check the pipeline's signed SLSA L2 metadata, and update the Kubernetes Deployment spec directly to point to the secure digest:
```bash
kubectl set image deployment/review-service review-service=ftgo/review-service@sha256:8f418b76c8c4e09f58ec4e1f7d58ecfd3b8a3b8a1f7d58ecfd3b8a3b8a1f7d58 -n ftgo-review-team
```

---

## Chapter Summary

* **Provenance** ensures every production binary can be traced back to its exact source version and transitive dependencies.
* SREs maintain **Stateful Asset Inventories** to dynamically query version distributions across cloud environments.
* The **SLSA framework** defines standards to protect the build pipeline against supply chain compromises.
* Generic Docker container tags are mutable; production systems target containers using immutable **cryptographic digests** (SHA-256 hashes).
* **CycloneDX** and **SPDX** are the primary industry standards for Software Bill of Materials (SBOM) data structures.
* OpenRewrite leverages **Abstract Syntax Trees (ASTs)** to safely automate code refactoring across microservice ecosystems.
* Conflict resolution schemes (like Maven's "Nearest Wins") require explicit dependency management declarations to prevent runtime dependency misalignments.
* The OWASP **CycloneDX plugin** automates SBOM compilation during standard Java build packaging lifecycles.
