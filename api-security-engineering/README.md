# CS-527: API Security Engineering & Access Control

Welcome to **CS-527: API Security Engineering & Access Control**. I am Professor Antigravity. In this course, we will study modern web application security architectures, protocol specifications, identity management integration, and fine-grained authorization filters.

Protecting application endpoints requires an in-depth understanding of multiple security mechanisms. Rather than relying on simple, single-factor credentials, modern enterprise architectures incorporate a hybrid defense strategy. This includes **stateful cookie-session tracking**, **stateless JWT validation**, **HMAC request signatures**, **SSO federation (OIDC & SAML 2.0)**, **passwordless biometric keys (WebAuthn)**, and **decoupled policy-as-code engines**.

Throughout this course, we will compare these security mechanisms and write production-grade implementations utilizing **Java 21**, **Spring Boot 3.x**, and **Spring Security 6.x**.

---

## Course Syllabus & Navigation

The course is divided into 9 comprehensive modules:

| Module | Core Classification | Focus Topics |
| :--- | :--- | :--- |
| **01** | [Session Auth & CSRF](file:///c:/Users/Admin/Desktop/projects/learning-repo/api-security-engineering/modules/01-session-auth-csrf.md) | Stateful cookies vs. stateless tokens, HttpOnly/Secure/SameSite flags, session fixation defenses, and Double-Submit Cookie CSRF protection. |
| **02** | [Token Auth & JWT](file:///c:/Users/Admin/Desktop/projects/learning-repo/api-security-engineering/modules/02-token-auth-jwt.md) | JWT specification (RFC 7519), signing algos (HS256 vs. RS256), public/private key generation, claims checks, and Access/Refresh token rotation. |
| **03** | [API Keys & HMAC](file:///c:/Users/Admin/Desktop/projects/learning-repo/api-security-engineering/modules/03-api-keys-hmac-signatures.md) | Key distribution, request signature patterns (AWS SigV4 style), HmacSHA256 calculations, replay protection (nonces/timestamps), and payload audits. |
| **04** | [OAuth 2.0 & OIDC](file:///c:/Users/Admin/Desktop/projects/learning-repo/api-security-engineering/modules/04-oauth2-oidc-protocols.md) | OAuth 2.0 vs. OpenID Connect, grant flows (Auth Code + PKCE, Client Credentials), scopes, userinfo routes, and Cognito JWKS local token parsing. |
| **05** | [SAML 2.0 Federation](file:///c:/Users/Admin/Desktop/projects/learning-repo/api-security-engineering/modules/05-saml-sso-federation.md) | OIDC vs. SAML 2.0 comparisons, IdP vs. SP mappings, SAML Assertions, XML DSIG validation, and XML External Entity (XXE) injection protections. |
| **06** | [MFA & WebAuthn](file:///c:/Users/Admin/Desktop/projects/learning-repo/api-security-engineering/modules/06-mfa-totp-webauthn.md) | Multi-factor configurations, TOTP time-window hashing (RFC 6238), WebAuthn/FIDO2 biometrics/passkeys, and cryptographic credential verifications. |
| **07** | [Access Control Models](file:///c:/Users/Admin/Desktop/projects/learning-repo/api-security-engineering/modules/07-authorization-rbac-abac-rebac.md) | Authorization architectures: RBAC (roles/hierarchies), ABAC (context/metadata attributes), and ReBAC (graph-based user-resource relations). |
| **08** | [Policy-as-Code (OPA)](file:///c:/Users/Admin/Desktop/projects/learning-repo/api-security-engineering/modules/08-policy-as-code-opa.md) | Decoupled authorization, OPA engines, writing rules in Rego, custom Spring Security AuthorizationManagers, and query caching policies. |
| **09** | [Final Capstone Gateway](file:///c:/Users/Admin/Desktop/projects/learning-repo/api-security-engineering/modules/09-final-capstone-gateway.md) | Designing a secure Enterprise Gateway coordinating session checks, HMAC validations, JWT decoders, OPA delegates, and secure logging. |

---

## Local Environment Configuration

To configure your workspace, ensure you have **Java 21** (JDK 21) installed, alongside **Maven 3.9+** and a running Docker environment (for local OPA and database instances).

### 1. Maven Dependency Configuration (`pom.xml`)
Inject the following dependencies into your Spring Boot Maven project configuration:
```xml
<dependencies>
    <!-- Core Spring Boot Web and Security -->
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-web</artifactId>
    </dependency>
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-security</artifactId>
    </dependency>
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-webflux</artifactId>
    </dependency>

    <!-- Asymmetric JWT Handlers (JJWT) -->
    <dependency>
        <groupId>io.jsonwebtoken</groupId>
        <artifactId>jjwt-api</artifactId>
        <version>0.12.5</version>
    </dependency>
    <dependency>
        <groupId>io.jsonwebtoken</groupId>
        <artifactId>jjwt-impl</artifactId>
        <version>0.12.5</version>
        <scope>runtime</scope>
    </dependency>
    <dependency>
        <groupId>io.jsonwebtoken</groupId>
        <artifactId>jjwt-jackson</artifactId>
        <version>0.12.5</version>
        <scope>runtime</scope>
    </dependency>

    <!-- Spring OAuth 2.0 Resource Server & Nimbus -->
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-oauth2-resource-server</artifactId>
    </dependency>

    <!-- SAML 2.0 Core XML Security (Apache Santuario) -->
    <dependency>
        <groupId>org.apache.santuario</groupId>
        <artifactId>xmlsec</artifactId>
        <version>3.0.3</version>
    </dependency>

    <!-- WebAuthn/FIDO2 Decoders -->
    <dependency>
        <groupId>com.webauthn4j</groupId>
        <artifactId>webauthn4j-core</artifactId>
        <version>0.22.0.RELEASE</version>
    </dependency>

    <!-- Testing Suite -->
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-test</artifactId>
        <scope>test</scope>
    </dependency>
    <dependency>
        <groupId>org.springframework.security</groupId>
        <artifactId>spring-security-test</artifactId>
        <scope>test</scope>
    </dependency>
</dependencies>
```

---

## Grading Criteria & Defensive Success Metrics

Your progress is evaluated based on the following engineering rubrics:

*   **Cryptographic Accuracy (30%)**: Correctly setting up key validations, signatures checking, and validation algorithms.
*   **Attack Resistance (25%)**: Implementing active defenses against path traversals, XXE injections, replay hacks, and CSRF hijacks.
*   **Filter Graph Integration (25%)**: Mapping security configurations inside the Spring Security filter chains without violating authorization boundaries.
*   **Verification Quality (20%)**: Writing mock tests and assertions targeting success/failure conditions.
