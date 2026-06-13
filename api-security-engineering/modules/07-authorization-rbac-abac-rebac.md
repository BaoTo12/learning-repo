# Module 07: Authorization Models — RBAC, ABAC, and ReBAC

Welcome back class. Today we analyze **Authorization Models — RBAC, ABAC, and ReBAC (CS-527)**.

Authentication establishes *who* the user is, but authorization dictates *what* they are allowed to do. In enterprise environments, access control logic quickly scales beyond simple static checks. If access logic is hardcoded directly into database queries or controller endpoints, modifying policies requires refactoring and deploying the entire codebase. To build a robust security framework, we must separate access policies from core business routing using formal authorization paradigms.

Today we study **Role-Based Access Control (RBAC)**, **Attribute-Based Access Control (ABAC)**, and **Relationship-Based Access Control (ReBAC)**, compare their trade-offs, and implement Method Security declarations in **Spring Security 6.x** using custom SpEL (Spring Expression Language) evaluators.

---

## 1. Academic Lecture: Authorization Paradigms & Evaluation Contexts

### 1. Role-Based Access Control (RBAC)
RBAC grants permissions to abstract **Roles** (e.g. `ROLE_ADMIN`, `ROLE_RECRUITER`), and assigns those roles to users.
*   **Role Hierarchies**: To simplify management, roles inherit permissions. For example, an `ADMIN` role should automatically possess all permissions granted to a `RECRUITER` role, which in turn inherits from a `CANDIDATE` role. In Spring Security, we configure this using the `RoleHierarchy` bean.
*   **Constraint**: RBAC is coarse-grained. It cannot express rules like: *"A Recruiter can only view resumes during working hours"* or *"A candidate can only edit their own resume."*

### 2. Attribute-Based Access Control (ABAC)
ABAC resolves fine-grained permissions by evaluating a set of runtime attributes:
*   **Subject Attributes**: User's role, age, department, IP address, device security status.
*   **Resource Attributes**: Owner ID, department classification, file age, data sensitivity level.
*   **Action Attributes**: Read, Write, Delete, Approve.
*   **Environment Attributes**: Current time, system load, network location boundaries.
ABAC policies are evaluated as Boolean equations (e.g. `Subject.Role == 'RECRUITER' && Environment.IPInOfficeRange && Resource.OwnerDepartment == Subject.Department`).

### 3. Relationship-Based Access Control (ReBAC)
ReBAC determines permissions based on **Relationships** between subjects and resources in a graph structure (made famous by Google's Zanzibar model). Instead of matching static attributes, ReBAC walks the graph path:
*   *Rule*: A user has `write` access to `Resume_001` if `User` is `Owner` of `Resume_001`, OR `User` is a `Member` of `HiringTeam` that `Controls` `Resume_001`.
*   *Advantage*: Extremely scalable for complex, hierarchical resource ownership models (e.g. folders containing subfolders, user-group nested memberships).

```text
[RBAC Evaluation]
Subject (User) ──> Has Role? (ROLE_RECRUITER) ─────────────────────────> [Grant Access]

[ABAC Evaluation]
Subject (User) ──┐
Resource (File) ─┼─> Check Attributes: OwnerID == UserID && IsWorkingHour? ──> [Grant Access]
Environment ─────┘

[ReBAC Evaluation]
Subject (User) ──(Is Member of Team?)──> [HiringTeam] ──(Owns)──> [File] ──> [Grant Access]
```

---

## 2. Theory vs. Production Trade-offs

When choosing an authorization architecture, match policy complexity to scaling goals:

| Authorization Model | Primary Data Source | Policy Complexity | Latency / Compute Overhead | Best Use Case |
| :--- | :--- | :--- | :--- | :--- |
| **Coarse RBAC** | User token claims | Low (Static role checks) | Low (Fast cache lookup) | Standard page access limits |
| **Contextual ABAC** | Runtime request context & DB | High (Complex logic chains) | Moderate (Requires context load) | Time-locks, geo-fenced routes |
| **Graph-based ReBAC**| Graph database queries | Moderate (Walks relations) | High (Requires graph query joins) | Google Drive style folders sharing |

---

## 3. How to Use: Dynamic Method Security in Spring Boot

Let us write a compile-grade Java 21 implementation of Method Security in Spring Boot, configuring a hierarchical role checker and implementing a custom SpEL permission evaluator for resource ownership verification.

### A. The Hardcoded Inline Check Pattern (Anti-Pattern)

Avoid scattering authorization logic inside controller method bodies. This results in code duplication and makes auditing policies difficult:

```java
package com.security.api.controller;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RestController;
import java.security.Principal;

@RestController
public class NaiveDocumentController {
    // DANGER: Hardcoding database ownership validation inside controller method bodies
    // obscures security boundaries. If an engineer forgets this line during a code copy,
    // they create an insecure direct object reference (IDOR) leak.
    @DeleteMapping("/api/resumes/{id}")
    public ResponseEntity<String> deleteResume(@PathVariable Long id, Principal principal) {
        String owner = getOwnerFromDatabase(id);
        if (!principal.getName().equals(owner)) { // VULNERABLE to omissions
            return ResponseEntity.status(HttpStatus.FORBIDDEN).body("Access Denied");
        }
        // execute delete
        return ResponseEntity.ok("Deleted");
    }

    private String getOwnerFromDatabase(Long id) { return "candidate_john"; }
}
```

### B. The Hardened SpEL Method Security (Production Pattern)

Here is the hardened pattern. We enable Spring Method Security, configure a hierarchical role hierarchy, and implement a reusable `PermissionEvaluator` bean that handles fine-grained attribute checks dynamically via annotations.

First, the Security Configuration setting up hierarchy:

```java
package com.security.api.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.access.expression.method.DefaultMethodSecurityExpressionHandler;
import org.springframework.security.access.expression.method.MethodSecurityExpressionHandler;
import org.springframework.security.access.hierarchicalroles.RoleHierarchy;
import org.springframework.security.access.hierarchicalroles.RoleHierarchyImpl;
import org.springframework.security.config.annotation.method.configuration.EnableMethodSecurity;

@Configuration
@EnableMethodSecurity // Activates @PreAuthorize and @PostAuthorize
public class MethodSecurityConfig {

    @Bean
    public RoleHierarchy roleHierarchy() {
        // Enforce role levels: ADMIN inherits RECRUITER permissions, which inherits CANDIDATE
        return RoleHierarchyImpl.withDefaultRolePrefix()
            .role("ADMIN").implies("RECRUITER")
            .role("RECRUITER").implies("CANDIDATE")
            .build();
    }

    @Bean
    public MethodSecurityExpressionHandler methodSecurityExpressionHandler(RoleHierarchy roleHierarchy) {
        DefaultMethodSecurityExpressionHandler handler = new DefaultMethodSecurityExpressionHandler();
        handler.setRoleHierarchy(roleHierarchy);
        // Wire custom target evaluator
        handler.setPermissionEvaluator(new ResourcePermissionEvaluator());
        return handler;
    }
}
```

Next, the custom `PermissionEvaluator` checking ABAC parameters:

```java
package com.security.api.config;

import org.springframework.security.access.PermissionEvaluator;
import org.springframework.security.core.Authentication;
import java.io.Serializable;
import java.time.LocalTime;

public class ResourcePermissionEvaluator implements PermissionEvaluator {

    @Override
    public boolean hasPermission(Authentication authentication, Object targetDomainObject, Object permission) {
        // Handle evaluation when the raw entity object is passed directly
        return false;
    }

    @Override
    public boolean hasPermission(Authentication authentication, Serializable targetId, String targetType, Object permission) {
        if (authentication == null || targetType == null || !(permission instanceof String)) {
            return false;
        }

        String username = authentication.getName();
        String action = ((String) permission).toUpperCase();

        // Check ABAC Attributes: Time of Day (Environment Attribute)
        LocalTime now = LocalTime.now();
        if (now.isBefore(LocalTime.of(8, 0)) || now.isAfter(LocalTime.of(19, 0))) {
            // Access blocked outside working hours (8:00 AM - 7:00 PM)
            return false;
        }

        // Check ABAC Attributes: Resource Ownership
        if ("RESUME".equalsIgnoreCase(targetType)) {
            Long resumeId = (Long) targetId;
            String owner = getOwnerFromDatabase(resumeId);
            
            // Allow access if User is Owner (ABAC relation), OR has RECRUITER authority
            boolean isOwner = username.equals(owner);
            boolean isRecruiter = authentication.getAuthorities().stream()
                .anyMatch(a -> a.getAuthority().equals("ROLE_RECRUITER"));
            
            if ("READ".equals(action)) {
                return isOwner || isRecruiter;
            } else if ("WRITE".equals(action)) {
                return isOwner; // Only owner can modify their resume
            }
        }

        return false;
    }

    private String getOwnerFromDatabase(Long id) {
        // Mock DB query: in production, fetch owner username matching target ID
        return "candidate_john";
    }
}
```

Now configure the controller cleanly using `@PreAuthorize`:

```java
package com.security.api.controller;

import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class SecureDocumentController {

    // Resolves permission checks by passing the ID parameters to our evaluator
    @GetMapping("/api/resumes/{id}")
    @PreAuthorize("hasPermission(#id, 'RESUME', 'READ')")
    public String getResumeDetail(@PathVariable Long id) {
        return "Target Resume Content for ID: " + id;
    }
}
```

---

## 4. Common Errors & Pitfalls

### Pitfall 1: SpEL Expression Syntax Typos
Writing syntactically incorrect SpEL expressions inside `@PreAuthorize` strings (e.g. `@PreAuthorize("hasRole('ADMIN') and #userId == principal.id")` where `principal.id` throws a NullPointerException).
*   **Why it fails**: Typo errors are compiled as raw strings. The system will throw runtime parsing exceptions only when the endpoint is queried, risking service instability.
*   **Mitigation**: Always write comprehensive unit tests that query secure endpoints with mock credentials to verify SpEL resolver paths during test execution.

### Pitfall 2: Bypassing Security Filters for Method Security
Assuming that adding `@PreAuthorize` to a controller bean guarantees security even if the endpoint path is marked as `permitAll()` in the filter chain.
*   **Why it fails**: If the filter chain lacks authorization bounds, requests enter the controller layer. While Method Security will still block execution, the initial authentication filters are bypassed, exposing the application to performance degradation or DDOS resource fatigue if the evaluator runs slow DB queries.
*   **Mitigation**: Always enforce coarse-grained filter boundary gates first (`requestMatchers().authenticated()`) before delegating to fine-grained Method Security.

---

## 5. Socratic Review Questions

### Question 1
How does a role hierarchy bean (e.g. `ROLE_ADMIN implies ROLE_RECRUITER`) reduce configuration complexity in applications with nested privilege structures?

#### Answer
Without hierarchies, if you add a new endpoint for recruiters, you must write `@PreAuthorize("hasRole('RECRUITER') or hasRole('ADMIN')")` explicitly. If a new manager role is introduced, you must edit all access checks across the app. With a hierarchy, you simply define `ADMIN implies RECRUITER`, and write `@PreAuthorize("hasRole('RECRUITER')")`. Any user with the `ADMIN` role is automatically granted the permission by the hierarchy compiler, eliminating code updates.

### Question 2
Under what scenario does the ABAC model perform poorly, and how can we mitigate this latency?

#### Answer
ABAC models perform poorly when checking list results (e.g., filtering 100 documents to display to a user). If the evaluator must check ownership attributes for all 100 documents, it executes 100 database query lookups. We mitigate this by using **data-level filtering** (pushing the attribute conditions down into the SQL query level: `SELECT * FROM doc WHERE owner = ? OR ? = TRUE`) rather than filtering objects in application memory.

---

## 6. Hands-on Challenge: Contextual ABAC Evaluator

### The Challenge
In this challenge, you will implement a permission evaluator method in Java.
Your task:
1. Complete the implementation of `hasPermission` inside `AttributeSecurityEvaluator`.
2. Enforce the ABAC rules:
   - Allow `READ` access if the user has the authority `ROLE_AUDITOR`.
   - Allow `READ` or `WRITE` access if the user is the owner of the resource.
   - Deny all access if the request originates outside the allowed hours (between 22:00 and 06:00).

Complete the implementation below:

```java
package com.security.api;

import org.springframework.security.core.Authentication;
import java.time.LocalTime;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class MockResource {
    private final Long id;
    private final String ownerUsername;

    public MockResource(Long id, String ownerUsername) {
        this.id = id;
        this.ownerUsername = ownerUsername;
    }
    public String getOwnerUsername() { return ownerUsername; }
}

class AttributeSecurityEvaluator {

    public boolean hasPermission(Authentication auth, MockResource resource, String action, LocalTime requestTime) {
        if (auth == null || resource == null || action == null) {
            return false;
        }

        // 1. Enforce Time-lock: deny access if requestTime is between 22:00:00 (10 PM) and 06:00:00 (6 AM) inclusive.
        //    (e.g., requestTime.isAfter(22:00) || requestTime.isBefore(06:00))
        
        // 2. Check if user is the resource owner (auth.getName().equals(resource.getOwnerUsername())).
        //    If yes, return true.
        
        // 3. Check if user has "ROLE_AUDITOR" authority and the action is "READ".
        //    If yes, return true.

        // 4. Fallback: return false.

        return false;
    }
}
```

Write the attribute verification checks. Save the completed file and verify that the ABAC test logic passes under `modules/07-authorization-rbac-abac-rebac.md`.
