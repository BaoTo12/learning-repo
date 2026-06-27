# Chapter 11: Designing Business Logic with Domain-Driven Design (DDD) Aggregates

In a traditional monolithic application, the business logic accesses a single, shared relational database. Because developers can write SQL queries that join arbitrary tables and use transactions that modify multiple entities, they often design the business logic as a single, highly coupled object model. In a microservices architecture, this monolithic design leads to tightly coupled services, distributed transaction locks, and unscalable network joins.

This chapter covers the design of business logic using the **Domain-Driven Design (DDD) Aggregate pattern**. We will explore why the traditional monolithic domain model fails in microservices, compare the procedural **Transaction Script** approach with the object-oriented **Domain Model** approach, and define the tactical and strategic patterns of DDD. We will analyze the strict rules for aggregate design—including referencing by identity only and limiting transactions to a single aggregate—examine domain event generation and enrichment, and write a functional Java implementation of an `Order` aggregate root and its child entities.

---

## Learning Objectives

By the end of this chapter, you will be able to:
1. Compare procedural Transaction Scripts and object-oriented Domain Models.
2. Outline the strategic (Subdomains, Bounded Contexts) and tactical (Entities, Value Objects, Aggregates, Repositories, Domain Services) building blocks of DDD.
3. Explain the limitations of a monolithic, interconnected domain model in a microservices environment.
4. Apply the rule of **Referencing by Identity Only** to decouple microservices.
5. Implement the rule of **One Transaction per Aggregate** using asynchronous domain events or sagas.
6. Design and implement a domain event publishing pipeline with event enrichment.
7. Build an encapsulated Java aggregate root with child entities using JPA, `@Version` optimistic locking, and state-machine validation.
8. Configure JPA Entity Lifecycle Listeners to automatically publish domain events during transaction commits.

---

## 11.1 Hexagonal Service Architecture & Transaction Script vs. Domain Model

In a microservice, the business logic represents the core of a hexagonal architecture, wrapped by inbound adapters (controllers, event listeners, command handlers) and outbound adapters (repositories, event publishers, client proxies):

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//0038d9f4-466f-427c-8cc9-4540e7a18458/markdown_2/imgs/img_in_image_box_183_104_899_861.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A55%3A37Z%2F-1%2F%2F8297efd4465e6d797404f20f03394ac5e9127e0b800d8de849e1c37b93ed6e44" alt="Image" width="67%" /></div>
<div style="text-align: center;">Figure 5.1: The Order Service has a hexagonal architecture. It consists of the business logic and one or more adapters that interface with external applications and other services.</div>

There are two primary patterns for organizing this business logic:

### 1. The Transaction Script Pattern (Procedural)
For simple business logic, developers write procedural scripts to handle each request. The key characteristic of this approach is that the classes that implement behavior are completely separate from those that store state:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//0038d9f4-466f-427c-8cc9-4540e7a18458/markdown_3/imgs/img_in_image_box_201_442_619_779.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A55%3A38Z%2F-1%2F%2F8a39d952781cbb08b9cbac3d7a2d34a5cf8d562ed011a7056e23f51c0518f776" alt="Image" width="39%" /></div>
<div style="text-align: center;">Figure 5.2: Organizing business logic as transaction scripts. In a typical transaction script-based design, one set of classes implements behavior and another set stores state. The transaction scripts are organized into classes that typically have no state. The scripts use data classes, which typically have no behavior.</div>

#### Procedural Transaction Script Implementation
Here is how a transaction script version of Order Service might be structured:

```java
package com.ftgo.order.procedural;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class OrderTransactionScriptService {

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @Transactional
    public void createOrder(Long orderId, Long consumerId, Long restaurantId, Double amount) {
        // 1. Validate rules procedurally
        Double orderMinimum = jdbcTemplate.queryForObject(
            "SELECT order_minimum FROM restaurants WHERE id = ?", Double.class, restaurantId);
        
        if (amount < orderMinimum) {
            throw new IllegalArgumentException("Order amount does not meet the restaurant minimum!");
        }

        // 2. Perform raw database insertions
        jdbcTemplate.update(
            "INSERT INTO orders (id, consumer_id, restaurant_id, amount, state) VALUES (?, ?, ?, ?, ?)",
            orderId, consumerId, restaurantId, amount, "APPROVAL_PENDING"
        );
    }
}
```

* **Pros**: Simple to write and understand for basic, data-centric CRUD services.
* **Cons**: As business logic grows, it degrades into a tangled web of copy-pasted SQL/JDBC statements inside a few massive, unmaintainable service files.

### 2. The Domain Model Pattern (Object-Oriented)
For complex business logic, the system is designed as a network of small, specialized classes that encapsulate both state and behavior:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//0038d9f4-466f-427c-8cc9-4540e7a18458/markdown_4/imgs/img_in_image_box_182_731_722_1143.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A55%3A39Z%2F-1%2F%2F8b4efd0870746ec0dfcf3be17ba746fd0edc435c8da76916685930ee48edd1a0" alt="Image" width="50%" /></div>
<div style="text-align: center;">Figure 5.3: Organizing business logic as a domain model. The majority of the business logic consists of classes that have state and behavior.</div>

* **Pros**: Business rules are cleanly encapsulated inside entities, making the system highly testable, modular, and easy to extend.
* **Cons**: Interconnected object graphs are difficult to map directly to decoupled, microservice database boundaries.

---

## 11.2 DDD Building Blocks: Strategic and Tactical Patterns

Domain-Driven Design (DDD) divides complex software domains into distinct components:

### Strategic DDD Patterns
* **Subdomains**: Decomposes the business problem domain into separate subdomains:
  * **Core Subdomain**: The primary differentiator for the business (e.g. order routing algorithms).
  * **Supporting Subdomain**: Necessary but not core (e.g. menu inventory).
  * **Generic Subdomain**: Common tasks that could be handled by off-the-shelf software (e.g. billing, user logins).
* **Bounded Contexts**: Defines the explicit boundary of a domain model. Each Bounded Context corresponds to a microservice.

### Tactical DDD Patterns
* **Entities**: Objects with a persistent identity (ID) that spans their lifecycle. Two entities with the same ID are identical even if their other properties differ.
* **Value Objects**: Immutable collections of values without identities. They are defined entirely by their properties. If two value objects have the same properties, they are identical.
* **Aggregates**: Clusters of entities and value objects treated as a transaction consistency boundary.
* **Repositories**: Abstractions that handle retrieval and storage of aggregates from databases.
* **Factories**: Encapsulate complex aggregate creation logic.
* **Domain Services**: Orchestrate business operations that cross multiple entities or value objects.

---

## 11.3 The Monolithic Domain Model and Its Limits

In a traditional domain model, classes form a web of interconnected associations. There are no explicit boundaries defining the scope of operations (load, update, delete):

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//f9d64181-d5de-4137-b5d0-3c66f0a9a149/markdown_1/imgs/img_in_image_box_110_658_931_1000.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A55%3A59Z%2F-1%2F%2Fc472dcd631bfb67263f60a41bc902be4f8b4bc7e529ca755450bf14f5ebd4b70" alt="Image" width="77%" /></div>
<div style="text-align: center;">Figure 5.4: A traditional domain model is a web of interconnected classes. It doesn't explicitly specify the boundaries of business objects, such as Consumer and Order.</div>

### The Concurrency/Consistency Anomaly
If two users concurrently load a coupled order object and directly update its child items (e.g. updating line item quantities), they can easily bypass validation invariants (such as enforcing a minimum order amount), leading to inconsistent database states.

To solve this, DDD introduces **Aggregates** which explicitly define consistency boundaries:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//f9d64181-d5de-4137-b5d0-3c66f0a9a149/markdown_4/imgs/img_in_image_box_206_110_933_433.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A56%3A01Z%2F-1%2F%2F41ec52100942952739b3c95ec0c0c6327c70d34afb2f4b08764d513184daf8db" alt="Image" width="68%" /></div>
<div style="text-align: center;">Figure 5.5: Structuring a domain model as a set of aggregates makes the boundaries explicit.</div>

---

## 11.4 Strict Rules for Aggregate Design

Aggregates must adhere to three fundamental architectural constraints:

### Rule 1: Reference Other Aggregates by Identity Only
An aggregate must never store direct Java references to objects belonging to another aggregate. Instead, it must store their unique primary keys (IDs):

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//c9a85add-844d-4657-8a12-430417074086/markdown_0/imgs/img_in_image_box_187_532_913_860.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A55%3A41Z%2F-1%2F%2Faa4b75531798901f1139b801715b72a10c020287af56547b9b7bf1b4af7f9bed" alt="Image" width="68%" /></div>
<div style="text-align: center;">Figure 5.6: References between aggregates are by primary key rather than by object reference. The Order aggregate has the IDs of the Consumer and Restaurant aggregates. Within an aggregate, objects have references to one another.</div>

* **Benefit**: Aggregates are fully decoupled. They can be sharded across databases and managed by separate microservices without violating referential integrity constraints.

### Rule 2: Limit Transactions to a Single Aggregate
A single database transaction must only create or update a single aggregate instance. To propagate updates to other aggregates, the system uses asynchronous messaging:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//c9a85add-844d-4657-8a12-430417074086/markdown_1/imgs/img_in_image_box_206_473_916_698.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A55%3A42Z%2F-1%2F%2Fd6ff62048853268cccd605fc89ec6a1350fadfc2cd6653c7ba3b9f4487fa200b" alt="Image" width="66%" /></div>
<div style="text-align: center;">Figure 5.7: A transaction can only create or update a single aggregate, so an application uses a saga to update multiple aggregates. Each step of the saga creates or updates one aggregate.</div>

### Rule 3: Reference the Aggregate Root Only
External classes can only obtain references to, and invoke methods on, the **Aggregate Root** entity. Direct modifications of child entities or value objects by external classes is strictly forbidden.

### Aggregate Granularity Trade-Offs
The size of aggregates impacts concurrency and scalability. Small aggregates increase simultaneous requests throughput but require more sagas. Large aggregates provide atomic consistency but create lock conflicts:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//c9a85add-844d-4657-8a12-430417074086/markdown_2/imgs/img_in_image_box_188_453_909_776.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A55%3A43Z%2F-1%2F%2F8a0f84aab8de644cf668e821167a71e9ba7b648a34a52087807cb51f3587f510" alt="Image" width="67%" /></div>
<div style="text-align: center;">Figure 5.8: An alternative design defines a Customer aggregate that contains the Customer and Order classes. This design enables an application to atomically update a Consumer and one or more of its Orders.</div>

---

## 11.5 Publishing Domain Events

An aggregate publishes a **Domain Event** when it is created or undergoes a significant state change.

### Why Publish Events?
* Enforces inter-service data consistency using choreography-based sagas.
* Propagates changes to CQRS query replicas.
* Sends notifications (emails, text messages) to users.
* Integrates with external systems via webhooks.

### 1. Core Domain Event Markers in Java
We define marker interfaces and wrappers to structure our events cleanly:

```java
package com.ftgo.order.event;

public interface DomainEvent {}

public interface OrderDomainEvent extends DomainEvent {}

public class DomainEventEnvelope<T extends DomainEvent> {
    private String aggregateType;
    private Object aggregateId;
    private T event;

    public DomainEventEnvelope(String aggregateType, Object aggregateId, T event) {
        this.aggregateType = aggregateType;
        this.aggregateId = aggregateId;
        this.event = event;
    }

    public String getAggregateType() { return aggregateType; }
    public Object getAggregateId() { return aggregateId; }
    public T getEvent() { return event; }
}
```

### 2. Event Enrichment Pattern
To save consumers from having to make round-trip HTTP queries to fetch details, we include the necessary state data in the event itself (enriched events):

```java
package com.ftgo.order.event;

import com.ftgo.order.domain.OrderLineItem;
import java.util.List;

public class OrderCreatedEvent implements OrderDomainEvent {
    private List<OrderLineItem> lineItems;
    private Long restaurantId;
    private Double totalAmount;

    public OrderCreatedEvent(List<OrderLineItem> lineItems, Long restaurantId, Double totalAmount) {
        this.lineItems = lineItems;
        this.restaurantId = restaurantId;
        this.totalAmount = totalAmount;
    }

    public List<OrderLineItem> getLineItems() { return lineItems; }
    public Long getRestaurantId() { return restaurantId; }
    public Double getTotalAmount() { return totalAmount; }
}
```

### 3. Identifying Domain Events: Event Storming
To discover events, commands, and aggregates, development teams conduct **Event Storming** workshops:
* **Events**: Sticky notes in orange representing significant state changes.
* **Commands**: Sticky notes in blue representing user actions/triggers.
* **Aggregates**: Yellow notes representing consistency invariants reacting to commands.

---

## 11.6 JPA Mapping Architecture

When mapping aggregate models using JPA/Hibernate:
1. **Cascade Operations**: The root `@OneToMany` configuration should define `cascade = CascadeType.ALL` and `orphanRemoval = true`. This guarantees that saving the aggregate root automatically persists or deletes child items.
2. **Optimistic Locking**: The root entity must define a `@Version` field to prevent concurrent update anomalies. If two threads load version $N$ and try to write concurrently, Hibernate automatically rolls back the slower thread with an `OptimisticLockException`.
3. **Access Types**: We use `@Access(AccessType.FIELD)` to enforce field-level JPA mapping. This ensures Hibernate accesses private variables directly, bypassing getters and setters, and preventing external classes from modifying the internal state.

---

## 11.7 Complete Java DDD Aggregate Implementation

The business logic of Order Service is structured as follows:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//c9a85add-844d-4657-8a12-430417074086/markdown_3/imgs/img_in_image_box_201_367_933_1024.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A55%3A45Z%2F-1%2F%2F42a139eaaa1321a0d8e4d2363f33c747d15543530091e1072736f38bc6d0a3d5" alt="Image" width="68%" /></div>
<div style="text-align: center;">Figure 5.9: An aggregate-based design for the Order Service business logic.</div>

Let's look at the high-level hexagonal design of Order Service:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//9c3e5333-e149-4940-a880-89df2729d1fe/markdown_3/imgs/img_in_image_box_111_109_932_966.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A55%3A38Z%2F-1%2F%2Fd72f727be6bf21691413d9c9744f348dfedeaae86eeafbaf6ad2b4953c18b335" alt="Image" width="77%" /></div>
<div style="text-align: center;">Figure 5.12: The design of the Order Service. It has a REST API for managing orders. It exchanges messages and events with other services via several message channels.</div>

Now we'll define the structure of the Order aggregate:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//9c3e5333-e149-4940-a880-89df2729d1fe/markdown_4/imgs/img_in_image_box_200_723_873_1136.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A55%3A38Z%2F-1%2F%2Fc7e204340137d7429ee31ff9fe61ddbe41789b3b08bd88172a5f7e1ba0125785" alt="Image" width="63%" /></div>
<div style="text-align: center;">Figure 5.13: The design of the Order aggregate, which consists of the Order aggregate root and various value objects.</div>

### 1. Value Object: `Money.java`
An immutable value object representing currency values:

```java
package com.ftgo.order.domain;

import javax.persistence.Embeddable;
import java.util.Objects;

@Embeddable
public class Money {
    private Double amount;

    protected Money() {} // Required by JPA

    public Money(Double amount) {
        if (amount == null || amount < 0) {
            throw new IllegalArgumentException("Amount must be positive!");
        }
        this.amount = amount;
    }

    public Double getAmount() { return amount; }

    public Money add(Money other) {
        return new Money(this.amount + other.amount);
    }

    public boolean isGreaterThanOrEqual(Money other) {
        return this.amount >= other.amount;
    }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (o == null || getClass() != o.getClass()) return false;
        Money money = (Money) o;
        return Objects.equals(amount, money.amount);
    }

    @Override
    public int hashCode() {
        return Objects.hash(amount);
    }
}
```

### 2. Value Object: `DeliveryInformation.java`
Stores delivery destination details inside the aggregate:

```java
package com.ftgo.order.domain;

import javax.persistence.Embeddable;
import java.time.LocalDateTime;

@Embeddable
public class DeliveryInformation {
    private String street;
    private String city;
    private String zipCode;
    private LocalDateTime deliveryTime;

    protected DeliveryInformation() {} // Required by JPA

    public DeliveryInformation(String street, String city, String zipCode, LocalDateTime deliveryTime) {
        this.street = street;
        this.city = city;
        this.zipCode = zipCode;
        this.deliveryTime = deliveryTime;
    }

    public String getStreet() { return street; }
    public String getCity() { return city; }
    public String getZipCode() { return zipCode; }
    public LocalDateTime getDeliveryTime() { return deliveryTime; }
}
```

### 3. The Child Entity: `OrderLineItem.java`
The `OrderLineItem` class is a child entity managed by the `Order` root:

```java
package com.ftgo.order.domain;

import javax.persistence.*;

@Entity
@Table(name = "order_line_items")
public class OrderLineItem {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    private String menuItemId;
    private String name;
    private Double price;
    private Integer quantity;

    protected OrderLineItem() {} // Required by JPA

    public OrderLineItem(String menuItemId, String name, Double price, Integer quantity) {
        this.menuItemId = menuItemId;
        this.name = name;
        this.price = price;
        this.quantity = quantity;
    }

    public Double getTotal() {
        return this.price * this.quantity;
    }

    // Getters
    public Long getId() { return id; }
    public String getMenuItemId() { return menuItemId; }
    public String getName() { return name; }
    public Double getPrice() { return price; }
    public Integer getQuantity() { return quantity; }
}
```

---

### 4. The Aggregate Root: `Order.java`
The `Order` class acts as the aggregate root, enforcing business invariants, transitions of its state machine, and exposing public methods:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//ce2ea9b6-4fac-430b-a944-05a28cce72f3/markdown_1/imgs/img_in_image_box_127_331_950_689.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A55%3A37Z%2F-1%2F%2F74258e1925cf34279855a020accea3afa25345a7eee1f5901bdb851d359a99d8" alt="Image" width="77%" /></div>
<div style="text-align: center;">Figure 5.14: Part of the state machine model of the Order aggregate.</div>

```java
package com.ftgo.order.domain;

import javax.persistence.*;
import java.util.ArrayList;
import java.util.List;

@Entity
@Table(name = "orders")
@Access(AccessType.FIELD)
@EntityListeners(DomainEventPublishingListener.class) // Event listener configuration
public class Order {

    @Id
    private Long id;

    @Version // Optimistic locking
    private Long version;

    // Decoupled reference to another aggregate (Restaurant) by ID only
    private Long restaurantId;

    // Decoupled reference to another aggregate (Consumer) by ID only
    private Long consumerId;

    @Enumerated(EnumType.STRING)
    private OrderState state;

    @Embedded
    private DeliveryInformation deliveryInformation;

    @Embedded
    private Money orderMinimum;

    // Cascade operations ensure child entities are persisted/deleted with the root
    @OneToMany(cascade = CascadeType.ALL, orphanRemoval = true, fetch = FetchType.EAGER)
    @JoinColumn(name = "order_id")
    private List<OrderLineItem> lineItems = new ArrayList<>();

    protected Order() {} // Required by JPA

    public Order(Long id, Long restaurantId, Long consumerId, 
                 DeliveryInformation deliveryInformation, Money orderMinimum, List<OrderLineItem> lineItems) {
        this.id = id;
        this.restaurantId = restaurantId;
        this.consumerId = consumerId;
        this.deliveryInformation = deliveryInformation;
        this.orderMinimum = orderMinimum;
        this.lineItems = lineItems;
        this.state = OrderState.APPROVAL_PENDING;
        
        // Enforce invariant during aggregate construction
        validateOrderTotal();
    }

    // Business Invariant: An order total must meet the restaurant's minimum order requirements
    private void validateOrderTotal() {
        Money total = getOrderTotal();
        if (!total.isGreaterThanOrEqual(orderMinimum)) {
            throw new IllegalStateException("Order total " + total.getAmount() + 
                " does not meet restaurant minimum of " + orderMinimum.getAmount());
        }
    }

    // Business Invariant: An order cannot be revised if it is already cancelled
    public void revise(List<OrderLineItem> newLineItems) {
        if (this.state == OrderState.CANCELLED) {
            throw new IllegalStateException("Cannot revise a cancelled order!");
        }
        this.lineItems.clear();
        this.lineItems.addAll(newLineItems);
        
        // Re-validate invariants after aggregate state edits
        validateOrderTotal();
    }

    public void approve() {
        if (this.state != OrderState.APPROVAL_PENDING) {
            throw new IllegalStateException("Order must be in APPROVAL_PENDING to approve!");
        }
        this.state = OrderState.APPROVED;
    }

    public void reject() {
        this.state = OrderState.REJECTED;
    }

    public void cancel() {
        if (this.state == OrderState.APPROVAL_PENDING) {
            throw new IllegalStateException("Cannot cancel order while approval is pending!");
        }
        this.state = OrderState.CANCELLED;
    }

    public Money getOrderTotal() {
        Double total = lineItems.stream()
                .mapToDouble(OrderLineItem::getTotal)
                .sum();
        return new Money(total);
    }

    // Getters
    public Long getId() { return id; }
    public Long getVersion() { return version; }
    public Long getRestaurantId() { return restaurantId; }
    public Long getConsumerId() { return consumerId; }
    public OrderState getState() { return state; }
    public DeliveryInformation getDeliveryInformation() { return deliveryInformation; }
    public List<OrderLineItem> getLineItems() { return lineItems; }
}
```

---

### 5. The JPA Repository interface: `OrderRepository.java`
Declare a spring data interface to query the aggregate root:

```java
package com.ftgo.order.domain;

import org.springframework.data.repository.CrudRepository;
import org.springframework.stereotype.Repository;
import java.util.List;

@Repository
public interface OrderRepository extends CrudRepository<Order, Long> {
    List<Order> findByConsumerId(Long consumerId);
}
```

### 6. The Domain Service interface: `OrderService.java`

```java
package com.ftgo.order.service;

import com.ftgo.order.domain.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import java.util.List;

@Service
public class OrderService {

    @Autowired
    private OrderRepository orderRepository;

    @Transactional
    public Order createOrder(Long id, Long restaurantId, Long consumerId, 
                             DeliveryInformation deliveryInfo, Money orderMinimum, List<OrderLineItem> items) {
        
        // Construct aggregate root (enforcing internal entity invariants)
        Order order = new Order(id, restaurantId, consumerId, deliveryInfo, orderMinimum, items);
        
        // Save aggregate root (cascades automatically write child line items to DB)
        return orderRepository.save(order);
    }

    @Transactional
    public void approveOrder(Long orderId) {
        Order order = orderRepository.findById(orderId)
            .orElseThrow(() -> new IllegalArgumentException("Order not found: " + orderId));
        
        order.approve();
        orderRepository.save(order);
    }

    @Transactional
    public void cancelOrder(Long orderId) {
        Order order = orderRepository.findById(orderId)
            .orElseThrow(() -> new IllegalArgumentException("Order not found: " + orderId));
        
        order.cancel();
        orderRepository.save(order);
    }
}
```

---

## 11.8 Automatic Event Publishing: JPA Entity Lifecycle Listeners

Rather than manually invoking an event publisher inside the service class (which violates segregation of concerns and introduces risks of developers forgetting to publish), we can hook into Hibernate's entity database persistence transaction cycle using **JPA Lifecycle Listeners**:

```
[ Client ] --> [ OrderService ] 
                     |
                     v
             [ OrderRepository ]
                     |
                     v (ACID Transaction Commit)
             [ Hibernate Engine ] --( @PostPersist / @PostUpdate )
                     |                           |
                     | (Save Row)                v
                     |             [ DomainEventPublishingListener ]
                     v                           |
              { database row }                   v (Asynchronous message publish)
                                        [ Kafka / Event Bus ]
```

Let's write a complete Spring-integrated Lifecycle listener implementation:

```java
package com.ftgo.order.domain;

import com.ftgo.order.event.OrderCreatedEvent;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;
import javax.persistence.PostPersist;
import javax.persistence.PostUpdate;

@Component
public class DomainEventPublishingListener {

    private static ApplicationEventPublisher eventPublisher;

    @Autowired
    public void setEventPublisher(ApplicationEventPublisher publisher) {
        // Wire Spring's event bus statically to allow the JPA listener access
        DomainEventPublishingListener.eventPublisher = publisher;
    }

    @PostPersist
    public void onPostPersist(Order order) {
        if (eventPublisher != null) {
            // Automatically compile and publish domain event during database inserts
            eventPublisher.publishEvent(new OrderCreatedEvent(
                order.getLineItems(),
                order.getRestaurantId(),
                order.getOrderTotal().getAmount()
            ));
        }
    }

    @PostUpdate
    public void onPostUpdate(Order order) {
        if (eventPublisher != null && order.getState() == OrderState.CANCELLED) {
            // Automatically notify system if the order was cancelled
            eventPublisher.publishEvent(new OrderCreatedEvent(
                order.getLineItems(),
                order.getRestaurantId(),
                order.getOrderTotal().getAmount()
            ));
        }
    }
}
```

This guarantees domain events are published automatically during database commits, preventing business logic and event propagation from diverging.

---

## 11.7 Procedural Logic: The Transaction Script Pattern

For simple services that contain minimal business logic, implementing complex DDD aggregates is unnecessary overhead. In these scenarios, developers employ the **Transaction Script** pattern.

A Transaction Script executes a procedural series of queries, calculations, and DTO updates directly inside a service layer method:

```java
package com.ftgo.order.service;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class OrderTransactionScriptService {

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @Transactional
    public void createOrderScript(Long consumerId, Long restaurantId, double totalAmount) {
        // 1. Procedural validation checks
        boolean isAuthorized = jdbcTemplate.queryForObject(
            "SELECT authorized FROM consumers WHERE id = ?",
            Boolean.class,
            consumerId
        );
        if (!isAuthorized) {
            throw new IllegalArgumentException("Consumer is not authorized!");
        }

        // 2. Direct INSERT queries instead of object model states
        jdbcTemplate.update(
            "INSERT INTO orders (consumer_id, restaurant_id, total, state) VALUES (?, ?, ?, 'PENDING')",
            consumerId, restaurantId, totalAmount
        );

        // 3. Procedural messaging side-effects
        System.out.println("Saga trigger message dispatched procedural logic.");
    }
}
```

---

## 11.8 Domain Event Enrichment Strategy

When designing event-driven microservices, we balance two domain event payload models:

### 1. Minimal Domain Events
The event contains only identifiers (like `orderId`). 
* **Pros**: Small message size, event schema rarely changes.
* **Cons**: Downstream services (like Delivery Service) must call back the Order Service via REST APIs to retrieve order details, adding network calls.

```java
package com.ftgo.order.event;

public class MinimalOrderCreatedEvent {
    private final Long orderId;

    public MinimalOrderCreatedEvent(Long orderId) {
        this.orderId = orderId;
    }

    public Long getOrderId() { return orderId; }
}
```

### 2. Enriched Domain Events
The event contains all entity details needed by downstream consumers (like total price, line items, and addresses).
* **Pros**: Eliminates the need for API callbacks. Consumers can maintain local state copies directly.
* **Cons**: Larger message size. Changes to child entity models require updating event schemas.

```java
package com.ftgo.order.event;

import java.util.List;

public class EnrichedOrderCreatedEvent {
    private final Long orderId;
    private final Long consumerId;
    private final List<String> items;
    private final double totalAmount;

    public EnrichedOrderCreatedEvent(Long orderId, Long consumerId, List<String> items, double totalAmount) {
        this.orderId = orderId;
        this.consumerId = consumerId;
        this.items = items;
        this.totalAmount = totalAmount;
    }

    public Long getOrderId() { return orderId; }
    public Long getConsumerId() { return consumerId; }
    public List<String> getItems() { return items; }
    public double getTotalAmount() { return totalAmount; }
}
```

---

---

## 11.10 Strategic Bounded Context Integration: Context Mapping Patterns

To prevent domain models from leaking and coupling services together, DDD defines strategic **Context Mapping** patterns:

* **Shared Kernel**: Services share a subset of the database schema and domain objects. This creates extreme coupling and is generally avoided in microservices.
* **Customer-Supplier**: Upstream service (Supplier) must coordinate change schedules with downstream services (Customer).
* **Conformist**: Downstream service accepts the upstream service's domain model as-is, conforming completely.
* **Anticorruption Layer (ACL)**: Downstream service implements a translation layer to isolate its clean domain model from upstream model modifications, shielding it from external churn.

---

## 11.11 Implementing an Anticorruption Layer (ACL) in Java

The `Order Service` downstream system receives raw vendor catalog updates from a legacy system. We implement an ACL Translator to sanitize and map this incoming JSON payload into our domain Value Objects (`Money`) before triggering aggregate behaviors:

```java
package com.ftgo.order.acl;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.ftgo.order.domain.Money;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

@Component
public class RestaurantCatalogACLTranslator {

    @Autowired
    private ObjectMapper objectMapper;

    public Money translateLegacyPrice(String rawJsonPayload) {
        try {
            JsonNode root = objectMapper.readTree(rawJsonPayload);
            
            // Legacy payload uses "price_in_cents" format: e.g. 1599
            if (root.has("price_in_cents")) {
                double cents = root.get("price_in_cents").asDouble();
                double dollars = cents / 100.0;
                
                // Return clean, immutable domain Value Object
                return new Money(dollars);
            }
            throw new IllegalArgumentException("Invalid legacy payload structure!");
        } catch (Exception ex) {
            throw new IllegalStateException("ACL Translation failure!", ex);
        }
    }
}
```

---

## 11.12 Optimistic Locking Conflicts and Automated Retry Aspects

When multiple concurrent requests attempt to mutate the same aggregate root instance, Hibernate throws a `javax.persistence.OptimisticLockException` because version tags mismatch on update commits.

Rather than returning error messages to users, we implement an automated **Aspect-oriented retry template** to intercept and retry these calls:

```java
package com.ftgo.order.resilience;

import org.aspectj.lang.ProceedingJoinPoint;
import org.aspectj.lang.annotation.Around;
import org.aspectj.lang.annotation.Aspect;
import org.springframework.dao.ConcurrencyFailureException;
import org.springframework.stereotype.Component;

import javax.persistence.OptimisticLockException;

@Aspect
@Component
public class OptimisticLockRetryAspect {

    private static final int MAX_RETRIES = 3;

    @Around("@annotation(com.ftgo.order.resilience.RetryOnConcurrencyFailure)")
    public Object retryOnFailure(ProceedingJoinPoint joinPoint) throws Throwable {
        int attempt = 0;
        while (true) {
            try {
                return joinPoint.proceed();
            } catch (Exception ex) {
                // Catch JPA Optimistic Lock exceptions or Spring's wrapped Concurrency Failures
                if (ex instanceof OptimisticLockException || ex instanceof ConcurrencyFailureException) {
                    attempt++;
                    if (attempt >= MAX_RETRIES) {
                        throw ex; // Retries exhausted, bubble error
                    }
                    System.out.println("Optimistic lock conflict detected. Retrying execution attempt: " + attempt);
                    // Introduce a small randomized backoff delay
                    Thread.sleep(100 + (long) (Math.random() * 200));
                } else {
                    throw ex; // Re-throw other business exceptions immediately
                }
            }
        }
    }
}
```

---


---


## 11.13 Summary of Domain-Driven Design and Aggregate Patterns

This table summarizes the configurations, rules, and patterns used to implement aggregates:

| Aggregate Element | Term / Config | Main Implementation Target | Scope Location |
| :--- | :--- | :--- | :--- |
| **Aggregate Root** | `Order` entity | Orchestrates all mutations to child entities. | Domain Layer |
| **Value Object** | `Money` type | Immutable attributes with zero identifiers. | Domain Layer |
| **Identifier Reference**| `RestaurantId` | Decouples relational mapping across DBs. | JPA Columns |
| **Transaction Boundary**| Single Aggregate Root | Prevents locks spanning multiple service tables. | Service Layer |
| **State Verification** | `@Version` annotation | Detects concurrent update clashes on flush. | Entity Columns |
| **Lifecycle Hook** | `@PostPersist` | Emits domain events automatically on commit. | JPA Listener |
| **Event Enrichment** | `EnrichedOrderCreated` | Includes full payload to reduce callbacks. | Messaging Event |

---

## Chapter Summary

* Monolithic domain models with highly coupled object graphs lead to distributed locks and unscalable joins.
* **Domain-Driven Design (DDD)** organizes logic using **Entities** (identity-based), **Value Objects** (immutable), and **Aggregates** (reusable lifecycle groups).
* Aggregates follow three strict rules: reference by identity only, limit transactions to a single aggregate root, and update child entities exclusively through root public methods.
* Apply **Transaction Scripts** for procedural CRUD operations, and **Domain Models** for complex business logic validation.
* Balance event-driven communications between minimal payloads (less coupling) and enriched payloads (eliminates API callbacks).
* Shield domain models from external changes by implementing an **Anticorruption Layer (ACL)** translation.
* Enforce optimistic concurrency control using JPA `@Version` tags and resolve conflicts automatically using AOP retry aspects.
* Automate domain events dispatch using JPA Lifecycle Listeners inside database commit boundaries.
