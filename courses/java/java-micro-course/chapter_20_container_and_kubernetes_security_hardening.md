# Chapter 20: Container & Kubernetes Security Hardening

Deploying microservices inside containerized environments (like Docker) and orchestrating them with container management platforms (like Kubernetes) introduces a new security boundary. Securing this environment requires applying security configurations at every level of the deployment lifecycle. In the CNCF (Cloud Native Computing Foundation) framework, this is known as the **4C Security Model**: Cloud, Cluster, Container, and Code.

This chapter focuses on the Container and Cluster layers. We will analyze the security threat model of container runtimes and Kubernetes clusters, build multi-stage hardened Dockerfiles that enforce non-root execution, manage sensitive configurations using Kubernetes ConfigMaps and Opaque Secrets, isolate service identities using custom ServiceAccounts, write Role-Based Access Control (RBAC) definitions, configure pod security contexts to enforce read-only filesystems and capability drops, restrict network flows using declarative NetworkPolicies, configure the Kubernetes Secret Store CSI Driver for Vault integration, define Kubernetes API audit logging, establish Pod Security Admission (PSA) rules, configure sandbox runtime classes (gVisor), and automate security auditing. Finally, we will write a dynamic Java watcher to handle runtime secret rotation.

---

## Learning Objectives

By the end of this chapter, you will be able to:
1. Explain the 4C Security Model and describe security concerns at each layer.
2. Build minimal, multi-stage Docker images to reduce threat exposure.
3. Harden container runtime configurations using non-root users, capability drops, and read-only root filesystems.
4. Manage configurations and credentials securely using Kubernetes ConfigMaps and Opaque Secrets.
5. Integrate HashiCorp Vault with Kubernetes using the Secret Store CSI Driver.
6. Create custom Kubernetes ServiceAccounts to isolate pod identities.
7. Write granular RBAC Roles, ClusterRoles, RoleBindings, and ClusterRoleBindings enforcing the principle of least privilege.
8. Enforce Pod Security Standards (PSS) using namespace labels and container `securityContext` parameters.
9. Isolate untrusted workloads using RuntimeClasses and gVisor sandboxing.
10. Implement zero-trust network isolation using egress and ingress Kubernetes NetworkPolicies.
11. Implement Kubernetes API Server audit logging policies and api-server startup arguments.
12. Write a dynamic Java watcher class to auto-reload rotated secrets from mounted volumes without pod restarts.
13. Audit container images and Kubernetes manifests using scanning tools like Trivy, Hadolint, and Kubeval.

---

## 20.1 The 4C Security Model

The security of a distributed system is only as strong as its weakest layer. The **4C Security Model** defines four concentric layers of security:

```
+-------------------------------------------------------+
|                       CLOUD                           |
|   (Compute, IAM, Virtual Private Cloud, Firewalls)    |
|   +-----------------------------------------------+   |
|   |                  CLUSTER                      |   |
|   |   (API Server, Etcd, Kubelet, RBAC, Network)  |   |
|   |   +---------------------------------------+   |
|   |   |             CONTAINER                 |   |   |
|   |   |   (Image signing, Non-root, cgroups)  |   |   |
|   |   |   +-------------------------------+   |   |   |
|   |   |   |             CODE              |   |   |   |
|   |   |   |   (OWASP Top 10, Dependency)  |   |   |   |
|   |   |   +-------------------------------+   |   |   |
|   |   +---------------------------------------+   |   |
|   +-----------------------------------------------+   |
+-------------------------------------------------------+
```

* **Cloud**: Refers to the underlying physical or virtual infrastructure (AWS, GCP, Azure, or bare-metal). If the cloud infrastructure's Identity and Access Management (IAM) controls are compromised, attackers can bypass all inner security layers.
* **Cluster**: Refers to the Kubernetes components coordinating the system (API Server, ZooKeeper, etcd database). Securing this layer involves encrypting etcd, securing API Server endpoints, and configuring access policies.
* **Container**: Refers to the packaging and runtime environment of the microservice (Docker, containerd). Securing this layer involves removing unused compiler binaries, checking images for vulnerabilities, and running processes with restricted system capabilities.
* **Code**: Refers to the application logic and open source libraries (Spring Boot, Spring Security). Securing this layer involves scanning dependencies for CVEs, writing secure code, and enforcing secure transport protocols.

This chapter details the **Container** and **Cluster** layers, highlighting how to harden microservices inside Kubernetes deployments.

As a starting point for our container deployments, consider the JWT token propagation flow we aim to secure within our containerized architecture:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//dbddeade-bae3-45d1-9699-1613a4d261ae/markdown_1/imgs/img_in_image_box_180_803_922_1138.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A20%3A31Z%2F-1%2F%2F99d55ed861c596776e903b70b95d9f6aed69f0af24297fd75a815d8f96f9aa37" alt="Image" width="69%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 10.1 The STS issues a JWT self-contained access token to the web application (probably following OAuth 2.0). The web application uses the token to access the Order Processing microservice on behalf of Peter.</div> </div>

---

## 20.2 Hardening Docker Container Runtimes

When writing a `Dockerfile` for a Spring Boot microservice, developers often default to generic base images (like `openjdk` or `ubuntu`) and execute applications as the `root` user. This approach creates security vulnerabilities: if an attacker compromises the application via a remote execution exploit, they gain root capabilities on the container host.

To understand how container commands are executed, review the high-level architecture of Docker components and socket communications:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//8d1b9c27-4d45-486d-85de-90023a985cc9/markdown_4/imgs/img_in_image_box_200_490_930_808.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A20%3A32Z%2F-1%2F%2Fe493db846b890f3f3e5880b3abe3081ef3d7db92a3ca62b6508b4541b0aed4e4" alt="Image" width="68%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 10.4 In this high-level Docker component architecture, the Docker client talks to the Docker daemon running on the Docker host over a REST API to perform various operations on Docker images and containers.</div> </div>

By default, access to this daemon must be strictly restricted. If remote access is required over TCP, it should be securely wrapped behind proxies:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//2db28035-392d-4849-a72c-fa9f4cfd1084/markdown_0/imgs/img_in_image_box_179_345_893_862.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A21%3A06Z%2F-1%2F%2F64f21d46a507e71381167b392ac6ccbc00d9087f8260b254745b4fa3861bf7a4" alt="Image" width="67%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 10.5 Exposing Docker APIs securely to remote clients via NGINX. Socat is used as a traffic forwarder between NGINX and the Docker daemon.</div> </div>

We can secure container runtimes using three practices:

### 1. Multi-Stage Builds to Reduce Attack Surface
A standard build image includes JDKs, compilers, shell environments, and package managers (like `apt` or `apk`). These tools are not needed at runtime. Attackers use these tools to download and run malicious scripts if they gain entry.

Multi-stage builds allow compiling the application in a build stage and copying only the generated `.jar` artifact into a minimal base runtime image (such as `distroless` or `alpine` runtime):

```dockerfile
# Stage 1: Build compilation stage
FROM maven:3.8.6-openjdk-11-slim AS build
WORKDIR /app
COPY pom.xml .
COPY src ./src
RUN mvn clean package -DskipTests

# Stage 2: Hardened runtime stage
FROM gcr.io/distroless/java:11
WORKDIR /opt
# Copy only the compiled JAR file, leaving build tools behind
COPY --from=build /app/target/order-service-1.0.jar /opt/order-service.jar
EXPOSE 8443
ENTRYPOINT ["java", "-jar", "/opt/order-service.jar"]
```

---

### 2. Enforcing Non-Root Process Execution
Containers share the host kernel. If a process inside a container runs as UID `0` (root), it executes as root on the host machine. By configuring a custom UID and GID inside the image, we restrict container processes to unprivileged actions:

```dockerfile
FROM alpine:3.18
RUN apk add --no-cache openjdk11-jre-headless

# 1. Create a secure system group and user with UID 10001
RUN addgroup -S appgroup && adduser -S appuser -G appgroup -u 10001

WORKDIR /app
COPY target/inventory-service.jar /app/inventory-service.jar

# 2. Change owner of the target runtime directories
RUN chown -R appuser:appgroup /app

# 3. Switch active user context to non-root UID
USER 10001

EXPOSE 8443
ENTRYPOINT ["java", "-jar", "/app/inventory-service.jar"]
```

---

### 3. Read-Only Root Filesystem Configuration
Allowing container processes to write to the local root filesystem (`/`) increases security risks. If an attacker exploits the application, they can write scripts or binaries to directories like `/tmp` or `/var`.

Configuring the container filesystem as read-only blocks write attempts. If the Spring Boot application needs to write temporary logs or cache files, mount an in-memory `tmpfs` volume to specific paths (e.g., `/tmp`):

```bash
# Example running a hardened container with read-only root filesystems using Docker CLI
docker run -d \
  --read-only \
  --tmpfs /tmp:rw,noexec,nosuid,size=65536k \
  -p 8443:8443 \
  --name secure-inventory \
  inventory-service:v1
```

---

## 20.3 Secret Management: ConfigMaps vs. Opaque Secrets

Decoupling configuration parameters from container image code is a key requirement of 12-factor application architecture. In Kubernetes, we achieve this decoupling using two resources: **ConfigMaps** and **Secrets**.

Here is the high-level layout of the services deployed in our Kubernetes environment:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//8d00e1b5-fe0b-4e91-968d-92b34c236da1/markdown_0/imgs/img_in_image_box_196_107_795_556.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A20%3A29Z%2F-1%2F%2F3f55e6f6283a3a73fe3e4d3424413c728db3848b7d5d7472422a0f01b0e6da0b" alt="Image" width="56%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 11.1 An STS issues a JWT access token to the client application, and the client application uses it to access the microservice on behalf of the user, Peter.</div> </div>

During testing and verification phases, requests flow to the API endpoints using the client tokens:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//8d00e1b5-fe0b-4e91-968d-92b34c236da1/markdown_4/imgs/img_in_image_box_200_385_893_770.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A20%3A31Z%2F-1%2F%2Fee6ea5083b698144872613a1bc32f2e052635370d8ee19380d45242feeffec9c" alt="Image" width="65%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 11.2 The STS issues a JWT access token to the client application, and the client application uses it to access the microservice on behalf of the user, Peter.</div> </div>

### 1. The Risk of ConfigMaps
ConfigMaps store configuration parameters in plaintext. They are suitable for non-sensitive values like logging levels or target service URLs:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: orders-configmap
  namespace: default
data:
  LOGGING_LEVEL_ROOT: "WARN"
  INVENTORY_SERVICE_URL: "https://inventory-service:8443/inventory"
```

ConfigMaps are stored in plaintext in the `etcd` datastore and returned in cleartext when queried via the API Server. **Never store passwords, private keys, or API tokens in ConfigMaps.**

---

### 2. Kubernetes Opaque Secrets
Secrets store sensitive data using base64 encoding. While base64 encoding is not secure encryption (as anyone can decode it), Kubernetes provides native security controls for Secrets:
* Secrets are stored in memory (`tmpfs` volumes) on the host nodes and are not written to disk.
* Secrets can be encrypted at rest within `etcd`.
* RBAC rules can restrict access to Secrets separately from ConfigMaps.

#### Creating an Opaque Secret (`orders-secrets.yaml`)
To generate base64 values, use the command line:
```bash
echo -n "springbootpassword" | base64
# Output: c3ByaW5nYm9vdHBhc3N3b3Jk
```

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: orders-key-credentials
  namespace: default
type: Opaque
data:
  KEYSTORE_PASSWORD: c3ByaW5nYm9vdHBhc3N3b3Jk
  TRUSTSTORE_PASSWORD: c3ByaW5nYm9vdHBhc3N3b3Jk
```

Apply this file to your cluster:
```bash
kubectl apply -f orders-secrets.yaml
```

---

### 3. Mount Passwords as Volumes vs. Environment Variables
You can inject Secrets into containers in two ways:
* **Environment Variables**: Simple to implement, but vulnerable to leaks. If an administrator runs `kubectl describe pod` or a library dumps debug environment logs, the plaintext values are exposed.
* **Volume Mounts (Recommended)**: Secrets are mounted as files on a virtual `tmpfs` in-memory volume. The application reads the password from a secure file path, and the values are never exposed in environment listings.

#### Secure Secret Volume Mount Deployment Manifest (`orders-deployment.yaml`)
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: orders-deployment
  namespace: default
spec:
  replicas: 2
  selector:
    matchLabels:
      app: orders-service
  template:
    metadata:
      labels:
        app: orders-service
    spec:
      containers:
        - name: orders-container
          image: orders-service:v1
          volumeMounts:
            # Mount the configmap file
            - name: config-volume
              mountPath: /opt/config/application.properties
              subPath: application.properties
            # Mount the secret key credentials directory as a secure volume
            - name: secrets-volume
              mountPath: /var/secrets/credentials
              readOnly: true
          resources:
            limits:
              cpu: "500m"
              memory: "512Mi"
            requests:
              cpu: "250m"
              memory: "256Mi"
      volumes:
        - name: config-volume
          configMap:
            name: orders-configmap
        - name: secrets-volume
          secret:
            secretName: orders-key-credentials
```

The Spring Boot application reads the credentials from the mounted directory path:
```properties
server.ssl.key-store-password=${file:/var/secrets/credentials/KEYSTORE_PASSWORD}
server.ssl.trust-store-password=${file:/var/secrets/credentials/TRUSTSTORE_PASSWORD}
```

---

## 20.4 Secret Store CSI Driver Integration (Vault Integration)

In highly regulated enterprise architectures, storing secrets locally inside Kubernetes `etcd` (even when base64-encoded or encrypted at rest) is discouraged. Instead, we use external secrets providers like **HashiCorp Vault**.

The **Secrets Store CSI (Container Storage Interface) Driver** allows Kubernetes to mount secrets stored in external Vault systems directly into pods as virtual volume files.

```
[ Vault Server ]
       | (Dynamic Retrieval)
       v
[ Secrets Store CSI Driver ] ===(mounts secrets in-memory)===> [ Pod Volume ]
```

### 1. The SecretProviderClass Manifest (`vault-provider.yaml`)
We define which Vault secret paths should map into the container:

```yaml
apiVersion: secrets-store.csi.x-k8s.io/v1
kind: SecretProviderClass
metadata:
  name: vault-db-credentials
  namespace: production
spec:
  provider: vault
  parameters:
    roleName: "database-reader-role"
    vaultAddress: "https://vault.internal.net:8200"
    objects: |
      - objectName: "db-password"
        secretPath: "secret/data/production/database"
        secretKey: "password"
```

### 2. Referencing the CSI Provider in the Deployment
Mount the `SecretProviderClass` inside the deployment pod specification:

```yaml
spec:
  containers:
    - name: application-container
      image: orders-service:v2
      volumeMounts:
        - name: vault-secrets
          mountPath: "/mnt/secrets-store"
          readOnly: true
  volumes:
    - name: vault-secrets
      csi:
        driver: secrets-store.csi.k8s.io
        readOnly: true
        volumeAttributes:
          secretProviderClass: "vault-db-credentials"
```

---

## 20.5 ServiceAccounts & Identity Isolation

Kubernetes uses two types of accounts: **User Accounts** (for human users) and **ServiceAccounts** (for processes inside pods).

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//e9a7f779-4671-4826-b79f-e8fbeaf6b868/markdown_4/imgs/img_in_image_box_189_106_930_607.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A20%3A34Z%2F-1%2F%2F1001a9a75ffbedd9154ca8468c260caf68a4bf96fd43ab1b2cf08b1534f0a181" alt="Image" width="69%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 11.4 A service account in Kubernetes can be assigned to one or more Pods, while a Pod at any given time can be bound to only a single service account.</div> </div>

When a pod is created, Kubernetes mounts a default ServiceAccount token (`/var/run/secrets/kubernetes.io/serviceaccount/token`) to the container filesystem. This token is a JSON Web Token (JWT) that identifies the pod to the API Server.

If no ServiceAccount is specified, pods default to the namespace's `default` ServiceAccount. If an application is compromised, the attacker can use the default token to query the API Server and exploit cluster resources.

### Hardening ServiceAccount Rules:
1. **Create Dedicated ServiceAccounts**: Never reuse default ServiceAccounts across different microservices.
2. **Disable Automounting Tokens**: If a microservice does not need to communicate with the API Server, disable token mounting:

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: orders-sa
  namespace: default
# Disable automatic injection of the service account token JWT
automountServiceAccountToken: false
```

Apply the configuration and bind it to the deployment:
```yaml
spec:
  template:
    spec:
      serviceAccountName: orders-sa
```

---

## 20.6 Role-Based Access Control (RBAC)

If a microservice needs to interact with the API Server (for example, to dynamically query services or read configurations), we must define permissions using **Role-Based Access Control (RBAC)**.

```
+------------------+             +-----------------------+             +-----------------------+
|  ServiceAccount  | ===(binds)==> RoleBinding /           | ===(binds)==> Role /                  |
|    (Identity)    |             | ClusterRoleBinding    |             | ClusterRole           |
|                  |             | (Assoc. Rule Mapping) |             | (Allowed Actions)     |
+------------------+             +-----------------------+             +-----------------------+
```

### 1. Roles vs. ClusterRoles
* **Role**: Defines namespaced permissions. It grants access to resources (e.g., Pods, Secrets, Services) within a single namespace.
* **ClusterRole**: Defines cluster-level permissions. It grants access to cluster-wide resources (e.g., Nodes, Namespaces, PersistentVolumes) or namespaced resources across all namespaces.

### 2. Implementing a Namespaced Read-Only Role
The following `Role` allows reading and listing services and pods within the `production` namespace:

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  namespace: production
  name: service-reader-role
rules:
  # Define target API groups (empty string denotes core API group)
  - apiGroups: [""]
    resources: ["services", "pods"]
    verbs: ["get", "list", "watch"]
```

### 3. Creating the RoleBinding
A `RoleBinding` maps the `service-reader-role` to the `orders-sa` ServiceAccount:

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: bind-orders-reader
  namespace: production
subjects:
  - kind: ServiceAccount
    name: orders-sa
    namespace: production
roleRef:
  kind: Role
  name: service-reader-role
  apiGroup: rbac.authorization.k8s.io
```

Apply these files to establish the security boundary:
```bash
kubectl apply -f read-role.yaml
kubectl apply -f role-binding.yaml
```

---

## 20.7 Pod Security Standards and SecurityContexts

Kubernetes features built-in **Pod Security Standards (PSA)** to enforce isolation policies at the namespace level. PSS defines three profiles:
* **Privileged**: Unrestricted policy, allowing root privileges and host access.
* **Baseline**: Prevents known privilege escalations, enforcing default container configurations.
* **Restricted**: Restricts execution to hardened, non-root constraints.

Enforce the `restricted` profile on the `production` namespace using labels:
```bash
kubectl label --overwrite ns production pod-security.kubernetes.io/enforce=restricted
```

To validate that the configurations conform before actual resource deployment, run a dry-run server validation:
```bash
kubectl label --dry-run=server --overwrite ns production pod-security.kubernetes.io/enforce=restricted
```

### Hardened Deployment with Container SecurityContext
This manifest configures a secure runtime environment by dropping root privileges, disabling privilege escalation, and setting a read-only root filesystem:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: secure-inventory-deployment
  namespace: production
spec:
  replicas: 3
  selector:
    matchLabels:
      app: inventory-service
  template:
    metadata:
      labels:
        app: inventory-service
    spec:
      # Pod level security configurations
      securityContext:
        runAsNonRoot: true
        runAsUser: 10001
        runAsGroup: 10001
        fsGroup: 10001
      containers:
        - name: inventory-app
          image: inventory-service:v2
          securityContext:
            # Prevent container process from gaining more privileges than its parent
            allowPrivilegeEscalation: false
            # Mount the root directory as read-only
            readOnlyRootFilesystem: true
            # Drop default Linux kernel privileges
            capabilities:
              drop:
                - ALL
          volumeMounts:
            # Mount a memory-buffered volume for application write operations
            - name: cache-volume
              mountPath: /tmp
      volumes:
        - name: cache-volume
          emptyDir:
            medium: Memory
```

---

## 20.8 Sandbox Runtimes using gVisor

Standard container technologies (like Docker and containerd) use the host machine's kernel directly. If an attacker achieves a container escape vulnerability, they can execute commands on the host machine.

To isolate untrusted workloads, configure **gVisor** (`runsc`). gVisor acts as a user-space kernel shim that intercepts and filters system calls before they reach the host kernel.

```
[ Container Process ] => [ gVisor (runsc) User-space kernel filter ] => [ Host Linux Kernel ]
```

### 1. Provision a RuntimeClass for gVisor
Define the custom container shim runtime:

```yaml
apiVersion: node.k8s.io/v1
kind: RuntimeClass
metadata:
  name: gvisor-sandbox
handler: runsc
```

### 2. Apply RuntimeClass to Pod Specifications
Add the `runtimeClassName` parameter to the pod configuration to run the container inside a sandbox:

```yaml
spec:
  runtimeClassName: gvisor-sandbox
  containers:
    - name: secure-workload
      image: untrusted-thirdparty-service:latest
```

---

## 20.9 Declarative NetworkPolicies for Service Isolation

By default, Kubernetes network configurations allow all pods to communicate with each other. This open architecture means that if an attacker compromises a frontend pod (like an API gateway), they can connect to any database or backend service in the cluster.

To prevent lateral movement and enforce zero-trust service boundaries, restrict network traffic flows:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//e9a7f779-4671-4826-b79f-e8fbeaf6b868/markdown_0/imgs/img_in_image_box_182_665_875_1127.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A20%3A31Z%2F-1%2F%2F3b669d9e359d621ac315cfeb9d07af8d742e88956eac460bfa9d70fed352e381" alt="Image" width="65%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 11.3 STS issues a JWT access token to the client application, and the client application uses it to access the Order Processing microservice on behalf of the user, Peter. The Order Processing microservice uses the same JWT it got from the client application to access the Inventory microservice.</div> </div>

We configure default-deny security policies and explicitly authorize only required service paths:

```
                                [ External Request ]
                                         |
                                         v
                              [ API Gateway Pod ]
                                         |
                       (Allowed Ingress by NetworkPolicy)
                                         |
                                         v
                            [ Inventory Service Pod ]
                                         |
                     (Blocked: Denies other internal pods)
                                         |
                                         x
                              [ Compromised Pod ]
```

### 1. Default-Deny NetworkPolicy (`default-deny-all.yaml`)
Apply a default-deny policy for all pods in the namespace:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
  namespace: production
spec:
  podSelector: {}
  policyTypes:
    - Ingress
    - Egress
```

### 2. Ingress Restriction Policy (`kitchen-netpolicy.yaml`)
This policy restricts traffic to the `kitchen-service` pods, allowing ingress connections only from the `order-service` pods on HTTPS port `8443`:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: kitchen-ingress-policy
  namespace: ftgo
spec:
  # Apply this policy to pods matching kitchen labels
  podSelector:
    matchLabels:
      app: kitchen-service
  policyTypes:
    - Ingress
  ingress:
    # Allow ingress connections only from pods matching order labels
    - from:
        - podSelector:
            matchLabels:
              app: order-service
      ports:
        - protocol: TCP
          port: 8443
```

### 3. Database Isolation NetworkPolicies (Enforcing Bounded Context Boundaries)

To enforce the **Database-per-Service** pattern at the network layer, we write NetworkPolicies that block cross-service database access. For example, we restrict access to the PostgreSQL database pod (`order-db` on port `5432`) so that only the `order-service` application pod can connect to it:

#### PostgreSQL Database Protection Policy (`order-db-netpolicy.yaml`)
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: order-db-ingress-policy
  namespace: ftgo
spec:
  podSelector:
    matchLabels:
      role: order-database # Target the PostgreSQL database pod
  policyTypes:
    - Ingress
  ingress:
    - from:
        - podSelector:
            matchLabels:
              app: order-service # Allow connections ONLY from the order-service pod
      ports:
        - protocol: TCP
          port: 5432
```

#### MongoDB Database Protection Policy (`delivery-db-netpolicy.yaml`)
Similarly, we protect the MongoDB database pod (`delivery-db` on port `27017`) so that only the `delivery-service` pod can connect:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: delivery-db-ingress-policy
  namespace: ftgo
spec:
  podSelector:
    matchLabels:
      role: delivery-database # Target the MongoDB database pod
  policyTypes:
    - Ingress
  ingress:
    - from:
        - podSelector:
            matchLabels:
              app: delivery-service # Allow connections ONLY from delivery-service pod
      ports:
        - protocol: TCP
          port: 27017
```


---

## 20.10 Kubernetes API Server Audit Logging

To comply with security standards (e.g., SOC2, PCI-DSS), you must audit requests made to the Kubernetes API Server. We configure an **Audit Policy** file (`audit-policy.yaml`) to log key events:

```yaml
apiVersion: audit.k8s.io/v1
kind: Policy
rules:
  # 1. Log RequestResponse changes to Secrets and ConfigMaps
  - level: RequestResponse
    resources:
      - group: ""
        resources: ["secrets", "configmaps"]
  # 2. Log metadata of Pod modifications
  - level: Metadata
    resources:
      - group: ""
        resources: ["pods"]
    verbs: ["update", "patch", "delete"]
  # 3. Drop logging for read-only events
  - level: None
    verbs: ["get", "list", "watch"]
```

To enable this policy on a self-managed cluster, modify the API Server configuration manifest (`/etc/kubernetes/manifests/kube-apiserver.yaml`) to pass the following daemon arguments:

```yaml
spec:
  containers:
    - name: kube-apiserver
      command:
        - kube-apiserver
        - --audit-policy-file=/etc/kubernetes/audit-policy.yaml
        - --audit-log-path=/var/log/kubernetes/audit.log
        - --audit-log-maxage=30
        - --audit-log-maxbackup=10
        - --audit-log-maxsize=100
      volumeMounts:
        - mountPath: /etc/kubernetes/audit-policy.yaml
          name: audit-policy
          readOnly: true
        - mountPath: /var/log/kubernetes
          name: audit-log
  volumes:
    - name: audit-policy
      hostPath:
        path: /etc/kubernetes/audit-policy.yaml
        type: File
    - name: audit-log
      hostPath:
        path: /var/log/kubernetes
        type: DirectoryOrCreate
```

---

## 20.11 Programmatic Watcher for Secret Rotations in Java

When mounting credentials from Kubernetes Opaque Secrets as volume files, Kubernetes updates the mounted files when the Secret is modified. However, Java applications do not automatically detect these changes. Developers typically restart the pod to force the application to reread the files.

To avoid service restarts, we write a **Java service** that watches the mounted folder directory using the Java `WatchService` API. It reloads passwords and connection configurations at runtime without service interruption:

```java
package com.ftgo.order.security;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import javax.annotation.PostConstruct;
import javax.annotation.PreDestroy;
import java.io.IOException;
import java.nio.file.*;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

@Service
public class SecretsRotationWatcher {

    private static final Logger logger = LoggerFactory.getLogger(SecretsRotationWatcher.class);
    private static final String SECRET_PATH = "/var/secrets/credentials";
    
    private WatchService watchService;
    private ExecutorService executor;

    @PostConstruct
    public void startWatcher() {
        try {
            this.watchService = FileSystems.getDefault().newWatchService();
            Path path = Paths.get(SECRET_PATH);
            
            // Register watcher for file modifications
            path.register(watchService, StandardWatchEventKinds.ENTRY_MODIFY);
            
            this.executor = Executors.newSingleThreadExecutor();
            this.executor.submit(this::watchLoop);
            logger.info("Dynamic secrets rotation watcher started on path: {}", SECRET_PATH);
        } catch (IOException e) {
            logger.error("Failed to initialize secrets rotation watcher!", e);
        }
    }

    private void watchLoop() {
        try {
            WatchKey key;
            while ((key = watchService.take()) != null) {
                for (WatchEvent<?> event : key.pollEvents()) {
                    WatchEvent.Kind<?> kind = event.kind();
                    if (kind == StandardWatchEventKinds.ENTRY_MODIFY) {
                        Path filename = (Path) event.context();
                        logger.info("Secret file modified: {}. Triggering dynamic reload.", filename);
                        
                        // Execute logic to refresh credentials in memory
                        reloadSecrets();
                    }
                }
                key.reset();
            }
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            logger.info("Watcher thread interrupted.");
        }
    }

    private synchronized void reloadSecrets() {
        try {
            Path passwordFile = Paths.get(SECRET_PATH, "KEYSTORE_PASSWORD");
            String newPassword = Files.readString(passwordFile).trim();
            
            // Dynamically refresh DB connections, SSLContext, or keystores in memory
            logger.info("Dynamic password successfully reloaded. Length: {} chars", newPassword.length());
            
        } catch (IOException e) {
            logger.error("Failed to reload rotated secret credentials file!", e);
        }
    }

    @PreDestroy
    public void stopWatcher() {
        try {
            if (watchService != null) {
                watchService.close();
            }
            if (executor != null) {
                executor.shutdownNow();
            }
            logger.info("Secrets rotation watcher service terminated.");
        } catch (IOException e) {
            logger.error("Failed to close watcher resource!", e);
        }
    }
}
```

---

## 20.12 Summary of Container Security Controls

The following table summarizes the key containerization and orchestration security mechanisms explored in this chapter:

| Security Domain | Kubernetes Control Mechanism | Main Protection Vector | Configuration Level |
| :--- | :--- | :--- | :--- |
| **Runtime Hardening** | `securityContext` | Prevents root privilege escalations and host access. | Container & Pod |
| **Key Management** | Opaque Secrets | Keeps credentials base64-encoded, memory-mapped (`tmpfs`). | Namespace |
| **External Secrets** | CSI Secrets Driver | Retrieves secrets dynamically from Vault or AWS SSM. | Pod Volumes |
| **Identity Isolation** | ServiceAccounts | Limits token capabilities exposed to individual Pods. | Pod |
| **Access Rights** | RBAC Roles & Bindings | restrains API Server interactions using resource verbs. | Namespace & Cluster |
| **Kernel Sandboxing** | RuntimeClasses / gVisor | Filters kernel system calls to prevent escapes. | Node & Pod |
| **Network Security** | NetworkPolicies | Implements zero-trust namespace and Pod routing. | Namespace |
| **Compliance Auditing**| API Server Audit Policy | Tracks resource updates, accesses, and modifications. | Cluster Master |

---

## 20.13 Automated Security Auditing and Linting

To ensure security configurations are maintained, run security checks as part of your CI/CD pipeline.

```
[ Git Push ] => [ Hadolint (Dockerfile Lint) ] => [ Trivy (Image Scan) ] => [ Kubeval (YAML Audit) ] => [ Deploy ]
```

During this build stage, we verify signed Docker images to establish trust:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//3c3ca55a-8cd7-4b8e-bc07-6b880265b1ec/markdown_3/imgs/img_in_image_box_111_104_915_758.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A20%3A30Z%2F-1%2F%2F75db3c26c04331e64634191a8d77ca64869955406129f03662ee4f6c92919ec6" alt="Image" width="75%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 10.2 DCT uses a key hierarchy to sign and verify Docker images.</div> </div>

### 1. Linting Dockerfiles with Hadolint
Hadolint audits Dockerfiles against security best practices (e.g., verifying that `USER` is set and non-root):
```bash
hadolint Dockerfile
```

### 2. Image Vulnerability Scanning with Trivy
Trivy scans container images for package vulnerabilities (CVEs) and configuration issues:
```bash
trivy image --severity HIGH,CRITICAL prabath/order-processing:v1
```

### 3. Validating Kubernetes Manifests with Kubeval
Kubeval validates Kubernetes YAML configuration files against schemas to catch misconfigurations before deployment:
```bash
kubeval deployment.yaml
```

---

## Chapter Summary

* Container and Kubernetes deployments introduce new vectors for security compromises that require hardening across all layers of the CNCF **4C Security Model**.
* Production Docker images should use multi-stage builds and run as non-root UIDs to mitigate root privilege escalation risks.
* Sensitive configurations and credentials should be managed using **Opaque Secrets** mounted as memory-backed files rather than cleartext ConfigMaps or environment variables.
* The CSI Secret Store Driver permits loading secrets from centralized Vault servers directly as volume mounts.
* **ServiceAccounts** should be isolated per pod, and token automounting should be disabled unless the application needs to interact with the API Server.
* **RBAC** (Roles, RoleBindings) should enforce the principle of least privilege for all processes interacting with the Kubernetes API Server.
* Container runtime privileges should be restricted by dropping Linux capabilities and mounting filesystems as read-only.
* Pod Admission controllers enforce Restricted security rules across target namespaces.
* Workload isolation is enhanced by routing untrusted packages through user-space shims like **gVisor**.
* **NetworkPolicies** establish a zero-trust network environment by applying default-deny rules and explicitly authorizing required service communication paths.
* API Server Audit policies track modifications and access to sensitive resources like Secrets and ConfigMaps.
* Dynamic secret rotations in mounted directories are loaded at runtime using Java directory watcher tasks.
* Automated auditing tools (like Trivy, Hadolint, and Kubeval) should scan configurations and images within build pipelines to prevent security regressions.
