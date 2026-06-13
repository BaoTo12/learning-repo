# Module 19: An Introduction to MongoDB Security (Chapter 19)

Welcome class. Today we analyze **An Introduction to MongoDB Security (CS-529)**.

Securing production databases requires enforcing strict authorization and encryption boundaries. Databases must protect against unauthorized network connections, validate identities using strong credentials, and encrypt all data in transit across the cluster.

Today we study **Database Security Engineering**, analyzing Role-Based Access Control (RBAC), SCRAM mechanisms, client TLS/SSL handshakes, and generating cluster x.509 member certificates.

---

## 1. Academic Lecture: RBAC Authorization & TLS Encryption

### 1. Role-Based Access Control (RBAC)
MongoDB enforces authorization using roles. Users are assigned specific roles (e.g., `readWrite`, `dbAdmin`, `root`) restricted to defined database contexts.
*   **SCRAM (Salted Challenge Response Authentication Mechanism)**: The default authentication protocol. The client and server verify credentials without transmitting passwords over the network.

### 2. Cluster Encryption (x.509)
In a production replica set or sharded cluster, nodes must communicate with each other securely.
*   **x.509 Certificates**: Instead of using shared secrets (keyfiles), nodes use mutual TLS (mTLS) with x.509 certificates issued by a trusted Certificate Authority (CA) to authenticate each other and encrypt data in transit.

```text
[Primary Node] <─── Mutual TLS (x.509 Cert) ───> [Secondary Node]
                    (Verifies CA signature)
```

---

## 2. Theory vs. Production Trade-offs

Compare cluster authentication mechanisms:

| Dimension / Metric | No Authentication | Keyfiles (Shared Secret) | x.509 Certificates (mTLS) |
| :--- | :--- | :--- | :--- |
| **Cluster Security** | Zero (Vulnerable to exploits) | Moderate | Absolute (Cryptographic validation) |
| **Setup Complexity** | Zero | Low (Single file shared) | High (Requires CA and cert management) |
| **Rotation Support** | None | Hard (Requires node restarts) | Easy (Online rotation in modern engines) |
| **Network Overhead** | Low | Low | Moderate (TLS handshake negotiation) |
| **Enterprise Standard**| Unacceptable | Small deployments | Mandatory |

---

## 3. How to Use: Securing Collections and Users

Let us configure database authorization. We contrast an un-authenticated public database deployment (vulnerable to data leaks) with a secure, role-restricted deployment.

### A. The Public Administrator Mode (Anti-Pattern)
Avoid running MongoDB without authentication enabled:

```javascript
// DANGER: Running MongoDB with auth disabled binds to public IP addresses,
// allowing anyone to access, modify, or delete your entire database.
```

### B. The Hardened RBAC Configuration (Production Pattern)
Enable authentication, create an admin superuser, and define a database-restricted readWrite user:

```javascript
// Robust Pattern 1: Run mongod with security enabled: mongod --auth

// Robust Pattern 2: Create a restricted application user in the target database.
db.getSiblingDB("ecommerce").createUser({
  user: "appServer",
  pwd: passwordPrompt(), // Secure password prompt input
  roles: [
    { role: "readWrite", db: "ecommerce" }
  ]
});
```

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Reusing x.509 Certificates Across Different Clusters
*   **Why it fails**: Using the same x.509 certificate for nodes in the staging cluster and the production cluster. If a staging node is compromised, the attacker can use its certificate to authenticate and join the production replica set as a member, gaining full access to the database.
*   **Mitigation**: Issue distinct certificates for each cluster environment. Restrict certificates using `O` (Organization) and `OU` (Organizational Unit) name constraints in the configuration.

---

## 5. Socratic Review Questions

### Question 1
Why does SCRAM authentication protect the database from timing attacks compared to basic plain-text password checks?

#### Answer
SCRAM does not compare plain-text password strings. Instead, it uses cryptographic challenges (HMAC-SHA-256) with unique iteration counts and salt values. The server validates the cryptographic proof computed by the client. This validation runs in constant time, preventing attackers from using timing differences to guess password hashes.

---

## 6. Hands-on Challenge: Constructing RBAC Roles

### The Challenge
In this challenge, you will implement database authorization.
Your task:
1. Write a script to create a custom role named `analyticsReader` in the `reporting` database.
2. The role must grant:
   - `find` action on all collections in the `reporting` database.
   - `listCollections` action on the `reporting` database.
   - No write privileges.

Complete the command stub below:

```javascript
// TODO: Create the custom role in the reporting database
db.getSiblingDB("reporting").createRole({
  role: "analyticsReader",
  privileges: [
    // Add target actions and resources here
  ],
  roles: []
});
```

### Verification Query
Validate the role:
```javascript
const roleInfo = db.getSiblingDB("reporting").getRole("analyticsReader", { showPrivileges: true });
if (roleInfo && roleInfo.privileges.length > 0) {
  print("Success: Custom read-only role defined successfully.");
} else {
  print("Error: Role configuration failed.");
}
```
