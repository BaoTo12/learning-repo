# Module 19: Security (Chapter 19)

Welcome class. Today we analyze **Security (CS-529)**.

Production database architectures must be protected from external attacks and unauthorized access. MongoDB secures data using Role-Based Access Control (RBAC), transport layer encryption (TLS/SSL), and client-side x.509 certificate authentication.

Today we study **Database Security Configurations**, analyzing user creation, access control, TLS settings, and mTLS client-certificate authentication in Java.

---

## 1. Academic Lecture: Role-Based Access Control & Certificate Authentication

### 1. Role-Based Access Control (RBAC)
MongoDB implements security using roles. Users are assigned roles that define their read, write, and administrative privileges:
*   `readWrite`: Authorizes CRUD operations on specific databases.
*   `dbAdmin`: Authorizes index builds, schema checking, and stats gathering.
*   `root`: Grants superuser access across all resources.

### 2. mTLS and x.509 Authentication
Instead of username/password authentication (which is vulnerable to brute force and leaks), production systems use mutual TLS (mTLS):
1. The client presents a trusted x.509 certificate to the database.
2. The database validates the certificate authority (CA) signature.
3. The database extracts the subject Distinguished Name (DN) from the certificate and maps it to a database user role.

```text
[Java Application (with Keystore)] ──(Client Cert)──> [MongoDB Server (Verify CA)]
                                                             │
                                                             ├── (Valid Signature) ──> Maps Subject DN to Role
                                                             └── (Invalid) ──────────> Terminate SSL Connection
```

---

## 2. Theory vs. Production Trade-offs

Compare authentication mechanisms:

| Dimension / Metric | Username / Password (SCRAM) | mTLS x.509 Authentication |
| :--- | :--- | :--- |
| **Credential Storage** | DB admin collection (salted hashes) | External Certificate Authority (CA) |
| **Secret Rotation** | Manual password updates / vault calls | Automatic certificate reissues |
| **Network Security** | Vulnerable to credential interception | Encrypted TLS channel required |
| **Driver Configuration**| Minimal | High (Requires JVM truststores/keystores) |
| **Revocation Strategy** | Drop user from database | Certificate Revocation Lists (CRL) / Online check |

---

## 3. How to Use: Secure Connection Settings in Java

Let us construct connection parameters. We contrast an insecure database connection with a secure, mTLS x.509 authenticated connection configuration.

### A. The Insecure Client Setup (Anti-Pattern)
Avoid connecting without configuring TLS or access credentials:

```java
// DANGER: Connection transmits database traffic in cleartext.
// If deployed in production, sensitive data can be intercepted on the network.
MongoClient client = MongoClients.create("mongodb://localhost:27017");
```

### B. The Production-Grade Client TLS Configuration (Production Pattern)
Configure SSL context settings and define x.509 credential mappings:

```java
import com.mongodb.ConnectionString;
import com.mongodb.MongoClientSettings;
import com.mongodb.MongoCredential;
import com.mongodb.connection.SslSettings;
import com.mongodb.client.MongoClient;
import com.mongodb.client.MongoClients;
import javax.net.ssl.SSLContext;

public class SecuritySettingsFactory {

    public static MongoClient createMTLSClient(String seedListUri, SSLContext sslContext) {
        // 1. Configure X.509 credentials using client certificate Subject DN
        // Note: When using X.509, the username is omitted; the DN is read from the cert.
        MongoCredential credential = MongoCredential.createMongoX509Credential();

        // 2. Build MongoClientSettings incorporating SSLContext and credentials
        MongoClientSettings settings = MongoClientSettings.builder()
                .applyConnectionString(new ConnectionString(seedListUri))
                .credential(credential)
                .applyToSslSettings(builder -> builder
                        .enabled(true)
                        .context(sslContext)
                        .invalidHostNameAllowed(false) // Strict host checks
                )
                .build();

        return MongoClients.create(settings);
    }
}
```

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Blind Hostname Verification Disabling
*   **Why it fails**: Setting `invalidHostNameAllowed(true)` on `SslSettings`. This disables validation of the server's certificate domain against its hostname, exposing the application to Man-in-the-Middle (MITM) attacks.
*   **Mitigation**: Keep hostname validation active (`invalidHostNameAllowed(false)`) and ensure server certificates match host names.

---

## 5. Socratic Review Questions

### Question 1
Why does MongoDB require custom roles to be defined in the `admin` database, even when those roles grant privileges on user collections in different databases?

#### Answer
Privileges are cataloged inside the `admin` database to centralize system authority. Keeping user configurations and roles in a single database prevents security conflicts and allows the database to cache authentication metadata efficiently, rather than scanning individual user databases on every connection.

---

## 6. Hands-on Challenge: X.509 Client Builder

### The Challenge
In this challenge, you will implement an X.509-enabled MongoClientSettings builder.
Your task:
1. Complete `buildSSLMongoClientSettings` in `SecurityConfigurator`.
2. Construct and return `MongoClientSettings` matching the requirements:
   - Apply the target connection string.
   - Configure credentials to use the Mongo X.509 authentication mechanism.
   - Enable SSL, passing the provided `SSLContext` instance.
   - Ensure hostname validation remains enabled (`invalidHostNameAllowed(false)`).

Complete the implementation stub:

```java
package com.mongodb.systems;

import com.mongodb.MongoClientSettings;
import javax.net.ssl.SSLContext;

public class SecurityConfigurator {

    public MongoClientSettings buildSSLMongoClientSettings(String connectionUri, SSLContext sslContext) {
        // TODO: Build and return MongoClientSettings incorporating X.509 credential and SSL Context
        return null;
    }
}
```

### Verification Test
Verify your code with this JUnit 5 test class:

```java
package com.mongodb.systems;

import com.mongodb.MongoClientSettings;
import com.mongodb.MongoCredential;
import org.junit.jupiter.api.Test;
import javax.net.ssl.SSLContext;
import static org.mockito.Mockito.*;
import static org.junit.jupiter.api.Assertions.*;

class SecurityConfiguratorTest {

    @Test
    void testX509SslConfiguration() {
        SSLContext sslContext = mock(SSLContext.class);
        SecurityConfigurator configurator = new SecurityConfigurator();
        String uri = "mongodb://secureserver:27017/";

        MongoClientSettings settings = configurator.buildSSLMongoClientSettings(uri, sslContext);

        assertNotNull(settings);
        
        // Assert X509 authentication
        MongoCredential cred = settings.getCredential();
        assertNotNull(cred);
        assertEquals(MongoCredential.MONGODB_X509_MECHANISM, cred.getMechanism());

        // Assert SSL enabled
        assertTrue(settings.getSslSettings().isEnabled());
        assertEquals(sslContext, settings.getSslSettings().getContext());
        assertFalse(settings.getSslSettings().isInvalidHostNameAllowed());
    }
}
```
