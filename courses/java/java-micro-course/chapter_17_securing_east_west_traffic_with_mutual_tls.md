# Chapter 17: Securing East-West Traffic with Mutual TLS

Securing the boundary of your microservices network (North-South traffic) is only the first step in a robust security strategy. If an attacker breaches the API Gateway or compromises a single container, they can intercept internal, unencrypted network communications (East-West traffic) between services. To prevent this lateral movement, we use the **Zero Trust Security** model, which requires verifying all requests—even those originating within the internal network.

This chapter covers the technical implementation of **Mutual TLS (mTLS)** to secure East-West service-to-service traffic. We will analyze the mTLS handshake sequence, generate a Root Certificate Authority (CA) and sign service certificates using Java's `keytool` utility, and configure Spring Boot services to require mutually authenticated SSL handshakes. We will program Tomcat custom connectors in Java to support HTTP-to-HTTPS redirection, build secure Feign Clients and reactive WebClients, implement dynamic in-memory certificate reloading without JVM reboots, configure periodic update schedulers in Spring, and deploy platform-level mTLS using **Istio Service Mesh** configurations. Finally, we will write a complete integration test using Spring Boot to verify mTLS channel authentication.

---

## Learning Objectives

By the end of this chapter, you will be able to:
1. Contrast North-South traffic security at the gateway with East-West traffic security.
2. Outline the principles of the **Zero Trust Security** model.
3. Detail the step-by-step cryptographic handshake sequence of Mutual TLS (mTLS).
4. Build a Root Certificate Authority (CA) and sign individual service certificates using the JDK `keytool` utility.
5. Configure Tomcat SSL server properties inside Spring Boot properties files.
6. Program custom Tomcat web connectors to redirect HTTP plaintext traffic to HTTPS.
7. Build custom secure Feign Clients and WebClients that load SSL keystores and truststores.
8. Design reloadable Java X509 Key and Trust Managers to refresh certificates dynamically in-memory without JVM restarts.
9. Configure a file-watcher scheduling task in Spring Boot to automatically detect certificate updates on disk.
10. Enforce STRICT mTLS at the Kubernetes platform layer using Istio peer authentication and destination rules.
11. Write a programmatic integration test using Spring Boot and RestTemplate to verify mTLS connectivity and certificate validation.

---

## 17.1 Zero Trust Security: Beyond Perimeter Security

Traditional security architectures rely on **Perimeter Security** (also known as the "castle-and-moat" model). The API Gateway acts as the moat: once a request passes gateway authentication, it is considered trusted and routes to internal services over unencrypted HTTP:

``  UNTRUSTED ZONE                      INTERNAL TRUST ZONE (Vulnerable)
  Client Application    API Gateway (mTLS Edge)   Kitchen Service      Order Service
           |                       |                      |                      |
           |--- HTTP (Token) ----->|                      |                      |
           |                       |--- Unencrypted HTTP ----------------------->|
           |                       |    (Plaintext headers visible)              |
```

In this model, if an attacker gains access to the internal network (e.g. via a compromised container), they can intercept passwords, tokens, and sensitive data.

The **Zero Trust Security** model eliminates the concept of an internal trusted zone. Its core principles are:
* **Verify Explicitly**: Authenticate and authorize every request based on all available data points.
* **Use Least-Privileged Access**: Restrict access using role-based permissions and dynamic policies.
* **Assume Breach**: Encrypt all traffic, monitor for anomalies, and isolate resources to minimize the blast radius of a breach.

Under a Zero Trust architecture, all service-to-service (East-West) traffic must be encrypted and authenticated using **Mutual TLS (mTLS)**.

---

## 17.2 The Cryptographic mTLS Handshake Sequence

In standard TLS, only the server presents a certificate. The client validates the server's certificate to verify its identity before establishing an encrypted connection.

A certificate represents the corresponding server's public key and binds it to a common name. Amazon's public certificate, for example, binds its public key to the `www.amazon.com` common name. When a browser talks to Amazon over TLS, it can verify that Amazon's certificate is valid by verifying its signature against a trusted CA's public key embedded in the browser:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//dfa6adb1-300d-478e-a021-c8e4845a42c0/markdown_0/imgs/img_in_image_box_199_117_665_627.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A20%3A26Z%2F-1%2F%2Fd149d52f04e73dc0a45ccce9fa2f3cf5fa1c9510514a4e3c3cad121f01cfd61f" alt="Image" width="43%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 6.1 The certificate of www.amazon.com, issued by the DigiCert Global CA. This certificate helps clients talking to www.amazon.com properly identify the server.</div> </div>

Two-way TLS, or mutual TLS (mTLS), fills this gap by helping the client and the server identify themselves to each other. With mTLS, the server knows the identity of the client it is communicating with:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//dfa6adb1-300d-478e-a021-c8e4845a42c0/markdown_0/imgs/img_in_image_box_193_687_882_1158.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A20%3A27Z%2F-1%2F%2Fecc58709043992ac11157271585e7c14e235d5cd938a85551369f5e4000913fa" alt="Image" width="64%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 6.2 mTLS among microservices lets those services identify themselves. All the microservices in the deployment trust one CA.</div> </div>

In **Mutual TLS (mTLS)**, both the client and the server must present and validate certificates:

```
  Client (Service A)                                   Server (Service B)
          |                                                    |
          |--- 1. ClientHello -------------------------------->|
          |<-- 2. ServerHello & Server Certificate ------------|
          |<-- 3. CertificateRequest (Request client cert) ----|
          |                                                    |
          |--- 4. Client Certificate ------------------------->|
          |--- 5. CertificateVerify (Client private signature) |
          |                                                    |
          | * BOTH VALIDATE CERTIFICATES AGAINST TRUSTSTORES * |
          |                                                    |
          |<-- 6. Handshake Finished (Session established) ----|
```

### The Step-by-Step Handshake Flow
1. **ClientHello**: The client initiates the handshake, offering supported TLS versions and cipher suites.
2. **ServerHello & Server Certificate**: The server responds, presenting its public X.509 certificate to the client.
3. **CertificateRequest**: The server requests that the client present its public certificate to prove its identity.
4. **Client Certificate**: The client sends its public X.509 certificate.
5. **CertificateVerify**: The client sends a digital signature signed with its private key. The server validates this signature using the client's public certificate, proving the client owns the private key.
6. **Handshake Finished**: Both parties validate the certificates against their respective truststores. If validation succeeds, they negotiate a symmetric session key and establish an encrypted channel.

This is the standard message exchange topology when the Order Processing service calls the Kitchen service over TLS:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//031dcec2-b94d-408f-8b90-f4282ceff925/markdown_2/imgs/img_in_image_box_174_692_898_1176.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A20%39Z%2F-1%2F%2F4d9a4517e277b05637021bdbb702479a09cb5ae2ef9e66fcfc191894d16eeacd" alt="Image" width="68%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 6.4 The Order Processing microservice talks to the Kitchen microservice over TLS.</div> </div>

---

## 17.3 Enterprise PKI Setup using JDK `keytool`

In production environments, services validate certificates against a shared Root Certificate Authority (CA) rather than manually exchanging self-signed certificates.

We will simulate this PKI architecture by generating a custom Root CA and signing certificates for the `kitchen-service` and `order-service`.

```
                  +-----------------------------------+
                  |      Shared Root CA Private Key   |
                  +-----------------+-----------------+
                                    |
            +-----------------------+-----------------------+
            | (Signs)                                       | (Signs)
            v                                               v
[ kitchen.p12 (Keystore) ]                     [ order.p12 (Keystore) ]
- Identity: kitchen-service                    - Identity: order-service
- Signed by: Root CA                           - Signed by: Root CA
```

To establish this layout, each microservice receives a Java keystore (`.jks` or `.p12`) holding its private key and public certificates signed by the Root CA:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//dfa6adb1-300d-478e-a021-c8e4845a42c0/markdown_2/imgs/img_in_image_box_200_706_784_992.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A20%3A28Z%2F-1%2F%2F9604755fbd332d71adca76fd8e44fb9323f0e6ff5ed0ba369ba36489a73d330b" alt="Image" width="54%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 6.3 Keystore setup: each microservice has its own public/private key pair stored in a Java keystore file (.jks), along with the CA's public key.</div> </div>

### Step 1: Create a Custom Root Certificate Authority (CA)
Generate a 4096-bit RSA key pair for the Root CA:
```bash
keytool -genkeypair \
  -alias root-ca \
  -keyalg RSA \
  -keysize 4096 \
  -ext bc:c \
  -keystore root-ca.p12 \
  -storetype PKCS12 \
  -validity 3650 \
  -dname "CN=FTGO Root CA, O=FTGO, C=US" \
  -storepass capassword
```

Export the Root CA's public certificate to distribute to all services:
```bash
keytool -exportcert \
  -alias root-ca \
  -file root-ca.cer \
  -keystore root-ca.p12 \
  -storepass capassword
```

---

### Step 2: Generate Service Private Keys and Certificate Requests (CSR)
Create a keystore and generate a key pair for the Kitchen Service:
```bash
keytool -genkeypair \
  -alias kitchen \
  -keyalg RSA \
  -keysize 2048 \
  -keystore kitchen-keystore.p12 \
  -storetype PKCS12 \
  -validity 365 \
  -dname "CN=kitchen-service, O=FTGO, C=US" \
  -storepass password
```

Generate a Certificate Signing Request (CSR) for the Kitchen Service:
```bash
keytool -certreq \
  -alias kitchen \
  -file kitchen.csr \
  -keystore kitchen-keystore.p12 \
  -storepass password
```

*(Repeat this process for the Order Service to generate `order-keystore.p12` and `order.csr`.)*

---

### Step 3: Sign the Service Certificates using the Root CA
Sign the Kitchen Service's CSR using the Root CA:
```bash
keytool -gencert \
  -alias root-ca \
  -infile kitchen.csr \
  -outfile kitchen-signed.cer \
  -validity 365 \
  -keystore root-ca.p12 \
  -storepass capassword
```

*(Repeat this process to sign the Order Service's CSR, generating `order-signed.cer`.)*

---

### Step 4: Import the Signed Certificates and Root CA into Service Keystores
To establish the chain of trust, import the Root CA certificate into the Kitchen Service's keystore first:
```bash
keytool -importcert \
  -alias root-ca \
  -file root-ca.cer \
  -keystore kitchen-keystore.p12 \
  -storepass password \
  -noprompt
```

Next, import the signed public certificate into the Kitchen Service's keystore:
```bash
keytool -importcert \
  -alias kitchen \
  -file kitchen-signed.cer \
  -keystore kitchen-keystore.p12 \
  -storepass password
```

*(Repeat this process for the Order Service's keystore, importing `root-ca.cer` and `order-signed.cer`.)*

---

### Step 5: Create Truststores Containing the Trusted Root CA
Import the Root CA certificate into the truststores of both services. This allows them to trust any certificate signed by the Root CA:
```bash
keytool -importcert \
  -alias root-ca \
  -file root-ca.cer \
  -keystore kitchen-truststore.p12 \
  -storepass password \
  -noprompt
```

*(Repeat this process to generate `order-truststore.p12` containing `root-ca.cer`.)*

---

## 17.4 Configuring Spring Boot Tomcat for mTLS

We will configure the `order-service` to accept HTTPS connections and require clients to present certificates.

Add the keystore and truststore files to the service's resources directory and update `order-service.yml` in the Config Server:

```yaml
server:
  port: 8443
  ssl:
    # Enable HTTPS
    enabled: true
    # Configure the server's keystore (identity)
    key-store: classpath:order-keystore.p12
    key-store-password: password
    key-store-type: PKCS12
    key-alias: order
    # Configure the server's truststore (list of trusted clients)
    trust-store: classpath:order-truststore.p12
    trust-store-password: password

    trust-store-type: PKCS12
    # Require clients to present certificates (enforces mTLS)
    client-auth: need
```

With `client-auth` set to `need`, Tomcat rejects requests from any client that does not present a certificate trusted in `order-truststore.p12`.

### HTTP to HTTPS Redirection Configuration
To support redirects from unencrypted HTTP traffic (e.g. port 8081) to secure HTTPS endpoints (port 8443), configure a custom Tomcat Web Connector in your Spring Boot application configuration:

```java
package com.ftgo.order.config;

import org.apache.catalina.connector.Connector;
import org.apache.tomcat.util.descriptor.web.SecurityCollection;
import org.apache.tomcat.util.descriptor.web.SecurityConstraint;
import org.springframework.boot.web.embedded.tomcat.TomcatServletWebServerFactory;
import org.springframework.boot.web.servlet.server.ServletWebServerFactory;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class HttpRedirectConfig {

    @Bean
    public ServletWebServerFactory servletContainer() {
        TomcatServletWebServerFactory tomcat = new TomcatServletWebServerFactory() {
            @Override
            protected void postProcessContext(org.apache.catalina.Context context) {
                SecurityConstraint securityConstraint = new SecurityConstraint();
                securityConstraint.setUserConstraint("CONFIDENTIAL");
                SecurityCollection collection = new SecurityCollection();
                collection.addPattern("/*");
                securityConstraint.addCollection(collection);
                context.addConstraint(securityConstraint);
            }
        };
        // Add HTTP connector to redirect requests
        tomcat.addAdditionalTomcatConnectors(createHttpConnector());
        return tomcat;
    }

    private Connector createHttpConnector() {
        Connector connector = new Connector(TomcatServletWebServerFactory.DEFAULT_PROTOCOL);
        connector.setScheme("http");
        connector.setPort(8081); // Listen for HTTP requests
        connector.setSecure(false);
        connector.setRedirectPort(8443); // Redirect to HTTPS port
        return connector;
    }
}
```

---

## 17.5 Building a Secure Feign Client in Java

We will configure the `kitchen-service` to call the `order-service` over mTLS using Feign.

### 1. Maven Dependency Setup
Include the Apache HttpClient dependency in `kitchen-service/pom.xml` to support custom SSL configurations in Feign:

```xml
<dependency>
    <groupId>io.github.openfeign</groupId>
    <artifactId>feign-httpclient</artifactId>
</dependency>
```

---

### 2. Feign SSL Configuration Class: `FeignClientSSLConfig.java`
Implement a configuration class that loads the kitchen keystore and truststore, creates a secure SSL context, and configures Feign to use a secure HTTP client:

```java
package com.ftgo.kitchen.config;

import feign.Client;
import org.apache.http.conn.ssl.NoopHostnameVerifier;
import org.apache.http.conn.ssl.SSLConnectionSocketFactory;
import org.apache.http.impl.client.CloseableHttpClient;
import org.apache.http.impl.client.HttpClients;
import org.apache.http.ssl.SSLContexts;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.io.ClassPathResource;

import javax.net.ssl.SSLContext;
import java.io.InputStream;
import java.security.KeyStore;

@Configuration
public class FeignClientSSLConfig {

    @Bean
    public Client feignClient() {
        try {
            // 1. Load the Kitchen Service's Keystore
            KeyStore keyStore = KeyStore.getInstance("PKCS12");
            try (InputStream keyStoreStream = new ClassPathResource("kitchen-keystore.p12").getInputStream()) {
                keyStore.load(keyStoreStream, "password".toCharArray());
            }

            // 2. Load the Truststore (containing Root CA certificate)
            KeyStore trustStore = KeyStore.getInstance("PKCS12");
            try (InputStream trustStoreStream = new ClassPathResource("kitchen-truststore.p12").getInputStream()) {
                trustStore.load(trustStoreStream, "password".toCharArray());
            }

            // 3. Build the SSL Context with both keystore and truststore
            SSLContext sslContext = SSLContexts.custom()
                    .loadKeyMaterial(keyStore, "password".toCharArray())
                    .loadTrustMaterial(trustStore, null)
                    .build();

            // 4. Create a Socket Factory that uses the SSL context
            SSLConnectionSocketFactory socketFactory = new SSLConnectionSocketFactory(
                    sslContext,
                    NoopHostnameVerifier.INSTANCE // Disable hostname verification for local testing
            );

            CloseableHttpClient httpClient = HttpClients.custom()
                    .setSSLSocketFactory(socketFactory)
                    .build();

            // 5. Configure Feign to use the secure HTTP client
            return new feign.httpclient.ApacheHttpClient(httpClient);

        } catch (Exception ex) {
            throw new IllegalStateException("Failed to configure secure mTLS Feign Client!", ex);
        }
    }
}
```

---

### 3. The Secure Feign Client Interface: `OrderFeignClient.java`
Declare the Feign client, importing the SSL configuration class:

```java
package com.ftgo.kitchen.client;

import com.ftgo.kitchen.model.Order;
import com.ftgo.kitchen.config.FeignClientSSLConfig;
import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestMethod;

@FeignClient(
    name = "order-service",
    url = "https://localhost:8443", // Call the service over HTTPS
    configuration = FeignClientSSLConfig.class
)
public interface OrderFeignClient {

    @RequestMapping(
        method = RequestMethod.GET,
        value = "/v1/orders/{orderId}",
        consumes = "application/json"
    )
    Order getOrder(@PathVariable("orderId") String orderId);
}
```

---

## 17.6 Building a Secure WebClient in Reactive Spring

If you are building reactive non-blocking microservices using Spring WebFlux, the outgoing HTTP client is configured using **Reactor Netty** wrappers:

```java
package com.ftgo.kitchen.config;

import io.netty.handler.ssl.SslContext;
import io.netty.handler.ssl.SslContextBuilder;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.io.ClassPathResource;
import org.springframework.http.client.reactive.ReactorClientHttpConnector;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.netty.http.client.HttpClient;

import javax.net.ssl.KeyManagerFactory;
import javax.net.ssl.TrustManagerFactory;
import java.io.InputStream;
import java.security.KeyStore;

@Configuration
public class WebClientMtlsConfig {

    @Bean
    public WebClient secureWebClient() {
        try {
            // 1. Load Keystore
            KeyStore keyStore = KeyStore.getInstance("PKCS12");
            try (InputStream ksStream = new ClassPathResource("kitchen-keystore.p12").getInputStream()) {
                keyStore.load(ksStream, "password".toCharArray());
            }
            KeyManagerFactory keyManagerFactory = KeyManagerFactory.getInstance(KeyManagerFactory.getDefaultAlgorithm());
            keyManagerFactory.init(keyStore, "password".toCharArray());

            // 2. Load Truststore
            KeyStore trustStore = KeyStore.getInstance("PKCS12");
            try (InputStream tsStream = new ClassPathResource("kitchen-truststore.p12").getInputStream()) {
                trustStore.load(tsStream, "password".toCharArray());
            }
            TrustManagerFactory trustManagerFactory = TrustManagerFactory.getInstance(TrustManagerFactory.getDefaultAlgorithm());
            trustManagerFactory.init(trustStore);

            // 3. Build netty SslContext
            SslContext sslContext = SslContextBuilder.forClient()
                    .keyManager(keyManagerFactory)
                    .trustManager(trustManagerFactory)
                    .build();

            // 4. Configure Netty HttpClient
            HttpClient httpClient = HttpClient.create()
                    .secure(sslContextSpec -> sslContextSpec.sslContext(sslContext));

            // 5. Wrap inside WebClient
            return WebClient.builder()
                    .clientConnector(new ReactorClientHttpConnector(httpClient))
                    .baseUrl("https://localhost:8443")
                    .build();

        } catch (Exception ex) {
            throw new IllegalStateException("Failed to build secure reactive WebClient mTLS context!", ex);
        }
    }
}
```

---

## 17.7 Dynamic Certificate Reloading Without JVM Restarts

By default, Spring Boot only loads keystores and truststores once at startup. If a certificate expires and is renewed on disk, you must restart the JVM to load it.

To resolve these lifecycle limits, companies automate provisioning by establishing certificate CA brokers to generate and inject signed keys at runtime:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//242cf2ed-100f-4743-a4a6-b7a3ea6dc618/markdown_3/imgs/img_in_image_box_201_747_897_1139.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A20%3A29Z%2F-1%2F%2Fd8e9a2af59b4ed2d198d168d510156f18a2c8af94dfaa0da7c280582dbf2d4d0" alt="Image" width="65%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 6.5 Key provisioning at Netflix. Each microservice at startup talks to Lemur to get a signed certificate from the CA in the domain.</div> </div>

Certificate validation requires checking revocation states to block compromised keys. This is achieved by referencing CRL distribution points:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//e9c24a68-5c71-4595-b9a1-9cf774b99260/markdown_0/imgs/img_in_image_box_182_668_663_1188.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A20%3A27Z%2F-1%2F%2Ffbff21a361bb867f5fa4f352212678e12d59bbdc7e1966acdc7b6652162ed449" alt="Image" width="45%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 6.6 The Amazon certificate embeds the corresponding CRL distribution points.</div> </div>

Or calling online status responders:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//e9c24a68-5c71-4595-b9a1-9cf774b99260/markdown_1/imgs/img_in_image_box_206_670_684_1200.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A20%3A27Z%2F-1%2F%2F663d14c902f20f911ea4b1b313b700ded7eaa0c32d03e01b7a501d7067c4727f" alt="Image" width="45%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 6.7 The Amazon certificate embeds the OCSP endpoint.</div> </div>

Workloads use short-lived certificates to minimize vulnerability windows when key compromise occurs:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//e9c24a68-5c71-4595-b9a1-9cf774b99260/markdown_4/imgs/img_in_image_box_194_557_890_945.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A20%3A29Z%2F-1%2F%2Fc754c9d33c50fdbda23c4de5cadb62a4f55845bc2078f343a1dea184125b9971" alt="Image" width="65%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 6.8 Netflix uses short-lived certificates with mTLS to secure service-to-service communications.</div> </div>

To prevent downtime, we implement a **custom reloadable key and trust manager** that periodically checks the certificate files on disk and refreshes the SSL context dynamically:

```
[ filesystem: keystore.p12 ] --( Update File )
                                      |
                                      v (Scheduled Check)
                  [ ReloadableX509Key & TrustManager ]
                                      |
                                      v (Refreshes In-Memory Context)
                         [ Secure HTTP Client / Netty ]
```

### 1. Reloadable Trust Manager Implementation
```java
package com.ftgo.kitchen.security;

import javax.net.ssl.X509ExtendedTrustManager;
import javax.net.ssl.TrustManagerFactory;
import java.io.File;
import java.io.FileInputStream;
import java.security.KeyStore;
import java.security.cert.CertificateException;
import java.security.cert.X509Certificate;
import java.net.Socket;
import javax.net.ssl.SSLEngine;

public class ReloadableX509TrustManager extends X509ExtendedTrustManager {
    
    private final String truststorePath;
    private final String password;
    private X509ExtendedTrustManager currentTrustManager;

    public ReloadableX509TrustManager(String truststorePath, String password) {
        this.truststorePath = truststorePath;
        this.password = password;
        reload();
    }

    public synchronized void reload() {
        try {
            KeyStore trustStore = KeyStore.getInstance("PKCS12");
            try (FileInputStream fis = new FileInputStream(new File(truststorePath))) {
                trustStore.load(fis, password.toCharArray());
            }
            
            TrustManagerFactory tmf = TrustManagerFactory.getInstance(TrustManagerFactory.getDefaultAlgorithm());
            tmf.init(trustStore);
            
            for (javax.net.ssl.TrustManager tm : tmf.getTrustManagers()) {
                if (tm instanceof X509ExtendedTrustManager) {
                    this.currentTrustManager = (X509ExtendedTrustManager) tm;
                    break;
                }
            }
        } catch (Exception e) {
            throw new IllegalStateException("Failed to reload truststore from disk!", e);
        }
    }

    @Override
    public void checkClientTrusted(X509Certificate[] chain, String authType) throws CertificateException {
        currentTrustManager.checkClientTrusted(chain, authType);
    }

    @Override
    public void checkServerTrusted(X509Certificate[] chain, String authType) throws CertificateException {
        currentTrustManager.checkServerTrusted(chain, authType);
    }

    @Override
    public X509Certificate[] getAcceptedIssuers() {
        return currentTrustManager.getAcceptedIssuers();
    }

    @Override
    public void checkClientTrusted(X509Certificate[] chain, String authType, Socket socket) throws CertificateException {
        currentTrustManager.checkClientTrusted(chain, authType, socket);
    }

    @Override
    public void checkServerTrusted(X509Certificate[] chain, String authType, Socket socket) throws CertificateException {
        currentTrustManager.checkServerTrusted(chain, authType, socket);
    }

    @Override
    public void checkClientTrusted(X509Certificate[] chain, String authType, SSLEngine engine) throws CertificateException {
        currentTrustManager.checkClientTrusted(chain, authType, engine);
    }

    @Override
    public void checkServerTrusted(X509Certificate[] chain, String authType, SSLEngine engine) throws CertificateException {
        currentTrustManager.checkServerTrusted(chain, authType, engine);
    }
}
```

---

### 2. Reloadable Key Manager Implementation
```java
package com.ftgo.kitchen.security;

import javax.net.ssl.X509ExtendedKeyManager;
import javax.net.ssl.KeyManagerFactory;
import java.io.File;
import java.io.FileInputStream;
import java.security.KeyStore;
import java.security.Principal;
import java.security.PrivateKey;
import java.security.cert.X509Certificate;
import java.net.Socket;
import javax.net.ssl.SSLEngine;

public class ReloadableX509KeyManager extends X509ExtendedKeyManager {
    private final String keystorePath;
    private final String password;
    private final String alias;
    private X509ExtendedKeyManager currentKeyManager;

    public ReloadableX509KeyManager(String keystorePath, String password, String alias) {
        this.keystorePath = keystorePath;
        this.password = password;
        this.alias = alias;
        reload();
    }

    public synchronized void reload() {
        try {
            KeyStore keyStore = KeyStore.getInstance("PKCS12");
            try (FileInputStream fis = new FileInputStream(new File(keystorePath))) {
                keyStore.load(fis, password.toCharArray());
            }
            KeyManagerFactory kmf = KeyManagerFactory.getInstance(KeyManagerFactory.getDefaultAlgorithm());
            kmf.init(keyStore, password.toCharArray());
            for (javax.net.ssl.KeyManager km : kmf.getKeyManagers()) {
                if (km instanceof X509ExtendedKeyManager) {
                    this.currentKeyManager = (X509ExtendedKeyManager) km;
                    break;
                }
            }
        } catch (Exception e) {
            throw new IllegalStateException("Failed to reload keystore from disk!", e);
        }
    }

    @Override
    public String[] getClientAliases(String keyType, Principal[] issuers) {
        return currentKeyManager.getClientAliases(keyType, issuers);
    }

    @Override
    public String chooseClientAlias(String[] keyType, Principal[] issuers, Socket socket) {
        return alias;
    }

    @Override
    public String[] getServerAliases(String keyType, Principal[] issuers) {
        return currentKeyManager.getServerAliases(keyType, issuers);
    }

    @Override
    public String chooseServerAlias(String keyType, Principal[] issuers, Socket socket) {
        return alias;
    }

    @Override
    public X509Certificate[] getCertificateChain(String alias) {
        return currentKeyManager.getCertificateChain(alias);
    }

    @Override
    public PrivateKey getPrivateKey(String alias) {
        return currentKeyManager.getPrivateKey(alias);
    }

    @Override
    public String chooseEngineClientAlias(String[] keyType, Principal[] issuers, SSLEngine engine) {
        return alias;
    }

    @Override
    public String chooseEngineServerAlias(String keyType, Principal[] issuers, SSLEngine engine) {
        return alias;
    }
}
```

---

### 3. Spring Scheduler Configuration
This scheduled bean checks modification timestamps on the files and triggers updates automatically:

```java
package com.ftgo.kitchen.security;

import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import java.io.File;

@Component
public class CertificateReloadScheduler {

    private final ReloadableX509KeyManager keyManager;
    private final ReloadableX509TrustManager trustManager;
    
    private long lastKeyManagerModified;
    private long lastTrustManagerModified;

    public CertificateReloadScheduler(ReloadableX509KeyManager keyManager, ReloadableX509TrustManager trustManager) {
        this.keyManager = keyManager;
        this.trustManager = trustManager;
        this.lastKeyManagerModified = new File("/var/certs/kitchen-keystore.p12").lastModified();
        this.lastTrustManagerModified = new File("/var/certs/kitchen-truststore.p12").lastModified();
    }

    @Scheduled(fixedDelay = 60000) // Check every 60 seconds
    public void checkForUpdates() {
        File keyFile = new File("/var/certs/kitchen-keystore.p12");
        if (keyFile.exists() && keyFile.lastModified() > lastKeyManagerModified) {
            keyManager.reload();
            lastKeyManagerModified = keyFile.lastModified();
        }

        File trustFile = new File("/var/certs/kitchen-truststore.p12");
        if (trustFile.exists() && trustFile.lastModified() > lastTrustManagerModified) {
            trustManager.reload();
            lastTrustManagerModified = trustFile.lastModified();
        }
    }
}
```

---

## 17.8 Alternative: Platform-Level mTLS using Service Mesh (Istio)

To avoid managing keystores, truststores, and Java code configurations for every service, you can offload mTLS encryption to a **Service Mesh** (like Istio) at the platform layer.

In this model, an **Envoy Proxy** runs as a sidecar container alongside every microservice pod. The proxies automatically intercept incoming and outgoing network traffic, handling mTLS handshakes and encryption transparently:

```
[ Pod A: Kitchen ]                  [ Pod B: Order ]
  [ Kitchen Container ]               [ Order Container ]
        |                                   ^
        v (Plaintext HTTP)                  | (Plaintext HTTP)
  [ Envoy Proxy (Client) ] ==( mTLS HTTPS )=> [ Envoy Proxy (Server) ]
```

To enforce STRICT mutual TLS across all internal services in the mesh, apply the following Istio manifests:

### 1. Istio PeerAuthentication Manifest (`peer-auth.yml`)
Enforces that all services in the namespace accept only encrypted mTLS traffic:

```yaml
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: default
  namespace: ftgo
spec:
  mtls:
    mode: STRICT
```

### 2. Istio DestinationRule Manifest (`destination-rule.yml`)
Instructs the client Envoy proxies to automatically use mTLS when calling downstream services:

```yaml
apiVersion: networking.istio.io/v1alpha3
kind: DestinationRule
metadata:
  name: default
  namespace: ftgo
spec:
  host: "*.ftgo.svc.cluster.local"
  trafficPolicy:
    tls:
      mode: ISTIO_MUTUAL
```

Offloading mTLS to Istio simplifies your code: Spring Boot applications can listen on unencrypted HTTP port 8080 without needing local keystore configs.

---

## 17.9 mTLS Channel Verification Integration Testing

We write an integration test that runs the `order-service` with SSL enabled and attempts to query it using a RestTemplate loaded with the client's keystore:

```java
package com.ftgo.order;

import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.core.io.ClassPathResource;
import org.springframework.http.ResponseEntity;
import org.springframework.http.client.HttpComponentsClientHttpRequestFactory;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestTemplate;

import javax.net.ssl.SSLContext;
import java.io.InputStream;
import java.security.KeyStore;
import org.apache.http.impl.client.CloseableHttpClient;
import org.apache.http.impl.client.HttpClients;
import org.apache.http.ssl.SSLContexts;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
public class MtlsServiceIntegrationTest {

    @LocalServerPort
    private int port;

    @Test
    public void testConnectWithClientCertificate_Succeeds() throws Exception {
        // 1. Set up secure RestTemplate with client certificate
        KeyStore keyStore = KeyStore.getInstance("PKCS12");
        try (InputStream ksStream = new ClassPathResource("kitchen-keystore.p12").getInputStream()) {
            keyStore.load(ksStream, "password".toCharArray());
        }

        KeyStore trustStore = KeyStore.getInstance("PKCS12");
        try (InputStream tsStream = new ClassPathResource("kitchen-truststore.p12").getInputStream()) {
            trustStore.load(tsStream, "password".toCharArray());
        }

        SSLContext sslContext = SSLContexts.custom()
                .loadKeyMaterial(keyStore, "password".toCharArray())
                .loadTrustMaterial(trustStore, null)
                .build();

        CloseableHttpClient httpClient = HttpClients.custom()
                .setSSLContext(sslContext)
                .build();

        RestTemplate secureTemplate = new RestTemplate(new HttpComponentsClientHttpRequestFactory(httpClient));

        // 2. Execute Request to secure port
        ResponseEntity<String> response = secureTemplate.getForEntity(
            "https://localhost:" + port + "/v1/orders/order-100", String.class
        );

        Assertions.assertEquals(200, response.getStatusCodeValue());
    }

    @Test
    public void testConnectWithoutClientCertificate_Fails() {
        // 1. Build an unauthenticated REST template (no keystore loaded)
        RestTemplate plaintextTemplate = new RestTemplate();

        // 2. Expect connection to fail during client certificate request
        Assertions.assertThrows(ResourceAccessException.class, () -> {
            plaintextTemplate.getForEntity(
                "https://localhost:" + port + "/v1/orders/order-100", String.class
            );
        });
    }
}
```

---

## Chapter Summary

* Perimeter Security protects boundary traffic but leaves internal communications vulnerable to interception and lateral movement.
* The **Zero Trust Security** model requires verifying and encrypting every request explicitly, even those inside the internal network.
* **Mutual TLS (mTLS)** authenticates both the client and the server by requiring them to present and validate certificates before connection establishment.
* Enforcing mTLS in Spring Boot is managed by configuring Tomcat SSL properties in `application.yml` and setting `client-auth: need`.
* Plaintext HTTP traffic can be redirected to HTTPS using custom programmed Tomcat servlet connectors.
* Secure HTTP clients configure Feign or WebClient to load keystores and truststores, establishing a secure connection to downstream HTTPS endpoints.
* Reloadable Java trust and key managers check the filesystem periodically, swapping keystore resources in-memory to prevent service restarts when certificates are renewed.
* Sidecar service mesh architectures (like Istio/Envoy) offload mTLS encryption transparently at the platform layer, eliminating local code configurations.

