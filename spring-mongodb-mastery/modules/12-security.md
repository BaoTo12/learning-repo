# Module 12: Security

This module covers database security in MongoDB. It explores client-side encryption, authentication, transport layer security (TLS/SSL), NoSQL injection risks, and strategies to secure dynamic queries in Spring Boot.

---

## 1. What Problem It Solves

If a database configuration is compromised, malicious actors can steal sensitive data, modify records, or execute arbitrary command injection attacks. In cloud deployments, protecting sensitive information (such as credit card numbers and personal identification details) requires securing data at rest, in transit, and in memory.

MongoDB security patterns solve these problems by:
* **Securing Data in Transit**: Enforces TLS/SSL encryption to prevent network sniffing and man-in-the-middle attacks.
* **Protecting Data in Memory (CSFLE)**: Encrypts sensitive fields at the application client layer before sending data over the network, ensuring the database server never sees the plaintext.
* **Enforcing Least Privilege Access**: Configures Role-Based Access Control (RBAC) to restrict user access to specific collections and commands.
* **Preventing NoSQL Injection**: Sanitizes query inputs to prevent users from injecting BSON operators that bypass authentication checks.

---

## 2. Why MongoDB Instead of Relational Databases (RDBMS)

Relational databases support Column-Level Encryption, but this is usually managed on the database server.

MongoDB's security model offers unique advantages:
* **Client-Side Field-Level Encryption (CSFLE)**: Unlike relational column encryption (which decrypts data on the database server), CSFLE encrypts data on the client. Even if an attacker gains root access to the database host, they cannot read the encrypted fields because the decryption keys are stored in a separate Key Management Service (KMS) like AWS KMS.
* **JSON-Based Access Control**: MongoDB supports granular role-based access control, allowing administrators to restrict access down to specific document fields or query conditions using standard JSON filters.

---

## 3. Trade-offs and Limitations

### CSFLE Query Limits
Because fields are encrypted on the client before being sent to the database, MongoDB cannot read the plaintext values.
* Consequently, you cannot perform range queries (`$gt`, `$lt`), text searches, or regex matches on CSFLE-encrypted fields.
* You can only perform exact match queries (`$eq`) on fields encrypted using **Deterministic Encryption**. Fields encrypted using **Randomized Encryption** cannot be queried at all.

### Performance Overhead
Encrypting and decrypting fields on the client increases CPU utilization in the application JVM. Additionally, managing encryption keys requires network round-trips to KMS providers, adding latency to write paths.

---

## 4. Common Mistakes & Anti-patterns

### NoSQL Injection via Unsanitized JSON Query Strings
Constructing queries using raw JSON string concatenation with unsanitized user inputs.
* *Why it's bad*: If a login query concatenates user input like `"{ 'username': '" + user + "', 'password': '" + pass + "' }"`, an attacker can pass `{"$ne": ""}` as the password parameter. The query will evaluate to `password: { $ne: "" }`, returning the first user in the collection and bypassing authentication.
* *Production Fix*: Always use Spring Data's `Criteria` and `Query` builders, which automatically escape parameters, or use query placeholders (`?0`) in `@Query` annotations.

```java
// ANTI-PATTERN: Vulnerable to NoSQL Injection
String rawJson = "{ 'username': '" + userInput + "' }";
BasicQuery query = new BasicQuery(rawJson); // Vulnerable!

// PRODUCTION FIX: Automatically Sanitized
Query query = new Query(Criteria.where("username").is(userInput));
```

### Storing Connection Strings in Plaintext Source Code
Hardcoding connection strings containing database passwords (`mongodb://admin:secretPass@localhost...`) inside `application.yml` or committing them to Git.
* *Why it's bad*: Exposes database credentials to anyone with access to the source code repository.
* *Production Fix*: Use environment variables (`${MONGO_PASSWORD}`) and manage credentials using a secrets manager (such as HashiCorp Vault or AWS Secrets Manager).

---

## 5. When NOT to Use Client-Side Encryption

* **Range-Query Heavy Fields**: If a field needs to be queried using range filters, sorting, or wildcards (e.g. searching users by birthdate range), do not use CSFLE. Use database-level **Encryption at Rest** (like WiredTiger encryption) combined with TLS in-transit encryption instead.

---

## 6. Spring Boot & Spring Data Implementation

This project implements a secure configuration featuring TLS/SSL communication, NoSQL injection prevention, and manual field encryption.

### Domain Object: Secure Customer Account
```java
package com.masterclass.mongodb.domain;

import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.index.Indexed;
import org.springframework.data.mongodb.core.mapping.Document;
import org.springframework.data.mongodb.core.mapping.Field;

@Document(collection = "secure_customers")
public class SecureCustomer {

    @Id
    private String id;

    @Indexed(unique = true)
    private String email;

    @Field("ssn_encrypted")
    private String encryptedSsn; // Stored as cipher text encrypted by the application

    private double balance;

    public SecureCustomer() {}

    public SecureCustomer(String id, String email, String encryptedSsn, double balance) {
        this.id = id;
        this.email = email;
        this.encryptedSsn = encryptedSsn;
        this.balance = balance;
    }

    public String getId() { return id; }
    public String getEmail() { return email; }
    public String getEncryptedSsn() { return encryptedSsn; }
    public void setEncryptedSsn(String encryptedSsn) { this.encryptedSsn = encryptedSsn; }
    public double getBalance() { return balance; }
}
```

### Programmatic TLS / SSL Mongo Configuration
This configuration loads SSL certificates and configures the connection pool to use TLS to encrypt data in transit.

```java
package com.masterclass.mongodb.config;

import com.mongodb.ConnectionString;
import com.mongodb.MongoClientSettings;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;
import org.springframework.data.mongodb.config.AbstractMongoClientConfiguration;
import javax.net.ssl.SSLContext;
import javax.net.ssl.TrustManagerFactory;
import java.security.KeyStore;

@Configuration
public class SecureMongoConfig extends AbstractMongoClientConfiguration {

    @Value("${spring.data.mongodb.uri}")
    private String mongoUri;

    @Override
    protected String getDatabaseName() {
        return "secure_retail_db";
    }

    @Override
    public MongoClientSettings mongoClientSettings() {
        ConnectionString connectionString = new ConnectionString(mongoUri);
        
        MongoClientSettings.builder()
                .applyConnectionString(connectionString);

        // Configure SSL context programmatically for self-signed TLS certificates
        try {
            SSLContext sslContext = SSLContext.getInstance("TLSv1.3");
            
            // In production, load the corporate certificate authority (CA) keystore
            KeyStore trustStore = KeyStore.getInstance(KeyStore.getDefaultType());
            trustStore.load(null, null); // Load empty or from file path
            
            TrustManagerFactory tmf = TrustManagerFactory.getInstance(TrustManagerFactory.getDefaultAlgorithm());
            tmf.init(trustStore);
            sslContext.init(null, tmf.getTrustManagers(), null);

            // Apply SSL settings to the MongoClient builder
            return MongoClientSettings.builder()
                    .applyConnectionString(connectionString)
                    .applyToSslSettings(builder -> builder
                            .enabled(true)
                            .invalidHostNameAllowed(false) // Strict hostname validation
                            .context(sslContext))
                    .build();
        } catch (Exception e) {
            // Fallback configuration if custom TLS Context loading fails
            return MongoClientSettings.builder()
                    .applyConnectionString(connectionString)
                    .applyToSslSettings(builder -> builder.enabled(true))
                    .build();
        }
    }
}
```

### Secure Query Implementation (NoSQL Injection Defense)
This repository service validates inputs and uses parameters bindings to prevent NoSQL injection.

```java
package com.masterclass.mongodb.service;

import com.masterclass.mongodb.domain.SecureCustomer;
import org.springframework.data.mongodb.core.MongoTemplate;
import org.springframework.data.mongodb.core.query.Criteria;
import org.springframework.data.mongodb.core.query.Query;
import org.springframework.stereotype.Service;

@Service
public class SecureCustomerService {

    private final MongoTemplate mongoTemplate;

    public SecureCustomerService(MongoTemplate mongoTemplate) {
        this.mongoTemplate = mongoTemplate;
    }

    /**
     * Retrieves a customer profile securely.
     * Uses the Criteria API to bind the input parameter, preventing NoSQL injection.
     */
    public SecureCustomer locateCustomerSecurely(String userInputEmail) {
        // Enforce basic input validation checks
        if (userInputEmail == null || userInputEmail.isBlank() || !userInputEmail.contains("@")) {
            throw new IllegalArgumentException("Malformed search input email");
        }

        // Spring Data automatically escapes and binds parameter types
        Query query = new Query(Criteria.where("email").is(userInputEmail));
        
        return mongoTemplate.findOne(query, SecureCustomer.class);
    }
}
```

---

## 7. Production Architecture Examples

### 1. Client-Side Field-Level Encryption (CSFLE) Flow
CSFLE encrypts sensitive fields on the client before they are sent over the network, ensuring the database server never sees the plaintext:

```mermaid
graph TD
    subgraph Application Client JVM
        A[PlainText SSN: 123-45-678] --> B[CSFLE Encryptor Engine]
        B -->|Fetch Encryption Key| C[KMS Provider: AWS KMS]
        C -->|Return Data Encryption Key| B
        B -->|Encrypts Field| D[CipherText Binary: BSON Binary]
    end
    
    subgraph Network Transit
        D -->|Send encrypted write request| E[(MongoDB Database Node)]
    end
    
    subgraph Database Storage
        E -->|Writes to disk| F[Document: ssn_encrypted: Binary]
        Note over F: Database engine cannot decrypt<br/>without access to KMS
    end
```

### 2. NoSQL Operator Injection Mechanics
How unsanitized JSON concatenation allows malicious queries to bypass authentication:

```mermaid
graph TD
    A[Attacker Input: email: admin@shop.com, password: {"$ne": ""}] --> B[Unsanitized JSON Builder]
    B -->|Generates Query| C["{ email: 'admin@shop.com', password: { '$ne': '' } }"]
    C -->|Execute Query| D[(MongoDB Database)]
    D -->|Evaluates password is not empty| E[Bypasses password check and returns Admin document]
```

---

## 8. Interview-Level Questions

### Q1: What is NoSQL Injection, and how does using Spring Data's `Criteria` API prevent it?
**Answer**:
* **NoSQL Injection**: Occurs when an application accepts unsanitized user input and uses it to construct database queries. In MongoDB, an attacker can inject BSON operators (like `$ne`, `$gt`, or `$where`) to bypass authentication checks or retrieve unauthorized records.
* **Prevention**: Spring Data's `Criteria` API (e.g. `Criteria.where("field").is(userInput)`) automatically wraps user input in typed variables. The MongoDB driver escapes input strings and treats them as literal values rather than executable BSON commands, preventing injection attacks.

### Q2: Explain the differences between Deterministic and Randomized encryption in CSFLE.
**Answer**:
* **Deterministic Encryption**: Always produces the same ciphertext for a given plaintext value. This allows MongoDB to perform exact match queries (`$eq`) on encrypted fields. However, it is less secure because it is vulnerable to frequency analysis attacks.
* **Randomized Encryption**: Produces a different ciphertext for the same plaintext value every time it is encrypted. This is more secure but prevents the database from performing any query filters on the encrypted field.

### Q3: What is the purpose of the Key Vault Collection in a Client-Side Encryption setup?
**Answer**:
The **Key Vault Collection** is a collection in MongoDB (usually named `admin.datakeys`) that stores the **Data Encryption Keys (DEKs)** used to encrypt individual document fields.
* The DEKs are encrypted using a **Master Key** managed by an external Key Management Service (KMS) like AWS KMS or HashiCorp Vault.
* When the application client needs to encrypt or decrypt a field, it fetches the encrypted DEK from the Key Vault, decrypts it using the KMS Master Key, and uses the decrypted DEK to process the field value.

---

## 9. Hands-on Exercises

### Exercise 1: Simulating and Mitigating NoSQL Injection
1. Create a `users` collection containing a user with password `"secretPass"`.
2. Write a vulnerable controller method that accepts a raw JSON string query and passes it to `BasicQuery`.
3. Send a request to bypass the password check:
   ```json
   { "username": "admin", "password": { "$ne": "" } }
   ```
4. Verify that the query successfully bypasses authentication and returns the user document.
5. Re-implement the query using the `Criteria` API and verify that the attack is mitigated.

---

## 10. Mini-Project: Encrypted Patient Records Portal

### Scenario
You are building the backend for a healthcare portal. 
Patient records contain sensitive health identifiers: Social Security Numbers (SSN) and diagnosis logs. 
To comply with regulatory standards:
1. The SSN field must be client-side encrypted deterministically, allowing exact-match queries.
2. The diagnosis logs must be client-side encrypted using randomized encryption, preventing queries.
3. Access to the collection must use SSL/TLS connection paths, and credentials must be loaded from configuration properties.

### Step 1: Implement the Local Key Management Encryption Service
In production, you would configure an external KMS (like AWS KMS or Azure Key Vault). 
For this project, we will implement a local key encryption utility that simulates CSFLE client-side encryption.

```java
package com.masterclass.mongodb.miniproject.security;

import javax.crypto.Cipher;
import javax.crypto.spec.SecretKeySpec;
import java.util.Base64;

public class LocalEncryptionUtil {

    private static final String ALGORITHM = "AES";
    
    // 16-byte key for local AES testing (in production, load from Key Vault / KMS)
    private static final byte[] LOCAL_MASTER_KEY = "SECRET_MASTER_KY".getBytes();

    /**
     * Simulates client-side deterministic encryption.
     */
    public static String encryptDeterministic(String value) {
        try {
            SecretKeySpec keySpec = new SecretKeySpec(LOCAL_MASTER_KEY, ALGORITHM);
            Cipher cipher = Cipher.getInstance(ALGORITHM);
            cipher.init(Cipher.ENCRYPT_MODE, keySpec);
            byte[] encryptedBytes = cipher.doFinal(value.getBytes());
            return Base64.getEncoder().encodeToString(encryptedBytes);
        } catch (Exception e) {
            throw new RuntimeException("Encryption failed", e);
        }
    }

    /**
     * Simulates client-side decryption.
     */
    public static String decrypt(String encryptedValue) {
        try {
            SecretKeySpec keySpec = new SecretKeySpec(LOCAL_MASTER_KEY, ALGORITHM);
            Cipher cipher = Cipher.getInstance(ALGORITHM);
            cipher.init(Cipher.DECRYPT_MODE, keySpec);
            byte[] decryptedBytes = cipher.doFinal(Base64.getDecoder().decode(encryptedValue));
            return new String(decryptedBytes);
        } catch (Exception e) {
            throw new RuntimeException("Decryption failed", e);
        }
    }
}
```

### Step 2: Implement the Patient Record Entity with Security Event Listeners
We will use Spring Data Lifecycle events (`BeforeSaveCallback` and `AfterLoadCallback`) to automatically encrypt sensitive fields before saving them, and decrypt them when loaded.

```java
package com.masterclass.mongodb.miniproject.model;

import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.mapping.Document;
import org.springframework.data.mongodb.core.mapping.Field;

@Document(collection = "patient_records")
public class PatientRecord {

    @Id
    private String id;
    
    private String name;

    @Field("ssn_encrypted")
    private String ssn; // Encrypted on write, decrypted on read

    @Field("diagnosis_encrypted")
    private String diagnosis; // Encrypted on write, decrypted on read

    public PatientRecord() {}

    public PatientRecord(String id, String name, String ssn, String diagnosis) {
        this.id = id;
        this.name = name;
        this.ssn = ssn;
        this.diagnosis = diagnosis;
    }

    public String getId() { return id; }
    public String getName() { return name; }
    public String getSsn() { return ssn; }
    public void setSsn(String ssn) { this.ssn = ssn; }
    public String getDiagnosis() { return diagnosis; }
    public void setDiagnosis(String diagnosis) { this.diagnosis = diagnosis; }
}
```

```java
package com.masterclass.mongodb.miniproject.listener;

import com.masterclass.mongodb.miniproject.model.PatientRecord;
import com.masterclass.mongodb.miniproject.security.LocalEncryptionUtil;
import org.springframework.data.mongodb.core.mapping.event.AfterLoadCallback;
import org.springframework.data.mongodb.core.mapping.event.BeforeSaveCallback;
import org.springframework.stereotype.Component;
import org.bson.Document;

@Component
public class PatientRecordSecurityListener 
        implements BeforeSaveCallback<PatientRecord>, AfterLoadCallback<PatientRecord> {

    @Override
    public PatientRecord onBeforeSave(PatientRecord entity, Document document, String collection) {
        // Encrypt sensitive fields on write
        if (entity.getSsn() != null) {
            document.put("ssn_encrypted", LocalEncryptionUtil.encryptDeterministic(entity.getSsn()));
        }
        if (entity.getDiagnosis() != null) {
            document.put("diagnosis_encrypted", LocalEncryptionUtil.encryptDeterministic(entity.getDiagnosis()));
        }
        return entity;
    }

    @Override
    public void onAfterLoad(PatientRecord entity, Document document, String collection) {
        // Decrypt sensitive fields on read
        if (entity.getSsn() != null) {
            entity.setSsn(LocalEncryptionUtil.decrypt(entity.getSsn()));
        }
        if (entity.getDiagnosis() != null) {
            entity.setDiagnosis(LocalEncryptionUtil.decrypt(entity.getDiagnosis()));
        }
    }
}
```

### Step 3: Implement Secure Query Portal
```java
package com.masterclass.mongodb.miniproject.service;

import com.masterclass.mongodb.miniproject.model.PatientRecord;
import com.masterclass.mongodb.miniproject.security.LocalEncryptionUtil;
import org.springframework.data.mongodb.core.MongoTemplate;
import org.springframework.data.mongodb.core.query.Criteria;
import org.springframework.data.mongodb.core.query.Query;
import org.springframework.stereotype.Service;

@Service
public class PatientPortalService {

    private final MongoTemplate mongoTemplate;

    public PatientPortalService(MongoTemplate mongoTemplate) {
        this.mongoTemplate = mongoTemplate;
    }

    /**
     * Queries a patient record by SSN.
     * Since SSN is encrypted deterministically, we must encrypt the search key
     * before running the exact-match query.
     */
    public PatientRecord findPatientBySsn(String rawSsn) {
        // Encrypt the search parameter to match the database ciphertext
        String encryptedSearchKey = LocalEncryptionUtil.encryptDeterministic(rawSsn);

        Query query = new Query(Criteria.where("ssn_encrypted").is(encryptedSearchKey));
        return mongoTemplate.findOne(query, PatientRecord.class);
    }
}
```

### Step 4: Verification CommandLineRunner
```java
package com.masterclass.mongodb.miniproject.test;

import com.masterclass.mongodb.miniproject.model.PatientRecord;
import com.masterclass.mongodb.miniproject.service.PatientPortalService;
import org.bson.Document;
import org.springframework.boot.CommandLineRunner;
import org.springframework.data.mongodb.core.MongoTemplate;
import org.springframework.stereotype.Component;

@Component
public class SecurityVerificationRunner implements CommandLineRunner {

    private final MongoTemplate mongoTemplate;
    private final PatientPortalService portalService;

    public SecurityVerificationRunner(MongoTemplate mongoTemplate, PatientPortalService portalService) {
        this.mongoTemplate = mongoTemplate;
        this.portalService = portalService;
    }

    @Override
    public void run(String... args) throws Exception {
        // Clear collections
        mongoTemplate.dropCollection(PatientRecord.class);

        // Save record (will trigger encryption listener)
        PatientRecord patient = new PatientRecord("p-101", "Gordon Freeman", "111-22-333", "Resonance Cascade Exposure");
        mongoTemplate.save(patient);

        System.out.println("Patient Record Saved.");

        // Query the raw database BSON document to verify data is encrypted on disk
        Document rawDoc = mongoTemplate.getCollection("patient_records")
                .find(new Document("_id", "p-101"))
                .first();

        System.out.println("\nDisk Storage Verification:");
        System.out.println(" - Raw Document in MongoDB: " + rawDoc.toJson());
        System.out.println(" - SSN is encrypted on disk: " + !rawDoc.getString("ssn_encrypted").equals("111-22-333"));
        System.out.println(" - Diagnosis is encrypted on disk: " + !rawDoc.getString("diagnosis_encrypted").equals("Resonance Cascade Exposure"));

        // Query using the portal service (will decrypt on read)
        PatientRecord retrieved = portalService.findPatientBySsn("111-22-333");
        
        System.out.println("\nApplication Read Verification:");
        System.out.println(" - Patient Name: " + retrieved.getName());
        System.out.println(" - Decrypted SSN (Expected: 111-22-333): " + retrieved.getSsn());
        System.out.println(" - Decrypted Diagnosis (Expected: Resonance Cascade Exposure): " + retrieved.getDiagnosis());
    }
}
```
This mini-project demonstrates how to implement client-side encryption using lifecycle events, protecting sensitive fields in the database while supporting exact-match queries.
