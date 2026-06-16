# Module 12: Security

Welcome class. Today we analyze security configurations and client-side encryption using **Spring Data MongoDB Security (CS-530)**.

To protect sensitive information, databases must implement authentication, authorization, secure transport, and field-level encryption. Today we study role-based access control, SSL/TLS, and Client-Side Field-Level Encryption (CSFLE).

---

## 1. Academic Lecture: Security & Field-Level Encryption

### Basic Level: Database Security Basics
Securing a database requires:
1.  **Transport Security (TLS/SSL)**: Encrypting traffic between applications and the database.
2.  **Authentication**: Verifying client identities (using username/password or certificate-based auth).
3.  **Role-Based Access Control (RBAC)**: Granting specific permissions to users (e.g., read-only access to specific databases).

### Intermediate Level: SSL/TLS Configurations
We configure secure transport parameters in Spring Boot using the application properties or a MongoClient bean:
*   Enabling SSL/TLS configurations: `ssl=true`.
*   Truststore mapping: Configuring truststore paths to allow JVM processes to trust self-signed database certificates.

### Advanced Level: Client-Side Field-Level Encryption (CSFLE)
*   **What is CSFLE?**: Standard database encryption encrypts data on disk (encryption-at-rest). However, database administrators can still read plain-text values in memory. CSFLE encrypts sensitive fields *on the client* before sending the BSON payload over the network.
*   **Key Vaults & Keys**: CSFLE uses a Key Vault collection (usually in a separate database) storing Data Encryption Keys (DEKs). These DEKs are wrapped using a master Key Encryption Key (KEK) hosted on a Key Management Service (KMS) like AWS KMS, Azure Key Vault, Google Cloud KMS, or a local file key.
*   **CSFLE Encryption Flow**:
    1.  The client requests a write.
    2.  The driver fetches the Data Encryption Key (DEK) from the Key Vault.
    3.  If not in cache, the driver decrypts the DEK using the KMS provider's master key (KEK).
    4.  The driver encrypts the field value locally using the decrypted DEK.
    5.  The encrypted BSON payload is sent to MongoDB.

```mermaid
sequenceDiagram
    participant App as Spring App
    participant Drv as Mongo Driver
    participant KMS as KMS Provider (AWS/GCP)
    participant DB as MongoDB Instance
    App->>Drv: Save User { ssn: "123-45" }
    Drv->>DB: Fetch DEK from KeyVault
    DB-->>Drv: Encrypted DEK
    Drv->>KMS: Decrypt DEK using KEK
    KMS-->>Drv: Plaintext DEK
    Drv->>Drv: Encrypt "123-45" to BSON Binary
    Drv->>DB: Save User { ssn: BinaryData }
```

---

## 2. Theory vs. Production Trade-offs

| Encryption Type | Execution Location | DB Admin Visibility | Performance Impact | Setup Complexity |
| :--- | :--- | :--- | :--- | :--- |
| **None** | None | Fully Visible | Zero | Low |
| **Encryption at Rest** | DB Storage Engine | Visible in memory | Low | Moderate |
| **CSFLE (Client-Side)** | Application Driver | Binary cipher text | Moderate-High (Client CPU) | High |

---

## 3. How to Use: Configuring SSL and Client-Side Field-Level Encryption

Below we show an un-encrypted configuration (anti-pattern) followed by a production-ready Client-Side Field-Level Encryption config.

### A. Unencrypted Configuration (Anti-Pattern)
*Avoid storing sensitive data (SSN, credit cards) in plain text:*

```yaml
# DANGER: Plaintext data can be read by database administrators,
# compromised read replicas, or during memory dumps.
spring:
  data:
    mongodb:
      uri: mongodb://admin:secret@localhost:27017/finance
```

### B. CSFLE Secure Client Configuration (Production Pattern)
Here is the client configuration utilizing KMS Local Key encryption for sensitive fields.

```java
package com.masterclass.mongodb.config;

import com.mongodb.ClientEncryptionSettings;
import com.mongodb.ConnectionString;
import com.mongodb.MongoClientSettings;
import com.mongodb.client.MongoClient;
import com.mongodb.client.MongoClients;
import com.mongodb.client.vault.ClientEncryption;
import com.mongodb.client.vault.ClientEncryptions;
import org.bson.BsonBinary;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import java.util.HashMap;
import java.util.Map;

@Configuration
public class EncryptionMongoConfig {

    /**
     * Configures the ClientEncryption manager using a local KMS provider key.
     * In production, replace the local key with an AWS, Azure, or GCP KMS configuration.
     */
    @Bean
    public ClientEncryption clientEncryption(MongoClient mongoClient) {
        // 96-byte local master key representation
        byte[] localMasterKey = new byte[96]; 
        // In production, load this secure byte array from an environment variable or key vault
        
        Map<String, Map<String, Object>> kmsProviders = new HashMap<>();
        Map<String, Object> localKeyMap = new HashMap<>();
        localKeyMap.put("key", localMasterKey);
        kmsProviders.put("local", localKeyMap);

        ClientEncryptionSettings settings = ClientEncryptionSettings.builder()
                .keyVaultMongoClientSettings(MongoClientSettings.builder()
                        .applyConnectionString(new ConnectionString("mongodb://localhost:27017"))
                        .build())
                .keyVaultNamespace("encryption.__keyVault")
                .kmsProviders(kmsProviders)
                .build();

        return ClientEncryptions.create(settings);
    }
}
```

```java
package com.masterclass.mongodb.service;

import com.mongodb.client.model.vault.EncryptOptions;
import com.mongodb.client.vault.ClientEncryption;
import org.bson.BsonBinary;
import org.bson.BsonString;
import org.springframework.stereotype.Service;

@Service
public class SecureDataService {

    private final ClientEncryption clientEncryption;

    public SecureDataService(ClientEncryption clientEncryption) {
        this.clientEncryption = clientEncryption;
    }

    /**
     * Encrypts sensitive fields manually using Client-Side Field-Level Encryption.
     * Uses a deterministic encryption algorithm to allow exact match searches.
     *
     * @param plainText The value to encrypt
     * @param dataKeyId The UUID identifier of the data encryption key
     */
    public BsonBinary encryptDeterministicField(String plainText, BsonBinary dataKeyId) {
        EncryptOptions options = new EncryptOptions("AEAD_AES_256_CBC_HMAC_SHA256-Deterministic")
                .keyId(dataKeyId);

        return clientEncryption.encrypt(new BsonString(plainText), options);
    }
}
```

### Line-by-Line Code Explanation:
1.  `ClientEncryptionSettings`: Configures the encryption driver, specifying where to store key vault data (`encryption.__keyVault`) and registering the KMS provider configuration.
2.  `ClientEncryptions.create(...)`: Initializes the driver-level encryption loop.
3.  `AEAD_AES_256_CBC_HMAC_SHA256-Deterministic`: Algorithm configuration. Deterministic encryption produces the same ciphertext for a given plaintext value, enabling indexing and exact-match queries. Randomized encryption (`AEAD_AES_256_CBC_HMAC_SHA256-Randomized`) prevents indexing but is more secure.

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Querying Randomized Encrypted Fields
*   **Why it fails**: If you encrypt a field (e.g., `ssn`) using a randomized algorithm, encrypting `"123-45"` produces different ciphertexts every time (e.g., `cipher_abc` then `cipher_xyz`). If you execute a query like `db.users.find({ ssn: "123-45" })`, the driver encrypts `"123-45"` at runtime. If it encrypts to `cipher_abc` but the document contains `cipher_xyz`, the query fails to find the record.
*   **Mitigation**: Use deterministic encryption for fields that require exact-match querying. Use randomized encryption for fields that do not need to be queried (e.g., profile pictures, descriptions).

---

## 5. Socratic Review Questions

### Question 1
Explain the difference between deterministic and randomized encryption in Client-Side Field-Level Encryption (CSFLE). Which one supports index lookups?

#### Answer
Deterministic encryption produces the same ciphertext value for a given plaintext value under the same key. This allows MongoDB to index the encrypted binary data and perform exact-match lookups. Randomized encryption produces different ciphertexts for the same plaintext value every time it is run, preventing index lookups but providing stronger security.

---

## 6. Hands-on Challenge: Encryption Helper Implementation

### The Challenge
In this challenge, you will implement a utility method to check if a byte array is valid as a KMS key representation.
Your task:
1. Complete `KmsKeyValidator.java`.
2. Verify if the provided key is not null and is exactly 96 bytes long (required for local KMS keys).

Complete the implementation stub:

```java
package com.masterclass.mongodb.challenge;

public class KmsKeyValidator {

    public static boolean isValidLocalKmsKey(byte[] keyBytes) {
        // TODO: Return true if the keyBytes array is not null and has a length of exactly 96 bytes
        return keyBytes != null && keyBytes.length == 96;
    }
}
```

### Verification Test
Verify your code with this JUnit 5 test class:

```java
package com.masterclass.mongodb.challenge;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class KmsKeyValidatorTest {

    @Test
    void testIsValidLocalKmsKey() {
        byte[] valid = new byte[96];
        byte[] invalidShort = new byte[64];
        byte[] invalidNull = null;

        assertTrue(KmsKeyValidator.isValidLocalKmsKey(valid));
        assertFalse(KmsKeyValidator.isValidLocalKmsKey(invalidShort));
        assertFalse(KmsKeyValidator.isValidLocalKmsKey(invalidNull));
    }
}
```
