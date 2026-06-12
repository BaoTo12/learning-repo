# Module 09: Security Logging and Monitoring Failures — Log Forging & Audit Trails

Welcome back, class. Today we analyze **Security Logging and Monitoring Failures (A09:2021)**.

When a security incident occurs in production, your logs are the primary source of forensic evidence. If your logs are uninformative, missing key transactional events, or contaminated with user-injected entries, you are blind to the breach. Today, we will study the mechanics of **Log Forging (Log Injection)** attacks and implement sanitization filters. We will also learn how to build secure, unalterable database audit trails using **Spring Data Envers** linked to our Spring Security user context.

---

## 1. Academic Lecture: Logging as a Security Control

Security logs must provide a tamper-resistant timeline of system activities.

### 1. Log Forging (Log Injection)
Log forging occurs when an application writes unsanitized user input to log files.
*   **The Attack Vector**: An attacker submits inputs containing carriage return (`\r`, ASCII 13) and line feed (`\n`, ASCII 10) characters.
*   **The Consequence**: When these characters are written to a line-based log file, they create a new line in the output. The attacker can inject fake log entries to confuse administrators or hide malicious actions. For example, a failed login attempt from an attacker can write a line that looks like a successful login by a system administrator:

```
[WARN] Failed login for user: guest\r\n[INFO] User admin logged in from 10.0.0.5 successfully!
```

If the administrator inspects the logs, they will see:
```log
[WARN] Failed login for user: guest
[INFO] User admin logged in from 10.0.0.5 successfully!
```

### 2. Log Injection Mitigation
To prevent log forging, you must sanitize all dynamic values before logging them, or use a structured logging format (like JSON) where newlines are escaped automatically as JSON string properties.

```mermaid
graph TD
    A[Attacker Input: guest\r\n[INFO] Admin Login] --> B[Spring Controller]
    B --> C{Sanitizer Filter Enabled?}
    C -- No --> D[Raw log output with injected lines]
    C -- Yes --> E[Log value sanitization: replace CRLF with spaces]
    E --> F[Clean Log Output: [WARN] Failed login: guest _ [INFO] Admin Login]
```

### 3. Transactional Audit Trails (Spring Data Envers)
For compliance (e.g., PCI-DSS, HIPAA), modifications to sensitive financial or user records must be tracked.
*   **Spring Data Envers**: Integrates with Hibernate to automatically capture entity changes (inserts, updates, deletes) in dedicated audit tables (suffix `_AUD`). Each change is associated with a **Revision** metadata entry storing the timestamp and the identity of the user who made the change.

---

## 2. Theory vs. Production Trade-offs

### High Logging Verbosity vs. PII Leakage
*   **Detailed Debug Logging**:
    *   *Pro*: Speeds up production debugging by capturing all request bodies and query parameters.
    *   *Con*: High risk of leaking Personally Identifiable Information (PII) like names, credit card numbers, and passwords, violating privacy laws (GDPR).
*   **Production Rule**: Never log sensitive variables. Use structured logging frameworks and configure regex-based maskers (such as Logback pattern layout filters) to find and replace patterns (e.g., credit cards) with `*****` before writing to disk.

---

## 3. How to Use: Secure Logging and Auditing

Let us write compile-grade Java 21 classes to sanitize log outputs and configure Spring Data Envers auditing.

### A. Sanitizing Log Strings against Log Forging

Here is a utility class to strip CRLF characters and prevent log injection:

```java
package com.capstone.security.logging;

import java.util.logging.Logger;

public class SecurityLogger {
    private static final Logger LOGGER = Logger.getLogger(SecurityLogger.class.getName());

    /**
     * Sanitizes inputs by removing CRLF characters and logging the safe output.
     */
    public static void logWarnSafe(String message, String userInput) {
        String sanitizedInput = sanitize(userInput);
        LOGGER.warning(message + ": " + sanitizedInput);
    }

    /**
     * Replaces CR (\r) and LF (\n) characters with underscores to prevent log forging.
     */
    public static String sanitize(String input) {
        if (input == null) {
            return null;
        }
        // Replace carriage return and line feed characters
        return input.replace('\n', '_').replace('\r', '_');
    }
}
```

### B. Building a Secure Audit Trail with Spring Data Envers

To audit an entity, annotate it with `@Audited`. We also define a custom `RevisionListener` to associate each database revision with the authenticated Spring Security user.

First, let's create the custom Audit Revision Entity:

```java
package com.capstone.security.logging.audit;

import jakarta.persistence.*;
import org.hibernate.envers.RevisionEntity;
import org.hibernate.envers.RevisionNumber;
import org.hibernate.envers.RevisionTimestamp;

import java.util.Date;

@Entity
@Table(name = "audit_revision_info")
@RevisionEntity(UserRevisionListener.class)
public class AuditRevisionEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @RevisionNumber
    @Column(name = "rev_id")
    private Long id;

    @RevisionTimestamp
    @Column(name = "rev_timestamp")
    private Date timestamp;

    @Column(name = "modified_by_user")
    private String modifiedByUser;

    // Getters and Setters
    public Long getId() { return id; }
    public Date getTimestamp() { return timestamp; }
    public String getModifiedByUser() { return modifiedByUser; }
    public void setModifiedByUser(String modifiedByUser) { this.modifiedByUser = modifiedByUser; }
}
```

Next, let's write the `UserRevisionListener` to resolve the current username from the Spring Security Context:

```java
package com.capstone.security.logging.audit;

import org.hibernate.envers.RevisionListener;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;

public class UserRevisionListener implements RevisionListener {

    @Override
    public void newRevision(Object revisionEntity) {
        AuditRevisionEntity auditEntity = (AuditRevisionEntity) revisionEntity;
        
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        if (auth != null && auth.isAuthenticated()) {
            auditEntity.setModifiedByUser(auth.getName());
        } else {
            auditEntity.setModifiedByUser("SYSTEM_ANONYMOUS");
        }
    }
}
```

Now, apply auditing to a JPA Entity:

```java
package com.capstone.security.logging.audit;

import jakarta.persistence.*;
import org.hibernate.envers.Audited;

@Entity
@Table(name = "accounts")
@Audited // Envers will automatically audit all modifications to this entity
public class Account {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    private String accountNumber;
    
    private double balance;

    // Getters, Setters, and Constructors
}
```

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Logging Exception Objects Direct to Console without sanitizing Messages
Passing exception objects to logging libraries when the exception message contains raw user inputs.
```java
try {
    double amount = Double.parseDouble(userInput);
} catch (NumberFormatException e) {
    // DANGER: The exception message contains userInput, leading to log forging!
    logger.error("Failed parsing: " + e.getMessage()); 
}
```
*   **Mitigation**: Do not include raw exception messages directly in log statements if they contain unverified client input. Catch the exception and log a static descriptive string or sanitize the message.

---

## 5. Socratic Review Questions

### Question 1
Why are Logback/Log4j2 layout filters that output JSON format (e.g. `LogstashEncoder`) immune to traditional line-based Log Forging?

#### Answer
Line-based log forging relies on the parser writing raw carriage returns (`\n`) to break the current output line and start a new one on the console or file. JSON log encoders do not output raw lines; they wrap log data in a structured JSON object. 
When the encoder encounters a carriage return or newline in a logged variable, it automatically escapes the characters (e.g., replacing `\n` with the string literal `\n`). The log aggregator parses the JSON object as a single event, preventing the creation of new log lines.

### Question 2
If an attacker gains administrative privileges on the database, can they bypass Spring Data Envers audit trails? What additional control is needed?

#### Answer
Yes. Spring Data Envers stores audit logs in standard database tables (e.g., `accounts_aud`). An attacker with database admin privileges can run SQL `UPDATE` or `DELETE` statements on these audit tables to erase their tracks.
To prevent this, you must send audit events to an external, write-once-read-many (WORM) log storage system or configure your database to export changes via transaction log streaming to a secured SIEM (Security Information and Event Management) system that database admins cannot access.

---

## 6. Hands-on Challenge: Log Sanitization Filter

### The Challenge
In this challenge, you will implement a helper class to scan and sanitize log inputs.

Your task is to write a filter that removes carriage return and line feed characters, and replaces any 16-digit sequences (potential credit card numbers) with a masked value (`XXXX-XXXX-XXXX-XXXX`).

Complete the sanitization method below:

```java
package com.capstone.security.logging.challenge;

import java.util.regex.Pattern;

public class LogSanitizationChallenge {

    private static final Pattern CREDIT_CARD_PATTERN = Pattern.compile("\\b\\d{16}\\b");

    /**
     * Sanitizes inputs:
     * 1. Removes all \r and \n characters.
     * 2. Masks 16-digit credit card sequences with XXXX-XXXX-XXXX-XXXX.
     * 
     * @param input The raw input log message
     * @return The sanitized message
     */
    public static String sanitizeLog(String input) {
        if (input == null) {
            return null;
        }

        // TODO: Complete the implementation.
        // 1. Replace all carriage return (\r) and newline (\n) characters with empty spaces.
        // 2. Match the CREDIT_CARD_PATTERN and replace matches with "XXXX-XXXX-XXXX-XXXX".
        // 3. Return the sanitized string.
        
        return input;
    }
}
```

Write out the regular expression replace block. Save the completed challenge class and document why logging password reset links is a security risk inside `modules/09-logging-monitoring-failures.md`.
