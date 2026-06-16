# Module 01: Stateful Session Security & CSRF Mitigations

Welcome class. Today we analyze **Stateful Session Security & CSRF Mitigations (CS-527)**.

Traditional web applications rely on cookies to maintain user state. However, because browsers automatically append cookies to all HTTP requests directed to a target domain, session-based designs are inherently vulnerable to ambient credential hijacks. If a user clicks a malicious link on an external website, the browser will silently transmit the user's session identifier, allowing attackers to execute unauthorized actions on behalf of the victim.

Today we study **Stateful Session Management**, analyze **Cookie Security Attributes**, dissect **Cross-Site Request Forgery (CSRF)**, and write a hardened session filter configuration in **Spring Security 6.x** enforcing Double-Submit Cookie validations.

---

## 1. Academic Lecture: Cookie-Based Authentication & Vulnerability Surfaces

### 1. Stateful Sessions vs. Stateless Tokens
*   **Stateful Sessions (Cookie-Based)**: The server creates a session entry in memory or database, generates a random unique identifier (Session ID), and returns it via a `Set-Cookie` header. The client stores it, and the browser automatically attaches it to subsequent requests. The server must check the session database on every request.
*   **Stateless Tokens (JWT-Based)**: The server signs a payload containing claims and returns it to the client. The client stores it (often in LocalStorage or sessionStorage) and sends it manually via an `Authorization: Bearer <token>` header. The server verifies the cryptographic signature locally without looking up database state.

### 2. Cookie Security attributes
To protect session cookies from exposure and theft, we configure three essential attributes:
*   **`HttpOnly`**: Prevents client-side scripts (JavaScript) from accessing the cookie via `document.cookie`. This prevents Cross-Site Scripting (XSS) tokens theft.
*   **`Secure`**: Directs the browser to only transmit the cookie over encrypted connections (HTTPS). This prevents network sniffing.
*   **`SameSite`**: Restricts cookie transmission on cross-origin requests. Values:
    *   `Strict`: Cookie is never sent on cross-site requests (e.g., clicking a link from an external site to your app won't send the session).
    *   `Lax`: Cookie is sent on top-level GET navigations (e.g., clicking links) but blocked on cross-origin POSTs. Standard safe default.
    *   `None`: Cookie is sent on all requests. Requires `Secure`.

### 3. Session Fixation & CSRF Mechanics
*   **Session Fixation**: An attacker provisions a valid session ID from the server and forces the candidate's browser to adopt it (e.g., by sending a link containing a session parameter). When the candidate logs in, the server elevates the privilege of that same session ID. The attacker can then access the active account. We mitigate this by generating a *new* session ID on every successful authentication.
*   **Double-Submit Cookie CSRF Defense**: The client-side application reads a unique CSRF token from a dedicated cookie (e.g., `XSRF-TOKEN`). For every state-changing request (POST, PUT, DELETE), the application client extracts this value and submits it inside a custom HTTP header (e.g., `X-XSRF-TOKEN`). The server compares the token in the cookie against the token in the header. Since cross-origin scripts cannot read cookies due to the Same-Origin Policy, they cannot forge the matching HTTP header, and the request is rejected.

```text
[Browser User] ──(1. Click Submit Form)──> [Spring Security Gateway]
      │                                                │
      ├─ Cookie: JSESSIONID=abc                        ├─ Intercepts Filter Chain
      ├─ Cookie: XSRF-TOKEN=xyz                        ├─ Extracts Cookie CSRF: xyz
      └─ Header: X-XSRF-TOKEN=xyz ─────────────────────┼─ Extracts Header CSRF: xyz
                                                       │
                                                       ▼
                                            Assert: xyz == xyz?
                                            - Yes: Pass request to controller
                                            - No: Return 403 Forbidden
```

---

## 2. Theory vs. Production Trade-offs

When choosing an authentication state strategy, weigh session databases against token models:

| Dimension / Metric | Stateful Sessions (Database-Backed) | Stateless Bearer Tokens (JWT) | Hybrid (Token Cache in Redis) |
| :--- | :--- | :--- | :--- |
| **Server State** | High (Requires database lookup per call) | None (Stateless verification) | Medium (Memory database checks) |
| **Instant Revocation**| Excellent (Delete entry in DB) | Poor (Valid until expiration time) | Excellent (Remove key from cache) |
| **Client Storage** | Secure Cookies (Automatic) | LocalStorage (Vulnerable to XSS) | Secure Cookies or Memory |
| **CSRF Vulnerability**| High (Requires active CSRF token repo) | None (No automatic headers match) | High (If cookies are utilized) |
| **Scalability** | Hard (Requires session clustering) | Excellent (Horizontal scale) | Good (Redis cluster dependency) |

---

## 3. How to Use: Hardened Session Filter Chain

Let us write a compile-grade Java 21 Spring Security configuration that sets up secure session creation policies, enables session fixation protection, and configures a `CookieCsrfTokenRepository`.

### A. The Vulnerable Security Configuration (Anti-Pattern)

Avoid disabling CSRF protection and allowing unrestricted session creations:

```java
package com.security.api.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.web.SecurityFilterChain;

@Configuration
public class NaiveSecurityConfig {

    // DANGER: Disabling CSRF exposes browser clients to session hijacking.
    // Setting session policy to always create entries wastes server RAM.
    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        http
            .csrf(csrf -> csrf.disable()) // VULNERABLE
            .authorizeHttpRequests(auth -> auth.anyRequest().permitAll());
        return http.build();
    }
}
```

### B. The Hardened Security Filter Chain (Production Pattern)

Here is the hardened pattern. We write a configuration class that registers a secure cookie CSRF repository with custom SameSite headers, configures session fixation migrations, and restricts session limits.

```java
package com.security.api.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.csrf.CookieCsrfTokenRepository;
import org.springframework.security.web.csrf.CsrfTokenRequestAttributeHandler;

@Configuration
@EnableWebSecurity
public class SecureSecurityConfig {

    @Bean
    public SecurityFilterChain securityFilterChain(HttpSecurity http) throws Exception {
        // Enforce Double-Submit Cookie configuration
        CookieCsrfTokenRepository tokenRepository = CookieCsrfTokenRepository.withHttpOnlyFalse();
        tokenRepository.setCookiePath("/");
        // Note: SameSite cookie headers are typically configured via Servlet filters 
        // or Spring Boot server properties: server.servlet.session.cookie.same-site=lax
        
        http
            .csrf(csrf -> csrf
                .csrfTokenRepository(tokenRepository)
                // Enforce deferred CSRF token resolving for performance
                .csrfTokenRequestHandler(new CsrfTokenRequestAttributeHandler())
            )
            .sessionManagement(session -> session
                // Create sessions only when required by the application
                .sessionCreationPolicy(SessionCreationPolicy.IF_REQUIRED)
                // Prevent session fixation: generate a new session ID upon successful login
                .sessionFixation(sessionFixation -> sessionFixation.changeSessionId())
                // Enforce concurrent session constraints
                .maximumSessions(1)
                .maxSessionsPreventsLogin(true)
            )
            .authorizeHttpRequests(auth -> auth
                .requestMatchers("/api/auth/login").permitAll()
                .anyRequest().authenticated()
            );

        return http.build();
    }
}
```

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Disabling CSRF for APIs consumed by single-page apps (SPAs)
Assuming that since an application serves JSON endpoints, it does not need CSRF protection.
*   **Why it fails**: If the SPA store session identifiers in cookies, browser extensions or cross-origin forms can still trigger state-changing HTTP queries.
*   **Mitigation**: Do not disable CSRF unless you use stateless bearer token headers exclusively. If utilizing session cookies, always enable the `CookieCsrfTokenRepository`.

### Pitfall 2: SameSite=Strict on redirect login callbacks
Configuring session cookies with `SameSite=Strict`.
*   **Why it fails**: When users click a redirect login link from an identity provider (e.g. AWS Cognito), the landing request is cross-origin. The browser blocks the cookie transmission, forcing the user to appear unauthenticated on entry.
*   **Mitigation**: Use `SameSite=Lax` for session cookies to allow session transmission on top-level GET transitions, protecting POSTs.

---

## 5. Socratic Review Questions

### Question 1
Why does setting `HttpOnly=true` on a cookie protect it from XSS theft but fail to protect against CSRF attacks?

#### Answer
`HttpOnly=true` blocks JavaScript code from reading the cookie value (e.g. `document.cookie` returns empty), preventing malicious scripts from stealing the session token and sending it to an external database. However, CSRF attacks do not require reading the cookie value. The browser automatically appends all matching domain cookies to outgoing HTTP requests, meaning the session cookie is transmitted even if JavaScript cannot inspect it.

### Question 2
How does Spring Security's `sessionFixation().changeSessionId()` mitigate session fixation exploits?

#### Answer
If an attacker forces a candidate browser to adopt a specific session identifier (e.g., `JSESSIONID=fixed_value`), that ID remains active before authentication. When the candidate logs in, Spring Security intercepts the request, copies all session attributes, invalidates the old `fixed_value` session, and issues a new session ID (e.g., `JSESSIONID=new_value`). Since the attacker only knows the `fixed_value`, they lose access.

---

## 6. Hands-on Challenge: CSRF Integration Test Suite

### The Challenge
In this challenge, you will implement an integration test using Spring MockMvc to verify that CSRF protections are correctly enforced.
Your task:
1. Complete the implementation of the `TestCsrfBehavior` suite.
2. Verify that a POST request to `/api/data` is rejected (HTTP 403) when no CSRF parameters are present.
3. Verify that a POST request is accepted (HTTP 200) when the Spring Security CSRF token is correctly injected via the test utility.

Complete the implementation stub below:

```java
package com.security.api;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.csrf;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
public class TestCsrfBehavior {

    @Autowired
    private MockMvc mockMvc;

    @Test
    public void testPostRequestWithoutCsrfIsForbidden() throws Exception {
        // TODO: Perform a POST request to "/api/data" with mock JSON content.
        // Assert that the response returns status().isForbidden() (HTTP 403).
    }

    @Test
    public void testPostRequestWithCsrfIsAllowed() throws Exception {
        // TODO: Perform a POST request to "/api/data" with mock JSON content.
        // Inject the CSRF request post-processor: post("/api/data").with(csrf())
        // Assert that the response returns status().isOk() (HTTP 200).
    }
}
```

Write the test assertions. Save the completed file and verify that the integration tests execute successfully under `modules/01-session-auth-csrf.md`.
