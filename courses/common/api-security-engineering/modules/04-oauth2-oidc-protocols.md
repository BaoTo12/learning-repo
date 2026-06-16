# Module 04: Federated Identity & OAuth 2.0 / OIDC

Welcome back class. Today we analyze **Federated Identity & OAuth 2.0 / OIDC (CS-527)**.

In modern enterprise systems, applications are rarely isolated. Users expect Single Sign-On (SSO) across multiple platforms without disclosing their password credentials to every sub-application. To solve this, we decouple authentication and authorization using federated protocols. We delegate user authentication to a dedicated Identity Provider (IdP), such as **AWS Cognito**, **Okta**, or **Auth0**, which issues signed tokens following the **OAuth 2.0** and **OpenID Connect (OIDC)** specifications.

Today we study federated identity protocols, analyze OIDC grant types, and configure a **Spring Security 6.x OAuth 2.0 Resource Server** to validate Cognito tokens.

---

## 1. Academic Lecture: Decoupled Authentication & Authorization Flows

### 1. OAuth 2.0 vs. OpenID Connect (OIDC)
*   **OAuth 2.0 (RFC 6749)**: A delegation framework focused on **Authorization** (delegated access). It issues an **Access Token** containing scopes (permissions) that grant a client application access to resources on behalf of the user. It does not define *how* the user authenticated or who they are.
*   **OpenID Connect (OIDC)**: An identity layer built on top of OAuth 2.0 focused on **Authentication**. It introduces the **ID Token** (always a JWT) and a standardized `/userinfo` endpoint. The ID token provides structured details about the authenticated subject (name, email, login timestamp).

### 2. Authorization Code Flow with PKCE (Proof Key for Code Exchange)
Historically, public clients (like single-page applications or mobile apps) used the *Implicit Flow*, where the Identity Provider returned the access token directly in the browser redirect URL. This is now deprecated due to token interception vulnerabilities.
Modern architectures mandate the **Authorization Code Flow with PKCE (RFC 7636)**:
1.  **Code Challenge**: The client generates a random string called `code_verifier`, hashes it using SHA-256 to create the `code_challenge`, and redirects the user to the IdP.
2.  **Authorization Code**: The user authenticates at the IdP. The IdP redirects back to the client with a temporary `authorization_code`.
3.  **Token Exchange**: The client sends the `authorization_code` and the raw `code_verifier` to the IdP's token endpoint.
4.  **Verification**: The IdP hashes the `code_verifier`. If it matches the original `code_challenge`, the IdP issues the tokens. An attacker intercepting the code cannot exchange it because they lack the verifier.

### 3. JWKS (JSON Web Key Set) and Cognito Validation
Identity Providers sign tokens using asymmetric key pairs and expose their public keys via a standard endpoint:
`https://cognito-idp.{region}.amazonaws.com/{userPoolId}/.well-known/jwks.json`
*   **Nimbus JWT Decoder**: Instead of hardcoding keys, Spring Security queries this URL, downloads the **JSON Web Key Set (JWKS)**, caches the keys locally, and uses the appropriate public key (matching the token's `kid` header) to validate signatures.

```text
[User SPA Client] ──(1. Access API with Bearer JWT)──> [Spring OAuth2 Resource Server]
                                                            │
                                                            ├─ Intercepts JWT Bearer
                                                            ├─ Extracts Key ID ('kid')
                                                            │
                                                    [Local JWKS Cache]
                                                            ├─ Matches kid?
                                                            ├─ Yes: Validate local RS256 signature
                                                            └─ No: Fetch JWKS from Cognito
                                                                      │
                                                                      ▼
                                                            [Cognito JWKS API]
                                                            (Download and update key sets)
```

---

## 2. Theory vs. Production Trade-offs

When choosing an identity integration flow, weigh grant types against client capabilities:

| OAuth 2.0 Grant Type | Client Type | Security Profile | Primary Use Case |
| :--- | :--- | :--- | :--- |
| **Auth Code + PKCE** | Public Client (SPA / Mobile) | Excellent (Code intercept resistant) | Single-page apps, Native iOS/Android apps |
| **Client Credentials** | Confidential Client (Server) | Strong (Secured server secrets) | Machine-to-machine backend microservices |
| **Implicit Flow** | Public Client | Deprecated (Token leakage vulnerability)| Do NOT use in modern architectures |
| **Resource Owner Password**| Trusted Client | Weak (Exposes user passwords to client)| Legacy migrations only |

---

## 3. How to Use: Spring Security Cognito Resource Server

Let us write a compile-grade Java 21 Spring Security configuration that sets up a stateless OAuth 2.0 Resource Server, pulls JWKS keys from a mock Cognito endpoint, and maps Cognito user groups to role authorities.

### A. The Insecure Token Parsing Pattern (Anti-Pattern)

Avoid manually decoding tokens using JSON libraries without verifying claims boundaries or validation keys:

```java
package com.security.api.util;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.Base64;
import java.util.Map;

public class NaiveTokenParser {
    // DANGER: Decoupled manual decoding without key verification is highly vulnerable.
    // An attacker can modify the user claims and send the altered payload. Without signature
    // checks, the system accepts the input as authentic.
    @SuppressWarnings("unchecked")
    public Map<String, Object> parseClaimsUnsafe(String bearerToken) throws Exception {
        String[] parts = bearerToken.split("\\.");
        String payloadJson = new String(Base64.getUrlDecoder().decode(parts[1]));
        return new ObjectMapper().readValue(payloadJson, Map.class); // VULNERABLE
    }
}
```

### B. The Hardened Cognito Resource Server (Production Pattern)

Here is the hardened pattern. We configure Spring Security to operate as a stateless OAuth2 Resource Server, specify the Cognito JWKS endpoint, and write a custom JwtAuthenticationConverter to extract Cognito group claims.

```java
package com.security.api.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.convert.converter.Converter;
import org.springframework.security.authentication.AbstractAuthenticationToken;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.security.oauth2.jwt.NimbusJwtDecoder;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationConverter;
import org.springframework.security.web.SecurityFilterChain;

import java.util.Collection;
import java.util.Collections;
import java.util.List;
import java.util.stream.Collectors;

@Configuration
@EnableWebSecurity
public class OAuth2ResourceServerConfig {

    private final String jwkSetUri = "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_mockPoolId/.well-known/jwks.json";

    @Bean
    public SecurityFilterChain resourceServerFilterChain(HttpSecurity http) throws Exception {
        http
            // Enforce stateless session policy (no JSESSIONID cookie creation)
            .sessionManagement(session -> session.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
            .csrf(csrf -> csrf.disable()) // Stateless APIs do not use cookies; CSRF can be safely disabled
            .authorizeHttpRequests(auth -> auth
                .requestMatchers("/api/public/**").permitAll()
                // Enforce role checks resolved from Cognito groups
                .requestMatchers("/api/admin/**").hasRole("ADMIN")
                .anyRequest().authenticated()
            )
            .oauth2ResourceServer(oauth2 -> oauth2
                .jwt(jwt -> jwt
                    // Inject JWKS URL decoder
                    .decoder(jwtDecoder())
                    // Inject custom claims converter
                    .jwtAuthenticationConverter(cognitoGroupsConverter())
                )
            );

        return http.build();
    }

    @Bean
    public JwtDecoder jwtDecoder() {
        // Build Nimbus decoder fetching from Cognito JWKS endpoint
        return NimbusJwtDecoder.withJwkSetUri(jwkSetUri).build();
    }

    @Bean
    public Converter<Jwt, ? extends AbstractAuthenticationToken> cognitoGroupsConverter() {
        JwtAuthenticationConverter converter = new JwtAuthenticationConverter();
        converter.setJwtGrantedAuthoritiesConverter(new Converter<Jwt, Collection<GrantedAuthority>>() {
            @Override
            public Collection<GrantedAuthority> convert(Jwt jwt) {
                // Cognito stores groups inside the "cognito:groups" claim array
                List<String> groups = jwt.getClaimAsStringList("cognito:groups");
                if (groups == null) {
                    return Collections.emptyList();
                }
                
                // Map groups to Spring Security granted authorities (ROLE_ prefixed)
                return groups.stream()
                    .map(group -> new SimpleGrantedAuthority("ROLE_" + group.toUpperCase()))
                    .collect(Collectors.toList());
            }
        });
        return converter;
    }
}
```

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Relying on OIDC ID tokens for API Resource Access
Submitting the OIDC ID Token inside the `Authorization: Bearer` header when querying backend API services.
*   **Why it fails**: ID Tokens are meant for client applications to read user metadata (such as profile photos or names). Backend resource servers should validate **Access Tokens**, which define scope permissions. Using ID tokens can lead to authorization bypasses if scopes are not checked.
*   **Mitigation**: Always request and validate OAuth 2.0 Access Tokens for resource API access, reserving ID tokens for authentication interface metadata rendering.

### Pitfall 2: Neglecting the token Audience (`aud`) validation claim
Verifying the signature of a token but skipping the verification of the audience field.
*   **Why it fails**: An attacker can obtain a valid signature token issued by the same IdP for a completely different client application, and present it to your API. If audience is unchecked, your server accepts it, compromising data boundaries.
*   **Mitigation**: Configure your `JwtDecoder` validator rules to explicitly check that the `aud` claim matches your specific Client ID.

---

## 5. Socratic Review Questions

### Question 1
Why does the Authorization Code Flow + PKCE mitigate code interception vulnerabilities in public client applications where client secrets cannot be securely stored?

#### Answer
In public clients, standard client secrets would be exposed. Without a secret, anyone intercepting the authorization code could exchange it for tokens. PKCE introduces a dynamic, one-time secret: the `code_verifier`. The client sends the *hashed* version (`code_challenge`) on the initial redirect. When exchanging the code, the client must present the raw `code_verifier`. An attacker intercepting the code lacks the raw verifier and cannot guess it, failing the exchange validation check at the Identity Provider.

### Question 2
What is the role of a JSON Web Key (JWK) in federated security architectures, and why does it contain a `kid` property?

#### Answer
An Identity Provider signs tokens using a private key and publishes the public verification key inside a JWK structure (which defines parameters like RSA modulus `n` and exponent `e`). Because providers periodically rotate keys to maintain security, a JWKS contain multiple keys. Each key has a unique **Key ID (`kid`)**. When a client presents a token, the verifier inspects the token's header `kid` parameter to locate the matching public key in the JWKS list, enabling automated, zero-downtime key rotation.

---

## 6. Hands-on Challenge: Cognito Custom Claims Converter

### The Challenge
In this challenge, you will implement a Spring Security Jwt converter in Java.
Your task:
1. Complete the `convert` method inside `CognitoRoleAuthorityConverter`.
2. Extract the claim named `"cognito:groups"` as a string list.
3. Extract the scope claim named `"scope"` as a space-separated string (e.g. `"read write"`).
4. Map Cognito groups to authorities with a `"ROLE_"` prefix.
5. Map scopes to authorities with a `"SCOPE_"` prefix.
6. Return the combined collection.

Complete the implementation below:

```java
package com.security.api;

import org.springframework.core.convert.converter.Converter;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.oauth2.jwt.Jwt;
import java.util.ArrayList;
import java.util.Collection;
import java.util.List;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class CognitoRoleAuthorityConverter implements Converter<Jwt, Collection<GrantedAuthority>> {

    @Override
    public Collection<GrantedAuthority> convert(Jwt jwt) {
        Collection<GrantedAuthority> authorities = new ArrayList<>();

        // TODO: Implement the conversion logic:
        // 1. Extract "cognito:groups" list using jwt.getClaimAsStringList("cognito:groups").
        //    If present, loop and add SimpleGrantedAuthority("ROLE_" + group.toUpperCase()).
        // 2. Extract "scope" string using jwt.getClaimAsString("scope").
        //    If present, split the string by space " ", loop and add SimpleGrantedAuthority("SCOPE_" + scope.toUpperCase()).
        // 3. Return the combined authorities collection.

        return authorities;
    }
}
```

Write the conversion rules and verifications. Save the completed file and verify that role/scope mapping works under `modules/04-oauth2-oidc-protocols.md`.
