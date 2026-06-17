# Module 15: Security

Welcome, student. Today we study transport security and access control in **MongoDB Security (CS-529)**.

---

## 1. What problem does this solve?
Exposing databases to the network without encryption or access controls invites data breaches, modifications by unauthorized users, or query injection exploits.

We secure database systems using **TLS/SSL encryption**, **Role-Based Access Control (RBAC)**, and **SCRAM authentication**.

---

## 2. Why does MongoDB provide this feature?
MongoDB provides built-in authentication and encryption to:
*   **Enforce the Least Privilege Principle**: Restricts application access to only the necessary collections and commands.
*   **Protect Data in Transit**: Uses SSL/TLS certificates to encrypt all data moving between the application and database.

---

## 3. How does it work internally or conceptually?
*   **SCRAM (Salted Challenge Response Authentication Mechanism)**: The default authentication mechanism. Validates passwords without sending them over the network.
*   **x.509 Certificate Validation**: Authenticates cluster nodes and client drivers using secure SSL certificates.
*   **RBAC**: Restricts user accounts by assigning roles (e.g. `readWriteAnyDatabase`, `dbAdmin`).
*   **Injection Mitigations**: Unlike SQL databases where queries are parsed as text strings (which allows SQL Injection), MongoDB queries are parsed as structured BSON objects. However, passing un-sanitized user input directly to query filters can still lead to unexpected query matches.

```text
[Java Client] ──(TLS Socket Handshake)──> [SCRAM Auth Check] ──> [Granted RBAC Role]
```

---

## 4. How do we use it in Java?
We configure authentication and TLS settings in the connection string URI:

```java
import com.mongodb.client.MongoClient;
import com.mongodb.client.MongoClients;

public class SecureConnection {
    public MongoClient connectSecurely() {
        // Enforce TLS and pass credentials securely
        String uri = "mongodb://app_user:secure_pass@localhost:27017/prod_db?ssl=true&authSource=admin";
        return MongoClients.create(uri);
    }
}
```

---

## 5. What are the trade-offs?
*   **Pros**: Protects data from network eavesdropping; prevents unauthorized database access.
*   **Cons**: TLS handshakes add encryption overhead, increasing CPU usage; managing certificates increases operational complexity.

---

## 6. Common Mistakes
*   **Hardcoding Passwords**: Placing database credentials in source files. **Always load credentials from secure environment variables.**
*   **Open Network Bindings**: Binding MongoDB to public IP addresses without configuring whitelists.

---

## 7. When should we use it?
*   Configure SSL/TLS and RBAC access roles in all staging and production environments.

---

## 8. When should we avoid it?
*   Never disable authentication or TLS in environments connected to public networks.

---

## 9. Code Examples
Here is a service class demonstrating secure query generation to prevent query injection risks.

```java
package com.mongodb.systems;

import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.Filters;
import org.bson.Document;
import java.util.ArrayList;
import java.util.List;

public class InputSanitizationService {

    public List<Document> findUserByEmailSafe(MongoCollection<Document> collection, String userInput) {
        // DANGER: If userInput is passed as a raw BSON Query object, it can contain operator injections like {$ne: ""}
        // FIX: Always map user input strictly to a String typed Filter, preventing operator injections
        var filter = Filters.eq("email", userInput);
        return collection.find(filter).into(new ArrayList<>());
    }
}
```

---

## 10. Hands-on Exercises

### The Challenge
Implement a method `sanitizeRegexInput` that strips out special regular expression characters (`^`, `$`, `*`, `+`, `?`) from a user input string to prevent regex injection attacks.

Complete the implementation stub:

```java
package com.mongodb.systems;

public class InputSanitizer {

    public static String sanitizeRegexInput(String input) {
        if (input == null) {
            return "";
        }
        // TODO: Replace special characters with empty strings
        return input.replaceAll("[\\^\\$\\*\\+\\?]", "");
    }
}
```

### Verification Test
Verify your code with this JUnit 5 test class:

```java
package com.mongodb.systems;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class InputSanitizerTest {

    @Test
    void testInputSanitization() {
        assertEquals("normaltext", InputSanitizer.sanitizeRegexInput("normaltext"));
        assertEquals("user101", InputSanitizer.sanitizeRegexInput("^user$101*+?"));
    }
}
```
