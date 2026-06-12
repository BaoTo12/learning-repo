# Module 10: Security & Operations Tuning

## 1. What Problem This Module Solves
Securing data and maintaining database performance in production is a critical responsibility. A standard database deployment is vulnerable to security breaches if data is not encrypted in transit or at rest. Similarly, a database server will experience performance bottlenecks if operating system limits and database engine settings are not configured correctly.

This module addresses security and operational tuning. A senior engineer must understand Client-Side Field-Level Encryption (CSFLE), Queryable Encryption, Key Management Services (KMS), memory and CPU capacity planning, and operating system optimizations. Without this knowledge, you risk data leaks, operational instability, and resource starvation in production environments.

---

## 2. Why This Topic Matters
Security is not an afterthought; it must be designed into the database architecture. Traditional database encryption (Encryption at Rest) protects data on disk, but the database engine can still read all data in memory, making it vulnerable to database administrator (DBA) access or memory leaks.

Furthermore, running MongoDB under default operating system configurations (e.g. enabling NUMA or using default swap rates) can cause sudden server crashes and latency spikes under heavy loads. This module provides the technical details required to deploy a secure, high-performance database instance.

---

## 3. Core Concepts & Internals

### 3.1 Client-Side Field-Level Encryption (CSFLE) & Queryable Encryption
MongoDB supports encrypting sensitive fields *before* they are sent over the network to the database engine.

```
 [Client Application]
         │ (Checks schema map)
         ├──────────────────────────┐
         ▼ (Finds sensitive field)  │
 [Request Key from KMS]             │
         │                          │
         ▼ (Fetch DEK)              │
 [Encrypt Field in Driver]          │
         │ (Plaintext -> Cipher)    ▼ (Non-sensitive fields)
         ├──────────────────────────┘
         ▼ (Sends encrypted BSON payload)
 [mongod Database Engine] ── (Only sees ciphertext for encrypted fields)
```

#### CSFLE Mechanics:
1.  **Schema Map Configuration**: The client driver is configured with a JSON Schema map that identifies which collection fields must be encrypted.
2.  **Key Vault and KMS**: The key vault is a collection (e.g. `encryption.__keyVault`) that stores encrypted **Data Encryption Keys (DEKs)**. The master key that encrypts these DEKs is held in an external Key Management Service (KMS), such as AWS KMS, Azure Key Vault, Google Cloud KMS, or HashiCorp Vault.
3.  **Client-side Encryption**: When the client driver inserts a document, it:
    *   Requests the DEK from the key vault collection.
    *   Decrypts the DEK using the master key from the KMS.
    *   Encrypts the sensitive field values using the DEK.
    *   Sends the encrypted BSON document to the database engine.
4.  **Database View**: The database engine only sees ciphertext for the encrypted fields. It cannot decrypt or read the values.

#### CSFLE vs. Queryable Encryption:
*   **CSFLE (Deterministic)**: Always encrypts a specific plaintext value to the same ciphertext. This allows exact match queries on the database (e.g. `{ ssn: encryptedSSN }`), but it is less secure because it is vulnerable to frequency analysis attacks. Randomized encryption is more secure, but prevents exact match queries.
*   **Queryable Encryption**: Introduced in MongoDB 6.0, this allows applications to run search queries (exact matches, range searches, and prefix/suffix searches) on randomized encrypted fields using advanced cryptographic techniques (such as structured encryption). This provides high security and query flexibility without exposing sensitive data.

---

### 3.2 Role-Based Access Control (RBAC) & Custom Roles
MongoDB uses Role-Based Access Control to manage database permissions.

#### Built-in Roles:
*   `read`: Grants read-only access to user collections.
*   `readWrite`: Grants read and modify access to user collections.
*   `dbAdmin`: Grants administrative access (e.g. index management, statistics queries) but not read/write access.
*   `userAdmin`: Grants ability to create and manage users for the database.
*   `dbOwner`: Combines `readWrite`, `dbAdmin`, and `userAdmin` roles.
*   `root`: Superuser role; available only on the `admin` database.

#### Custom Role Configuration:
If built-in roles do not meet your security requirements, you can define custom roles with precise privilege structures:
```javascript
db.getSiblingDB("admin").createRole({
  role: "restrictedOperator",
  privileges: [
    {
      resource: { db: "ecommerce_db", collection: "orders" },
      actions: ["find", "update"] // Can read and update orders, but cannot insert or delete
    },
    {
      resource: { db: "ecommerce_db", collection: "" }, // All collections in database
      actions: ["collStats"]
    }
  ],
  roles: [] // List of inherited roles
});
```

---

### 3.3 Audit Logging Configurations
Audit logs record administrative operations and security events. You configure audit logging in `/etc/mongod.conf`:

```yaml
auditLog:
  destination: file
  format: JSON
  path: /var/log/mongodb/audit.json
  filter: '{ "atype": { "$in": ["authCheck", "createCollection", "dropCollection"] } }'
```

#### Audit Event Structure:
```json
{
  "atype": "authCheck",
  "ts": { "$date": "2026-06-12T07:32:00Z" },
  "local": { "ip": "127.0.0.1", "port": 27017 },
  "remote": { "ip": "192.168.1.102", "port": 49152 },
  "users": [ { "user": "CN=admin,OU=Engineering,O=EcommerceCorp", "db": "$external" } ],
  "roles": [ { "role": "root", "db": "admin" } ],
  "param": {
    "db": "ecommerce_db",
    "collection": "orders",
    "command": "find"
  },
  "result": 0 // 0 indicates success, non-zero indicates authorization failure
}
```

---

### 3.4 Operating System Tuning & WiredTiger Cache Sizing
To prevent resource contention and latency spikes under production workloads, you must tune the underlying Linux host settings:

#### 1. Non-Uniform Memory Access (NUMA) Settings:
*   **The Problem**: NUMA partitions memory across CPU sockets. By default, Linux allocates memory from the local CPU socket. If that socket runs out of memory, Linux can swap memory pages even if other sockets have free RAM, causing query delays.
*   **Tuning**: MongoDB requires NUMA to be disabled or set to interleave memory allocation:
    ```bash
    # Start mongod using numactl interleave
    numactl --interleave=all mongod --config /etc/mongod.conf
    ```

#### 2. Virtual Memory Swappiness (`vm.swappiness`):
*   **The Problem**: Linux swaps memory pages to disk to free up active memory. Swapping WiredTiger cache memory to disk degrades performance.
*   **Tuning**: Set `vm.swappiness` to `1` (or `0` on older kernels) to prevent the OS from swapping database memory unless absolutely necessary:
    ```bash
    sysctl -w vm.swappiness=1
    ```

#### 3. Storage Mount Options & I/O Schedulers:
*   **`noatime`**: Mount the database disk volumes with the `noatime` option to prevent the OS from writing access times to metadata during reads, reducing disk write overhead:
    ```bash
    /dev/xvdf /var/lib/mongodb xfs defaults,noatime 0 2
    ```
*   **I/O Scheduler**: For solid-state drives (SSDs), use the `none` or `kyber` I/O scheduler to bypass OS-level buffering and allow the drive to schedule requests:
    ```bash
    echo none > /sys/block/sdf/queue/scheduler
    ```

#### 4. Ulimits and Limits Configuration:
Verify system ulimits inside `/etc/security/limits.conf` to prevent process resource exhaustion:
```
mongod soft nofile 64000
mongod hard nofile 64000
mongod soft nproc 32000
mongod hard nproc 32000
```

#### 5. WiredTiger Cache Sizing:
*   **Capacity Formula**:
    $$\text{WT Cache Size} = 0.5 \times (\text{Total System RAM} - 1\text{GB})$$
*   *Tuning Tip*: Leave remaining system RAM free for the operating system page cache. The OS page cache caches compressed data pages and manages file IO, improving read throughput.

---

## 4. Practical Examples

### Complete CSFLE Local Key Vault Setup (Node.js)
The following script demonstrates how to set up client-side field-level encryption, generate a local master key, create a data encryption key (DEK) in the key vault, and configure the client driver to automatically encrypt social security numbers.

```javascript
/**
 * Client-Side Field-Level Encryption (CSFLE) Setup
 * Generates local keys and configures automatic client-side encryption.
 */
const { MongoClient, ClientEncryption } = require('mongodb');
const crypto = require('crypto');
const log = require('console');
const fs = require('fs');

const localKeyPath = './master-key.txt';

// Generate local master key if not present (must be 96 bytes)
if (!fs.existsSync(localKeyPath)) {
  fs.writeFileSync(localKeyPath, crypto.randomBytes(96));
}
const localMasterKey = fs.readFileSync(localKeyPath);

const kmsProviders = {
  local: {
    key: localMasterKey
  }
};

const keyVaultNamespace = 'encryption.__keyVault';
const uri = 'mongodb://localhost:27017/?replicaSet=rs0';

async function setupEncryption() {
  const client = new MongoClient(uri);
  await client.connect();

  const keyVault = client.db('encryption').collection('__keyVault');
  await keyVault.createIndex({ keyAltNames: 1 }, { unique: true, sparse: true });

  const clientEncryption = new ClientEncryption(client, {
    keyVaultNamespace,
    kmsProviders
  });

  // Create a Data Encryption Key (DEK)
  log.info("Generating Data Encryption Key (DEK) in Vault...");
  const dataKeyId = await clientEncryption.createDataKey('local', {
    keyAltNames: ['ssnKeyAltName']
  });

  log.info("DEK generated successfully. UUID:", dataKeyId.toString('base64'));

  // Configure BSON Schema Map for automatic encryption
  const schemaMap = {
    'ecommerce_db.customers': {
      bsonType: 'object',
      properties: {
        socialSecurityNumber: {
          encrypt: {
            bsonType: 'string',
            algorithm: 'AEAD_AES_256_CBC_HMAC_SHA_512-Deterministic',
            keyId: [dataKeyId]
          }
        }
      }
    }
  };

  // Start client with automatic encryption enabled
  const secureClient = new MongoClient(uri, {
    autoEncryption: {
      keyVaultNamespace,
      kmsProviders,
      schemaMap
    }
  });

  await secureClient.connect();
  const db = secureClient.db('ecommerce_db');
  const customers = db.collection('customers');

  // Insert document - driver automatically encrypts the field
  await customers.insertOne({
    name: "John Doe",
    socialSecurityNumber: "123-456-7890"
  });
  log.info("Encrypted document inserted successfully.");

  // Fetch document using secure client (automatically decrypts)
  const doc = await customers.findOne({ name: "John Doe" });
  log.info("Decrypted SSN read from client:", doc.socialSecurityNumber);

  // Fetch document using raw client (shows ciphertext)
  const rawDoc = await client.db('ecommerce_db').collection('customers').findOne({ name: "John Doe" });
  log.info("Raw BSON document stored in database:", rawDoc.socialSecurityNumber);

  await client.close();
  await secureClient.close();
}

setupEncryption().catch(err => log.error("Encryption setup failed:", err));
```

---

### Production Deployment with mTLS and SSL/TLS Authentication (Docker Compose)
The following configuration shows how to deploy a secure MongoDB instance using mutual TLS (mTLS) certificate authentication.

```yaml
version: '3.8'

services:
  secure-mongo:
    image: mongo:6.0
    container_name: secure_mongo
    command: >
      mongod --sslMode requireSSL
             --sslPEMKeyFile /etc/ssl/mongodb.pem
             --sslCAFile /etc/ssl/ca.pem
             --sslClusterFile /etc/ssl/cluster.pem
             --auth
             --bind_ip_all
    volumes:
      - ./certs/mongodb.pem:/etc/ssl/mongodb.pem:ro
      - ./certs/ca.pem:/etc/ssl/ca.pem:ro
      - ./certs/cluster.pem:/etc/ssl/cluster.pem:ro
      - secure_db_data:/data/db
    ports:
      - 27017:27017

volumes:
  secure_db_data:
```

---

### Initializing mTLS User Authentication (Bash / mongosh)
This script demonstrates how to connect to the secure instance and create an administrator user authenticated using x.509 client certificates.

```bash
#!/usr/bin/env bash
# Secure User Setup Script

# 1. Connect to the SSL database using the CA and client certificate
echo "Connecting to the database using mTLS certificates..."
mongosh --host "secure_mongo" \
        --tls \
        --tlsCertificateKeyFile ./certs/client.pem \
        --tlsCAFile ./certs/ca.pem \
        --eval '
  // Create x.509 authenticated administrator user
  db.getSiblingDB("$external").createUser({
    user: "CN=admin,OU=Engineering,O=EcommerceCorp",
    roles: [
      { role: "root", db: "admin" }
    ]
  });
  print("Authenticated administrator user created successfully.");
'
```

---

## 5. Trade-offs & Alternatives

Choosing a security and operational architecture involves trade-offs between protection levels and resource usage:

| Security Pattern | Protection Level | Performance Overhead | Operational Complexity | Primary Use Case |
| :--- | :--- | :--- | :--- | :--- |
| **Transport Encryption (TLS/SSL)** | **Standard**: Encrypts data in transit. | **Low**: Minor CPU overhead for handshake and encryption. | **Medium**: Requires certificate generation and rotation. | Standard production environments. |
| **Encryption at Rest** | **Standard**: Encrypts physical storage disks. | **Low**: Handled by the storage engine or host OS. | **Low** | Compliance requirements, protecting physical disks. |
| **Client-Side Field Encryption (CSFLE)** | **Maximum**: Encrypts fields before sending to database. | **High**: Client-side CPU overhead for crypt processing. | **High**: Requires KMS integration and schema mapping. | High-security fields (SSNs, credit cards, bank accounts). |
| **Queryable Encryption** | **Maximum**: Allows queries on randomized encrypted fields. | **High**: Crypt processing overhead. | **High**: Requires KMS integration and key management. | Sensitive searchable fields (emails, phone numbers). |

---

## 6. Common Mistakes & Anti-patterns
*   **Leaving NUMA Enabled on Linux Hosts**: Running MongoDB on Linux hosts with NUMA enabled. This can lead to memory allocation imbalances and page swapping, causing query delays and system instability.
*   **Using Deterministic CSFLE for Low-Entropy Fields**: Encrypting fields with low cardinality (e.g. status, gender) using deterministic encryption. This allows attackers to decrypt values using frequency analysis. Use randomized encryption for low-entropy fields.
*   **Under-sizing System Swap Space**: Disabling swap space entirely on production database servers. If the system experiences sudden memory spikes, the Linux Out-Of-Memory (OOM) killer will terminate the `mongod` process, causing unplanned downtime. Configure a small swap partition with `vm.swappiness=1` instead.

---

## 7. Hands-on Exercises
1.  Configure a secure MongoDB deployment using mTLS certificates and the Docker Compose file from Section 4.
2.  Generate client certificates and authenticate using `mongosh` via x.509 certificate authentication.
3.  Write a script to check the NUMA configuration and swappiness settings on a Linux host.
4.  Configure Client-Side Field-Level Encryption using a mock KMS provider (local master key) and verify that encrypted fields are stored as ciphertext in the database.

---

## 8. Mini-Project: Security Hardening Audit
**Scenario**: Audit and harden a production MongoDB deployment.

1.  Review a target database configuration and identify security gaps, such as:
    *   No TLS configuration.
    *   Missing authentication rules.
    *   Operating system settings with NUMA active or swappiness set to default values.
2.  Configure security rules to:
    *   Restrict network access using IP binding.
    *   Enable role-based access control (RBAC) and configure custom roles.
    *   Deploy SSL/TLS certificates and enforce transport encryption.
3.  Write a hardening report listing the identified gaps, the implemented fixes, and verification checks.

---

## 9. Interview Questions

### Q1: What is the difference between Deterministic and Randomized encryption algorithms in CSFLE?
**Answer**:
*   **Deterministic Encryption** always encrypts a specific plaintext value to the same ciphertext. This allows exact match queries on the database (e.g. `{ ssn: encryptedSSN }`), but it is less secure because it is vulnerable to frequency analysis attacks.
*   **Randomized (Probabilistic) Encryption** encrypts the same plaintext value to a different ciphertext every time. This is highly secure, but the database cannot perform match queries on the encrypted fields without decrypting them first.

### Q2: How do you calculate the required RAM size for a production MongoDB server?
**Answer**: To prevent performance bottlenecks, the database RAM must accommodate the index size and active hot data (the Working Set). The capacity model formula is:
$$\text{Required RAM} \ge \frac{\text{Size of All Indexes} + \text{Active Hot Data (30 days)}}{\text{Target Cache Utilization (e.g. 0.8)}} + 1\text{GB}$$
If your indexes take 10GB and your hot active data is 20GB, you need at least 38.5GB of RAM. If RAM size is less than this, the database will experience page faults and disk swapping, degrading performance.

### Q3: Why is disabling NUMA memory allocation critical for MongoDB databases?
**Answer**: NUMA partitions memory across CPU sockets. If a database process requests memory from a CPU socket that is full, Linux may swap memory pages to disk to satisfy the request, even if other sockets have free RAM. This disk swapping introduces random query latency. Disabling NUMA or setting it to interleave memory ensures that memory allocations are distributed uniformly across all sockets, preventing swapping.

---

---

---

## 10. Production Runbook & Deployment Guidelines

### 1. Secure Certificate Rotation Runbook
To rotate mTLS certificates in production without database downtime:
1. Deploy the new CA and client certificates to the server hosts.
2. Restart the secondaries one-by-one using the updated certificate files.
3. Step down the primary, wait for election, and restart the old primary.
4. Verify that client drivers connect successfully using the new certificates.

### 2. Auditing User Connections
Regularly monitor access logs and query audits for unauthorized command executions:
```bash
grep "authCheck" /var/log/mongodb/audit.json | grep "result": 13" # Filter auth failures
```

## 11. Appendix: Advanced Troubleshooting & Operational Failure Modes

### 1. CSFLE Key Rotation Conflicts
*   **Failure Mode**: Rotating master keys in the KMS without updating registered data keys leaves fields unreadable, throwing decryption errors.
*   **Resolution**: Configure key rotation processes in the KMS to maintain compatibility with older key versions.

### 2. NUMA Memory Node Page Swapping
*   **Failure Mode**: Linux swaps database memory to disk even if other sockets have free RAM, causing latency spikes.
*   **Resolution**: Start the `mongod` daemon using `numactl --interleave=all`.

### 3. File Descriptor Limit Exhaustion
*   **Failure Mode**: MongoDB reaches Linux file descriptor limits, rejecting new client connections.
*   **Resolution**: Enforce system ulimits to at least 64,000 open files.

---

## 12. Summary
Production database deployments require securing data and optimizing resource usage. By leveraging mTLS certificate authentication, configuring Client-Side Field-Level Encryption, tuning OS settings (NUMA, swappiness, mount options), and allocating WiredTiger cache size correctly, senior engineers build secure, high-performance database infrastructure.

---

## 11. Enterprise Case Study: Mutual TLS Certificate Expiry & Rotation Lockout

### 1. Scenario Description
A financial services cluster enforces strict mutual TLS (mTLS) authentication for all database access. The system administrators scheduled a rolling certificate renewal. During the deployment, the team updated the primary node first. This triggered a cluster disconnection: secondary nodes rejected connections from the primary, and client drivers were locked out from the database, causing a complete system outage.

### 2. Analytical Diagnostic Investigation
The admin team opened log files on the primary node and saw repeating handshake failures:
```text
{"t":{"$date":"2026-06-12T07:15:22.102Z"},"s":"E", "c":"NETWORK", "id":23280, "ctx":"conn42","msg":"SSL handshake failed","attr":{"error":"SSL peer certificate validation failed: Certificate has expired or CA chain mismatch."}}
```
**Diagnostic Findings**:
*   The renewal script updated the CA file, but did not deploy the complete intermediate certificate bundle containing both the old and new root certificates.
*   When the primary restarted with the new certificate, secondaries (which still used the old CA file) could not authenticate the primary's certificate, blocking replication connection attempts.
*   Client drivers also failed to connect because their trust stores lacked the new CA certificate.

### 3. Step-by-Step Certificate Rotation Runbook
To rotate certificates in production without database downtime, you must follow this exact rolling sequence:

1.  **Generate and Distribute Combined CA Certificate Bundle**:
    Combine the old and new root CA certificates into a single `ca.pem` file. This ensures the database will accept certificates signed by either authority:
    ```bash
    cat new_ca.crt old_ca.crt > combined_ca.pem
    ```
2.  **Distribute the Combined CA to All Database Nodes**:
    Deploy `combined_ca.pem` to the TLS directory on all cluster nodes without restarting.
3.  **Perform Rolling Update of Server Certificates**:
    For each secondary node:
    *   Deploy the new server certificate (signed by the new CA).
    *   Configure `mongod.conf` to use the new server certificate and the `combined_ca.pem`.
    *   Restart the node and verify that it rejoins the replica set: `rs.status()`
4.  **Step Down the Primary**:
    Force the primary node to step down to allow a secondary to become the new primary:
    ```javascript
    rs.stepDown(120);
    ```
5.  **Update the Former Primary Node**:
    Deploy the new certificate to the former primary and restart the node.
6.  **Deploy New Client Certificates**:
    Once all database nodes trust both authorities, update client application certificates.
7.  **Clean Up the CA Bundle**:
    Once all nodes and client drivers are updated, remove the old CA from the combined file, leaving only the new root CA for security enforcement.

### 4. Code Artifact: OpenSSL CA and Certificate Generation Script
Save this script as `generate-certs.sh` to build compliant cert configurations:
```bash
#!/usr/bin/env bash
set -euo pipefail

echo "Generating mTLS Certificate Authority and keys..."

# 1. Create Root CA
openssl genrsa -out ca.key 4096
openssl req -x509 -new -nodes -key ca.key -sha256 -days 365   -subj "/CN=DatabaseCA" -out ca.crt

# 2. Create Server Certificate Request
openssl genrsa -out server.key 2048
openssl req -new -key server.key   -subj "/CN=mongodb-server.internal" -out server.csr

# 3. Sign Server Certificate with CA
openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial   -out server.crt -days 365 -sha256

# 4. Combine key and cert for MongoDB PEM format
cat server.key server.crt > mongodb.pem

echo "Certificates created successfully: mongodb.pem, ca.crt"
```

### 5. Architectural Trade-offs & Lessons Learned
*   **PEM Files Contain Keys and Certs**: MongoDB expects server certificates and private keys to be combined into a single `.pem` file. If they are separated, the service will fail to start.
*   **Verify San Subject Alternative Names**: Ensure server certificates contain valid SANs matching the DNS hosts used in the connection URI to avoid connection rejections.

---

## 12. Hands-on Lab Exercise: Auditing Database Access Logs Programmatically

### 1. Objective and Scenario
Analyze database server connection audits and query logs to detect unauthorized access patterns, invalid authentication attempts, and command violations.

### 2. Code Implementation: `audit-parser.js`
Create a file named `audit-parser.js` and paste the following code:
```javascript
const fs = require('fs');
const readline = require('readline');

async function processAuditLogs(logFilePath) {
  const fileStream = fs.createReadStream(logFilePath);
  const rl = readline.createInterface({
    input: fileStream,
    crlfDelay: Infinity
  });

  console.log(`--- Processing Log File: ${logFilePath} ---`);
  
  for await (const line of rl) {
    if (!line.trim()) continue;
    
    try {
      const logEntry = JSON.parse(line);
      
      // Check for failed authentication checks
      if (logEntry.attr && logEntry.attr.error && logEntry.attr.error.includes("AuthenticationFailed")) {
        console.warn(`[WARN] Failed Auth Attempt at: ${logEntry.t.$date} | Source: ${logEntry.ctx}`);
      }
      
      // Filter authorization failure commands
      if (logEntry.msg === "authCheck" && logEntry.attr && logEntry.attr.result !== 0) {
        console.error(`[ALERT] Unauthorized command attempt: ${logEntry.attr.command} by user: ${logEntry.attr.users}`);
      }
    } catch (err) {
      // Handle legacy non-JSON formats if necessary
    }
  }
}

// Generate mock audit data file for demo
const mockLog = '{"t":{"$date":"2026-06-12T07:15:22.102Z"},"msg":"authCheck","attr":{"command":"dropDatabase","users":"developer_user","result":13}}\n';
fs.writeFileSync("mock-audit.log", mockLog);
processAuditLogs("mock-audit.log");
```

### 3. Lab Verification Steps
1.  Run the log parser script:
    ```bash
    node audit-parser.js
    ```
2.  Confirm that the script flags the unauthorized `dropDatabase` attempt.

---

## 13. Security Auditing & RBAC Configuration Reference

### 1. Key Security Settings
Configure these settings in `mongod.conf` to secure the database cluster:
*   `security.authorization`: Enables role-based access control (RBAC) (Default: `disabled`).
*   `security.keyFile`: Configures the keyfile path for node-to-node authentication in replica sets.
*   `net.tls.mode`: Enforces TLS encrypted connections (`requireTLS`).

### 2. Operational Diagnostic Commands
Verify security credentials and run audits:
```javascript
// List details of all custom roles in the database
db.getRoles({ showPrivileges: true });

// Check current user credentials and privilege levels
db.runCommand({ connectionStatus: 1 });
```

### 3. Senior Engineer's Production Checklist
*   [ ] Enable IP whitelisting in configurations to restrict access to trusted hosts.
*   [ ] Audit configuration parameters using security scanning tools prior to database deployment.
*   [ ] Rotate TLS certificates annually using rolling restart methods to maintain access.
