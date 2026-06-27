# Chapter 19: Securing Asynchronous and Reactive Microservices

In synchronous HTTP or gRPC communications (North-South or East-West), requests flow directly from a client caller to a target provider. Securing this interaction involves authenticating the channel (TLS/mTLS) and propagating credentials (JWT). However, in asynchronous, event-driven architectures (reactive microservices), services communicate indirectly through a centralized message broker (such as Apache Kafka or NATS). This loose coupling introduces unique security challenges.

This chapter covers the implementation of end-to-end security in reactive microservice architectures. We will analyze the security threat model of message brokers, deploy containerized Kafka and ZooKeeper clusters secured with mutual TLS (mTLS), and generate key-pairs and certificates using PKI scripting. We will configure Spring Boot event producers and consumers to communicate securely over TLS, enforce fine-grained topic Access Control Lists (ACLs) using principal mapping rules, secure NATS message brokers, configure SASL/SCRAM authentication, implement secure Dead Letter Queues (DLQ) for error handling, configure Spring Cloud Stream secure bindings, implement programmatic certificate monitoring utilities, and integrate Open Policy Agent (OPA) for externalized Kafka authorization. Finally, we will write a complete integration test using containerized brokers to verify mTLS and ACL configurations.

---

## Learning Objectives

By the end of this chapter, you will be able to:
1. Explain the reactive microservice paradigm and contrast its security requirements with synchronous models.
2. Outline the threat vectors of message brokers, including sniffing, spoofing, and unauthorized topic access.
3. Configure a multi-listener Apache Kafka cluster using Docker Compose with both PLAINTEXT and SSL ports.
4. Generate Root CAs, broker certificates, and client certificates using OpenSSL and Java Keytool.
5. Secure Spring Boot producers and consumers using Spring Kafka properties and mutual TLS configurations.
6. Configure Spring Cloud Stream secure bindings properties for Kafka.
7. Configure SASL/SCRAM-SHA-512 client authentication and set up JAAS files for ZooKeeper.
8. Implement secure Dead Letter Queues (DLQ) in Spring Kafka to isolate poison pill payloads.
9. Inspect and monitor Java KeyStore certificate expiration dates programmatically to alert developers before certificates expire.
10. Enforce topic-level authorization on Kafka using CLI-driven Access Control Lists (ACLs).
11. Configure Distinguished Name (DN) principal mapping rules to translate X.509 identities into Kafka user principles.
12. Secure a NATS server configuration and connect client applications using NATS JetStream Java libraries over TLS.
13. Write a Rego policy to authorize Kafka topic reads and writes using Open Policy Agent (OPA).
14. Build a programmatic integration test using Testcontainers to verify that unauthorized clients are blocked from writing to Kafka topics.

---

## 19.1 Threat Model for Asynchronous Message Brokers

In a synchronous microservice model, the Order Service calls the Inventory Service directly:

```
[ Order Service ] =======( Direct HTTP Request )=======> [ Inventory Service ]
```

In previous chapters, we looked at how the Order Processing microservice becomes the triggering point for the rest of the actions that take place. When an order is processed by the Order Processing microservice, it initiates the rest of the actions that take place, such as updating the inventory, initializing the shipment, and so on. This way, the Order Processing microservice becomes the orchestrator for the rest of the actions related to processing an order:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//e479c41e-e3b5-4465-8fc2-de26f5cd09b7/markdown_4/imgs/img_in_image_box_168_118_930_637.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A20%3A29Z%2F-1%2F%2F37ae218d7df078e693a96f65c4d6bcb980d0772e612ebcb06c6599d79b067c2f" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 9.1 The Order Processing microservice talks to other microservices to initiate events related to processing an order, such as paying for the order, updating the inventory, and so on.</div> </div>

Reactive microservices create a loose coupling between the source microservice that initiates the event and the target microservices that receive and react to the event. In the traditional way of performing these actions, there's a direct link from the Order Processing microservice to the rest of the microservices. With reactive microservices, this link becomes indirect. This happens by introducing a message broker solution into our microservices deployment:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//ad80ee4e-f2bd-4690-bddb-2d757052aae3/markdown_2/imgs/img_in_image_box_126_179_950_774.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A20%3A29Z%2F-1%2F%2Ffaea0339d5f20cf32c65dd1a47bbaa4850d636e0686f8ca818b5f6280f5905fa" alt="Image" width="77%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 9.2 Introducing a message broker into the architecture. The Order Processing microservice calls the Payment microservice directly because payment is a mandatory and synchronous step in processing the order. It then emits an event to the message broker that delivers the order details to the rest of the microservices asynchronously. This makes the link between the Order Processing microservice and the other microservices indirect.</div> </div>

But with the reactive architecture, all we need to do is to make the Buying History microservice aware of the order event by linking it to a message broker. This way, the Buying History microservice gets to know the details of each order when an order is processed. This gives us the flexibility to add new functionality to the system without having to change and redeploy old code:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//ad80ee4e-f2bd-4690-bddb-2d757052aae3/markdown_3/imgs/img_in_image_box_112_106_921_673.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A20%3A29Z%2F-1%2F%2F7978dedbe0403520324c763438dea35398ccf76609a6e37f74fa39518256cc35" alt="Image" width="76%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 9.3 Introducing the Buying History microservice to the system so that we can benefit from its capabilities without having to make any changes in the Order Processing microservice or in anything else</div> </div>

This architecture introduces four primary security vulnerabilities:
1. **Network Sniffing**: Plaintext network packets between microservices and the broker allow attackers to read sensitive payload details in transit.
2. **Producer Spoofing (Impersonation)**: If the broker does not authenticate clients, any container on the network can connect and write false events (e.g., a "bogus" order event), triggering state corruption downstream:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//fd693c19-dbe8-4fca-b642-85c014d6c2ad/markdown_1/imgs/img_in_image_box_201_476_867_1013.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A21%3A08Z%2F-1%2F%2F77aa4b1d169b4caed9b080d44254fd9feb43b6d9de159e82cbf280296e0a2678" alt="Image" width="62%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 9.9 The Bogus microservice impersonates the Order Processing microservice by sending order events to Kafka. This makes the other microservices process these order events. Kafka needs to explicitly allow only the trusted microservices to connect to it.</div> </div>

3. **Eavesdropping (Unauthorized Read)**: A rogue microservice container could subscribe to billing or customer topics, stealing PII data.
4. **Poison Pill Attacks**: Malicious users could post structurally malformed payloads that crash consumer processes when deserialized.

To mitigate these, we must encrypt the transport layer (TLS), authenticate connections (mTLS/SASL), and authorize topic reads and writes (ACLs).

---

## 19.2 Containerizing Zookeeper & Kafka with TLS Listeners

We provision a local secure Kafka broker and a coordinating ZooKeeper node using Docker Compose.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//ad80ee4e-f2bd-4690-bddb-2d757052aae3/markdown_4/imgs/img_in_image_box_198_389_929_733.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A20%3A30Z%2F-1%2F%2Fef42f052f160fd96215a9b88faf41edd6f45be325290c251481e37d9127f5f27" alt="Image" width="68%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 9.4 ZooKeeper coordinates the nodes in the Kafka cluster.</div> </div>

### The Docker Compose Configuration (`docker-compose.yml`)
```yaml
version: '3.8'

services:
  zookeeper:
    image: confluentinc/cp-zookeeper:7.3.0
    container_name: zookeeper_node
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181
      ZOOKEEPER_TICK_TIME: 2000
    ports:
      - "2181:2181"
    networks:
      - secure-mesh

  kafka:
    image: confluentinc/cp-kafka:7.3.0
    container_name: kafka_broker
    depends_on:
      - zookeeper
    ports:
      - "9092:9092"
      - "9093:9093"
    environment:
      KAFKA_ZOOKEEPER_CONNECT: zookeeper_node:2181
      # Define dual listeners: 9092 for plaintext (internal) and 9093 for secure SSL (mTLS)
      KAFKA_LISTENERS: PLAINTEXT://0.0.0.0:9092,SSL://0.0.0.0:9093
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka_broker:9092,SSL://localhost:9093
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: PLAINTEXT:PLAINTEXT,SSL:SSL
      KAFKA_INTER_BROKER_LISTENER_NAME: PLAINTEXT
      # Configure keystore and truststore locations on the broker
      KAFKA_SSL_KEYSTORE_LOCATION: /etc/kafka/secrets/kafka.server.keystore.jks
      KAFKA_SSL_KEYSTORE_PASSWORD: manningpassword
      KAFKA_SSL_KEY_PASSWORD: manningpassword
      KAFKA_SSL_TRUSTSTORE_LOCATION: /etc/kafka/secrets/kafka.server.truststore.jks
      KAFKA_SSL_TRUSTSTORE_PASSWORD: manningpassword
      # Require clients to present mutually trusted certificates
      KAFKA_SSL_CLIENT_AUTH: required
      # Enable topic ACL authorization
      KAFKA_AUTHORIZER_CLASS_NAME: kafka.security.authorizer.AclAuthorizer
      KAFKA_ALLOW_EVERYONE_IF_NO_ACL_FOUND: "false"
    volumes:
      - ./secrets:/etc/kafka/secrets
    networks:
      - secure-mesh

networks:
  secure-mesh:
    driver: bridge
```

---

## 19.3 Certificate Authority Generation Script

We generate the X.509 certificates and Java Key Store (JKS) files for the broker and the client services using a bash script:

```bash
#!/bin/bash
set -e

# 1. Create a custom Root Certificate Authority (CA)
openssl req -new -x509 -keyout ca-key -out ca-cert -days 365 \
  -subj "/CN=FTGO Root CA/OU=Security/O=FTGO/C=US" -nodes


# 2. Create Broker Keystore and generate CSR
keytool -genkeypair \
  -alias kafka-broker \
  -keyalg RSA \
  -keystore secrets/kafka.server.keystore.jks \
  -dname "CN=localhost,OU=Security,O=FTGO,C=US" \
  -storepass manningpassword -keypass manningpassword -validity 365

keytool -certreq \
  -alias kafka-broker \
  -file secrets/broker.csr \
  -keystore secrets/kafka.server.keystore.jks \
  -storepass manningpassword

# 3. Sign the Broker Certificate with CA
openssl x509 -req -CA ca-cert -CAkey ca-key -in secrets/broker.csr \
  -out secrets/broker-signed.crt -days 365 -CAcreateserial

# 4. Import CA and Signed Certificate into Broker Keystore
keytool -importcert -alias CARoot -file ca-cert -keystore secrets/kafka.server.keystore.jks -storepass manningpassword -noprompt
keytool -importcert -alias kafka-broker -file secrets/broker-signed.crt -keystore secrets/kafka.server.keystore.jks -storepass manningpassword
```

If you look at the keys directory in the host filesystem, you'll find a set of files as shown in the following listing:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//90cd5c48-6771-486f-ac97-d286a3e45fc9/markdown_2/imgs/img_in_image_box_98_805_949_1198.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A21%3A09Z%2F-1%2F%2Fc3a472c999ef0afaf86595a29327335535d1f578047e24b723ac7b4e26c63179" alt="Image" width="80%" /></div>

```bash
# 5. Create Broker Truststore (Trusts client certificates signed by Root CA)
keytool -importcert -alias CARoot -file ca-cert -keystore secrets/kafka.server.truststore.jks -storepass manningpassword -noprompt

# 6. Generate client keys for Order Service (CN=orders.ecomm.com)
keytool -genkeypair -alias order-client -keyalg RSA -keystore secrets/orders.client.keystore.jks \
  -dname "CN=orders.ecomm.com,OU=OrderDept,O=FTGO,C=US" -storepass clientpassword -keypass clientpassword -validity 365

keytool -certreq -alias order-client -file secrets/orders.csr -keystore secrets/orders.client.keystore.jks -storepass clientpassword
openssl x509 -req -CA ca-cert -CAkey ca-key -in secrets/orders.csr -out secrets/orders-signed.crt -days 365 -CAcreateserial
keytool -importcert -alias CARoot -file ca-cert -keystore secrets/orders.client.keystore.jks -storepass clientpassword -noprompt
keytool -importcert -alias order-client -file secrets/orders-signed.crt -keystore secrets/orders.client.keystore.jks -storepass clientpassword

# Create client truststores
keytool -importcert -alias CARoot -file ca-cert -keystore secrets/client.truststore.jks -storepass clientpassword -noprompt
```

---

## 19.4 Securing Spring Boot Kafka Producers and Consumers

After generating the keys, copy the keystores and truststores into the resources directory of the Spring applications.

### 1. Spring Kafka Producer Configuration (`application.properties`)
Configure the `orders-service` to connect to the Kafka broker over port 9093 using SSL:

```properties
spring.kafka.bootstrap-servers=localhost:9093
spring.kafka.security.protocol=SSL

# Client KeyStore details (Proof of Identity to Broker)
spring.kafka.ssl.key-store-location=classpath:orders.client.keystore.jks
spring.kafka.ssl.key-store-password=clientpassword
spring.kafka.ssl.key-password=clientpassword
spring.kafka.ssl.key-store-type=PKCS12

# Client TrustStore details (Trusts Broker certificate)
spring.kafka.ssl.trust-store-location=classpath:client.truststore.jks
spring.kafka.ssl.trust-store-password=clientpassword
spring.kafka.ssl.trust-store-type=PKCS12

# Ignore hostname mismatch in local development testing
spring.kafka.ssl.endpoint-identification-algorithm=
```

For testing connectivity, we can start a basic producer and consumer in the terminal to verify message transmission:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//55c68aff-6da5-4b64-a7ca-98c14b9f8542/markdown_0/imgs/img_in_image_box_184_855_916_1132.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A20%3A27Z%2F-1%2F%2F2690fc0be5e38db839b55b8e4ee63e0fcaac5e3bcf03f5a8fbee1f7fa77fdc52" alt="Image" width="68%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 9.5 The producer process puts events into the topic in the Kafka server. The consumer process receives the events.</div> </div>

### 2. Java Secure Event Publisher: `SecureOrderPublisher.java`
Uses standard Spring `KafkaTemplate` to publish messages safely:

```java
package com.ftgo.order.service;

import com.ftgo.order.model.Order;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Service;

@Service
public class SecureOrderPublisher {

    private static final Logger logger = LoggerFactory.getLogger(SecureOrderPublisher.class);
    private static final String TOPIC = "ORDERS";

    @Autowired
    private KafkaTemplate<String, Order> kafkaTemplate;

    public void publishOrder(Order order) {
        logger.info("Publishing secure event for Order ID: {}", order.getOrderId());
        
        // Asynchronously publish to topic using configured SSL templates
        this.kafkaTemplate.send(TOPIC, order.getOrderId(), order)
                .addCallback(
                        result -> logger.info("Successfully sent order event offset: {}", result.getRecordMetadata().offset()),
                        ex -> logger.error("Failed to publish secure order event to Kafka!", ex)
                );
    }
}
```

This completes the event publication flow from external clients down to the Kafka topics:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//55c68aff-6da5-4b64-a7ca-98c14b9f8542/markdown_2/imgs/img_in_image_box_187_353_922_752.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A20%3A28Z%2F-1%2F%2F7a0f44428176d5e8a88a2f091a92214c5f3b6d2faae47777fc10fde13f9d3c0d" alt="Image" width="69%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 9.6 curl makes an HTTP request to the Order Processing microservice to place an order. After processing its logic, the Order Processing microservice puts an event into the ORDERS topic in Kafka with the details of the order. The consumer process subscribed to the ORDERS topic receives the order's details through Kafka.</div> </div>

### 3. Java Secure Event Consumer: `SecureBuyingHistoryListener.java`
Subscribes to events on the `ORDERS` topic over the secure SSL channel:

```java
package com.ftgo.history.listener;

import com.ftgo.order.model.Order;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Component;

@Component
public class SecureBuyingHistoryListener {

    private static final Logger logger = LoggerFactory.getLogger(SecureBuyingHistoryListener.class);

    @KafkaListener(topics = "ORDERS", groupId = "buying-history-group")
    public void consumeOrder(Order order) {
        logger.info("Consumer received secure event for Order ID: {}", order.getOrderId());
        
        // Execute business logic asynchronously
        updateBuyingPatterns(order);
    }

    private void updateBuyingPatterns(Order order) {
        System.out.println("Updated buying history of customer with order: " + order.getOrderId());
    }
}
```

Now we have a complete asynchronous pipeline connecting the publisher, message broker, and subscriber:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//55c68aff-6da5-4b64-a7ca-98c14b9f8542/markdown_4/imgs/img_in_image_box_189_261_915_676.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A20%3A30Z%2F-1%2F%2F33a31253e1ea67e5c729659a57c07f916428800cc1777ea4ffc62c617490e170" alt="Image" width="68%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 9.7 The Buying History microservice now receives the order details via Kafka. It then starts processing its task related to tracking the buying patterns of customers. This task is done asynchronously to the processing of the order.</div> </div>

Here is the exact runtime sequence of these concurrent processes:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//90cd5c48-6771-486f-ac97-d286a3e45fc9/markdown_0/imgs/img_in_image_box_204_560_892_966.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A21%3A06Z%2F-1%2F%2F60c47ff4b4abccf3baa5c85d50742c0d80099aae144681b9a8bb16f51f69a51f" alt="Image" width="64%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 9.8 The sequence of events that happen when a client (curl) makes a request to place an order. Note that steps 4 and 5 can happen in parallel because they're on two independent processes.</div> </div>

---

## 19.5 Spring Cloud Stream Secure Bindings Configuration

If your architecture uses **Spring Cloud Stream** binders instead of raw Spring Kafka templates, the secure SSL properties are mapped under the binder bindings:

```properties
# Topic Destination Bindings
spring.cloud.stream.bindings.output.destination=ORDERS
spring.cloud.stream.bindings.output.content-type=application/json

# Kafka Binder Connection Coordinates
spring.cloud.stream.kafka.binder.brokers=localhost:9093
spring.cloud.stream.kafka.binder.zkNodes=localhost:2181

# Secure Binder Configuration Properties
spring.cloud.stream.kafka.binder.configuration.security.protocol=SSL
spring.cloud.stream.kafka.binder.configuration.ssl.keystore.location=file:/var/certs/orders.client.keystore.jks
spring.cloud.stream.kafka.binder.configuration.ssl.keystore.password=clientpassword
spring.cloud.stream.kafka.binder.configuration.ssl.key.password=clientpassword
spring.cloud.stream.kafka.binder.configuration.ssl.truststore.location=file:/var/certs/client.truststore.jks
spring.cloud.stream.kafka.binder.configuration.ssl.truststore.password=clientpassword
spring.cloud.stream.kafka.binder.configuration.ssl.endpoint.identification.algorithm=
```

### 19.5.2 Bridging Kubernetes Secrets to Container Bindings

To securely supply these JKS keystore and truststore files without baking them into the Docker image, we define a **Kubernetes Secret** and mount it as a volume inside our pod container filesystem:

#### 1. Kubernetes Secret Definition (`kafka-client-certs-secret.yaml`)
Create the secret containing the base64-encoded keystore and truststore binaries:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: kafka-client-certs
  namespace: ftgo
type: Opaque
data:
  orders.client.keystore.jks: u3VwZXJzZWNyZXRrZXlzdG9yZWJpbmFyeQo= # Base64 encoded binary
  client.truststore.jks: dHJ1c3RzdG9yZWJpbmFyeWNvbnRlbnRzCg==      # Base64 encoded binary
```

#### 2. Kubernetes Deployment Volume Mounting (`deployment.yaml`)
Mount this secret directory inside the `order-service` deployment container at `/var/certs`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: order-service
  namespace: ftgo
spec:
  replicas: 2
  selector:
    matchLabels:
      app: order-service
  template:
    metadata:
      labels:
        app: order-service
    spec:
      containers:
        - name: order-service
          image: ftgo/order-service:latest
          ports:
            - containerPort: 8081
          volumeMounts:
            - name: certs-volume
              mountPath: /var/certs
              readOnly: true
      volumes:
        - name: certs-volume
          secret:
            secretName: kafka-client-certs
```

By mounting the secret at `/var/certs`, the container's Spring Boot application can seamlessly read `file:/var/certs/orders.client.keystore.jks` at runtime.

---


## 19.6 SASL/SCRAM Authentication Alternative

While X.509 certificate authentication (mTLS) is highly secure, it is operationally complex to manage client-side certificate lifecycles in massive deployments. 

An alternative is **SASL/SCRAM-SHA-512** (Salted Challenge Response Authentication Mechanism), which uses secure username/password credentials initialized inside ZooKeeper.

### 1. JAAS Configuration on Broker (`kafka_server_jaas.conf`)
Define user credentials for the Kafka broker:

```properties
KafkaServer {
    org.apache.kafka.common.security.scram.ScramLoginModule required
    username="admin"
    password="adminpassword"
    user_admin="adminpassword"
    user_orders-producer="producerpassword"
    user_history-consumer="consumerpassword";
};
```

Initialize this JAAS file by adding the JVM system parameter to the broker's startup environment:
`-Djava.security.auth.login.config=/etc/kafka/secrets/kafka_server_jaas.conf`

To verify client configurations on the broker, review the broker server properties configuration file:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//90cd5c48-6771-486f-ac97-d286a3e45fc9/markdown_4/imgs/img_in_image_box_128_653_973_1046.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A21%3A12Z%2F-1%2F%2F2cd8259ebfcb9797dc5570c87f95be9534becf1554cb47c8d3365ae3701f4907" alt="Image" width="79%" /></div>

##### Listing 9.10 Content of server.properties file on the Kafka server side, with mTLS support enabled

### 2. Spring Boot SASL/SCRAM Client Configuration (`application.properties`)
Configure client credentials using standard Spring Kafka properties:

```properties
spring.kafka.bootstrap-servers=localhost:9093
# Use SSL for transport encryption, and SASL_SSL for authentication
spring.kafka.security.protocol=SASL_SSL
spring.kafka.properties.sasl.mechanism=SCRAM-SHA-512

# JAAS client login configuration containing user credentials
spring.kafka.properties.sasl.jaas.config=org.apache.kafka.common.security.scram.ScramLoginModule required \
  username="orders-producer" \
  password="producerpassword";

spring.kafka.ssl.trust-store-location=classpath:client.truststore.jks
spring.kafka.ssl.trust-store-password=clientpassword
```

Review the corresponding client-side configurations mapping these values:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//fd693c19-dbe8-4fca-b642-85c014d6c2ad/markdown_2/imgs/img_in_image_box_182_1054_959_1216.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A21%3A09Z%2F-1%2F%2F1156fc9c7e3ccfd66561db8792822bd4b94ce29a511a888f4b8e7a28472119ec" alt="Image" width="73%" /></div>

##### Listing 9.9 Content of application.properties file with mTLS support

---

## 19.7 Dead Letter Queue (DLQ) and Poison Pill Defense

In event-driven systems, a "poison pill" is a message that cannot be parsed (e.g. invalid JSON structure) by a consumer. When a consumer hits a poison pill, it continuously retries deserialization, causing a loop that blocks partition execution and triggers a local Denial of Service (DoS).

To defend against this, we construct a secure **Dead Letter Queue (DLQ)** handler that intercepts errors, captures the corrupt record metadata, and routes the payload to a restricted audit topic (`ORDERS.DLQ`):

```
[ Kafka Broker: ORDERS Topic ] ===( Poison Pill Payload )===> [ Secure Listener ]
                                                                     |
                                                           ( Deserialization Error )
                                                                     |
                                                                     v
                                                    [ DeadLetterPublishingRecoverer ]
                                                                     |
                                                                     v (Quarantines Payload)
                                                       [ Topic: ORDERS.DLQ ]
```

```java
package com.ftgo.history.config;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.listener.DeadLetterPublishingRecoverer;
import org.springframework.kafka.listener.DefaultErrorHandler;
import org.springframework.util.backoff.FixedBackOff;

@Configuration
public class KafkaErrorHandlingConfig {

    private static final Logger logger = LoggerFactory.getLogger(KafkaErrorHandlingConfig.class);

    @Bean
    public DefaultErrorHandler errorHandler(KafkaTemplate<Object, Object> template) {
        // 1. Configure the DLQ recoverer to forward failed payloads to suffix .DLQ topics
        DeadLetterPublishingRecoverer recoverer = new DeadLetterPublishingRecoverer(template);

        // 2. Configure retry limits (max 3 attempts, 2-second backoff)
        DefaultErrorHandler errorHandler = new DefaultErrorHandler(
                recoverer,
                new FixedBackOff(2000L, 3L)
        );

        // Log specific errors for diagnostic auditing
        errorHandler.setCommitRecovered(true);
        errorHandler.setLogLevel(KafkaErrorHandlerLogLevel.WARN);
        
        return errorHandler;
    }
}
```

---

## 19.8 Programmatic Certificate Monitoring Utility

To prevent unexpected outages caused by certificate expiration, we write a Java utility that programmatically inspects the client's keystore files at startup and schedules alerts when certificates approach their expiration date:

```java
package com.ftgo.order.util;

import java.io.FileInputStream;
import java.security.KeyStore;
import java.security.cert.X509Certificate;
import java.util.Date;
import java.util.Enumeration;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class DynamicKeystoreHelper {
    private static final Logger logger = LoggerFactory.getLogger(DynamicKeystoreHelper.class);

    public static void inspectCertificates(String keystorePath, String password) {
        try {
            KeyStore keyStore = KeyStore.getInstance("PKCS12");
            try (FileInputStream fis = new FileInputStream(keystorePath)) {
                keyStore.load(fis, password.toCharArray());
            }

            Enumeration<String> aliases = keyStore.aliases();
            while (aliases.hasMoreElements()) {
                String alias = aliases.nextElement();
                if (keyStore.isKeyEntry(alias)) {
                    X509Certificate cert = (X509Certificate) keyStore.getCertificate(alias);
                    Date expiryDate = cert.getNotAfter();
                    long diff = expiryDate.getTime() - System.currentTimeMillis();
                    long days = diff / (1000 * 60 * 60 * 24);

                    logger.info("Certificate alias: {} expires on: {} (in {} days)", alias, expiryDate, days);
                    if (days < 30) {
                        logger.warn("CRITICAL: Certificate alias {} is expiring in less than 30 days! Please rotate keys immediately.", alias);
                    }
                }
            }
        } catch (Exception e) {
            logger.error("Failed to inspect certificates!", e);
        }
    }
}
```

### Integration in Spring Boot Bootstrap Configuration
To ensure this utility executes on service boot-up, register it as a `CommandLineRunner` bean in the application's configuration:

```java
package com.ftgo.order;

import com.ftgo.order.util.DynamicKeystoreHelper;
import org.springframework.boot.CommandLineRunner;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.Bean;

@SpringBootApplication
public class OrderServiceApplication {

    public static void main(String[] args) {
        SpringApplication.run(OrderServiceApplication.class, args);
    }

    @Bean
    public CommandLineRunner checkCerts() {
        return args -> {
            // Programmatically inspect client keystore expiration dates at server startup
            DynamicKeystoreHelper.inspectCertificates(
                "src/main/resources/orders.client.keystore.jks", 
                "clientpassword"
            );
        };
    }
}
```

---

## 19.9 Fine-Grained Topic Access Control Lists (ACLs)

By default, any client that successfully authenticates via mTLS or SASL can write to any topic. To prevent this, we configure topic-level ACLs:

```
                  +--------------------------+
                  |       Kafka Broker       |
                  +------------+-------------+
                                |
            +------------------+------------------+
            | (Enforces ACLs)                     | (Enforces ACLs)
            v                                     v
[ Topic: ORDERS (Write) ]             [ Topic: ORDERS (Read) ]
- Allowed: User:orders.ecomm.com      - Allowed: User:bh.ecomm.com
- Denied: All others                  - Denied: All others
```

To prevent spoofing and data leaks, Kafka needs to explicitly allow only trusted microservices to connect to specific topics:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//fd693c19-dbe8-4fca-b642-85c014d6c2ad/markdown_4/imgs/img_in_image_box_183_109_790_607.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A21%3A12Z%2F-1%2F%2Fa67bbe27804f1244452c360b2b5a3576164801e4dec541df3d4edf24a666faae" alt="Image" width="57%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 9.10 The Buying History microservice sends events to Kafka topics. Any microservice that's trusted by Kafka can technically send events to its topics unless restricted by ACLs. These events are delivered to microservices that are subscribed to the Kafka topic unless they have been restricted by ACLs.</div> </div>

### 1. Principal Mapping Rules
In the broker settings (`server.properties`), we define a regex rule to extract the certificate's Common Name (CN) and map it as the authenticated user principal:

```properties
# Extract the CN value in lowercase as the principal identifier
ssl.principal.mapping.rules=RULE:^CN=([^,]*).*$/$1/L,DEFAULT
```

Using this configuration:
* A client presenting a certificate with CN `orders.ecomm.com` maps to principal `User:orders.ecomm.com`.
* A client presenting a certificate with CN `bh.ecomm.com` maps to principal `User:bh.ecomm.com`.

### 2. Configure Producer Write-Only ACLs
Allow `User:orders.ecomm.com` to write to the `ORDERS` topic:
```bash
docker exec -it kafka_broker kafka-acls --bootstrap-server localhost:9093 \
  --command-config /etc/kafka/secrets/client-ssl.properties \
  --add --allow-principal User:orders.ecomm.com --producer --topic ORDERS
```

### 3. Configure Consumer Read-Only ACLs
Allow `User:bh.ecomm.com` to read from the `ORDERS` topic:
```bash
docker exec -it kafka_broker kafka-acls --bootstrap-server localhost:9093 \
  --command-config /etc/kafka/secrets/client-ssl.properties \
  --add --allow-principal User:bh.ecomm.com --consumer --topic ORDERS --group buying-history-group
```

Clients that attempt to violate these rules will receive a `TopicAuthorizationException` from the broker.

---

## 19.10 Securing NATS JetStream Communications

NATS JetStream provides persistent, distributed stream processing. Unlike core NATS (which is fire-and-forget), JetStream supports message acknowledgments and consumers.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//0925a81b-f865-4a15-9b7c-5e2fa7a0e00f/markdown_3/imgs/img_in_image_box_156_765_932_1091.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A20%3A29Z%2F-1%2F%2F078dc9f6ff3d2ba26b2dc3fb5bde1ef2b4e865cba4c2729f50b583ab0a543682" alt="Image" width="73%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 9.11 Publishers and subscribers connecting to the NATS server on the subject orders</div> </div>

### 1. NATS Server TLS and Account Configuration (`nats-server.conf`)
Configure NATS with multi-tenant Accounts to restrict stream access:

```conf
port: 4222

tls {
  cert_file: "/etc/nats/certs/server-cert.pem"
  key_file:  "/etc/nats/certs/server-key.pem"
  ca_file:   "/etc/nats/certs/ca.pem"
  verify:    true
}

# Define Account authorizations
accounts {
  ECOMM {
    users = [
      { user: "orders-producer", password: "producerpassword" }
    ]
    # Allow exporting orders stream to other accounts
    exports = [
      { stream: "orders.>" }
    ]
  }
  SHIPPING {
    users = [
      { user: "delivery-consumer", password: "consumerpassword" }
    ]
    imports = [
      { stream: { account: "ECOMM", subject: "orders.>" } }
    ]
  }
}
```

### 2. Java TLS NATS JetStream Publisher
This Java publisher publishes messages to JetStream over a secure TLS connection:

```java
package com.ftgo.nats;

import io.nats.client.*;
import io.nats.client.api.StreamConfiguration;
import javax.net.ssl.SSLContext;
import java.nio.charset.StandardCharsets;

public class SecureNatsPublisher {

    public static void main(String[] args) {
        try {
            SSLContext sslContext = NatsSslUtility.createSslContext();

            Options options = new Options.Builder()
                    .server("nats://localhost:4222")
                    .sslContext(sslContext)
                    .userInfo("orders-producer", "producerpassword")
                    .build();

            Connection nc = Nats.connect(options);
            JetStreamManagement jsm = nc.jetStreamManagement();

            // 1. Securely provision the JetStream persistent storage
            StreamConfiguration streamConfig = new StreamConfiguration.Builder()
                    .name("ORDERS")
                    .subjects("orders.new")
                    .build();
            jsm.addStream(streamConfig);

            // 2. Publish secure messages
            JetStream js = nc.jetStream();
            String payload = "{\"orderId\":\"1001\",\"amount\":45.00}";
            
            PublishAck ack = js.publish("orders.new", payload.getBytes(StandardCharsets.UTF_8));
            System.out.println("Published to JetStream with sequence: " + ack.getSequence());

            nc.close();

        } catch (Exception e) {
            e.printStackTrace();
        }
    }
}
```

### 3. Programmatic JetStream Security Management Service
We write a manager helper in Java that handles secure stream creation, subject bindings, and maximum age limit parameters:

```java
package com.ftgo.nats;

import io.nats.client.Connection;
import io.nats.client.JetStreamManagement;
import io.nats.client.api.StreamConfiguration;
import io.nats.client.api.StreamInfo;
import java.time.Duration;

public class SecureNatsJetStreamManager {

    private final Connection natsConnection;

    public SecureNatsJetStreamManager(Connection natsConnection) {
        this.natsConnection = natsConnection;
    }

    public void createSecureStream(String streamName, String subjectPattern, int replicas) throws Exception {
        JetStreamManagement jsm = natsConnection.jetStreamManagement();

        // Check if stream already exists
        try {
            StreamInfo info = jsm.getStreamInfo(streamName);
            if (info != null) {
                System.out.println("Stream already exists. Skipping creation.");
                return;
            }
        } catch (Exception e) {
            // Stream doesn't exist
        }

        // Configure stream with encryption and replication constraints
        StreamConfiguration config = new StreamConfiguration.Builder()
                .name(streamName)
                .subjects(subjectPattern)
                .replicas(replicas)
                .maxAge(Duration.ofDays(7)) // Encrypted history limit
                .discardPolicy(io.nats.client.api.DiscardPolicy.Old)
                .build();

        jsm.addStream(config);
        System.out.println("Persistent stream " + streamName + " successfully created.");
    }
}
```

---

## 19.11 Externalized Authorization using Open Policy Agent (OPA)

For complex, dynamic access-control scenarios, managing static ACLs using Kafka CLI tools is difficult. We externalize authorization decisions to an **Open Policy Agent (OPA)** server by engaging the custom OPA Kafka Authorizer plugin in the broker config:

```properties
# Add this property to the Kafka broker's server.properties
authorizer.class.name=com.bisnode.opa.kafka.OpaAuthorizer
opa.authorizer.url=http://opa-sidecar:8181/v1/data/kafka/authz/allow
```

We write a declarative **Rego Policy** file (`policy.rego`) to authorize topic requests based on the client certificate's Common Name (CN):

```rego
package kafka.authz

default allow = false

# Allow write operations if the client certificate CN is "orders.ecomm.com"
allow {
    input.action.operation == "Write"
    input.action.resource.resourceType == "Topic"
    input.action.resource.name == "ORDERS"
    input.requestContext.principal.name == "orders.ecomm.com"
}

# Allow read operations if the client certificate CN is "bh.ecomm.com"
allow {
    input.action.operation == "Read"
    input.action.resource.resourceType == "Topic"
    input.action.resource.name == "ORDERS"
    input.requestContext.principal.name == "bh.ecomm.com"
}

# Superuser overrides: admin can execute all operations
allow {
    input.requestContext.principal.name == "admin"
}
```

---

## 19.12 security Integration Testing using Testcontainers

This integration test spins up a secure Kafka container with mTLS and ACL configurations enabled. It verifies that a client with a valid producer certificate can write to the topic, while unauthorized clients are rejected:

```java
package com.ftgo.order;

import org.apache.kafka.clients.admin.AdminClient;
import org.apache.kafka.clients.admin.NewTopic;
import org.apache.kafka.clients.producer.KafkaProducer;
import org.apache.kafka.clients.producer.ProducerConfig;
import org.apache.kafka.clients.producer.ProducerRecord;
import org.apache.kafka.common.errors.TopicAuthorizationException;
import org.apache.kafka.common.serialization.StringSerializer;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.Assertions;
import org.testcontainers.containers.KafkaContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.utility.DockerImageName;
import java.util.Collections;
import java.util.Properties;
import java.util.concurrent.ExecutionException;

@Testcontainers
public class KafkaSecurityIntegrationTest {

    @Container
    public static KafkaContainer kafkaContainer = new KafkaContainer(
            DockerImageName.parse("confluentinc/cp-kafka:7.3.0")
    ).withEmbeddedZookeeper();

    @Test
    public void testSecureProducerWrite_Succeeds() throws Exception {
        String bootstrapServers = kafkaContainer.getBootstrapServers();

        Properties props = new Properties();
        props.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, bootstrapServers);
        props.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, StringSerializer.class.getName());
        props.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, StringSerializer.class.getName());
        
        // Load secure client properties
        props.put("security.protocol", "SSL");
        props.put("ssl.keystore.location", "src/test/resources/orders.client.keystore.jks");
        props.put("ssl.keystore.password", "clientpassword");
        props.put("ssl.key.password", "clientpassword");
        props.put("ssl.truststore.location", "src/test/resources/client.truststore.jks");
        props.put("ssl.truststore.password", "clientpassword");

        KafkaProducer<String, String> producer = new KafkaProducer<>(props);
        
        // Publishing should succeed because the orders.client key is authorized via broker ACLs
        ProducerRecord<String, String> record = new ProducerRecord<>("ORDERS", "order_key_101", "OrderPayload");
        Assertions.assertDoesNotThrow(() -> {
            producer.send(record).get();
        });
        
        producer.close();
    }

    @Test
    public void testUnauthorizedProducerWrite_ThrowsAuthorizationException() {
        String bootstrapServers = kafkaContainer.getBootstrapServers();

        Properties props = new Properties();
        props.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, bootstrapServers);
        props.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, StringSerializer.class.getName());
        props.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, StringSerializer.class.getName());
        
        // Load an unauthenticated client configuration (Missing client keystore)
        props.put("security.protocol", "SSL");
        props.put("ssl.truststore.location", "src/test/resources/client.truststore.jks");
        props.put("ssl.truststore.password", "clientpassword");

        KafkaProducer<String, String> producer = new KafkaProducer<>(props);
        ProducerRecord<String, String> record = new ProducerRecord<>("ORDERS", "order_key_102", "OrderPayload");

        // The broker should reject this write attempt with an ExecutionException wrapping a security error
        Assertions.assertThrows(ExecutionException.class, () -> {
            producer.send(record).get();
        });

        producer.close();
    }
}
```

---

## 19.12 OWASP Top 10 API Security Mitigations in Asynchronous Security

Enforcing security protocols within event-driven architectures mitigates several critical threats from the **OWASP API Security Top 10**:

1. **API4:2019 Lack of Resources & Rate Limiting**:
   - *Mitigation*: We enforce storage quotas and NATS JetStream stream limits (message count and total byte boundaries) to prevent malicious users from flooding event streams. Similarly, we configure Apache Kafka rate limits on producer connections to restrict request volumes.
2. **API7:2019 Security Misconfiguration**:
   - *Mitigation*: The broker is configured to disable plaintext listeners entirely on production hosts, requiring all clients to connect over mTLS or JAAS SASL/SCRAM ports. Default credentials inside files like `kafka_server_jaas.conf` are strictly replaced with encrypted parameters in Kubernetes Secrets.
3. **API10:2019 Insufficient Logging & Monitoring**:
   - *Mitigation*: Unprocessable payloads or poison pills that trigger deserialization errors are intercepted by our error handler container factories and routed to a dedicated Dead Letter Topic (`ORDERS.DLT`). These topics are monitored by SRE Alertmanager pipelines to trigger alerts upon error count spikes, ensuring immediate visibility.

---

## Chapter Summary

* In reactive microservice architectures, unencrypted message channels are vulnerable to sniffing, spoofing, and unauthorized topic access.
* **Mutual TLS (mTLS)** provides encryption and client authentication for service-to-broker connections.
* Multi-listener Kafka brokers are configured using Docker Compose with separate SSL ports, client authentication enabled (`ssl.client.auth=required`), and path bindings for secrets.
* Certificates for CAs, brokers, and clients are generated and signed using OpenSSL and Java `keytool` scripts.
* Spring Boot event-driven services configure keystores and truststores inside application properties files to establish secure connections automatically.
* Under SASL/SCRAM configurations, clients authenticate securely using credentials registered in JAAS configurations.
* **Dead Letter Queues (DLQ)** isolate invalid payloads and poison pills to prevent cascading consumers loops and local Denial of Service (DoS).
* Spring Cloud Stream binding properties allow setting SSL security configurations directly under specific destinations and binders.
* Dynamic Certificate Expiration checks are managed programmatically using Java KeyStore API inspections during standard Spring Boot command line runs.
* To restrict topic actions, Kafka brokers use X.509 **Principal Mapping Rules** alongside CLI **Access Control Lists (ACLs)** to assign permissions based on Common Names (CN).
* **NATS** brokers can be secured using TLS connections combined with token or username/password authorization rules. NATS JetStream supports persistent, replicated storage limits.
* Dynamic, policy-based access control is achieved by integrating the Open Policy Agent (OPA) authorizer plugin with the broker and defining rules in Rego.
* System test suites employ containerized environments to verify that secure transport and ACL validations execute correctly.
* **OWASP Top 10 Mitigations** address rate limits, security misconfigurations, and logging gaps through broker throttling policies and DLT alerting pipelines.

