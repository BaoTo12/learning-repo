# Chapter 16: Edge Security & OAuth 2.0 Access Delegation

In a microservices architecture, securing backend endpoints is a primary design concern. If every microservice implements its own authentication forms, user databases, and credential validation logic, the codebase becomes bloated and hard to maintain. A secure architecture centralizes authentication at the network edge (the API Gateway) and delegates identity management to a specialized Identity Provider (IdP) using open standards.

This chapter covers the technical implementation of **Edge Security** and **OAuth 2.0 Access Delegation**. We will analyze the core concepts of OAuth 2.0 and OpenID Connect (OIDC). We will write a Docker configuration to spin up a **Keycloak** server, register realms, clients, and roles, and secure the API Gateway using Spring Security and OAuth 2.0 Resource Server dependencies. We will configure route-level authorization filters to block unauthorized traffic at the edge, write a custom Keycloak JWT parser in Java, configure downstream microservices to validate propagated tokens, and implement inter-service token propagation.

---

## Learning Objectives

By the end of this chapter, you will be able to:
1. Explain the differences between authentication, authorization, and access delegation.
2. Outline the core actors of the OAuth 2.0 framework and OIDC protocol layers.
3. Configure and deploy a Keycloak identity server using Docker Compose.
4. Set up Keycloak realms, clients, client secrets, roles, and user profiles.
5. Retrieve OAuth 2.0 tokens using `curl` and form-encoded payloads.
6. Configure Spring Cloud Gateway as an OAuth 2.0 Login Client and resource routing edge.
7. Implement user role extraction from Keycloak JWT custom JSON claims in Java.
8. Configure downstream Spring microservices as OAuth 2.0 Resource Servers validating JWT tokens.
9. Implement a Spring RestTemplate interceptor to propagate JWT bearer tokens in inter-service calls.
10. Extract and verify custom token claims (such as tenant IDs) within a Spring Security Web Filter.
11. Write security unit tests to verify authorization rules for endpoint GET, POST, and DELETE calls.

---

## 16.1 Security at the Edge: Gateway vs. Downstream Services

In a monolithic application, security is handled in a single process. When transitioning to microservices, securing each service individually introduces architectural problems:
* **Code Duplication**: Every service must implement security logic.
* **Tight Coupling**: Downstream services become tightly coupled to user storage databases or corporate directories (LDAP/Active Directory).
* **High Database Overhead**: Validating user credentials constantly burdens databases.

### The Edge Security Pattern
To solve this, we centralize security at the network edge. The API Gateway acts as the gatekeeper:

```
[ Client ] --( Credentials )--> [ API Gateway (Edge) ] <---> [ Keycloak (IdP) ]
                                      |
                               ( Validates JWT )
                                      |
                                      v (Passes Bearer Token)
                              [ Downstream Services ]
```

The client first authenticates at the edge. Downstream microservices sit behind the firewall and trust the Gateway's validations, verifying the propagated digital tokens on each request:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//f9c06346-608b-4b11-93aa-6b0148cc4a3d/markdown_0/imgs/img_in_image_box_180_104_932_861.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T09%3A47%3A41Z%2F-1%2F%2F198e3b33ac775b8a07c08272834b47fb841b9d9c2a2b0e6a394a53ed09a15f0a" alt="Image" width="77%" /></div>
<div style="text-align: center;">Figure 9.1: Keycloak allows a user to authenticate without having to present credentials constantly.</div>

---

## 16.2 Core OAuth 2.0 and OpenID Connect (OIDC) Protocols

OAuth 2.0 is an authorization framework that enables a third-party application to obtain limited access to an HTTP service, either on behalf of a resource owner or by allowing the third-party application to obtain access on its own behalf.

OpenID Connect (OIDC) is an identity layer built on top of the OAuth 2.0 protocol. It allows clients to verify the identity of the end-user based on the authentication performed by an Authorization Server.

### The Four Core Actors of OAuth 2.0
1. **Resource Owner**: Typically the end-user who grants access to a protected resource.
2. **Client**: The application making protected resource requests on behalf of the Resource Owner (e.g. API Gateway, SPA frontend).
3. **Resource Server**: The microservice hosting the protected data, capable of accepting and validating access tokens.
4. **Authorization Server**: The server issuing access tokens to the client after successfully authenticating the Resource Owner (e.g., Keycloak).

### Token Classifications
* **Access Token**: A string representing an authorization issued to the client. Most commonly structured as a **JSON Web Token (JWT)**, which is cryptographically signed using public/private key pairs (RS256).
* **Refresh Token**: A long-lived token used by the client to obtain a new access token without requiring user interaction when the current access token expires.
* **ID Token**: An OIDC-specific JWT containing claims about the identity of the authenticated user (e.g. name, email, profile picture).

---

## 16.3 Deploying Keycloak with Docker Compose

Keycloak is a leading open source identity and access management server. We run Keycloak in our local Docker mesh, using the official image:

```yaml
version: '3.8'

services:
  keycloak:
    image: jboss/keycloak:15.0.2
    container_name: keycloak_server
    environment:
      KEYCLOAK_USER: admin
      KEYCLOAK_PASSWORD: adminpassword
      DB_VENDOR: H2
    ports:
      - "8080:8080"
    networks:
      - microservices-network

networks:
  microservices-network:
    driver: bridge
```

Run this command to spin up Keycloak:
```bash
docker-compose up -d keycloak
```

Once started, access the console at `http://localhost:8080/auth/` and log in using the admin credentials.

---

## 16.4 Keycloak Administration & Realm Configuration

Keycloak organizes users and client applications into **Realms**:

### 1. Realms
A realm is a tenant domain. It manages a set of users, credentials, roles, and groups. The default realm is `master`, which is reserved for admin tasks. For our microservices, we create a new realm named `spmia-realm`.

### 2. Clients
Clients are applications that request user authentication. We register the API Gateway as a client:
* **Client ID**: `ostock`
* **Access Type**: `confidential` (requires a client secret to exchange authorization codes)
* **Valid Redirect URIs**: `http://localhost:8086/*` (representing the API Gateway host address)

On the client credentials tab, copy the auto-generated **Client Secret** (e.g., `5988f899-a5bf-4f76-b15f-f1cd0d2c81ba`).

### 3. Roles
We create two realm roles to manage user permissions:
* `USER`: Standard read permissions.
* `ADMIN`: Write, edit, and delete permissions.

### 4. Users
We register a test user (e.g., `testuser`) in `spmia-realm`, set a permanent password, and map the roles on the **Role Mappings** tab:

```
[ Realm: spmia-realm ]
        |
        +---> [ Client: ostock ] (Secret: 5988f899...)
        |
        +---> [ Roles: USER, ADMIN ]
        |
        +---> [ User: testuser ] --( Assigned Roles )--> USER, ADMIN
```

---

## 16.5 Acquiring Tokens using OAuth 2.0 Form Payloads

To acquire an access token, the client sends a `POST` request to Keycloak's token endpoint using form-encoded parameters:

* **Endpoint**: `POST /auth/realms/spmia-realm/protocol/openid-connect/token`
* **Headers**: `Content-Type: application/x-www-form-urlencoded`

### 1. The Token Request (cURL)
```bash
curl -X POST http://localhost:8080/auth/realms/spmia-realm/protocol/openid-connect/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=password" \
  -d "client_id=ostock" \
  -d "client_secret=5988f899-a5bf-4f76-b15f-f1cd0d2c81ba" \
  -d "username=testuser" \
  -d "password=testpassword"
```

### 2. The Token Response
On successful authentication, Keycloak returns the JSON token payload:

```json
{
  "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCIgOiAiSldUIiwia2lkIiA6IC...",
  "expires_in": 3600,
  "refresh_expires_in": 1800,
  "refresh_token": "eyJhbGciOiJSUzI1NiIsInR5cCIgOiAiSldUIiwia2lkIiA6...",
  "token_type": "Bearer",
  "not-before-policy": 0,
  "session_state": "d3d28da8-22b9-4a37-b7b9-c1ec66ef7b92",
  "scope": "profile email"
}
```

---

## 16.6 Configuring Spring Cloud Gateway as an Edge Security Client

The Spring Cloud Gateway intercepts incoming traffic and handles OAuth 2.0 login redirect flows:

### 1. Maven Dependencies (`pom.xml`)
```xml
<dependencies>
    <!-- Spring Cloud Gateway routing -->
    <dependency>
        <groupId>org.springframework.cloud</groupId>
        <artifactId>spring-cloud-starter-gateway</artifactId>
    </dependency>
    <!-- Spring Security OAuth2 Client for OAuth2 logins -->
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-oauth2-client</artifactId>
    </dependency>
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-security</artifactId>
    </dependency>
</dependencies>
```

---

### 2. Application Configuration (`application.yml`)
```yaml
server:
  port: 8086

spring:
  security:
    oauth2:
      client:
        registration:
          keycloak:
            client-id: ftgo-gateway
            client-secret: ftgo-gateway-secret
            authorization-grant-type: authorization_code
            redirect-uri: "{baseUrl}/login/oauth2/code/{registrationId}"
            scope: openid, profile, email
        provider:
          keycloak:
            issuer-uri: http://localhost:8080/auth/realms/ftgo-realm
            user-name-attribute: preferred_username

  cloud:
    gateway:
      routes:
        - id: order-service
          uri: lb://order-service
          predicates:
            - Path=/v1/orders/**
          filters:
            # Propagate JWT token to downstream microservices in headers
            - TokenRelay
```

---

### 3. API Gateway WebFlux Security Configuration

```java
package com.ftgo.gateway.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.web.reactive.EnableWebFluxSecurity;
import org.springframework.security.config.web.server.ServerHttpSecurity;
import org.springframework.security.web.server.SecurityWebFilterChain;

@Configuration
@EnableWebFluxSecurity
public class GatewaySecurityConfig {

    @Bean
    public SecurityWebFilterChain springSecurityFilterChain(ServerHttpSecurity http) {
        http
            .csrf().disable()
            .authorizeExchange()
                // Allow static resources and discovery routes publicly
                .pathMatchers("/actuator/**", "/eureka/**").permitAll()
                // Enforce authentication for all business microservice endpoints
                .anyExchange().authenticated()
            .and()
                // Enable OAuth2 login flow redirecting to Keycloak
                .oauth2Login()
            .and()
                // Configure gateway as a resource server validating JWTs
                .oauth2ResourceServer().jwt();
        
        return http.build();
    }
}
```

---

## 16.7 Custom Keycloak JWT Authorization Converter

By default, Spring Security maps claims from standard JWT profiles. Keycloak, however, stores user roles in custom JSON claim locations (inside the `realm_access.roles` nested array):

```json
{
  "iss": "http://localhost:8080/auth/realms/ftgo-realm",
  "sub": "user_id_1001",
  "realm_access": {
    "roles": [
      "USER",
      "ADMIN"
    ]
  }
}
```

We write a custom `Converter` in Java to extract these roles and map them to Spring Security `GrantedAuthority` objects:

```java
package com.ftgo.order.security;

import org.springframework.core.convert.converter.Converter;
import org.springframework.security.authentication.AbstractAuthenticationToken;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;
import org.springframework.security.oauth2.server.resource.authentication.JwtGrantedAuthoritiesConverter;

import java.util.Collection;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

public class KeycloakGrantedAuthoritiesConverter implements Converter<Jwt, AbstractAuthenticationToken> {

    private final JwtGrantedAuthoritiesConverter defaultAuthoritiesConverter = new JwtGrantedAuthoritiesConverter();

    @Override
    public AbstractAuthenticationToken convert(Jwt jwt) {
        // 1. Get default Spring OAuth2 authorities
        Collection<GrantedAuthority> authorities = defaultAuthoritiesConverter.convert(jwt);

        // 2. Extract Keycloak custom realm roles
        Map<String, Object> realmAccess = jwt.getClaim("realm_access");
        if (realmAccess != null && realmAccess.containsKey("roles")) {
            @SuppressWarnings("unchecked")
            List<String> roles = (List<String>) realmAccess.get("roles");
            
            // Map roles to SimpleGrantedAuthority with standard ROLE_ prefix
            List<SimpleGrantedAuthority> keycloakAuthorities = roles.stream()
                    .map(role -> new SimpleGrantedAuthority("ROLE_" + role))
                    .collect(Collectors.toList());
            
            authorities.addAll(keycloakAuthorities);
        }

        return new JwtAuthenticationToken(jwt, authorities, jwt.getClaim("preferred_username"));
    }
}
```

---

## 16.8 Securing Downstream Microservices

Downstream microservices (e.g. `Order Service`) act as OAuth 2.0 Resource Servers, validating the JWT tokens propagated by the API Gateway:

### 1. Maven Dependencies (`pom.xml`)
```xml
<dependencies>
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-web</artifactId>
    </dependency>
    <!-- OAuth2 Resource Server for validating JWTs -->
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-oauth2-resource-server</artifactId>
    </dependency>
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-security</artifactId>
    </dependency>
</dependencies>
```

---

### 2. Application Properties (`application.properties`)
```properties
server.port=8180

# The Keycloak issuer URI used to fetch JWKS (JSON Web Key Sets) public keys to validate JWT signatures
spring.security.oauth2.resourceserver.jwt.issuer-uri=http://localhost:8080/auth/realms/ftgo-realm
```

---

### 3. Resource Server Security Configuration

```java
package com.ftgo.order.config;

import com.ftgo.order.security.KeycloakGrantedAuthoritiesConverter;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpMethod;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.web.SecurityFilterChain;

@Configuration
@EnableWebSecurity
public class ResourceServerSecurityConfig {

    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        http
            .csrf().disable()
            .authorizeRequests()
                // Read operations: Allowed for both USER and ADMIN roles
                .antMatchers(HttpMethod.GET, "/v1/orders/**").hasAnyRole("USER", "ADMIN")
                // Write/Delete operations: Restricted to ADMIN role only
                .antMatchers(HttpMethod.POST, "/v1/orders/**").hasRole("ADMIN")
                .antMatchers(HttpMethod.DELETE, "/v1/orders/**").hasRole("ADMIN")
                .anyRequest().authenticated()
            .and()
                .oauth2ResourceServer()
                // Configure our custom JWT parser to extract Keycloak roles
                .jwt()
                .jwtAuthenticationConverter(new KeycloakGrantedAuthoritiesConverter());
        
        return http.build();
    }
}
```

---

## 16.9 Inter-Service JWT Token Propagation

When a downstream service calls another microservice, it must forward the JWT bearer token it received in the incoming request to authorize the downstream call.

We implement this by configuring a **Spring RestTemplate Interceptor** that pulls the JWT token from the current Security Context and injects it into outgoing headers:

```
[ Client ] --( JWT )--> [ API Gateway ] --( JWT )--> [ Service A ]
                                                         |
                                             ( Context Token Extract )
                                                         |
                                                         v (Interceptor Inject JWT)
                                                     [ Service B ]
```

```java
package com.ftgo.order.security;

import org.springframework.http.HttpRequest;
import org.springframework.http.client.ClientHttpRequestExecution;
import org.springframework.http.client.ClientHttpRequestInterceptor;
import org.springframework.http.client.ClientHttpResponse;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;
import java.io.IOException;

public class UserContextInterceptor implements ClientHttpRequestInterceptor {

    @Override
    public ClientHttpResponse intercept(HttpRequest request, byte[] body, ClientHttpRequestExecution execution) 
            throws IOException {
        
        // Extract authenticated JwtAuthenticationToken from Spring Security Context Holder
        if (SecurityContextHolder.getContext().getAuthentication() instanceof JwtAuthenticationToken) {
            JwtAuthenticationToken authenticationToken = 
                (JwtAuthenticationToken) SecurityContextHolder.getContext().getAuthentication();
            
            String tokenValue = authenticationToken.getToken().getTokenValue();
            
            // Forward Bearer token into outgoing HTTP header context
            request.getHeaders().add("Authorization", "Bearer " + tokenValue);
        }

        return execution.execute(request, body);
    }
}
```

This interceptor is registered with a RestTemplate configuration:
```java
package com.ftgo.order.config;

import com.ftgo.order.security.UserContextInterceptor;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.client.RestTemplate;
import java.util.Collections;

@Configuration
public class RestClientConfig {

    @Bean
    public RestTemplate restTemplate() {
        RestTemplate restTemplate = new RestTemplate();
        // Register token propagation interceptor
        restTemplate.setInterceptors(Collections.singletonList(new UserContextInterceptor()));
        return restTemplate;
    }
}
```

---

## 16.10 ThreadLocal Custom Claim Propagation (Multi-Tenancy)

In multi-tenant microservices, we often need to extract custom token claims (e.g. `tenant_id` mapped via Keycloak claims) and propagate them through our services. 

We write a ThreadLocal utility class and Web Filter to capture this claim context:

```java
package com.ftgo.order.security;

public class UserContext {
    public static final String CORRELATION_ID = "correlation-id";
    public static final String AUTH_TOKEN = "auth-token";
    public static final String TENANT_ID = "tenant-id";

    private static final ThreadLocal<String> correlationId = new ThreadLocal<>();
    private static final ThreadLocal<String> authToken = new ThreadLocal<>();
    private static final ThreadLocal<String> tenantId = new ThreadLocal<>();

    public static String getCorrelationId() { return correlationId.get(); }
    public static void setCorrelationId(String id) { correlationId.set(id); }

    public static String getAuthToken() { return authToken.get(); }
    public static void setAuthToken(String token) { authToken.set(token); }

    public static String getTenantId() { return tenantId.get(); }
    public static void setTenantId(String id) { tenantId.set(id); }
}
```

```java
package com.ftgo.order.security;

import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.stereotype.Component;
import javax.servlet.*;
import javax.servlet.http.HttpServletRequest;
import java.io.IOException;

@Component
public class UserContextFilter implements Filter {

    @Override
    public void doFilter(ServletRequest request, ServletResponse response, FilterChain chain) 
            throws IOException, ServletException {
        
        HttpServletRequest httpServletRequest = (HttpServletRequest) request;
        
        // Extract correlation ID from HTTP headers
        UserContext.setCorrelationId(httpServletRequest.getHeader(UserContext.CORRELATION_ID));
        
        // Extract tenant ID custom claim from security context JWT
        if (SecurityContextHolder.getContext().getAuthentication() != null &&
            SecurityContextHolder.getContext().getAuthentication().getPrincipal() instanceof Jwt) {
            Jwt jwt = (Jwt) SecurityContextHolder.getContext().getAuthentication().getPrincipal();
            UserContext.setTenantId(jwt.getClaim("tenant_id"));
            UserContext.setAuthToken(jwt.getTokenValue());
        }
        
        chain.doFilter(request, response);
    }
}
```

---

## 16.11 Security Unit Testing with MockMvc

To verify our authorization rules without running the Keycloak server, we write unit tests. We mock JWT access tokens using Spring Security Test dependencies:

```java
package com.ftgo.order;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors;
import org.springframework.test.web.servlet.MockMvc;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
public class OrderSecurityUnitTests {

    @Autowired
    private MockMvc mockMvc;

    @Test
    public void getOrder_withUserRole_returnsOk() throws Exception {
        mockMvc.perform(get("/v1/orders/order-101")
                // Mock a valid JWT access token with the USER role
                .with(SecurityMockMvcRequestPostProcessors.jwt()
                        .jwt(jwt -> jwt.claim("preferred_username", "alice"))
                        .authorities(new org.springframework.security.core.authority.SimpleGrantedAuthority("ROLE_USER")))
                .accept(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk());
    }

    @Test
    public void deleteOrder_withUserRole_returnsForbidden() throws Exception {
        mockMvc.perform(delete("/v1/orders/order-101")
                // Mock a JWT with the USER role (which lacks admin permissions)
                .with(SecurityMockMvcRequestPostProcessors.jwt()
                        .authorities(new org.springframework.security.core.authority.SimpleGrantedAuthority("ROLE_USER"))))
                .andExpect(status().isForbidden());
    }

    @Test
    public void deleteOrder_withAdminRole_returnsOk() throws Exception {
        mockMvc.perform(delete("/v1/orders/order-101")
                // Mock a JWT with the ADMIN role
                .with(SecurityMockMvcRequestPostProcessors.jwt()
                        .authorities(new org.springframework.security.core.authority.SimpleGrantedAuthority("ROLE_ADMIN"))))
                .andExpect(status().isOk());
    }
}
```

---

## 16.12 OAuth 2.0 Client Credentials Grant Flow (M2M System-to-System Auth)

In a microservices mesh, backend jobs, messaging consumers, or cron tasks often need to make API calls to other services without a user context. In these cases, we cannot propagate a user's bearer token. Instead, the calling service must use the **OAuth 2.0 Client Credentials Grant Flow** to request a machine-to-machine (M2M) JWT token directly from Keycloak.

### 1. Spring Security Client Configuration: `application.yml`
Configure the client credentials client registration under the Spring security OAuth2 schema:

```yaml
spring:
  security:
    oauth2:
      client:
        registration:
          kitchen-service-m2m:
            client-id: kitchen-service
            client-secret: kitchen-service-m2m-secret
            authorization-grant-type: client_credentials
            scope: internal-access
        provider:
          keycloak:
            token-uri: http://localhost:8080/auth/realms/ftgo-realm/protocol/openid-connect/token
```

### 2. Register Authorized Client Manager Beans
To manage token requests, expirations, and renewals programmatically, we register an `OAuth2AuthorizedClientManager` bean:

```java
package com.ftgo.order.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.oauth2.client.AuthorizedClientServiceOAuth2AuthorizedClientManager;
import org.springframework.security.oauth2.client.OAuth2AuthorizedClientProvider;
import org.springframework.security.oauth2.client.OAuth2AuthorizedClientProviderBuilder;
import org.springframework.security.oauth2.client.OAuth2AuthorizedClientService;
import org.springframework.security.oauth2.client.registration.ClientRegistrationRepository;

@Configuration
public class OAuth2ClientConfig {

    @Bean
    public AuthorizedClientServiceOAuth2AuthorizedClientManager authorizedClientManager(
            ClientRegistrationRepository clientRegistrationRepository,
            OAuth2AuthorizedClientService authorizedClientService) {

        OAuth2AuthorizedClientProvider authorizedClientProvider =
                OAuth2AuthorizedClientProviderBuilder.builder()
                        .clientCredentials()
                        .build();

        AuthorizedClientServiceOAuth2AuthorizedClientManager authorizedClientManager =
                new AuthorizedClientServiceOAuth2AuthorizedClientManager(
                        clientRegistrationRepository, authorizedClientService);
        authorizedClientManager.setAuthorizedClientProvider(authorizedClientProvider);

        return authorizedClientManager;
    }
}
```

### 3. Inter-Service M2M RestTemplate Interceptor
We write an interceptor that checks for the presence of an active security context. If none exists (e.g., executing in a background thread), it uses the authorized client manager to obtain a new client credentials token:

```java
package com.ftgo.order.security;

import org.springframework.http.HttpRequest;
import org.springframework.http.client.ClientHttpRequestExecution;
import org.springframework.http.client.ClientHttpRequestInterceptor;
import org.springframework.http.client.ClientHttpResponse;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.oauth2.client.OAuth2AuthorizeRequest;
import org.springframework.security.oauth2.client.OAuth2AuthorizedClient;
import org.springframework.security.oauth2.client.AuthorizedClientServiceOAuth2AuthorizedClientManager;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;
import java.io.IOException;

public class M2MTokenPropagationInterceptor implements ClientHttpRequestInterceptor {

    private final AuthorizedClientServiceOAuth2AuthorizedClientManager authorizedClientManager;

    public M2MTokenPropagationInterceptor(
            AuthorizedClientServiceOAuth2AuthorizedClientManager authorizedClientManager) {
        this.authorizedClientManager = authorizedClientManager;
    }

    @Override
    public ClientHttpResponse intercept(HttpRequest request, byte[] body, ClientHttpRequestExecution execution) 
            throws IOException {
        
        // 1. If a user context is available, forward it
        if (SecurityContextHolder.getContext().getAuthentication() instanceof JwtAuthenticationToken) {
            JwtAuthenticationToken auth = (JwtAuthenticationToken) SecurityContextHolder.getContext().getAuthentication();
            request.getHeaders().add("Authorization", "Bearer " + auth.getToken().getTokenValue());
        } else {
            // 2. Otherwise, request an M2M Client Credentials token
            OAuth2AuthorizeRequest authorizeRequest = OAuth2AuthorizeRequest
                    .withClientRegistrationId("kitchen-service-m2m")
                    .principal("kitchen-service")
                    .build();

            OAuth2AuthorizedClient authorizedClient = authorizedClientManager.authorize(authorizeRequest);
            if (authorizedClient != null && authorizedClient.getAccessToken() != null) {
                String token = authorizedClient.getAccessToken().getTokenValue();
                request.getHeaders().add("Authorization", "Bearer " + token);
            }
        }

        return execution.execute(request, body);
    }
}
```

---

## 16.13 Reactive API Gateway Hardening & Security Filters

As the entry point to our network, the API Gateway must be hardened against common web vulnerabilities. In a reactive WebFlux environment, we configure Cross-Origin Resource Sharing (CORS), Cross-Site Request Forgery (CSRF) protection, and secure HTTP response headers.

### 1. Hardened Gateway Security Configuration
Update your `GatewaySecurityConfig` to enable and configure these security layers:

```java
package com.ftgo.gateway.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.web.reactive.EnableWebFluxSecurity;
import org.springframework.security.config.web.server.ServerHttpSecurity;
import org.springframework.security.web.server.SecurityWebFilterChain;
import org.springframework.security.web.server.csrf.CookieServerCsrfTokenRepository;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.reactive.CorsConfigurationSource;
import org.springframework.web.cors.reactive.UrlBasedCorsConfigurationSource;
import java.util.Collections;

@Configuration
@EnableWebFluxSecurity
public class GatewaySecurityConfig {

    @Bean
    public SecurityWebFilterChain springSecurityFilterChain(ServerHttpSecurity http) {
        http
            .cors().configurationSource(corsConfigurationSource())
            .and()
            .csrf()
                // Store CSRF tokens in HTTP-only cookies readable by frontend scripts
                .csrfTokenRepository(CookieServerCsrfTokenRepository.withHttpOnlyFalse())
            .and()
            .headers()
                // Prevent clickjacking
                .frameOptions().mode(org.springframework.security.web.server.header.XFrameOptionsServerHttpHeadersWriter.Mode.DENY)
                // Enforce HSTS (HTTP Strict Transport Security)
                .hsts().maxAge(java.time.Duration.ofDays(365)).includeSubDomains(true)
            .and()
            .authorizeExchange()
                .pathMatchers("/actuator/**", "/eureka/**").permitAll()
                .anyExchange().authenticated()
            .and()
            .oauth2Login()
            .and()
            .oauth2ResourceServer().jwt();
        
        return http.build();
    }

    @Bean
    public CorsConfigurationSource corsConfigurationSource() {
        CorsConfiguration config = new CorsConfiguration();
        config.setAllowedOrigins(Collections.singletonList("https://ftgo.com"));
        config.setAllowedMethods(Collections.singletonList("*"));
        config.setAllowedHeaders(Collections.singletonList("*"));
        config.setAllowCredentials(true);

        UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/**", config);
        return source;
    }
}
```

---

## 16.14 JWK Key Rotation & Offline Validation Caching

To validate JSON Web Tokens (JWT) efficiently, downstream microservices query Keycloak's JSON Web Key Set (JWKS) endpoint to fetch the public keys used to sign the tokens. Querying the IdP for every request creates a major performance bottleneck and increases latency.

To solve this, Spring Security's reactive JWT decoder automatically caches public keys:
* **Caching**: The public keys are held in memory. Sub-microsecond validation times are achieved because no network requests are required to validate incoming JWTs.
* **Key Rotation**: If Keycloak rotates its signing keys, a microservice might receive a token signed with a key ID (`kid`) that is not present in its local cache. Spring Security detects the missing `kid` and automatically triggers a single network query to refresh the JWKS keys.

### Programmatic WebFlux JWT Decoder with Cache Settings
If you need to configure public key cache timeouts and refresh rules programmatically, you can expose a custom `ReactiveJwtDecoder` bean:

```java
package com.ftgo.order.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.oauth2.jwt.NimbusReactiveJwtDecoder;
import org.springframework.security.oauth2.jwt.ReactiveJwtDecoder;
import org.springframework.security.oauth2.jwt.ReactiveJwtDecoders;

@Configuration
public class JwtDecoderConfig {

    @Bean
    public ReactiveJwtDecoder reactiveJwtDecoder() {
        String jwkSetUri = "http://localhost:8080/auth/realms/ftgo-realm/protocol/openid-connect/certs";
        // NimbusReactiveJwtDecoder comes configured with default in-memory key caching and rotation handlers
        return NimbusReactiveJwtDecoder.withJwkSetUri(jwkSetUri).build();
    }
}
```

---

## 16.15 Advanced Gateway Token Exchange Pattern

In complex enterprise environments, propagating external user JWTs directly to downstream microservices can violate security segmentation rules. The **Token Exchange Pattern** solves this:
1. The API Gateway receives an external-facing JWT from the client.
2. The Gateway makes a token exchange request to Keycloak, swapping the user's token for an internal-scoped service token containing only the specific roles required for downstream routing.
3. The Gateway propagates the exchanged internal token downstream, isolating internal service metrics and roles from the public network.

---

## Chapter Summary

* In a microservices architecture, security is centralized at the **API Gateway (Edge)** and user identity management is delegated to an **Identity Provider (IdP)**.
* **OAuth 2.0** handles authorization and access delegation using signed JSON Web Tokens (JWT). **OpenID Connect (OIDC)** adds authentication and profile information.
* **Keycloak** is an open source IdP that runs in our Docker mesh. We configure Keycloak realms, clients, client secrets, and roles.
* Clients request user access tokens by posting credentials to Keycloak's token endpoint.
* **Spring Cloud Gateway** is configured as an OAuth 2.0 Login Client. Using the `TokenRelay` filter, it forwards validated JWT bearer tokens to downstream microservices in request headers.
* To map Keycloak roles to Spring Security permissions, we implement a custom JWT converter class in Java.
* Downstream services validate JWT signatures using public key sets (JWKS) exposed by Keycloak and enforce route-level authorization rules based on user roles.
* Outgoing API calls from a microservice to other backend services utilize a Spring RestTemplate interceptor to propagate the JWT bearer token.
* Custom claims such as `tenant_id` are processed using a Servlet filter and stored in ThreadLocal wrappers for runtime access.
* Machine-to-machine (M2M) communication without user contexts is secured using the **OAuth 2.0 Client Credentials Grant Flow**, implemented via Spring's `OAuth2AuthorizedClientManager`.
* API Gateway deployments are hardened using WebFlux CORS configurations, secure HSTS headers, clickjacking protections, and HTTP-only cookie-backed CSRF repositories.
* Cryptographic signature validations are optimized through memory-cached JWK configurations, executing network fetches dynamically on public key rotation signals.

