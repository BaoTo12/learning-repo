# CS-518: OWASP Top 10 Security & Mitigations in Java/Spring

Welcome to **CS-518: OWASP Top 10 Security & Mitigations in Java/Spring**. I am Professor Antigravity. In this course, we will transition from basic API functionality to advanced defensive systems engineering.

Building secure backend architectures requires developers to understand the anatomy of common web vulnerabilities. Relying on default framework behaviors is not enough. You must understand how attackers bypass token validations, inject queries inside ORM layers, exploit deserialization flows, execute requests from server-side clients, and hijack unhardened microservice configurations.

In this course, we will study **Insecure Direct Object References (IDOR), Argon2id cryptosystems, JPQL injection refactorings, session fixation preventions, Jackson polymorphic serialization boundaries, log forging sanitization, and SSRF HTTP filters**.

---

## Course Syllabus & Navigation

The course is divided into 11 detailed modules and a final application hardening capstone project:

| Module | Core Classification | Focus Topics |
| :--- | :--- | :--- |
| **01** | [Broken Access Control](file:///c:/Users/Admin/Desktop/projects/learning-repo/owasp-security-spring/modules/01-broken-access-control.md) | Insecure Direct Object References (IDOR), privilege escalation, and custom PermissionEvaluators. |
| **02** | [Cryptographic Failures](file:///c:/Users/Admin/Desktop/projects/learning-repo/owasp-security-spring/modules/02-cryptographic-failures.md) | Weak hashes (MD5), password protection (Argon2id vs. BCrypt), and symmetric data encryption (AES-GCM). |
| **03** | [Injection Attacks](file:///c:/Users/Admin/Desktop/projects/learning-repo/owasp-security-spring/modules/03-injection-attacks.md) | JPQL string SQLi, OS Command execution (ProcessBuilder filters), and Log4Shell mitigations. |
| **04** | [Insecure Design](file:///c:/Users/Admin/Desktop/projects/learning-repo/owasp-security-spring/modules/04-insecure-design.md) | API denial-of-service throttling (Bucket4j), secure password recovery token state flows. |
| **05** | [Security Misconfiguration](file:///c:/Users/Admin/Desktop/projects/learning-repo/owasp-security-spring/modules/05-security-misconfiguration.md) | Disabling CSRF/CORS hazards, securing `/actuator` management paths, and header leakages. |
| **06** | [Vulnerable & Outdated Components](file:///c:/Users/Admin/Desktop/projects/learning-repo/owasp-security-spring/modules/06-vulnerable-outdated-components.md) | Maven Dependency-Check configurations, Software Bill of Materials (SBOM) pipelines. |
| **07** | [Identification & Authentication Failures](file:///c:/Users/Admin/Desktop/projects/learning-repo/owasp-security-spring/modules/07-authentication-identification-failures.md) | Brute-force credentials stuffing blockages, Session Fixation protections, and MFA. |
| **08** | [Software & Data Integrity Failures](file:///c:/Users/Admin/Desktop/projects/learning-repo/owasp-security-spring/modules/08-software-data-integrity-failures.md) | Jackson insecure deserialization, XML External Entity (XXE) safe parsing. |
| **09** | [Security Logging & Monitoring Failures](file:///c:/Users/Admin/Desktop/projects/learning-repo/owasp-security-spring/modules/09-logging-monitoring-failures.md) | Log injection and forging sanitization, Spring Data Envers transactional audit trails. |
| **10** | [SSRF Mitigation](file:///c:/Users/Admin/Desktop/projects/learning-repo/owasp-security-spring/modules/10-ssrf-mitigation.md) | Server-Side Request Forgery, url validation filters in `RestTemplate` and `WebClient`. |
| **11** | [Final Capstone Project](file:///c:/Users/Admin/Desktop/projects/learning-repo/owasp-security-spring/modules/11-final-capstone-application-hardening.md) | Auditing and patching a vulnerable Spring Boot sandbox e-commerce platform. |

---

## Security Audit & Vulnerability Testing Setup

To analyze dependencies and scan Java code for OWASP vulnerabilities, configure the following plugin tools in your Maven `pom.xml` build lifecycle:

### 1. OWASP Dependency-Check Maven Plugin
To automatically scan your classpath dependencies for CVE alerts, configure this execution plugin:
```xml
<plugin>
    <groupId>org.owasp</groupId>
    <artifactId>dependency-check-maven</artifactId>
    <version>8.4.0</version>
    <executions>
        <execution>
            <goals>
                <goal>check</goal>
            </goals>
        </execution>
    </executions>
</plugin>
```
Run the scanner from your CLI terminal:
```bash
mvn dependency-check:check
```

### 2. Spring Boot Actuator Path Lockdown
Enforce strict path isolation in your `application.properties` configuration file:
```properties
management.endpoints.web.exposure.include=health,info,metrics
management.endpoint.health.show-details=when_authorized
```

---

## Grading Criteria & Defensive Success Metrics

Your performance in this course is evaluated based on the following defensive metrics:

*   **Access Control & Authorization Rigor (30%)**: Correctly structuring security contexts, preventing IDOR leaks, and enforcing method-level Spring Security filters.
*   **Input Sanitization & Injection Defense (35%)**: Eliminating query strings concatenation, command injection paths, and preventing XML External Entity (XXE) parser compromises.
*   **Data Integrity & Serialization Safeguards (25%)**: Hardening Jackson polymorphic formats, validating message signatures, and enforcing secure cryptosystem configurations.
*   **Audit Logging & Monitoring Compliance (10%)**: Implementing log forging sanitization and setting transactional system audits.
