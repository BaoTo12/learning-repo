# Chapter 4: Distributed Configuration Management

Mismanaged application configuration is a fertile breeding ground for difficult-to-detect bugs and unplanned outages. In a monolithic application, configuration parameters are typically bundled directly inside the deployable archive. However, in a distributed microservices architecture, this approach fails. Separating configuration information from the compiled code creates an external asset that must be version-controlled, audited, and secured.

This chapter covers the conceptual and technical implementation of distributed configuration management. We will explore the core architectural design principles of external configuration. We will walk through building a **Spring Cloud Configuration Server** from scratch and configure it to retrieve application properties from the local filesystem, Git repositories, and HashiCorp Vault. Finally, we will configure a microservice client to consume these properties, implement dynamic configuration updates using Spring Boot Actuator and `@RefreshScope`, and secure sensitive parameters using symmetric key encryption.

---

## Learning Objectives

By the end of this chapter, you will be able to:
1. Explain the four core principles of configuration management: segregate, abstract, centralize, and harden.
2. Detail the bootstrapping lifecycle of a microservice and explain the role of `bootstrap.yml` in reading configuration server credentials.
3. Build a standalone **Spring Cloud Configuration Server** using Maven, `@EnableConfigServer`, and properties configurations.
4. Configure the Config Server to serve properties from a **filesystem-based** native profile.
5. Integrate the Config Server with a **Git-based** version-controlled repository.
6. Configure the Config Server to consume secrets from **HashiCorp Vault**.
7. Implement dynamic configuration reloading on a client microservice using `@RefreshScope` and the Actuator `/actuator/refresh` endpoint.
8. Secure sensitive credentials inside property files using **symmetric encryption** and the `{cipher}` prefix.

---

## 4.1 The Configuration Management Architecture

Externalizing configurations isolates environment-specific settings (database URIs, service discovery ports, security certificates) from the compiled application code. This isolation is driven by four core design principles:

1. **Segregate**: Separate the configuration data completely from the compiled service package. The application artifact (e.g., JAR file) must compile once and run unmodified in development, staging, and production environments.
2. **Abstract**: Abstract access to the properties behind a unified REST API endpoint. The client microservice does not need to know where the properties are physically stored (filesystem, database, or Vault); it queries a unified configuration service.
3. **Centralize**: Manage all environment parameters in a single, version-controlled repository. This allows operations to track, audit, and roll back configuration changes.
4. **Harden**: Encrypt sensitive data (like database passwords and API keys) at rest and decrypt them securely in transit.

---

### The Microservice Bootstrapping Lifecycle
The loading of configuration properties occurs at the very beginning of a microservice's lifecycle:

![Figure 4.1: Microservice lifecycle phases](https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//b5b1561f-a310-4c8b-82f3-922ecc42f846/markdown_1/imgs/img_in_image_box_147_821_932_1155.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T09%3A47%3A36Z%2F-1%2F%2F9f785491713026a7b2ac48d2f02cd158f6401a54a0fb7bb306f50d1d2a254c4d)
*Figure 4.1: The bootstrapping phase is the first step when a microservice boots.*

When a container starts up, the bootstrap context initializes:

![Figure 4.2: Configuration bootstrapping process](https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//b5b1561f-a310-4c8b-82f3-922ecc42f846/markdown_2/imgs/img_in_image_box_152_226_937_908.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T09%3A47%3A37Z%2F-1%2F%2F3a5d10efb7aa720ae9ce4940cfc809ddcc40e7680b631b923da3c7e8e15e94cf)
*Figure 4.2: Conceptual flow of configuration bootstrapping, storage, pipeline, and dynamic updates.*

1. **Local Setup**: The service starts and loads the local `bootstrap.yml` configuration. This file contains the address of the Config Server and any necessary credentials.
2. **Config Request**: The service sends an HTTP request to the Config Server, passing its application name (`spring.application.name`) and active profile (`spring.profiles.active`).
3. **Repository Fetch**: The Config Server reads properties from its configured backend repository (filesystem, Git, or HashiCorp Vault).
4. **Environment Population**: The Config Server returns the properties as a JSON payload, and the client service injects them into its Spring `Environment` context.
5. **Main Context Boot**: The main application context starts up, using the newly loaded environment properties to connect to the database, bind server ports, and configure beans.

---

### Implementation Choices

Multiple open-source projects can serve as a configuration key-value backend:

| Project Name | Description | Characteristics |
| :--- | :--- | :--- |
| **etcd** | A distributed, consistent key-value store written in Go. Uses the Raft consensus protocol. | Very fast, highly scalable, and container-friendly. Requires custom integration logic for Spring Boot. |
| **Eureka** | A service registry developed by Netflix. Can store minor configuration parameters. | Primarily designed for service discovery, not as a general-purpose configuration store. |
| **Consul** | A service mesh and configuration system by HashiCorp. Uses a Raft-based consensus protocol. | Provides native key-value storage and DNS-based service discovery. |
| **ZooKeeper** | A centralized service for maintaining configuration information and hierarchical naming. | Battle-tested but complex to configure and manage. |
| **Spring Cloud Config Server** | A REST-based configuration server built on top of Spring Boot. | Integrates tightly with Spring Boot applications. Supports filesystem, Git, and HashiCorp Vault backends out of the box. |

In this course, we use **Spring Cloud Config Server** due to its seamless integration with the Spring ecosystem and its support for multiple swappable backends.

---

## 4.2 Building the Spring Cloud Configuration Server

We will bootstrap the Config Server using Spring Initializr, specifying:
* **Group**: `com.optimagrowth`
* **Artifact**: `configserver`
* **Dependencies**: `Config Server` and `Spring Boot Actuator`

### The Maven POM Configuration
Create the following file in `configserver/pom.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <parent>
        <groupId>com.optimagrowth</groupId>
        <artifactId>parent-pom</artifactId>
        <version>1.0.0-SNAPSHOT</version>
        <relativePath>../pom.xml</relativePath>
    </parent>

    <artifactId>config-server</artifactId>
    <name>Configuration Server</name>

    <dependencies>
        <dependency>
            <groupId>org.springframework.cloud</groupId>
            <artifactId>spring-cloud-config-server</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-actuator</artifactId>
        </dependency>
    </dependencies>

    <build>
        <plugins>
            <plugin>
                <groupId>org.springframework.boot</groupId>
                <artifactId>spring-boot-maven-plugin</artifactId>
            </plugin>
        </plugins>
    </build>
</project>
```

---

### The Configuration Server Application Class
Create the bootstrap class inside `com.optimagrowth.configserver.ConfigurationServerApplication.java` and annotate it with `@EnableConfigServer`:

```java
package com.optimagrowth.configserver;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.cloud.config.server.EnableConfigServer;

@SpringBootApplication
@EnableConfigServer // Activates the Spring Cloud Config Server features
public class ConfigurationServerApplication {
    public static void main(String[] args) {
        SpringApplication.run(ConfigurationServerApplication.class, args);
    }
}
```

---

### The Application Properties
Configure the server port and application name in `configserver/src/main/resources/application.yml`:

```yaml
server:
  port: 8071 # Config server binds to default port 8071

spring:
  application:
    name: config-server
```

---

## 4.3 Swappable Configuration Backends

Spring Cloud Config Server supports multiple backend storage profiles. We select the active backend by defining the `spring.profiles.active` property.

### 1. Filesystem-Based native Profile
For local development, you can store property files in a local directory on your filesystem:

Configure the backend path in `configserver/src/main/resources/application.yml`:

```yaml
spring:
  profiles:
    active: native # Activates the local filesystem profile
  cloud:
    config:
      server:
        native:
          # Search location path on the local disk
          search-locations: file:///C:/Users/Admin/Desktop/projects/learning-repo/courses/java/java-micro-course/config-repo
```

Inside the search location, create environment property files named after the client service (e.g., `order-service.yml`, `order-service-dev.yml`):

```yaml
# config-repo/order-service-dev.yml
server:
  port: 8081
example:
  property: "Value loaded from local native filesystem profile!"
```

---

### 2. Version-Controlled git Profile
In staging and production, configurations should be stored in a private Git repository to track and audit changes.

Configure the Git repository URI in `configserver/src/main/resources/application.yml`:

```yaml
spring:
  profiles:
    active: git # Activates the Git backend profile
  cloud:
    config:
      server:
        git:
          uri: https://github.com/BaoTo12/microservices-config-repo.git
          search-paths: order-service,kitchen-service
          clone-on-start: true
          # For private repositories, configure access credentials:
          # username: git_username
          # password: git_personal_access_token
```

When a client requests configuration, the Config Server pulls the latest changes from the Git repository, caches them locally, and serves them to the client.

---

### 3. Secure HashiCorp Vault Backend
For sensitive production credentials (e.g., database passwords, encryption keys), use **HashiCorp Vault** as a secure secrets manager.

Configure the Vault integration in `configserver/src/main/resources/application.yml`:

```yaml
spring:
  profiles:
    active: vault # Activates the Vault backend profile
  cloud:
    config:
      server:
        vault:
          host: 127.0.0.1
          port: 8200
          scheme: http
          backend: secret # Key-value engine mount path
          profile-separator: '/'
          default-key: application
```

To authenticate with Vault, the client service must send a valid Vault token (`X-Config-Token` HTTP header) with its bootstrap request, which the Config Server delegates to Vault to authorize access to the secrets.

---

## 4.4 Spring Cloud Config Client Integration

Now, we will configure the `order-service` to retrieve its configurations from the Config Server during bootstrap.

### 1. Add Client Maven Dependency
Add the Spring Cloud Config client starter to `order-service/pom.xml`:

```xml
<dependency>
    <groupId>org.springframework.cloud</groupId>
    <artifactId>spring-cloud-starter-config</artifactId>
</dependency>
```

---

### 2. Configure Client Bootstrap: `bootstrap.yml`
Create a `bootstrap.yml` file in `order-service/src/main/resources/bootstrap.yml`. This file is loaded before `application.yml` during the bootstrap phase:

```yaml
spring:
  application:
    name: order-service # Must match the property file name in the config repository
  profiles:
    active: dev
  cloud:
    config:
      # Address of the Config Server
      uri: http://localhost:8071
      fail-fast: true # Fail startup if Config Server is unreachable
      max-attempts: 6 # Retry connections up to 6 times
      initial-interval: 2000 # Wait 2 seconds before first retry
```

When the client starts, it fetches `order-service-dev.yml` from the Config Server at `http://localhost:8071` and injects the properties into the Spring context.

---

## 4.5 Dynamic Configuration Reloading

By default, Spring Boot beans read configuration properties once at startup. If a property is modified in the Git repository, the running service will not see the change until it is restarted.

To reload configurations dynamically without restarting the application, we use Spring Boot Actuator and the `@RefreshScope` annotation.

### 1. Add Actuator Starter
Add the Actuator dependency to `order-service/pom.xml`:

```xml
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-actuator</artifactId>
</dependency>
```

---

### 2. Enable Actuator Refresh Endpoint
By default, sensitive Actuator endpoints are hidden. Expose the `/refresh` endpoint in `order-service/src/main/resources/application.yml`:

```yaml
management:
  endpoints:
    web:
      exposure:
        include: refresh,health,info # Exposes the refresh endpoint
```

---

### 3. Annotate Beans with `@RefreshScope`
Add the `@RefreshScope` annotation to any Spring bean that reads dynamic configuration properties (e.g., using `@Value` or `@ConfigurationProperties`):

```java
package com.ftgo.order.controller;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.cloud.context.config.annotation.RefreshScope;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping(value = "v1/properties")
@RefreshScope // Enables dynamic configuration reloading in memory for this bean
public class PropertyController {

    @Value("${example.property}")
    private String exampleProperty;

    @GetMapping
    public ResponseEntity<String> getProperty() {
        return ResponseEntity.ok(exampleProperty);
    }
}
```

---

### 4. Triggering the Reload Workflow
When a configuration property changes, apply the update without restarting the microservice:

1. **Modify the configuration**: Update `example.property` in the Git repository:
   ```yaml
   # order-service-dev.yml
   example:
     property: "Updated dynamic config value!"
   ```
2. **Commit and push** the changes to the Git repository.
3. **Trigger Actuator refresh**: Send an empty HTTP POST request to the client service's refresh endpoint (port `8081`):
   ```bash
   curl -X POST http://localhost:8081/actuator/refresh
   ```
4. **Verify reload**: The response returns a JSON list of updated keys:
   ```json
   ["example.property"]
   ```
   Querying the client's `/v1/properties` endpoint now returns the updated value.

---

## 4.6 Securing Configuration Properties with Symmetric Encryption

Property files must not store plaintext passwords or secrets. Spring Cloud Config Server provides built-in encryption and decryption capabilities to secure sensitive properties.

```
       Developer                  Config Server               PostgreSQL Database
           |                            |                              |
           |-- {cipher}encryptedPass -->|                              |
           |                            |-- (Decrypts using ENCRYPT_KEY)|
           |                            |                              |
           |                            |-- plaintext password ------->|
           |                            |                              |
```

### 1. Configure the Encryption Key
To enable symmetric encryption, configure the shared encryption key. Set the `ENCRYPT_KEY` environment variable before starting the Config Server:

* On Windows Powershell:
  ```powershell
  $env:ENCRYPT_KEY="FTGOSecretKeyLongString"
  ```
* On Linux/macOS:
  ```bash
  export ENCRYPT_KEY="FTGOSecretKeyLongString"
  ```

---

### 2. Encrypting Plaintext Secrets
With the encryption key configured, the Config Server exposes `/encrypt` and `/decrypt` endpoints to process text.

To encrypt a plaintext password:
```bash
curl -X POST -d "dev_postgres_password" http://localhost:8071/encrypt
```

The server returns the encrypted ciphertext string:
```
c2d0f39e8d4a7f39b1a0e8c7d6f5e4d3c2b1a0e8d9c8b7a6...
```

---

### 3. Storing Encrypted Properties
Store the encrypted string in the configuration file, prefixing it with `{cipher}` to tell the Config Server to decrypt the value before serving it to the client:

```yaml
# config-repo/order-service-dev.yml
spring:
  datasource:
    password: '{cipher}c2d0f39e8d4a7f39b1a0e8c7d6f5e4d3c2b1a0e8d9c8b7a6...'
```

When the client service starts and requests its configurations, the Config Server detects the `{cipher}` prefix, decrypts the password using `ENCRYPT_KEY`, and sends the plaintext password to the client over HTTPS. The client microservice does not need to know the decryption key or perform decryption logic.

---

## 4.6.4 The Bootstrapping Context Lifecycle & Parent Contexts

When a Spring Boot application starts up with the Spring Cloud Config client on its classpath, it instantiates an isolated parent context called the **Bootstrap Application Context**. This context is responsible for locating external configurations before the main application context starts.

```
+-----------------------------------------------------------+
|               Bootstrap Application Context               |
|  - Loads bootstrap.yml                                    |
|  - Locates Config Server endpoints                        |
|  - Fetches properties and instantiates property sources    |
+-----------------------------------------------------------+
                              |
                              v (Propagates environment properties)
+-----------------------------------------------------------+
|                 Main Application Context                  |
|  - Loads application.yml                                  |
|  - Auto-configures database connections, JPA, Web server |
|  - Instantiates application controller beans              |
+-----------------------------------------------------------+
```

### Implementing a Custom Programmatic Property Source Locator
Under the hood, Spring Cloud Config uses the `PropertySourceLocator` interface to fetch configurations. If you need to integrate a proprietary configuration source (e.g. an internal network catalog), you can implement a custom locator bean:

```java
package com.ftgo.order.config;

import org.springframework.cloud.bootstrap.config.PropertySourceLocator;
import org.springframework.core.env.Environment;
import org.springframework.core.env.MapPropertySource;
import org.springframework.core.env.PropertySource;
import org.springframework.stereotype.Component;

import java.util.HashMap;
import java.util.Map;

@Component
public class CustomPropertySourceLocator implements PropertySourceLocator {

    @Override
    public PropertySource<?> locate(Environment environment) {
        Map<String, Object> properties = new HashMap<>();
        
        // Fetch properties programmatically from a secure company API
        properties.put("custom.ftgo.gateway-url", "https://api.ftgo.com/v1");
        properties.put("custom.ftgo.partner-timeout-ms", 5000);

        return new MapPropertySource("customCompanyProperties", properties);
    }
}
```

By packaging this class inside the bootstrap classpath (registered in `META-INF/spring.factories` under `org.springframework.cloud.bootstrap.BootstrapConfiguration`), Spring Boot automatically calls it during the bootstrap context phase, merging its keys into the application's active `Environment`.

---

## 4.6.5 Config Server REST Endpoints Mapping Reference

Spring Cloud Config Server exposes property files via a RESTful API. The following table maps URL resource paths to the corresponding property files in the Git or native search locations:

| Endpoint Resource Path | Description | Translated Git Filename Mappings |
| :--- | :--- | :--- |
| `/{application}/{profile}` | Returns a structural JSON object containing raw source lists. | `{application}.yml`, `{application}-{profile}.yml` |
| `/{application}/{profile}/{label}` | Returns properties matching a specific Git branch or commit hash (`label`). | Reads files from target branch `{label}`. |
| `/{application}-{profile}.yml` | Returns properties formatted as a raw, single YAML block. | Flattens properties into valid YAML output. |
| `/{application}-{profile}.properties` | Returns properties formatted as a raw, flat properties list. | Flattens properties into flat key=value output. |

For example, a client service executing `curl http://localhost:8071/order-service/dev` receives a JSON document containing a list of property sources, sorted by priority (specific environment overrides general configurations):

```json
{
  "name": "order-service",
  "profiles": ["dev"],
  "label": null,
  "version": "a1b2c3d4",
  "propertySources": [
    {
      "name": "https://github.com/BaoTo12/config-repo/order-service-dev.yml",
      "source": {
        "example.property": "Updated dynamic config value!"
      }
    },
    {
      "name": "https://github.com/BaoTo12/config-repo/order-service.yml",
      "source": {
        "server.port": 8081
      }
    }
  ]
}
```

---

## 4.6.6 Configuring Vault AppRole Authentication

In production environments, using a static root token for Vault authentication is a security violation. Instead, the Config Server must authenticate using Vault's **AppRole Authentication**, which uses a role ID and a secret ID to acquire a temporary client token:

### 1. Enable AppRole Authentication in Vault
```bash
# Enable AppRole backend
docker exec -it ftgo_vault vault auth enable approle

# Create a policy mapping read permissions on the secrets path
docker exec -it ftgo_vault vault policy write config-server-policy - <<EOF
path "secret/data/*" {
  capabilities = ["read"]
}
EOF

# Create a role binding the policy
docker exec -it ftgo_vault vault write auth/approle/role/config-server-role \
    token_policies="config-server-policy" \
    token_ttl=1h \
    token_max_ttl=4h

# Retrieve the Role ID
docker exec -it ftgo_vault vault read auth/approle/role/config-server-role/role-id

# Generate a Secret ID
docker exec -it ftgo_vault vault write -f auth/approle/role/config-server-role/secret-id
```

### 2. Configure AppRole in Config Server Configurations
Update `configserver/src/main/resources/application.yml` to authenticate via AppRole:

```yaml
spring:
  cloud:
    config:
      server:
        vault:
          host: vault
          port: 8200
          scheme: http
          backend: secret
          profile-separator: '/'
          app-role:
            role-id: ${VAULT_ROLE_ID} # Inject from env secret
            secret-id: ${VAULT_SECRET_ID} # Inject from env secret
```

---

## 4.7 Integrating HashiCorp Vault Backend in Detail

Using symmetric encryption handles database passwords, but it still stores ciphertexts in git, which fails standard compliance audits. To implement a highly secure setup, we bind the Config Server to **HashiCorp Vault**.

### 4.7.1 Starting Vault locally via Docker
We spin up a local instance of Vault in development mode using Docker Compose:

```yaml
  vault:
    image: vault:1.13.0
    container_name: ftgo_vault
    ports:
      - "8200:8200"
    environment:
      VAULT_DEV_ROOT_TOKEN_ID: "ftgo-root-token"
      VAULT_DEV_LISTEN_ADDRESS: "0.0.0.0:8200"
```

### 4.7.2 Writing Secrets into Vault
Using Vault's Key-Value version 2 engine, we store secret parameters for `order-service`:

```bash
# Exec into the container and log in
docker exec -it ftgo_vault vault login ftgo-root-token

# Enable the v2 Key-Value engine
docker exec -it ftgo_vault vault secrets enable -path=secret kv-v2

# Store the database password
docker exec -it ftgo_vault vault kv put secret/order-service spring.datasource.password="VaultSecurePassword99"
```

### 4.7.3 Configuring Config Server to Fetch from Vault
In `configserver/src/main/resources/application.yml`, enable both git and vault profiles:

```yaml
spring:
  profiles:
    active: git,vault
  cloud:
    config:
      server:
        vault:
          host: vault
          port: 8200
          scheme: http
          backend: secret
          profile-separator: '/'
          default-key: application
```

When the `order-service` calls Config Server, the server pulls structural parameters from git, retrieves sensitive credentials from Vault, and merges them into a single response block.

---

## 4.8 Scaling Reloads with Spring Cloud Bus and Apache Kafka

Manually sending an HTTP POST `/actuator/refresh` request to every running instance of `order-service` is not feasible in production environments where instances scale up or down dynamically.

To scale configuration refreshes across multiple instances, we implement **Spring Cloud Bus**. This library links all microservice instances via a shared message broker (Apache Kafka). When configurations change, a single request to the `/actuator/bus-refresh` endpoint on any instance broadcasts a refresh event to all instances:

```
 Developer               Config Server              Kafka Broker              Order Service Instances
     |                        |                          |                       |           |
     |-- POST /bus-refresh -->|                          |                       |           |
     |                        |-- Publish RefreshEvent ->|                       |           |
     |                        |                          |-- Broadcast Event --->|           |
     |                        |                          |                       |-- Refresh |
     |                        |                          |                       |           |-- Refresh
```

### 4.8.1 Add Dependencies to `order-service`
Add the Spring Cloud Bus Kafka starter to the service's `pom.xml`:

```xml
<dependency>
    <groupId>org.springframework.cloud</groupId>
    <artifactId>spring-cloud-starter-bus-kafka</artifactId>
</dependency>
```

### 4.8.2 Configure Spring Cloud Bus properties
In `order-service/src/main/resources/application.yml`, define the connection settings:

```yaml
spring:
  cloud:
    bus:
      enabled: true
      destination: springCloudBus # Name of the Kafka topic used for bus events
      id: ${spring.application.name}:${random.uuid}
    stream:
      kafka:
        binder:
          brokers: ${SPRING_KAFKA_BOOTSTRAP_SERVERS:localhost:29092}
```

### 4.8.3 Triggering the Bus Reload
When properties are committed to Git, send a single request to the Config Server or any microservice instance's bus refresh endpoint:

```bash
curl -X POST http://localhost:8081/actuator/bus-refresh
```

This publishes a `RefreshRemoteApplicationEvent` to the `springCloudBus` Kafka topic. All running microservice instances consume this event and refresh their `@RefreshScope` beans simultaneously.

---

## 4.9 Config Client Resiliency: Retry Strategies and Local Caching

If the Spring Cloud Config Server is offline or undergoing a rolling update during a client microservice's startup, the client container may crash immediately because it cannot fetch critical properties. To make the bootstrap flow resilient, we implement client-side retries and local filesystem configuration caching.

### 4.9.1 Spring Retry and AOP Dependency
To support reconnection attempts, add the Spring Retry and AOP starters to the client's `pom.xml`:

```xml
<dependency>
    <groupId>org.springframework.retry</groupId>
    <artifactId>spring-retry</artifactId>
</dependency>
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-aop</artifactId>
</dependency>
```

### 4.9.2 Configuring Reconnection Parameters
In `order-service/src/main/resources/bootstrap.yml`, configure the config client to enable retries and configure backoff boundaries:

```yaml
spring:
  cloud:
    config:
      fail-fast: true # Terminate startup if reconnection threshold is exceeded
      retry:
        max-attempts: 10 # Attempt to connect up to 10 times
        initial-interval: 1000 # Wait 1 second before first retry
        max-interval: 5000 # Maximum delay between attempts (5 seconds)
        multiplier: 1.5 # Exponential backoff factor
```

With these parameters, the client service will try to reconnect recursively, waiting 1s, then 1.5s, then 2.25s, etc. before timing out.

### 4.9.3 Implementing Local Configuration Caching (Fallback)
If the Config Server cannot be reached after all retries, the microservice can fall back to using a local file cache of the properties fetched during its last successful run.

Enable local configuration caching in the client's bootstrap configuration:

```yaml
spring:
  cloud:
    config:
      server-effects:
        local-cache:
          enabled: true
          # Directory path on the local disk where property files are cached
          location: ${java.io.tmpdir}/config-client-cache/
```

When local caching is enabled, the client performs the following steps:
1. On a successful boot, the client writes the retrieved configuration properties to a local JSON file in `${java.io.tmpdir}/config-client-cache/order-service-${profile}.json`.
2. On a subsequent boot, if the Config Server is unreachable and the retry threshold is reached, the client loads properties from the cached JSON file, allowing the microservice to start successfully.

---

## 4.10 Securing the Config Server with HTTP Basic Authentication

Serving microservice properties in plaintext over a public endpoint without security controls is a severe vulnerability. To restrict access to unauthorized users, we secure the Config Server using HTTP Basic Authentication:

### 4.10.1 Add Security Dependency to Config Server
Add the Spring Boot starter security to `configserver/pom.xml`:

```xml
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-security</artifactId>
</dependency>
```

### 4.10.2 Configure Security Policies Class
Create a configuration class `SecurityConfig.java` to enforce basic authentication across all endpoints:

```java
package com.ftgo.configserver;

import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.WebSecurityConfigurerAdapter;

@Configuration
public class SecurityConfig extends WebSecurityConfigurerAdapter {

    @Override
    protected void configure(HttpSecurity http) throws Exception {
        http
            .csrf().disable() // Disable CSRF for stateless API access
            .authorizeRequests()
            .anyRequest().authenticated() // All config resource queries must be authenticated
            .and()
            .httpBasic(); // Enforce standard HTTP Basic Auth header validation
    }
}
```

### 4.10.3 Define Access Credentials
Configure the username and password in the Config Server's own properties file (`configserver/src/main/resources/application.yml`):

```yaml
spring:
  security:
    user:
      name: ftgo-config-admin
      password: ${CONFIG_SERVER_PASSWORD:SuperSecureConfigPassword123}
```

### 4.10.4 Configure Client Services to Authenticate
Update the client's `bootstrap.yml` configuration (`order-service/src/main/resources/bootstrap.yml`) to pass basic credentials:

```yaml
spring:
  cloud:
    config:
      uri: http://localhost:8071
      username: ftgo-config-admin
      password: ${CONFIG_SERVER_PASSWORD:SuperSecureConfigPassword123}
```

With this configured, the client service automatically attaches the `Authorization: Basic [base64]` header to its request, enabling secure transport validation.

---
## Chapter Summary

* **Distributed configuration management** isolates environment settings from code by applying four principles: segregate, abstract, centralize, and harden.
* A microservice retrieves configurations during its **bootstrapping phase** using local configurations defined in `bootstrap.yml`.
* **Spring Cloud Config Server** centralizes properties using active profiles to switch between **local filesystem (native)**, **version-controlled Git**, and **HashiCorp Vault** backends.
* Integrating the client microservice requires adding the config client dependency and specifying the server URI inside `bootstrap.yml`.
* Dynamic configuration updates are managed using `@RefreshScope` annotations on client beans and triggering the Actuator `/actuator/refresh` endpoint.
* Sensitive configurations are secured using the Config Server's **symmetric encryption** support, encrypting credentials using a shared key and storing them with the `{cipher}` prefix.
* Secure corporate environments integrate **HashiCorp Vault** to isolate secrets, securing access credentials using **AppRole Authentication** to acquire temporary client tokens dynamically.
* To broadcast configuration reloads across multiple scaled-out client instances, we leverage **Spring Cloud Bus** backed by **Apache Kafka**, routing a single Actuator `/actuator/bus-refresh` POST event to refresh the entire cluster in parallel.
* Clients are made resilient using **Spring Retry** configuration reconnect loops and **Local File Caching** properties fallback systems to survive Config Server outages during bootstrap.
* The Config Server interface endpoints are hardened against unauthorized queries by implementing **HTTP Basic Authentication** policies using Spring Security.

