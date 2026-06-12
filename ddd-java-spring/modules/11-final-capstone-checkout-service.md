# Module 11: Capstone — Hardening the E-Commerce Checkout Aggregate

Welcome to your **Final Capstone Project**, class.

You have studiedstrategic boundaries, context mapping, value objects, entities, aggregate root encapsulation, stateless domain services, eventual consistency via domain events, persistence mapping adapters, and ports-and-adapters architecture. Now, it is time to bring these concepts together to build a secure, decoupled, production-ready **Checkout Service** using Domain-Driven Design (DDD).

Today we will review the system design for a distributed e-commerce checkout flow, discuss architectural boundaries, and complete a hands-on coding challenge to implement aggregate invariants and ports in Java.

---

## 1. Academic Lecture: Architectural Synthesis

In high-scale e-commerce architectures, the checkout process is a critical core subdomain. It must be isolated from the complexities of catalog searches, inventory tracking, shipping calculations, and email notification systems.

```
       Capstone Hexagonal Checkout Architecture
       
       +--------------------------------------------+
       | Infrastructure Adapters (Controllers, DB)  |
       |                                            |
       |   +------------------------------------+   |
       |   | Ports (Inbound/Outbound)          |   |
       |   |                                   |   |
       |   |   +---------------------------+   |   |
       |   |   | Core Domain: Checkout     |   |   |
       |   |   | (Aggregate Root, Events)  |   |   |
       |   |   +---------------------------+   |   |
       |   +-----------------------------------+   |
       +--------------------------------------------+
(The Checkout aggregate root enforces all rules.
 Web controllers and JPA repositories plug in as adapters.)
```

### The Invariants of the Checkout Aggregate
An e-commerce checkout flow must enforce strict business constraints:
*   **State Integrity**: Once a checkout is marked as `COMPLETED` or `CANCELLED`, no further items can be added, and the shipping address cannot be modified.
*   **Monetary Precision**: Money calculations (tax, shipping, subtotal, discounts) must use Value Objects with matching currencies to prevent precision issues.
*   **Verification Invariants**: A checkout cannot transition to `COMPLETED` unless it contains at least one item, has a valid shipping address, and has a positive total amount.

---

## 2. Theory vs. Production Trade-offs

### Rich Aggregates vs. Orchestrated Application Logic
*   **Rich Aggregate Pattern**: Place all validation checks (e.g., checking if the checkout is already paid, calculating discounts) directly in the `Checkout` class.
    *   *Pro*: Business logic is encapsulated in the domain model, making it easy to test and review.
    *   *Con*: The aggregate root cannot query the database directly. If a check requires database validation (e.g., verifying if a promo code exists in the database), the service layer must retrieve the validation data and pass it into the aggregate.
*   **Production Rule**: Keep the aggregate focused on validating its internal state. Retrieve external data (like catalog availability or coupon validation) in the Application Service, and pass the resolved values into the aggregate root's methods.

---

## 3. How to Use: The Hardened E-Commerce Hexagon

Let us trace a production-ready implementation of the `CheckoutCompletedEvent` and the `Checkout` aggregate root boundary.

### A. The Core Domain Event

```java
package com.capstone.security.capstone.domain;

import java.time.Instant;
import java.util.UUID;

public record CheckoutCompletedEvent(
    UUID checkoutId,
    UUID customerId,
    double totalAmount,
    Instant occurredAt
) {
    public CheckoutCompletedEvent(UUID checkoutId, UUID customerId, double totalAmount) {
        this(checkoutId, customerId, totalAmount, Instant.now());
    }
}
```

### B. The Outbound Port Interfaces

Defined in the `ports/outbound/` directory:

```java
package com.capstone.security.capstone.ports.outbound;

import com.capstone.security.capstone.domain.Checkout;

public interface CheckoutRepositoryPort {
    Checkout load(java.util.UUID checkoutId);
    void save(Checkout checkout);
}
```

```java
package com.capstone.security.capstone.ports.outbound;

import com.capstone.security.capstone.domain.CheckoutCompletedEvent;

public interface EventPublisherPort {
    void publish(CheckoutCompletedEvent event);
}
```

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Modifying Aggregate State directly from Application Services
Application services bypassing the aggregate root's methods and updating fields directly (e.g., `checkout.setStatus("PAID")`).
*   **Why it fails**: This turns the aggregate into an anemic data holder. The service layer is forced to manage the business rules, leading to duplication and potential consistency bugs.
*   **Mitigation**: Set mutable fields to `private` access and expose only expressive business methods (like `completeCheckout()`) that update internal state.

---

## 5. Socratic Review Questions

### Question 1
Explain why checking business constraints in a REST controller (e.g., verifying that an item list is not empty using Spring's `@NotEmpty` validation annotation) is insufficient for enforcing domain invariants.

#### Answer
REST controllers are inbound adapters. Checking values at the controller layer ensures the HTTP request is formatted correctly, but does not protect the core application. 
If another entry point is added (like a message consumer or a scheduled task runner), those components will bypass the controller's validation rules. Domain invariants must be enforced in the core **Domain Entities** to ensure they are validated regardless of how the request enters the system.

### Question 2
How does the Outbox Pattern protect an e-commerce checkout service from failing when external payment or notification systems go down?

#### Answer
When checkout is completed, we save the updated state and the `CheckoutCompleted` event to the database in a single transaction. 
If the external notification system is offline, the transaction still completes successfully, and the user receives a confirmation screen. The background outbox worker will continually retry sending the event until the notification system recovers, ensuring eventual consistency.

---

## 6. Hands-on Challenge: Implementing the Checkout Aggregate Root

### The Challenge
In this final capstone challenge, you will implement the core business logic of the `Checkout` aggregate root.

Your task is to implement the `Checkout` aggregate root class:
1.  Enforce that items cannot be added, and shipping address cannot be modified, if the checkout is already in the `COMPLETED` state.
2.  Implement `addItem(UUID productId, int qty, double price)`.
3.  Implement `completeCheckout()`. Enforce that checkout can only complete if:
    - The shipping address is present.
    - There is at least one item in the checkout list.
    - The status transitions to `COMPLETED`.
4.  Generate and track a `CheckoutCompletedEvent` inside the aggregate when it is completed.

Complete the implementation below:

```java
package com.capstone.security.capstone.challenge;

import com.capstone.security.valueobject.secure.Money;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.UUID;

public class Checkout {
    public enum Status { NEW, COMPLETED }

    private final UUID checkoutId;
    private final UUID customerId;
    
    private final List<CheckoutItem> items;
    private String shippingAddress;
    private Status status;
    private final List<Object> domainEvents = new ArrayList<>();

    public Checkout(UUID checkoutId, UUID customerId) {
        this.checkoutId = java.util.Objects.requireNonNull(checkoutId);
        this.customerId = java.util.Objects.requireNonNull(customerId);
        this.items = new ArrayList<>();
        this.status = Status.NEW;
    }

    /**
     * Sets the shipping address.
     * Enforces that modifications are blocked if the status is COMPLETED.
     */
    public void setShippingAddress(String address) {
        if (status == Status.COMPLETED) {
            throw new IllegalStateException("Cannot update address on completed checkouts.");
        }
        this.shippingAddress = address;
    }

    // TODO: Implement checkout business operations.
    // 1. Implement public void addItem(UUID productId, int qty, double price):
    //    - Throw IllegalStateException if status is COMPLETED.
    //    - Verify qty is > 0 and price is > 0.0.
    //    - Instantiate and append a new CheckoutItem.
    // 2. Implement public void completeCheckout():
    //    - Throw IllegalStateException if status is already COMPLETED.
    //    - Verify shippingAddress is not null or blank.
    //    - Verify items list is not empty.
    //    - Set status = Status.COMPLETED.
    //    - Calculate total amount = sum of (item.qty * item.price).
    //    - Add a new CheckoutCompletedEvent(checkoutId, customerId, totalAmount) to domainEvents list.

    public UUID getCheckoutId() { return checkoutId; }
    public UUID getCustomerId() { return customerId; }
    public String getShippingAddress() { return shippingAddress; }
    public Status getStatus() { return status; }
    
    public List<CheckoutItem> getItems() {
        return Collections.unmodifiableList(items);
    }

    public List<Object> getDomainEvents() {
        return Collections.unmodifiableList(domainEvents);
    }

    public void clearDomainEvents() {
        this.domainEvents.clear();
    }
}
```

Write the aggregate validation logic. Save your completed code and outline your unit testing strategy using JUnit and Mockito mocks for verification inside `modules/11-final-capstone-checkout-service.md`.
