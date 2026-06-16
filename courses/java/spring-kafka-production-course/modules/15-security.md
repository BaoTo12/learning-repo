# Module 15 — Security

In this module, we will explore security configurations in Spring Kafka. We will cover transport layer encryption using SSL/mTLS, SASL authentication options (SCRAM-SHA-512, Kerberos/GSSAPI), broker-side Access Control Lists (ACLs), and secure credential storage. Finally, we will cover troubleshooting, answer 5 Socratic questions, and implement hands-on labs with complete code structures.

---

## 1. Academic Lecture: SSL, SASL & Broker Access Control Lists (ACLs)

### Basic Level: SSL Transport Encryption vs. SASL Authentication

#### Encryption vs. Authentication
Security in Kafka covers two main areas:
* **Transport Encryption (SSL/TLS)**: Encrypts data as it travels between microservices and Kafka brokers, preventing eavesdropping.
* **Authentication (SASL)**: Validates the identity of clients connecting to the brokers.

#### Mutual TLS (mTLS)
With mTLS (Mutual TLS):
1. The broker presents its certificate to verify its identity to the client.
2. The client presents its certificate to verify its identity to the broker.
* **KeyStore**: Contains the client's private key and certificate.
* **TrustStore**: Contains the root certificate authority (CA) certificates used to verify the broker's identity.

---

### Intermediate Level: SASL Authentication Mechanisms

If certificates are too complex to manage, you can use **SASL (Simple Authentication and Security Layer)**:
* **SASL/PLAIN**: Sends username and password in plain text. Must always be combined with SSL encryption to prevent theft.
* **SASL/SCRAM** (Salted Challenge Response Authentication Mechanism): Secure challenge-response mechanism that stores salted credentials in ZooKeeper or KRaft metadata.
  * *SCRAM-SHA-512* is the recommended standard for password-based security in enterprise environments.
* **SASL/GSSAPI (Kerberos)**: Enterprise directory integration. Highly secure but requires hosting a Kerberos Key Distribution Center (KDC).

---

### Advanced Level: Access Control Lists (ACLs) & Secrets Management

#### Access Control Lists (ACLs)
Once a client is authenticated, **Authorization** defines what actions they can perform. Kafka uses ACLs to enforce permissions:
* A principal (e.g., `User:order-service-client`) is granted permissions to execute **Operations** (`Read`, `Write`, `Describe`) on **Resources** (`Topic`, `Group`, `TransactionalId`).
* **Principle of Least Privilege**: Never grant wildcard (`*`) access to microservices. Grant `Write` access to producers only on their destination topics, and `Read` access to consumers on their input topics.

#### Secrets Management in Spring Boot
Never hardcode passwords or keystore credentials in `application.yml`. Use placeholder variables resolved from environment variables or secure vault managers (such as HashiCorp Vault or AWS Secrets Manager):
* Configuration example: `ssl.keystore.password: ${KAFKA_SSL_KEYSTORE_PASSWORD}`

---

## 2. Theory & Production Best Practices

### Mutual TLS (mTLS) vs. SASL/SCRAM

| Feature | mTLS (Mutual TLS) | SASL/SCRAM-SHA-512 |
| :--- | :--- | :--- |
| **Credential Type** | X.509 Certificates | Username and Password |
| **Revocation** | Requires updating CRL/OCSP | Simple database user deletion |
| **Broker CPU Overhead** | High (constant handshake encryption) | Low (password hash check) |
| **Setup Complexity** | High (requires CA administration) | Medium |

### SASL Authentication Options Comparison

| Mechanism | Security Strength | Setup Effort | Best Use Case |
| :--- | :--- | :--- | :--- |
| **SASL/PLAIN** | Very Low (needs TLS tunnel) | Low | Testing environments. |
| **SASL/SCRAM-SHA-512**| High | Medium | Standard enterprise microservices. |
| **SASL/GSSAPI** | Extremely High | Very High | Large scale active directory environments. |

---

## 3. Common Errors & Troubleshooting

### 1. SSL Handshake Failure
* **Symptom**: Client fails to connect, showing `javax.net.ssl.SSLHandshakeException: General SSLEngine problem`.
* **Root Cause**: The client's truststore does not contain the Certificate Authority (CA) certificate that signed the broker's certificate. The client cannot verify the broker's identity.
* **Fix**: Import the root CA certificate into the client truststore: `keytool -import -trustcacerts -file ca.crt -keystore truststore.jks`.

### 2. TopicAuthorizationException
* **Symptom**: Client crashes with `org.apache.kafka.common.errors.TopicAuthorizationException: Not authorized to access topics`.
* **Root Cause**: The client authenticated successfully, but the broker has no ACL record allowing this principal to read/write to the target topic.
* **Fix**: Grant the appropriate ACL permissions using `kafka-acls.sh` on the broker.

### 3. Keystore Password Access Denied
* **Symptom**: Boot fails with `FileNotFoundException` or `IOException: Keystore password is incorrect`.
* **Root Cause**: The keystore password variable was not injected correctly at runtime, or file access permissions are too restrictive.
* **Fix**: Verify environment variables and ensure the keystore file has read permissions for the Spring Boot JVM process.

---

## 4. Socratic Review Questions

### Question 1
*What is the difference between a Keystore and a Truststore in SSL client authentication?*
* **Answer**: The Keystore contains your own private key and certificate (used to authenticate you to others). The Truststore contains certificates of trusted Certificate Authorities (used to verify the identity of others).

### Question 2
*Why is SASL/PLAIN considered insecure, and how can we secure it?*
* **Answer**: Because it transmits credentials in plain text. We must wrap the connection in an SSL/TLS tunnel (`security.protocol = SASL_SSL`) to encrypt the credentials in transit.

### Question 3
*What Kafka ACL permissions are required for a consumer group client to start consuming?*
* **Answer**: The principal needs two permissions: `Read` and `Describe` operations on the target **Topic** resource, and `Read` operations on the target **Group** resource (matching their `group.id`).

### Question 4
*What is the purpose of wildcard ACLs, and why are they discouraged in production?*
* **Answer**: Wildcard ACLs allow access to all resources (e.g. topic `*`). They are discouraged because they violate the Principle of Least Privilege. If a microservice is compromised, the attacker can access, modify, or delete data on all topics.

### Question 5
*How does mTLS certificate expiration affect client connectivity, and how can we prevent outages?*
* **Answer**: When a client certificate expires, the broker rejects the connection, causing immediate downtime. To prevent this, set up alerts to monitor certificate expiration dates and automate renewal processes.

---

## 5. Hands-on Labs

### Lab 15.1 — Secure mTLS Spring Boot Configuration

#### Scenario
We will configure a Spring Boot application to connect securely to a Kafka cluster using mutual TLS (mTLS) transport encryption and authentication.

#### Application Properties (`application.yml`)
Add the following properties to secure the transport layer:

```yaml
spring:
  kafka:
    bootstrap-servers: broker1:9093
    security:
      protocol: SSL
    ssl:
      trust-store-location: file:/c:/Users/Admin/Desktop/projects/learning-repo/courses/secrets/truststore.jks
      trust-store-password: ${KAFKA_SSL_TRUSTSTORE_PASSWORD}
      key-store-location: file:/c:/Users/Admin/Desktop/projects/learning-repo/courses/secrets/keystore.jks
      key-store-password: ${KAFKA_SSL_KEYSTORE_PASSWORD}
      key-password: ${KAFKA_SSL_KEY_PASSWORD}
```

---

### Lab 15.2 — SASL/SCRAM-SHA-512 Configuration

#### Scenario
We will configure a Spring Boot application to authenticate using SASL/SCRAM-SHA-512 username and password credentials.

#### Application Properties (`application.yml`)
Add the following properties to configure SASL credentials securely:

```yaml
spring:
  kafka:
    bootstrap-servers: broker1:9093
    security:
      protocol: SASL_SSL # Authenticate with SASL and encrypt transport with SSL
    properties:
      sasl:
        mechanism: SCRAM-SHA-512
        jaas:
          config: org.apache.kafka.common.security.scram.ScramLoginModule required username="order-service" password="${KAFKA_SASL_PASSWORD}";
```

---

### Lab 15.3 — Broker ACL Configuration Scripts

#### Scenario
We will write a shell script using Kafka CLI tools to grant read/write permissions to a microservice client principal on a target topic.

#### Complete ACL Shell Script DDL
Create the file [setup-acls.sh](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/src/main/resources/setup-acls.sh) with the following content:

```bash
#!/bin/bash

# Kafka broker connection settings
BOOTSTRAP_SERVER="localhost:9092"

echo "Applying ACL permissions..."

# 1. Grant Write permission to Producer
kafka-acls.sh --bootstrap-server $BOOTSTRAP_SERVER \
  --add \
  --allow-principal User:order-service-client \
  --operation Write \
  --operation Describe \
  --topic orders

# 2. Grant Read permission to Consumer
kafka-acls.sh --bootstrap-server $BOOTSTRAP_SERVER \
  --add \
  --allow-principal User:billing-service-client \
  --operation Read \
  --operation Describe \
  --topic orders \
  --group billing-consumer-group

echo "ACL configuration successfully applied!"
```

---

### Step-by-Step Code Walkthrough & Parameter Configuration Tables

#### Step-by-Step Code Walkthrough

##### Lab 15.1 Walkthrough
1. **`protocol: SSL`**: Instructs the Kafka client to use mTLS certificates for connection security.
2. **`trust-store-location`**: Points to the client truststore file containing trusted CA certificates.

##### Lab 15.2 Walkthrough
1. **`SASL_SSL`**: Authenticates credentials using SASL, and encrypts the connection using SSL certificates.
2. **`jaas.config`**: Defines the JAAS config details for the `ScramLoginModule` client authentication call.

##### Lab 15.3 Walkthrough
1. **`--allow-principal User:order-service-client`**: Identifies the authenticated client ID we are configuring.
2. **`--operation Write --topic orders`**: Grants permission to write to the `orders` topic.
3. **`--group` boundary constraint**: Restricts consumer read permission to a specific consumer group name.

---

### Configuration Parameter Tables

#### Spring Boot Kafka Security Protocol Configurations

| Property Key | Expected Value | Description |
| :--- | :--- | :--- |
| `spring.kafka.security.protocol` | `PLAINTEXT`, `SSL`, `SASL_PLAINTEXT`, `SASL_SSL` | Defines transport and authentication protocols. |
| `sasl.mechanism` | `SCRAM-SHA-256`, `SCRAM-SHA-512`, `GSSAPI` | Specifies the SASL challenge-response mechanism. |

