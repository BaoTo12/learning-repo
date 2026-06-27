# Chapter 2: Decomposition Strategies & Domain-Driven Design (DDD)

Decomposing an application into services by applying the decomposition patterns *Decompose by business capability* and *Decompose by subdomain*, and using the Bounded Context concept from Domain-Driven Design (DDD) to untangle data, resolve modular dependencies, and build a scalable microservices architecture.

---

## Learning Objectives

By the end of this chapter, you will be able to:
1. Define software architecture and explain the 4+1 View Model (Logical, Implementation, Process, Deployment, and Scenarios).
2. Contrast the layered architectural style with the hexagonal (ports and adapters) architectural style.
3. Apply the *Decompose by Business Capability* pattern to map enterprise business capabilities to independent services.
4. Apply Domain-Driven Design (DDD) concepts (Subdomains: Core, Supporting, Generic; and Bounded Contexts) to decompose database tables and entities.
5. Identify and resolve obstacles to functional decomposition, specifically network latency, distributed transaction boundaries, and the presence of **God Classes**.
6. Design service API contracts by mapping system operations to collaborative service interactions.
7. Set up a multi-module Spring Boot project skeleton demonstrating domain decomposition.

---

## 2.1 The Concept of Software Architecture

The key idea of the microservice architecture is functional decomposition. Instead of developing one large, monolithic application, you structure the application as a set of services. To understand this functional decomposition, we must look at the broader discipline of software architecture.

### What is Software Architecture?
Len Bass and colleagues at the Software Engineering Institute (SEI) define software architecture as:
> "The software architecture of a computing system is the set of structures needed to reason about the system, which comprise software elements, relations among them, and properties of both."

An application's architecture is its decomposition into parts (the elements) and the relationships (the relations) between those parts. This decomposition is critical for:
* **Division of Labor**: It allows developers and autonomous teams to work productively in parallel on different parts of a system without constant communication overhead.
* **Component Interaction**: It defines the contracts, APIs, and protocols through which software elements interact.
* **Quality Attributes (-ilities)**: It determines how well the application satisfies non-functional requirements such as scalability, reliability, maintainability, testability, and deployability.

---

### The 4+1 View Model of Software Architecture
A software architecture is multidimensional and cannot be described by a single blueprint. Phillip Krutchen proposed the **4+1 View Model**, which defines four distinct architectural views, animated by scenarios:

![Figure 2.1: Krutchen's 4+1 View Model](https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//f9a7fb73-a514-4163-9f6f-e447b3726962/markdown_0/imgs/img_in_image_box_185_105_846_609.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A55%3A52Z%2F-1%2F%2F3962214f08c4df91334f6390a76420e90ab55e55769dadd612b8e7ad93cd38ff)
*Figure 2.1: The 4+1 view model describes an application's architecture using four views, along with scenarios (+1) that show how elements collaborate.*

#### 1. Logical View
The software elements created by developers. In object-oriented languages (like Java), the elements are classes and packages. The relations are the compile-time relationships between classes and packages, including inheritance, interface implementation, associations, and dependencies.

#### 2. Implementation View
The output of the build system. This view consists of packaged modules (e.g., Java JAR files) and components (e.g., Java WAR files or executable JAR files). The relations include dependency relationships between modules and composition relationships between components.

#### 3. Process View
The components at runtime. Each element is a runtime process (e.g., a JVM process or a containerized instance), and the relations represent interprocess communication (IPC) protocols (e.g., REST, gRPC, messaging).

#### 4. Deployment View
How the processes are mapped to hardware infrastructure. The elements are physical servers, virtual machines, or container runtimes, and the relations represent network topologies.

#### Scenarios (+1)
The scenarios represent the execution paths (use cases) that animate the views. A scenario describes how the various elements in a view collaborate to handle a specific request (e.g., how classes interact in the logical view, and how processes exchange messages in the process view).

---

### Quality of Service Requirements
An application has two categories of requirements:
1. **Functional Requirements**: Define what the application must do (e.g., "A consumer can place an order"). These can be implemented using almost any architecture, including a "big ball of mud."
2. **Quality of Service Requirements (Non-Functional Requirements)**: Define how well the system operates. The architecture determines these quality attributes:
  * **Maintainability**: The ease of modifying the application to fix bugs, adopt new technologies, or add features.
  * **Testability**: The ease of validating that the application behaves correctly through automated tests.
  * **Deployability**: The ease of releasing the application to production safely and quickly.
  * **Scalability**: The capacity to handle increased traffic and request volumes.
  * **Reliability**: The resilience of the system to runtime failures.

---

## 2.2 Architectural Styles

An architectural style defines a family of software systems in terms of a pattern of structural organization. It determines the vocabulary of components and connectors that can be used, along with a set of constraints on how they can be combined.

### The Layered Architectural Style (Three-Tier Architecture)
A layered architecture organizes software elements into horizontal layers, restricting dependencies: a layer can only depend on layers immediately below it or layers further down.

The standard three-tier architecture is a layered architecture applied to the logical view:
1. **Presentation Layer**: Implements user interfaces or REST controllers.
2. **Business Logic Layer**: Implements core business rules and domain logic.
3. **Persistence Layer**: Implements database interactions and data access objects (DAOs).

#### Drawbacks of Layered Architecture:
* **Single Presentation and Persistence Assumptions**: Real-world applications are invoked by multiple clients (web UIs, mobile apps, batch schedulers) and interact with multiple external backing services (databases, message brokers, cloud APIs). A single layer is insufficient.
* **Database Dependency**: The business logic layer depends directly on the persistence layer. This makes it difficult to test the business logic in isolation without starting a database.
* **Reverse Dependencies**: In a clean design, the business logic defines repository interfaces, and the persistence layer defines classes that implement them. The actual dependencies are the reverse of a layered design.

---

### The Hexagonal Architectural Style (Ports and Adapters)
Hexagonal architecture is an alternative to layered architecture that places the business logic at the center:

![Figure 2.2: Hexagonal Architecture](https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//f9a7fb73-a514-4163-9f6f-e447b3726962/markdown_3/imgs/img_in_image_box_203_102_926_678.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A55%3A54Z%2F-1%2F%2F4a0a298ba698e9119f9d753d24a8ebdfee7b2297ca7206d4d077c7a92c73daed)
*Figure 2.2: Hexagonal architecture: Business logic is at the core, surrounded by inbound and outbound adapters.*

* **The Core**: Contains the domain model, business services, and rules. It is isolated from databases, UI technologies, and messaging frameworks.
* **Ports**: Define interfaces for communication:
  * **Inbound Ports**: Define the API exposed by the business logic, enabling external clients to invoke it (e.g., service interfaces).
  * **Outbound Ports**: Define how the business logic invokes external systems (e.g., repository interfaces or payment gateway interfaces).
* **Adapters**: Translate protocols:
  * **Inbound Adapters**: Intercept external events (HTTP requests, message events) and call an inbound port (e.g., REST controllers).
  * **Outbound Adapters**: Implement outbound ports and translate calls from the business logic into database queries or API calls targeting external systems (e.g., JPA repositories, external HTTP clients).

This architectural style decouples business logic from technical details, allowing developers to run tests on the core business logic without databases or web servers.

---

## 2.3 Decomposition Strategies

Decomposing a system into microservices is an architectural challenge. The goal is to design a set of services that are loosely coupled, cohesive, and easily maintained.

### Decomposition Pattern: Decompose by Business Capability
A business capability represents what a business does to generate value. It is defined by the organization's business model and operations:

* **Identifying Capabilities**: Capabilities are identified by analyzing an organization's business objects, processes, and org structures.
* **FTGO Business Capabilities**:
  * *Consumer Management*: Registering and managing consumers.
  * *Restaurant Management*: Managing menus and restaurant data.
  * *Order Management*: Taking and processing food orders.
  * *Courier Management*: Assigning couriers and tracking deliveries.
  * *Billing*: Charging customers, paying restaurants, and compensating couriers.
* **Mapping to Services**: Each business capability maps to a dedicated microservice (e.g., Order Service, Billing Service, Delivery Service). This ensures that services are aligned with business capabilities, reducing changes that cross service boundaries.

---

### Decomposition Pattern: Decompose by Subdomain (Domain-Driven Design)
Domain-Driven Design (DDD) is a software design approach that aligns code structures with the business domain. It uses **Subdomains** and **Bounded Contexts** to define service boundaries.

#### Subdomains
A domain represents the entire business capability space. In DDD, you decompose this domain into **Subdomains**, categorized by business importance:
1. **Core Subdomain**: The core differentiator of the business. For FTGO, this is the delivery matching and scheduling algorithm that coordinates couriers. It must be implemented in-house with high-quality custom code.
2. **Supporting Subdomain**: Capabilities that are specific to the business but do not provide a competitive advantage (e.g., menu catalog management, order taking). These are written in-house but require less focus.
3. **Generic Subdomain**: Standard capabilities that are not unique to the business (e.g., customer identity management, payment processing). These can be handled using off-the-shelf software or SaaS APIs (such as Keycloak or Stripe).

#### Bounded Contexts
In a monolithic application, developers build a single, shared domain model. This leads to tight coupling. For example, the `Order` class is shared across multiple modules, containing fields and rules for order taking, kitchen preparation, courier dispatch, and billing.

DDD resolves this with the **Bounded Context** pattern. A Bounded Context is a boundary within which a specific domain model applies. Each subdomain has its own bounded context and domain model:

```
  +--------------------------------------------------------------+
  |                        FTGO Domain                           |
  +-------------------+--------------------+---------------------+
  |   Order Service   |   Kitchen Service  |  Delivery Service   |
  |  Bounded Context  |   Bounded Context  |   Bounded Context   |
  |                   |                    |                     |
  |  +-------------+  |   +-------------+  |   +-------------+   |
  |  |    Order    |  |   | Ticket      |  |   | Delivery    |   |
  |  |  - state    |  |   | - prepTime  |  |   | - route     |   |
  |  |  - consumer |  |   | - status    |  |   | - courierId |   |
  |  +-------------+  |   +-------------+  |   +-------------+   |
  +-------------------+--------------------+---------------------+
```

* In the **Order Service** context, the `Order` entity represents customer orders (states: `APPROVAL_PENDING`, `APPROVED`).
* In the **Kitchen Service** context, the order is modeled as a `Ticket`, representing kitchen preparation states (states: `PREPARING`, `READY_FOR_PICKUP`).
* In the **Delivery Service** context, the order is modeled as a `Delivery`, representing courier routing states.

Each service owns its domain model. This isolation avoids shared classes and allows teams to develop services independently.

---

## 2.4 Obstacles to Decomposition

When decomposing an application into services, developers face three main obstacles: network latency, distributed transaction boundaries, and **God Classes**.

### 1. Network Latency
Replacing in-memory method calls with remote network calls (REST/gRPC) introduces network latency:
* **The Problem**: A request might require a service to make sequential API calls to multiple other services, creating a latency bubble.
* **Mitigation**:
  * Implement batch endpoints to retrieve multiple resources in a single call.
  * Use asynchronous event-driven communication (messaging) to update local caches.
  * Apply the API Composition or CQRS patterns to aggregate read data, avoiding sequential queries.

### 2. Distributed Transaction Boundaries
Under the database-per-service model, a business transaction must update databases across multiple services:
* **The Problem**: Traditional distributed transactions (2-Phase Commit / XA) are not suitable for modern, highly scaled microservices because they block database resources during consensus, reducing system availability.
* **Mitigation**: Implement the **Saga Pattern**, which coordinates a series of local transactions across services. Sagas use asynchronous messaging to propagate state changes and execute compensating transactions to roll back updates if a step fails.

### 3. Resolving God Classes
A God Class is an entity that is referenced throughout a monolithic codebase, containing fields and logic from multiple business subdomains. In the FTGO monolith, `Order` is a God Class:

```java
// Monolithic God Class (Antipattern)
public class Order {
    private Long id;
    private Consumer consumer;
    private Restaurant restaurant;
    private List<OrderLineItem> lineItems;
    private PaymentDetails paymentDetails;
    private DeliveryRoute deliveryRoute;
    private TicketState ticketState;
    // ... hundreds of fields and tangled methods ...
}
```

This shared class prevents decomposing the application into separate services because any change to the `Order` class affects multiple teams.

#### Decomposing the God Class:
Applying Bounded Contexts, we split the monolithic `Order` class into separate, independent models owned by individual services:
* **Order Service**: Tracks state, line items, and pricing.
* **Kitchen Service**: Tracks the preparation state (`Ticket`).
* **Delivery Service**: Tracks routing and delivery coordinates (`Delivery`).

These separate models are linked only by a shared identifier (e.g., `orderId`). When a state change occurs in one service, it publishes an event containing the `orderId` to notify other services.

---

## 2.5 Defining Service APIs

To establish the interfaces of a microservice architecture, we map system requirements to collaborative service interactions:

### 1. Define System Operations
System operations are the entry-point requests sent by users or external systems to trigger business logic. We define these operations by identifying use cases and analyzing system behavior:
* **Commands**: Write operations that update system state (e.g., `createOrder()`, `updateCourierLocation()`).
* **Queries**: Read operations that retrieve system state (e.g., `findOrderHistory()`, `findMenu()`).

### 2. Map Operations to Services
Assign each system operation to a target service based on domain ownership. For example, `createOrder()` is assigned to the `Order Service`, while `updateCourierLocation()` is assigned to the `Delivery Service`.

### 3. Design Collaboration Scenarios
Design the APIs and message flows required to support each operation:

```
  Consumer             API Gateway           Order Service        Kitchen Service
     |                     |                      |                      |
     |--- postOrder() ---->|                      |                      |
     |                     |---- createOrder() -->|                      |
     |                     |                      |--- createTicket() -->|
     |                     |                      |                      |
```

When the gateway invokes `createOrder()`, the `Order Service` verifies the order details, persists the entity to its database, and calls the `Kitchen Service` to schedule food preparation.

---

## 2.6 Skeletal Domain Implementation (Spring Boot)

To demonstrate domain decomposition, let's look at the codebase structure for a multi-module microservice setup:

### Project Skeleton Directory Layout
We configure a parent project containing two independent microservices: `order-service` and `kitchen-service`.

```
ftgo-microservices/
├── pom.xml
├── order-service/
│   ├── pom.xml
│   └── src/
│       └── main/
│           ├── java/com/ftgo/order/
│           │   ├── OrderServiceApplication.java
│           │   ├── controller/OrderController.java
│           │   ├── domain/Order.java
│           │   ├── domain/OrderLineItem.java
│           │   ├── repository/OrderRepository.java
│           │   ├── service/OrderService.java
│           │   └── acl/RestaurantCatalogACLTranslator.java
│           └── resources/application.yml
└── kitchen-service/
    ├── pom.xml
    └── src/
        └── main/
            ├── java/com/ftgo/kitchen/
            │   ├── KitchenServiceApplication.java
            │   ├── controller/KitchenController.java
            │   ├── domain/Ticket.java
            │   ├── repository/TicketRepository.java
            │   └── service/KitchenService.java
            └── resources/application.yml
```

---

### Parent Project Configuration: `pom.xml`
The parent POM manages dependency versions across all modules using Maven's `dependencyManagement` element:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <groupId>com.ftgo</groupId>
    <artifactId>parent-pom</artifactId>
    <version>1.0.0-SNAPSHOT</version>
    <packaging>pom</packaging>

    <name>FTGO Food Delivery Parent POM</name>

    <parent>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-parent</artifactId>
        <version>2.5.4</version>
        <relativePath/>
    </parent>

    <properties>
        <java.version>11</java.version>
        <spring-cloud.version>2020.0.3</spring-cloud.version>
        <lombok.version>1.18.20</lombok.version>
    </properties>

    <modules>
        <module>order-service</module>
        <module>kitchen-service</module>
    </modules>

    <dependencyManagement>
        <dependencies>
            <dependency>
                <groupId>org.springframework.cloud</groupId>
                <artifactId>spring-cloud-dependencies</artifactId>
                <version>${spring-cloud.version}</version>
                <type>pom</type>
                <scope>import</scope>
            </dependency>
        </dependencies>
    </dependencyManagement>
</project>
```

---

### Order Service Configuration: `order-service/pom.xml`
The module-level POM imports starters and parents, and inherits version definitions from the parent:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <parent>
        <groupId>com.ftgo</groupId>
        <artifactId>parent-pom</artifactId>
        <version>1.0.0-SNAPSHOT</version>
        <relativePath>../pom.xml</relativePath>
    </parent>

    <artifactId>order-service</artifactId>
    <name>Order Service</name>

    <dependencies>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-web</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-data-jpa</artifactId>
        </dependency>
        <dependency>
            <groupId>org.postgresql</groupId>
            <artifactId>postgresql</artifactId>
            <scope>runtime</scope>
        </dependency>
        <dependency>
            <groupId>org.projectlombok</groupId>
            <artifactId>lombok</artifactId>
            <version>${lombok.version}</version>
            <scope>provided</scope>
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

### Bounded Context Entity: `Order.java`
The `Order` entity is mapped to its private table, referencing the parent restaurant only by an ID (`restaurantId`), avoiding a direct object relationship across service boundaries:

```java
package com.ftgo.order.domain;

import lombok.Getter;
import lombok.Setter;
import lombok.ToString;

import javax.persistence.*;
import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;

@Getter
@Setter
@ToString
@Entity
@Table(name = "orders")
public class Order {

    @Id
    @Column(name = "id", nullable = false)
    private String id;

    @Column(name = "consumer_id", nullable = false)
    private String consumerId;

    @Column(name = "restaurant_id", nullable = false)
    private String restaurantId;

    @Column(name = "total_amount", nullable = false)
    private BigDecimal totalAmount;

    @Column(name = "state", nullable = false)
    private String state;

    @Column(name = "version", nullable = false)
    private Long version;

    @Column(name = "created_at", nullable = false)
    private LocalDateTime createdAt;

    @OneToMany(mappedBy = "order", cascade = CascadeType.ALL, orphanRemoval = true)
    private List<OrderLineItem> lineItems = new ArrayList<>();
}
```

---

### Child Value Object Entity: `OrderLineItem.java`

```java
package com.ftgo.order.domain;

import lombok.Getter;
import lombok.Setter;
import lombok.ToString;

import javax.persistence.*;
import java.math.BigDecimal;

@Getter
@Setter
@ToString
@Entity
@Table(name = "order_line_items")
public class OrderLineItem {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "order_id")
    private Order order;

    @Column(name = "menu_item_id", nullable = false)
    private String menuItemId;

    @Column(name = "name", nullable = false)
    private String name;

    @Column(name = "price", nullable = false)
    private BigDecimal price;

    @Column(name = "quantity", nullable = false)
    private Integer quantity;
}
```

---

### Inbound Controller: `OrderController.java`
Implements inbound adapters by exposing REST HTTP operations:

```java
package com.ftgo.order.web;

import com.ftgo.order.domain.Order;
import com.ftgo.order.service.OrderService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping(value = "v1/restaurant/{restaurantId}/order")
public class OrderController {

    @Autowired
    private OrderService orderService;

    @GetMapping(value = "/{orderId}")
    public ResponseEntity<Order> getOrder(
            @PathVariable("restaurantId") String restaurantId,
            @PathVariable("orderId") String orderId) {
        
        Order order = orderService.getOrder(orderId, restaurantId);
        return ResponseEntity.ok(order);
    }

    @PostMapping
    public ResponseEntity<Order> createOrder(
            @PathVariable("restaurantId") String restaurantId,
            @RequestBody Order request) {
        
        Order order = orderService.createOrder(request, restaurantId);
        return ResponseEntity.ok(order);
    }

    @PutMapping
    public ResponseEntity<Order> updateOrder(
            @PathVariable("restaurantId") String restaurantId,
            @RequestBody Order request) {
        
        Order order = orderService.updateOrder(request, restaurantId);
        return ResponseEntity.ok(order);
    }

    @DeleteMapping(value = "/{orderId}")
    public ResponseEntity<String> deleteOrder(
            @PathVariable("restaurantId") String restaurantId,
            @PathVariable("orderId") String orderId) {
        
        String response = orderService.deleteOrder(orderId, restaurantId);
        return ResponseEntity.ok(response);
    }
}
```

---

### Core Domain Service: `OrderService.java`
Processes core business transactions inside the bounded context:

```java
package com.ftgo.order.service;

import com.ftgo.order.domain.Order;
import com.ftgo.order.repository.OrderRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.UUID;

@Service
public class OrderService {

    @Autowired
    private OrderRepository orderRepository;

    public Order getOrder(String orderId, String restaurantId) {
        Order order = orderRepository.findByIdAndRestaurantId(orderId, restaurantId);
        if (order == null) {
            throw new IllegalArgumentException("Order not found");
        }
        return order;
    }

    public Order createOrder(Order order, String restaurantId) {
        order.setId(UUID.randomUUID().toString());
        order.setRestaurantId(restaurantId);
        return orderRepository.save(order);
    }

    public Order updateOrder(Order order, String restaurantId) {
        Order existing = getOrder(order.getId(), restaurantId);
        existing.setTotalAmount(order.getTotalAmount());
        existing.setState(order.getState());
        return orderRepository.save(existing);
    }

    public String deleteOrder(String orderId, String restaurantId) {
        Order order = getOrder(orderId, restaurantId);
        orderRepository.delete(order);
        return String.format("Deleted order %s for restaurant %s", orderId, restaurantId);
    }
}
```

---

### Private Repository Interface: `OrderRepository.java`
Exposes the repository port for data access, which is implemented at runtime by Spring Data JPA:

```java
package com.ftgo.order.repository;

import com.ftgo.order.domain.Order;
import org.springframework.data.repository.CrudRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface OrderRepository extends CrudRepository<Order, String> {
    Order findByIdAndRestaurantId(String id, String restaurantId);
}
```

---

## 2.7 Bounded Context Integration & The Anticorruption Layer (ACL)

When integrating different bounded contexts, teams often encounter legacy third-party partner applications. Direct database access or model-sharing with these external systems leads to **Domain Model Pollution**, where core entities are forced to model external concepts.

To protect the `Order Service` domain model, we implement an **Anticorruption Layer (ACL)**. The ACL translates external data structures into clean internal value objects:

```
[ Legacy Partner XML Catalog API ]
                 |
                 v (Legacy Schema)
  +------------------------------+
  |    Anticorruption Layer      |
  |  - XML Stream Parser         |
  |  - Domain Model Translator   |
  +------------------------------+
                 |
                 v (com.ftgo.order.domain.MenuItem)
      [ Order Service Domain ]
```

### Inbound Catalog Translator: `RestaurantCatalogACLTranslator.java`
Below is the complete implementation of the ACL translator class. It parses legacy partner catalogs formatted in XML, sanitizes the price strings, and translates them into clean internal `MenuItem` value objects:

```java
package com.ftgo.order.acl;

import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.NodeList;
import org.xml.sax.InputSource;

import javax.xml.parsers.DocumentBuilder;
import javax.xml.parsers.DocumentBuilderFactory;
import java.io.StringReader;
import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

public class RestaurantCatalogACLTranslator {

    public static class PartnerMenuItem {
        private final String code;
        private final String label;
        private final BigDecimal cost;

        public PartnerMenuItem(String code, String label, BigDecimal cost) {
            this.code = code;
            this.label = label;
            this.cost = cost;
        }

        public String getCode() { return code; }
        public String getLabel() { return label; }
        public BigDecimal getCost() { return cost; }
    }

    public List<PartnerMenuItem> translatePartnerCatalog(String legacyXmlCatalog) {
        if (legacyXmlCatalog == null || legacyXmlCatalog.isBlank()) {
            return Collections.emptyList();
        }

        List<PartnerMenuItem> items = new ArrayList<>();
        try {
            // Instantiate parser to prevent external entities processing (XXE attack protection)
            DocumentBuilderFactory dbFactory = DocumentBuilderFactory.newInstance();
            dbFactory.setFeature("http://xml.org/sax/features/external-general-entities", false);
            dbFactory.setFeature("http://xml.org/sax/features/external-parameter-entities", false);
            dbFactory.setFeature("http://apache.org/xml/features/nonvalidating/load-external-dtd", false);
            
            DocumentBuilder dBuilder = dbFactory.newDocumentBuilder();
            Document doc = dBuilder.parse(new InputSource(new StringReader(legacyXmlCatalog)));
            doc.getDocumentElement().normalize();

            NodeList nodeList = doc.getElementsByTagName("legacy-item");
            for (int i = 0; i < nodeList.getLength(); i++) {
                Element element = (Element) nodeList.item(i);
                
                String rawCode = element.getElementsByTagName("item-code").item(0).getTextContent();
                String rawLabel = element.getElementsByTagName("item-label").item(0).getTextContent();
                String rawCost = element.getElementsByTagName("item-cost").item(0).getTextContent();

                // Clean price strings (remove commas, currency symbols)
                String sanitizedCost = rawCost.replaceAll("[^0-9.]", "");
                BigDecimal cost = new BigDecimal(sanitizedCost);

                items.add(new PartnerMenuItem(rawCode, rawLabel, cost));
            }
        } catch (Exception e) {
            throw new IllegalArgumentException("Failure parsing legacy catalog payload", e);
        }
        return items;
    }
}
```

---

## 2.8 Hexagonal Architecture in Detail

A major benefit of the decomposition strategies detailed above is the transition from Layered styles to **Hexagonal (Ports and Adapters) Architecture**. In this layout, the business domain is placed at the center, isolated from databases, HTTP frameworks, and message brokers:

```
                  ======================================
                  |             Adapters               |
                  |                                    |
                  |   [ OrderController ] (Inbound)    |
                  |                |                   |
                  |                v (Port)            |
                  |        [ OrderService ]            |
                  |        [   Domain     ]            |
                  |                |                   |
                  |                v (Port)            |
                  |   [ OrderRepository ] (Outbound)   |
                  |                                    |
                  ======================================
```

1. **The Core Domain**: Contains the business logic (`Order` entity, `OrderLineItem` value objects). It has zero dependencies on frameworks (like Spring, Hibernate, or Jackson).
2. **Ports**: Interfaces that define how outer components interact with the domain (e.g., `OrderRepository`).
3. **Adapters**: The plumbing classes that translate external signals to inputs, or ports to infrastructure outputs (e.g., controllers mapping HTTP calls, Hibernate repositories connecting to databases).

---

## 2.9 Monolithic Database Schema Split Strategy

Decomposing a database is significantly more difficult than splitting application code. During the migration of the monolithic FTGO dining database into independent microservice databases (`order_db` and `kitchen_db`), we use a phased schema split approach.

### 2.9.1 The Legacy Monolithic Table Schema
In the legacy monolith, order data and kitchen ticket details were stored in a single table, creating tight database coupling:

```sql
-- Legacy Monolithic Database Table
CREATE TABLE legacy_orders (
    order_id INT PRIMARY KEY,
    consumer_id INT,
    restaurant_id INT,
    order_total DECIMAL(10, 2),
    order_status VARCHAR(50),
    ticket_status VARCHAR(50), -- Coupled kitchen state
    estimated_prep_time TIMESTAMP, -- Coupled kitchen data
    delivery_address TEXT, -- Coupled delivery data
    delivery_status VARCHAR(50)
);
```

### 2.9.2 Phase 1: Split Table and Implement Database Views
To separate the subdomains without breaking the legacy monolithic code immediately, we split the physical table into two separate tables: `orders` (retained in the order schema) and `tickets` (migrated to the kitchen schema). We then expose a database view to mimic the legacy table:

```sql
-- Step 1: Create Order Service Schema Table
CREATE TABLE orders (
    id VARCHAR(36) PRIMARY KEY,
    consumer_id VARCHAR(36) NOT NULL,
    restaurant_id VARCHAR(36) NOT NULL,
    total_amount DECIMAL(10, 2) NOT NULL,
    state VARCHAR(50) NOT NULL,
    created_at TIMESTAMP NOT NULL
);

-- Step 2: Create Kitchen Service Schema Table
CREATE TABLE tickets (
    id VARCHAR(36) PRIMARY KEY,
    order_id VARCHAR(36) UNIQUE NOT NULL,
    restaurant_id VARCHAR(36) NOT NULL,
    preparation_status VARCHAR(50) NOT NULL,
    estimated_ready_time TIMESTAMP NOT NULL
);

-- Step 3: Create Legacy Compatibility View in the Shared Schema
CREATE VIEW legacy_orders_view AS
SELECT 
    o.id AS order_id,
    o.consumer_id,
    o.restaurant_id,
    o.total_amount AS order_total,
    o.state AS order_status,
    t.preparation_status AS ticket_status,
    t.estimated_ready_time AS estimated_prep_time
FROM orders o
LEFT JOIN tickets t ON o.id = t.order_id;
```

---

## 2.10 Managing Context Communication with Shared Kernels

While Bounded Contexts promote decoupling, some subdomains require shared definitions. To prevent duplicated concepts, we can implement a **Shared Kernel**.

A Shared Kernel is a subset of the domain model that is shared directly between multiple bounded contexts. In the FTGO application, the `Money` value object and core exception classes are candidates for a Shared Kernel:

```java
package com.ftgo.shared.domain;

import java.math.BigDecimal;
import java.util.Objects;

public final class Money {
    public static final Money ZERO = new Money(BigDecimal.ZERO);

    private final BigDecimal amount;

    public Money(BigDecimal amount) {
        this.amount = amount.setScale(2, BigDecimal.ROUND_HALF_UP);
    }

    public BigDecimal getAmount() {
        return amount;
    }

    public Money add(Money other) {
        return new Money(this.amount.add(other.amount));
    }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (o == null || getClass() != o.getClass()) return false;
        Money money = (Money) o;
        return amount.compareTo(money.amount) == 0;
    }

    @Override
    public int hashCode() {
        return Objects.hash(amount);
    }
}
```

---


## Chapter Summary

* **Software architecture** defines an application's decomposition into parts (elements) and the relationships between them. It is best documented using the **4+1 View Model** (Logical, Implementation, Process, Deployment, and Scenarios).
* **Layered architecture** organizes classes horizontally but creates tight database coupling. **Hexagonal architecture** places the business logic at the core, decoupling it from technical details using **Ports** and **Adapters**.
* Service boundaries are defined using the **Decompose by Business Capability** pattern (mapping business capabilities to services) or the **Decompose by Subdomain** pattern (aligning services with subdomains identified through Domain-Driven Design).
* DDD's **Bounded Context** pattern untangles shared models by creating distinct domain models for separate subdomains, communicating via APIs instead of sharing tables or classes.
* Common obstacles to functional decomposition include network latency, distributed transaction boundaries (resolved using **Sagas**), and **God Classes** (decomposed using Bounded Contexts).
* Service APIs are designed by identifying **system operations** (Commands and Queries) and mapping them to collaborative service interactions.
* Skeletal configurations in Spring Boot use parent-child POM structures and define entity models linked only by unique identifiers (e.g., `restaurantId`), maintaining modular boundaries at the database layer.
* To safely integrate with third-party, legacy networks without polluting the domain model, we implement an **Anticorruption Layer (ACL)** that translates external payloads into internal domain models.

