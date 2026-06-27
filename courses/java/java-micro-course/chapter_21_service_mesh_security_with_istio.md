# Chapter 21: Service Mesh Security with Istio

In previous chapters, we implemented security at the application level by embedding Spring Security libraries, keystores, and filters directly into our microservice binaries. While this approach works, it forces application developers to maintain security infrastructure, certificate rotations, and validation logic. In large enterprise deployments containing hundreds of services written in different programming languages, maintaining consistent security policies at the code level becomes a maintenance challenge.

To address this, modern architectures decouple security, routing, and observability from the application logic by using a **Service Mesh** with **Istio**. By intercepting network traffic using out-of-process sidecar proxies, Istio offloads security tasks from our code. This chapter covers implementing edge-to-edge service mesh security using Istio. We will configure TLS termination at the Istio Ingress Gateway, enforce strict Mutual TLS (mTLS) for East-West traffic, configure JWT verification using RequestAuthentication, define fine-grained access control rules using AuthorizationPolicies, analyze the SPIFFE identity standard, configure custom Certificate Authorities (CAs) for Citadel, establish dynamic JWT header claims propagation, configure secure Egress Gateways, explore client-to-gateway mTLS, trace certificate distribution using the Envoy Secret Discovery Service (SDS), and outline CLI-based security troubleshooting. Finally, we will write a complete Java filter to propagate the extracted Envoy context headers down the call chain.

---

## Learning Objectives

By the end of this chapter, you will be able to:
1. Explain the Service Mesh pattern and describe the role of the data plane (Envoy proxy) and the control plane (istiod).
2. Configure namespace labels to enable transparent Envoy proxy sidecar autoinjection.
3. Configure the Istio Ingress Gateway to terminate TLS at the edge using Simple and Mutual TLS configurations.
4. Define VirtualServices to map domain hosts and route external traffic to internal microservices.
5. Integrate corporate PKI root keys with `istiod` by provisioning the `cacerts` Kubernetes Secret.
6. Implement PeerAuthentication policies to enforce permissive or strict Mutual TLS (mTLS) across namespaces.
7. Configure JWT end-user validation using RequestAuthentication policies and JWKS key endpoints.
8. Propagate verified JWT claims from Envoy sidecars to downstream microservices using HTTP header mapping rules.
9. Protect against JWT bypass vulnerabilities by combining RequestAuthentication with AuthorizationPolicies.
10. Write granular AuthorizationPolicies restricting traffic based on HTTP verbs, paths, JWT claims, and service identities.
11. Secure outgoing traffic using Egress Gateways, ServiceEntry, and DestinationRules to prevent data exfiltration.
12. Write a custom Java user propagation filter to consume and forward headers written by Envoy.
13. Explain the SPIFFE identity format and trace how Citadel and Envoy SDS provision and rotate certificates in-memory.
14. Use `istioctl` commands to troubleshoot TLS connections, inspect sidecar certificates, and diagnose authorization failures.

---

## 21.1 Service Mesh Architecture and Sidecar Interception

A service mesh splits networking and security operations into two functional planes:

```
+-------------------------------------------------------+
|                    CONTROL PLANE                      |
|                        istiod                         |
|   (CA Citadel, Pilot Configurations, Injector APIs)   |
+--------------------------+----------------------------+
                           | (Distributes Policies & Certs)
                           v
+--------------------------+----------------------------+
|                      DATA PLANE                       |
|   [ Pod: Orders Service ]       [ Pod: Inventory ]    |
|   +-------------------+         +------------------+  |
|   |  Application Code |         | Application Code |  |
|   +--------^----------+         +--------^---------+  |
|            | (localhost)                 | (localhost)|
|   +--------v----------+   (mTLS) +--------v--------+  |
|   |    Envoy Proxy    |<========>|    Envoy Proxy    |  |
|   |  (Sidecar Proxy)  |          |  (Sidecar Proxy)  |  |
|   +-------------------+         +------------------+  |
+-------------------------------------------------------+
```

* **The Control Plane (`istiod`)**: Manages and injects configurations into sidecars. It includes Citadel (the Certificate Authority for certificate distribution and rotation) and Pilot (which translates YAML rules into configuration tables read by Envoy proxies).
* **The Data Plane**: Formed by Envoy proxies deployed alongside each microservice container inside the same Kubernetes Pod. All inbound and outbound traffic is dynamically intercepted by the local Envoy proxy using iptables rules, applying TLS settings and authorization rules without the application's knowledge.

This is the standard microservice request verification flow using JWT tokens distributed from the Security Token Service:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//94a411bf-9938-4dc9-bfe8-fdf2f815c956/markdown_3/imgs/img_in_image_box_200_660_935_1129.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A20%3A30Z%2F-1%2F%2F727fbd2772b0d9c90e06b9396732fd6ea6f46e41e0ef1c6b4d0e19aa39ccd5cc" alt="Image" width="69%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 12.1 STS issues a JWT access token to the client application, and the client application uses it to access the Order Processing microservice on behalf of the user, Peter. The Order Processing microservice uses the same JWT it got from the client application to access the Inventory microservice.</div> </div>

To enable sidecar injection transparently, we label our target namespace:
```bash
kubectl label namespace default istio-injection=enabled
```

When pods are launched or restarted in this namespace, Istio's mutating webhook injector intercepts the request and injects an `istio-proxy` container alongside the application container:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//94a411bf-9938-4dc9-bfe8-fdf2f815c956/markdown_4/imgs/img_in_image_box_114_663_926_1090.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A20%3A31Z%2F-1%2F%2F7a915b0172f949030e632ac0a646d2fb3f557a4935b424995e41307ce42e3827" alt="Image" width="76%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 12.2 Istio introduces the Envoy sidecar proxy to each Pod, along with the container that carries the microservice.</div> </div>

---

## 21.2 TLS Termination at the Ingress Gateway

To secure traffic entering the mesh from external client applications (North-South traffic), we configure the **Istio Ingress Gateway**.

The Ingress Gateway acts as a reverse proxy running at the cluster boundary. It terminates TLS connections at the edge, validates incoming host headers, and routes traffic over plaintext HTTP or secure mTLS to the corresponding internal microservices.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//3c1bf1f5-d41b-4977-a292-fd6bf5e24a9d/markdown_3/imgs/img_in_image_box_154_562_930_1068.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A20%3A31Z%2F-1%2F%2Fe3a34bac80653353b7e0a929f1acc7fccbafd462b32b638c9f7430cd1b7702bf" alt="Image" width="73%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 12.3 The Istio Ingress gateway intercepts all the requests coming to the microservice and terminates the TLS connection.</div> </div>

### 1. Creating the TLS Key Secret
First, generate the public and private key files for the domain using OpenSSL:
```bash
openssl req -new -x509 -keyout server.key -out server.cert -days 365 \
  -subj "/CN=orders.ecomm.com/O=FTGO/C=US" -nodes
```

Deploy the keys as a Kubernetes TLS Secret inside the `istio-system` namespace where the Ingress Gateway resides:
```bash
kubectl create -n istio-system secret tls ecomm-credential \
  --key=server.key --cert=server.cert
```

---

### 2. Update the Gateway resource
To expose our services, define a `Gateway` configuration. If the deployment runs without Envoy SDS enabled, we configure the certificates manually:

##### Listing 12.2 The definition of the Gateway resource with no SDS

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//4f32837d-d2e8-4d0d-8429-2b3e46073994/markdown_1/imgs/img_in_image_box_201_290_981_851.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A20%3A33Z%2F-1%2F%2F20ec1de3fa7148c7b2196efe88e58b3094d373b447cddb14b27ae35728752e98" alt="Image" width="73%" /></div>

When running under modern clusters, enable SDS to provision the credentials dynamically from Kubernetes secret resources:

##### Listing 12.3 The definition of the Gateway resource with SDS

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//4f32837d-d2e8-4d0d-8429-2b3e46073994/markdown_4/imgs/img_in_image_box_183_146_908_666.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A20%3A35Z%2F-1%2F%2F398c47122d483f2ab0775e86665dac705b0a3895cbe4d9649cf695c0479972d2" alt="Image" width="68%" /></div>

Apply the SDS Gateway file:
```yaml
apiVersion: networking.istio.io/v1alpha3
apiVersion: networking.istio.io/v1alpha3
kind: Gateway
metadata:
  name: ecomm-gateway
  namespace: istio-system
spec:
  selector:
    istio: ingressgateway
  servers:
    - port:
        number: 443
        name: https
        protocol: HTTPS
      tls:
        mode: SIMPLE
        credentialName: ecomm-credential
      hosts:
        - "orders.ecomm.com"
```

Apply this file to configure the Ingress Gateway:
```bash
kubectl apply -f gateway.yaml
```

---

### 3. Create the VirtualService
To route traffic from the Ingress Gateway to the internal microservices, configure a `VirtualService` resource mapping the domain host and URI patterns:
```yaml
apiVersion: networking.istio.io/v1alpha3
kind: VirtualService
metadata:
  name: orders-virtual-service
  namespace: default
spec:
  hosts:
    - "orders.ecomm.com"
  gateways:
    - istio-system/ecomm-gateway
  http:
    - match:
        - uri:
            prefix: /orders
      route:
        - destination:
            host: orders-service.default.svc.cluster.local
            port:
              number: 8080
```

Apply the routing rules:
```bash
kubectl apply -f virtualservice.yaml
```

---

## 21.3 Custom Certificate Authorities (CAs) for Citadel

By default, Istio's `istiod` control plane acts as a self-signed Certificate Authority (CA) to sign workload certificates. For enterprise security compliance, you should integrate Istio with your corporate Root PKI.

To configure `istiod` to use custom root keys, create a Kubernetes Secret named `cacerts` in the `istio-system` namespace containing the signing certificates:

```bash
# Provision the corporate CA files as a Kubernetes Secret
kubectl create secret generic cacerts -n istio-system \
  --from-file=secrets/ca-cert.pem \
  --from-file=secrets/ca-key.pem \
  --from-file=secrets/root-cert.pem \
  --from-file=secrets/cert-chain.pem
```

When `istiod` boots up, it detects the presence of the `cacerts` secret and mounts it automatically, using the corporate CA keys to sign sidecar workloads.

---

## 21.4 Enforce Client Mutual TLS at the Ingress Gateway (B2B Integrations)

For secure Business-to-Business (B2B) interactions, we configure the Ingress Gateway to perform **Mutual TLS** validation on external clients. This requires clients to present valid certificates signed by a trusted corporate CA.

1. Deploy the client root certificates to the `istio-system` namespace:
   ```bash
   kubectl create -n istio-system secret generic client-ca-credential \
     --from-file=cacert.pem=secrets/client-ca-root.pem
   ```
2. Update the `Gateway` resource, changing the TLS mode to `MUTUAL`:

```yaml
apiVersion: networking.istio.io/v1alpha3
kind: Gateway
metadata:
  name: ecomm-b2b-gateway
  namespace: istio-system
spec:
  selector:
    istio: ingressgateway
  servers:
    - port:
        number: 443
        name: https
        protocol: HTTPS
      tls:
        mode: MUTUAL
        credentialName: ecomm-credential
        # Reference the client CA secret for trust validation
        caCertificateDescriptor: client-ca-credential
      hosts:
        - "api-b2b.ecomm.com"
```

---

## 21.5 Securing East-West Traffic with Mutual TLS (mTLS)

Once traffic passes the Ingress Gateway, we secure communications between services inside the mesh (East-West traffic) using Mutual TLS (mTLS).

Istio uses the **PeerAuthentication** resource to configure mTLS settings. It supports three authentication modes:
* `DISABLE`: Plaintext HTTP connections are enforced.
* `PERMISSIVE`: Pods accept both plaintext and TLS traffic. This mode allows migrating legacy services to the mesh without breaking connections.

##### Listing 12.7 The permissive authentication policy

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//baea09cc-0002-4e37-94f3-c6c076a40df4/markdown_2/imgs/img_in_image_box_200_223_900_445.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A20%3A33Z%2F-1%2F%2F6e164413b8a85802838d8230bd59b08a2364f52392e2ea315247a1d238307aaf" alt="Image" width="65%" /></div>

* `STRICT`: Pods accept only mTLS connections. Any plaintext connection is rejected.

```
                    +--------------------------------+
                    |       PeerAuthentication       |
                    +---------------+----------------+
                                      | (Set to STRICT)
                                      v
              +----------------------+----------------------+
              |                                             |
              v                                             v
[ order-service ] ==========( strictly mTLS )==========> [ kitchen-service ]
              ^                                             ^
              | (Plaintext Blocked)                         | (Plaintext Blocked)
              x                                             x

[ Non-Mesh Pod ]                                  [ Non-Mesh Pod ]
```

When strict mTLS is disabled, we validate that the Ingress gateway terminates TLS, but the downstream microservices communicate via unauthenticated channels:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//baea09cc-0002-4e37-94f3-c6c076a40df4/markdown_3/imgs/img_in_image_box_155_113_923_637.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A20%3A34Z%2F-1%2F%2F2ae9569736a1ce569a7aa0c783736c5fba1f5ea3b749501f1a65fe097db38439" alt="Image" width="72%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 12.4 STS issues a JWT access token to the client application, and the client application uses it to access the Order Processing microservice on behalf of the user, Peter. The Order Processing microservice uses the same JWT it got from the client application to access the Inventory microservice. The Istio Ingress gateway intercepts all the requests coming to the microservice and terminates the TLS connection.</div> </div>

When strict mTLS is enforced, all communication paths are protected by mutual TLS verification:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//39045f8d-b9d1-4cc8-8b22-8937103065ef/markdown_1/imgs/img_in_image_box_169_111_941_636.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A20%3A30Z%2F-1%2F%2F79bf93a92f9df1096cc9bccdf27e2b244505a1918fab9c78cf0da7603c85988b" alt="Image" width="72%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 12.5 The Istio Ingress gateway intercepts all the requests coming to the microservice and terminates the TLS connection. The communications between the Ingress gateway and microservices, as well as among microservices, are protected with mTLS.</div> </div>

#### Decoupling Code-Level mTLS from Platform-Level mTLS (Offloading Chapter 17)

Recall that in [Chapter 17](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/java/java-micro-course/chapter_17_securing_east_west_traffic_with_mutual_tls.md), implementing mTLS required writing custom Java security loaders (`FeignClientSSLConfig`, `WebClientMtlsConfig`), scheduling certificate reloaders, and managing physical JKS stores on disk. 

When deploying inside an **Istio Service Mesh**, we offload this entire configuration from the Java application codebase:
1. **Developer Simplicity**: The Spring Boot microservice code is simplified to bind to standard plaintext ports (`8081` for `order-service`, `8082` for `kitchen-service`) without any SSL configurations.
2. **Envoy Proxy Interception**: Istio automatically injects an Envoy sidecar proxy container next to each application container.
3. **Out-of-Process mTLS**:
   - When `order-service` calls `kitchen-service` via a standard HTTP WebClient on port `8082`, the outbound Envoy proxy intercepts the packet.
   - It performs the TLS handshake with the target pod's inbound Envoy proxy, presenting a dynamic certificate signed by Citadel (encoded with the SPIFFE identity `spiffe://cluster.local/ns/ftgo/sa/order-service-sa`).
   - The inbound Envoy proxy validates the certificate, terminates the TLS tunnel, and forwards the payload as a local loopback plaintext HTTP request to the Java application.

This offloads certificate management, rotation, and cryptographic operations to the Kubernetes platform infrastructure.

### 1. Enforcing Namespace-Wide Strict mTLS (`peer-auth.yaml`)
Enforce STRICT mTLS for all services inside the `ftgo` namespace:

```yaml
apiVersion: security.istio.io/v1beta1
kind: Secret
metadata:
  name: cacerts
  namespace: istio-system
# ... Integrates corporate PKI to Citadel
---
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: ftgo-mtls-policy
  namespace: ftgo
spec:
  mtls:
    mode: STRICT
```

Apply this file to configure the `ftgo` namespace:
```bash
kubectl apply -f peer-auth.yaml
```


---

### 2. DestinationRules for Client-Side Settings (Legacy Support)
In older Istio installations (prior to 1.5.0), you must define client-side policies using **DestinationRules** to instruct Envoy proxies to use `ISTIO_MUTUAL` when calling other services:

```yaml
apiVersion: networking.istio.io/v1alpha3
kind: DestinationRule
metadata:
  name: ecomm-services-mtls
  namespace: default
spec:
  host: "*.default.svc.cluster.local"
  trafficPolicy:
    tls:
      mode: ISTIO_MUTUAL
```

---

## 21.6 JWT Authentication and Header Claims Propagation

To validate the identity of the end user initiating the request, we verify JSON Web Tokens (JWT) at the sidecar proxy level:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//398bc407-a951-440c-bd82-c710289e5740/markdown_0/imgs/img_in_image_box_161_115_947_633.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A20%31Z%2F-1%2F%2F73f4149a4ad461f67e3185bfa75f3c2b78b7e784049c934848ed39611d7385b6" alt="Image" width="74%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 12.6 The Istio Ingress gateway intercepts all the requests coming to the microservice and terminates the TLS connection. The communications between the Ingress gateway and microservices, as well as among microservices, are protected with mTLS. The Envoy proxy does JWT verification for the Order Processing and Inventory microservices.</div> </div>

We configure this using the **RequestAuthentication** resource. The local Envoy proxy intercepts requests, retrieves public keys from a JWKS (JSON Web Key Set) endpoint, and validates the signature, issuer, and expiration of the token.

```
[ Client Request with JWT ] => [ Envoy Proxy (RequestAuthentication) ] => [ Application Container ]
                                       |                                           |
                     (Validates Signature via JWKS URI)                    (Reads X-User-Name Header)
                                       |
                                       v
                                  [ Allow/Deny ]
```

### 1. The RequestAuthentication Resource (`request-auth.yaml`)
To register policies enforcing JWT verification, configure a policy that specifies the targets and the JWT issuer configurations:

##### Listing 12.11 The RequestAuthentication policy applicable to Order Processing and Inventory microservices

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//398bc407-a951-440c-bd82-c710289e5740/markdown_2/imgs/img_in_image_box_198_747_943_1034.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A20%3A33Z%2F-1%2F%2F07e4ab5c1137e7e8c545a55e0c3da0a24ea5f568d25f17b19a3cc73def3d612d" alt="Image" width="70%" /></div>

To restrict a policy to a single service, match the selector tag labels:

##### Listing 12.13 The RequestAuthentication policy applicable to only the Order Processing microservice

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//398bc407-a951-440c-bd82-c710289e5740/markdown_3/imgs/img_in_image_box_112_560_934_953.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A20%3A34Z%2F-1%2F%2F51b807e597968290225e64fc05ec0b06c5cf710487c4946e282c02d7e7aff29e" alt="Image" width="77%" /></div>

To verify signatures, declare the JWKS (JSON Web Key Set) public registry keys:

##### Listing 12.15 The content of the jwtkey.jwk file containing JWKS public keys

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//dad71785-d027-45cb-99a7-5e308cb52775/markdown_0/imgs/img_in_image_box_176_651_931_886.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A20%3A29Z%2F-1%2F%2F8515edaab8296eb5413b751221884bd43ff73ffcf058b866abd5bed809f1b1f8" alt="Image" width="71%" /></div>

Decoded JWT payload verification context layout:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//dad71785-d027-45cb-99a7-5e308cb52775/markdown_1/imgs/img_in_image_box_191_211_941_599.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A20%3A30Z%2F-1%2F%2Fda68fd22382a52dcfda2e56887c17f8c1b422b840d59499d9200b658a962f4ca" alt="Image" width="70%" /></div>

---

### 2. Copying JWT Claims to HTTP Request Headers
Downstream microservices often need user details (like username or email) to execute business logic. To prevent application code from parsing raw JWT strings, we configure the Envoy proxy to extract JWT claims and propagate them as HTTP headers:

```yaml
# Add to the VirtualService HTTP routing rules
apiVersion: networking.istio.io/v1alpha3
kind: VirtualService
metadata:
  name: orders-virtual-service
  namespace: default
spec:
  hosts:
    - "orders.ecomm.com"
  gateways:
    - istio-system/ecomm-gateway
  http:
    - match:
        - uri:
            prefix: /orders
      headers:
        request:
          set:
            # Map claims dynamically into HTTP headers
            X-User-Name: "%REQ(Authorization.Claims.user_name)%"
            X-User-Roles: "%REQ(Authorization.Claims.authorities)%"
      route:
        - destination:
            host: orders-service
```

---

### 3. Mitigating the JWT Bypass Vulnerability
The RequestAuthentication resource has a security caveat:
> [!IMPORTANT]
> If a request contains an invalid JWT, RequestAuthentication rejects the request. However, if the request contains **no JWT at all**, the policy allows it to pass through to the application container.

To prevent unauthenticated access, you must combine RequestAuthentication with an **AuthorizationPolicy** that denies requests lacking a valid authentication principal:

```yaml
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: require-jwt-auth
  namespace: default
spec:
  selector:
    matchLabels:
      app: orders
  action: ALLOW
  rules:
    - from:
        - source:
            # Rejects requests that do not have a valid subject (requestPrincipal)
            requestPrincipals: ["*"]
```

---

## 21.7 Fine-Grained Authorization Policies

Istio uses the **AuthorizationPolicy** resource to enforce access control rules based on paths, HTTP verbs, JWT claims, and service identities.

```
                    +------------------------------------+
                    |         AuthorizationPolicy        |
                    +-----------------+------------------+
                                      |
            +-------------------------+-------------------------+
            | (Restricts Methods)                               | (Restricts Claims)
            v                                                   v
[ HTTP GET on /orders ]                               [ request.auth.claims[authorities] ]
- Allowed: Users with ROLE_USER                       - Allowed: ROLE_ADMIN / ROLE_USER
- Denied: Unauthenticated                             - Denied: Others
```

Under older versions, this was mapped using ServiceRoles and bindings:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//dad71785-d027-45cb-99a7-5e308cb52775/markdown_3/imgs/img_in_image_box_128_103_927_672.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A20%3A31Z%2F-1%2F%2F242fb7a0f27d00d9c9b9beac146a60800ae864905ad9ecaff28c093d9ea9cdf5" alt="Image" width="75%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 12.7 A ServiceRole binds a set of actions to a set of resources, and a ServiceRoleBinding binds a set of ServiceRoles to one or more subjects based on certain properties.</div> </div>

This is the consolidated architecture diagram showing TLS terminations, mTLS validations, and JWT authorization rules active at the sidecar proxies:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//5f0119dd-b7cf-4765-bb85-5e2339b59c12/markdown_0/imgs/img_in_image_box_161_110_945_633.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A20%3A30Z%2F-1%2F%2Ffb14cbac42f9d0e46e81661f0621edcce78d63514f384c3a003afa1b44947612" alt="Image" width="73%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 12.8 The Istio Ingress gateway intercepts all the requests coming to the microservice and terminates the TLS connection. The communications between the Ingress gateway and microservices, as well as among microservices, are protected with mTLS. The Envoy proxy does JWT verification for the Order Processing and Inventory microservices.</div> </div>

### 1. Role-Based Access Control using JWT Claims (`orders-authz.yaml`)
Allow `GET` requests for users with the `ROLE_USER` authority, and restrict `POST` requests to users with the `ROLE_ADMIN` authority:

```yaml
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: orders-rbac-policy
  namespace: default
spec:
  selector:
    matchLabels:
      app: orders
  action: ALLOW
  rules:
    # Rule 1: Allow GET calls for user role
    - to:
        - operation:
            methods: ["GET"]
            paths: ["/orders/*"]
      when:
        - key: request.auth.claims[authorities]
          values: ["ROLE_USER", "ROLE_ADMIN"]
    
    # Rule 2: Restrict POST calls to admin role
    - to:
        - operation:
            methods: ["POST"]
            paths: ["/orders"]
      when:
        - key: request.auth.claims[authorities]
          values: ["ROLE_ADMIN"]
```

---

### 2. Service-to-Service Authorization using SPIFFE Identities (`inventory-authz.yaml`)
To prevent internal service spoofing, restrict ingress traffic to the `inventory-service` to accept requests only from the `orders-service` based on its ServiceAccount identity:

```yaml
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: inventory-authz-policy
  namespace: default
spec:
  selector:
    matchLabels:
      app: inventory
  action: ALLOW
  rules:
    - from:
        # Enforce source principal identification using SPIFFE format
        - source:
            principals: ["cluster.local/ns/default/sa/orders-sa"]
      to:
        - operation:
            methods: ["GET"]
            paths: ["/inventory/*"]
```

Apply both policies:
```bash
kubectl apply -f orders-authz.yaml
kubectl apply -f inventory-authz.yaml
```

---

## 21.8 Securing Outbound Traffic with Egress Gateways

To prevent malicious workloads from exfiltrating data, we configure the mesh to restrict outbound traffic. By default, Istio allows outbound calls to any external IP address.

To restrict egress traffic:
1. Configure the mesh to block external traffic:
   ```bash
   kubectl get configmap istio -n istio-system -o yaml | sed 's/mode: ALLOW_ANY/mode: REGISTRY_ONLY/g' | kubectl replace -f -
   ```
2. Define a **ServiceEntry** to whitelist approved external domains (such as payment processing APIs):

```yaml
apiVersion: networking.istio.io/v1alpha3
kind: ServiceEntry
metadata:
  name: stripe-api-whitelist
  namespace: default
spec:
  hosts:
    - "api.stripe.com"
  ports:
    - number: 443
      name: https
      protocol: HTTPS
  resolution: DNS
  location: MESH_EXTERNAL
```

---

### 3. Route Outbound Traffic through a Dedicated Egress Gateway
For auditing, we route whitelisted traffic through an Egress Gateway rather than allowing sidecars to connect to the internet directly:

```yaml
apiVersion: networking.istio.io/v1alpha3
kind: Gateway
metadata:
  name: istio-egressgateway
  namespace: default
spec:
  selector:
    istio: egressgateway
  servers:
    - port:
        number: 443
        name: https
        protocol: HTTPS
      hosts:
        - "api.stripe.com"
      tls:
        mode: PASSTHROUGH
---
apiVersion: networking.istio.io/v1alpha3
kind: DestinationRule
metadata:
  name: egressgateway-stripe-destination
  namespace: default
spec:
  host: istio-egressgateway.istio-system.svc.cluster.local
  subsets:
    - name: stripe
---
apiVersion: networking.istio.io/v1alpha3
kind: VirtualService
metadata:
  name: direct-stripe-through-egress
  namespace: default
spec:
  hosts:
    - "api.stripe.com"
  gateways:
    - mesh
    - istio-egressgateway
  http:
    - match:
        - gateways:
            - mesh
          port: 80
      route:
        - destination:
            host: istio-egressgateway.istio-system.svc.cluster.local
            subset: stripe
            port:
              number: 443
    - match:
        - gateways:
            - istio-egressgateway
          port: 443
      route:
        - destination:
            host: api.stripe.com
            port:
              number: 443
```

---

## 21.9 Key Provisioning and Secret Discovery Service (SDS)

Istio establishes service identity and secures communications using certificates distributed to each sidecar proxy.

### 1. SPIFFE Identifiers
Istio assigns each workload a unique identity using the **SPIFFE** (Secure Production Identity Framework for Enterprise) standard. The SPIFFE identity is embedded in the Subject Alternative Name (SAN) of the X.509 certificate:

`spiffe://<trust-domain>/ns/<namespace>/sa/<service-account-name>`

Example identity for the Order Service:
`spiffe://cluster.local/ns/default/sa/orders-sa`

---

### 2. Envoy Secret Discovery Service (SDS)
* **Legacy Method (Volume Mounts)**: Citadel wrote certificate keys to temporary disk directories on the host, which were mounted into sidecar containers. This approach presented security risks as certificates were written to disk, and rotating them required reloading the container filesystem.
* **Modern Method (SDS API)**: Envoy requests certificates directly from the local agent over a Unix Domain Socket using the SDS API. Keys are generated and stored in memory, removing the need to write certificates to disk.

This dynamic delivery allows Citadel to rotate short-lived certificates (which expire in 24 hours) automatically without restarting the application or sidecar container:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//4a6c9768-0c45-4135-9827-aea299805d8d/markdown_2/imgs/img_in_image_box_115_107_921_697.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A20%3A31Z%2F-1%2F%2Fc0e1e72b76c1ab3a72208344c990eed4d57f77883b0154e902f8ae0dc4dab193" alt="Image" width="75%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 12.9 SDS introduces a node agent (prior to version 1.5.0), which runs on each Kubernetes node. This node agent generates a key pair for each workload (proxy) in the corresponding node and gets those signed by Citadel.</div> </div>

---

## 21.10 Java Downstream HTTP Header Propagation Filter

To propagate user details across downstream services, write a Java servlet filter (`UserContextPropagationFilter`) that extracts header claims written by the Envoy proxy (e.g., `X-User-Name`), stores them in a `ThreadLocal` context, and propagates them during outgoing RestTemplate calls:

```java
package com.ftgo.order.security;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpRequest;
import org.springframework.http.client.ClientHttpRequestExecution;
import org.springframework.http.client.ClientHttpRequestInterceptor;
import org.springframework.http.client.ClientHttpResponse;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;
import javax.servlet.FilterChain;
import javax.servlet.ServletException;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import java.io.IOException;

@Component
public class UserContextPropagationFilter extends OncePerRequestFilter implements ClientHttpRequestInterceptor {

    private static final Logger logger = LoggerFactory.getLogger(UserContextPropagationFilter.class);
    private static final ThreadLocal<String> userContext = new ThreadLocal<>();

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain filterChain)
            throws ServletException, IOException {
        
        // 1. Read claims mapped into headers by the Envoy sidecar proxy
        String userName = request.getHeader("X-User-Name");
        if (userName != null) {
            logger.debug("Intercepted incoming user claim from Envoy: {}", userName);
            userContext.set(userName);
        }

        try {
            filterChain.doFilter(request, response);
        } finally {
            // Clean up context to prevent thread reuse leaks
            userContext.remove();
        }
    }

    // 2. Intercept outgoing RestTemplate requests to propagate the header
    @Override
    public ClientHttpResponse intercept(HttpRequest request, byte[] body, ClientHttpRequestExecution execution)
            throws IOException {
        
        String currentUser = userContext.get();
        if (currentUser != null) {
            logger.debug("Propagating user claim down the chain: {}", currentUser);
            request.getHeaders().add("X-User-Name", currentUser);
        }
        return execution.execute(request, body);
    }
}
```

---

## 21.11 Troubleshooting Service Mesh Security via CLI

When debugging TLS termination, identity handshakes, or authorization blockages inside the mesh, the command-line utility `istioctl` is essential for analyzing Envoy's dynamic configuration:

```bash
# 1. Analyze configuration issues in active namespaces
istioctl analyze -n default

# 2. Inspect active in-memory certificates for a sidecar proxy
istioctl proxy-config secret orders-deployment-f7bc58fbc-bbhwd.default

# 3. Verify downstream connection endpoints for a container proxy
istioctl proxy-config endpoint orders-deployment-f7bc58fbc-bbhwd.default

# 4. View sync status of all Envoy sidecars across the control plane
istioctl proxy-status
```

### Deciphering `istioctl analyze` Warning Outputs
When you run `istioctl analyze`, the utility outputs structured verification events indicating policy inconsistencies. For example:
```
Analysis messages:
- Info [IST0102] (Namespace default) The namespace default is labeled for istio-injection=enabled. Workloads will automatically be injected with sidecars.
- Warn [IST0136] (AuthorizationPolicy require-jwt-auth/default) Policy has no from sources matching requestPrincipal, potentially leaving endpoints unauthenticated if JWT is missing.
- Error [IST0129] (DestinationRule ecomm-services-mtls/default) DestinationRule default/ecomm-services-mtls specifies mTLS mode ISTIO_MUTUAL but no matching PeerAuthentication policy is declared, which will cause connection failures.
```
These compiler warnings help you rectify matching logic before releasing resources.

If clients receive a `403 RBAC Access Denied` response, check proxy logs:
```bash
kubectl logs orders-deployment-f7bc58fbc-bbhwd -c istio-proxy --tail=100
```
Look for `rbac_access_denied_matched_policy` errors to identify which `AuthorizationPolicy` rules are blocking connection routes.

---

## 21.12 Validation and Testing Walkthrough

Follow these steps to verify your Istio configurations:

### 1. Find the Ingress Gateway Host IP and Port
Retrieve the external ingress IP and port details from the cluster:
```bash
export INGRESS_HOST=$(kubectl -n istio-system get service istio-ingressgateway -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
export INGRESS_PORT=$(kubectl -n istio-system get service istio-ingressgateway -o jsonpath='{.spec.ports[?(@.name="https")].port}')
```

### 2. Retrieve JWT access token from STS
Send a POST request to retrieve a valid JWT token:
```bash
curl -k -X POST --basic -u applicationid:applicationsecret \
  -d "grant_type=password&username=peter&password=peter123&scope=foo" \
  --resolve sts.ecomm.com:$INGRESS_PORT:$INGRESS_HOST \
  https://sts.ecomm.com:$INGRESS_PORT/oauth/token
```

Save the returned access token value to an environment variable:
```bash
export TOKEN="eyJhbGciOiJSUzI1Ni..."
```

### 3. Verify Valid Access Request (GET)
This call should return an HTTP `200 OK` status:
```bash
curl -k -H "Authorization: Bearer $TOKEN" \
  --resolve orders.ecomm.com:$INGRESS_PORT:$INGRESS_HOST \
  https://orders.ecomm.com:$INGRESS_PORT/orders/11
```

### 4. Verify Unauthorized Post Request (POST)
If a user with the `ROLE_USER` role attempts to place an order using a POST request, Envoy blocks the connection and returns an HTTP `403 Forbidden` status:
```bash
curl -k -v -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  --resolve orders.ecomm.com:$INGRESS_PORT:$INGRESS_HOST \
  -d '{"customer_id":"101"}' \
  https://orders.ecomm.com:$INGRESS_PORT/orders
# Output: HTTP/2 403 Forbidden
```

### 5. Verify Request Without a JWT
If the request is sent without an Authorization header, Envoy blocks the request at the Ingress Gateway and returns an HTTP `403 Forbidden` status:
```bash
curl -k -v \
  --resolve orders.ecomm.com:$INGRESS_PORT:$INGRESS_HOST \
  https://orders.ecomm.com:$INGRESS_PORT/orders/11
# Output: HTTP/2 403 Forbidden
```

---

## Chapter Summary

* A Service Mesh decouples security, routing, and policy enforcement from application code by using out-of-process sidecar proxies.
* The **Istio Ingress Gateway** acts as the single entry point for external traffic, managing TLS termination and host routing rules.
* Custom PKI certificate roots can be integrated with Citadel using the `cacerts` Kubernetes Secret.
* Ingress Gateways can enforce B2B mutual TLS configurations by validating client-side certificate chains.
* **PeerAuthentication** policies enforce Mutual TLS (mTLS) across namespace boundaries, with modes including `STRICT` and `PERMISSIVE`.
* **RequestAuthentication** policies validate JWT signatures, issuers, and audiences using public keys retrieved from JWKS endpoints.
* Verified JWT claim attributes are propagated dynamically as HTTP request headers, allowing backend services to read claims without JWT parsing libraries.
* To prevent authentication bypass when no JWT is supplied, combine RequestAuthentication with an **AuthorizationPolicy** checking `requestPrincipals`.
* **AuthorizationPolicies** enforce access control based on paths, HTTP methods, JWT claims, and service identities.
* Outgoing traffic is secured using **Egress Gateways** combined with **ServiceEntry** and custom routing rules to prevent data exfiltration.
* Service identity is established using the **SPIFFE** standard, and certificates are distributed securely in-memory using Envoy's **Secret Discovery Service (SDS)**.
* Active configurations, certificates, and endpoints are audited and debugged using `istioctl` commands.
