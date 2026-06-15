# Module 11 — Saga Pattern

In this module, we will explore the Saga Pattern. We will discuss the challenges of distributed transactions in microservices and look at Choreography-based vs. Orchestration-based Saga architectures. We will cover compensating events and error recovery. Finally, we will cover troubleshooting, answer 5 Socratic questions, and implement hands-on labs with complete code structures.

---

## 1. Academic Lecture: Saga Architectures, Compensating Transactions & Distributed Flows

### Basic Level: Distributed Transactions & Saga Introduction

#### Why 2PC (Two-Phase Commit) Fails in Microservices
In monolithic architectures, maintaining consistency is simple because we have database transactions. 
* **The Problem**: In a microservice mesh, each service has its own database (e.g., `OrderService` has MySQL, `PaymentService` has Postgres). Standard distributed transactions (like Two-Phase Commit or XA transactions) require locking databases during the coordination phase. This slows down processing, creates single points of failure, and does not scale in modern containerized networks.
* **The Solution**: Use the **Saga Pattern**. A Saga is a sequence of local transactions. Each transaction updates database state within a single service. If a step fails, the Saga runs compensating transactions to undo the changes made by preceding steps.

```text
  [ Order Service ] ──(Local Tx 1)──► [ Payment Service ] ──(Local Tx 2)──► [ Inventory Service ]
         │                                   │                                     │
         └◄──────(Compensating Tx 1)─────────┴◄────────(Compensating Tx 2)─────────┘
```

---

### Intermediate Level: Choreography vs. Orchestration Sagas

There are two primary architectures for designing Sagas:

#### 1. Choreography-based Saga (Event-Driven)
In Choreography, there is no central controller. Each service listens for events from other services and decides when to execute its local transactions.
* **Flow**:
  1. `OrderService` creates an order and publishes `OrderCreated`.
  2. `PaymentService` consumes `OrderCreated`, processes payment, and publishes `PaymentAuthorized`.
  3. `InventoryService` consumes `PaymentAuthorized`, reserves stock, and publishes `StockReserved`.
* *Pros*: Simple to start; loose coupling.
* *Cons*: Difficult to track workflow status; risk of circular dependency loops.

#### 2. Orchestration-based Saga (Command-Driven)
In Orchestration, a central controller class (called the **Saga Orchestrator**) coordinates the workflow. It sends command messages to services and handles their success/failure responses.
* **Flow**:
  1. `OrderService` tells the `SagaOrchestrator` to begin.
  2. The Orchestrator publishes a `ProcessPayment` command.
  3. `PaymentService` completes payment and replies with `PaymentSuccess`.
  4. The Orchestrator publishes a `ReserveStock` command.
* *Pros*: Single point of monitoring; workflow logic is centralized.
* *Cons*: Single point of failure; tighter coupling.

---

### Advanced Level: Compensation Events & Idempotency

#### Compensating Transactions
A compensating transaction is a step that programmatically reverses a previous local transaction.
* **Important distinction**: It is *not* a database rollback. The previous transaction was already committed. A compensating transaction is a new database insert or update that logically cancels the original action (e.g., if a transaction charged $50, the compensating action issues a $50 refund).

#### Idempotency Requirements
Since Sagas rely on network messaging (which guarantees At-Least-Once delivery), services will receive duplicate commands or compensation events.
* **Fix**: Every service must track transaction IDs (Saga IDs) in its database. If a service receives a `RefundPayment` command but the database shows the refund was already processed, the service must skip processing and reply with success to prevent double refunding.

---

## 2. Theory & Production Best Practices

### Choreography vs. Orchestration Saga

| Dimension | Choreography (Event-Driven) | Orchestration (Command-Driven) |
| :--- | :--- | :--- |
| **Workflow Logic** | Distributed across services | Centralized in one Orchestrator |
| **Coupling** | Loose (services only know events) | Tighter (orchestrator knows all endpoints) |
| **Circular Loops Risk**| High | None |
| **Complexity** | Low for 2-3 services | Low for complex high-step flows |

### Local DB Rollbacks vs. Compensating Transactions

| Aspect | Local Database Rollback | Saga Compensating Transaction |
| :--- | :--- | :--- |
| **Scope** | Single database session | Across multiple microservices |
| **Execution** | Automatic (handled by DB engine) | Programmatic (handled by application code) |
| **Committed States?** | No. Intermediate state is hidden. | Yes. Intermediate states are visible. |

---

## 3. Common Errors & Troubleshooting

### 1. Circular Dependency Event Loops
* **Symptom**: Infinite event loop occurs between services, overloading Kafka brokers.
* **Root Cause**: In Choreography, `Service A` publishes `Event X`, which triggers `Service B` to publish `Event Y`, which accidentally triggers `Service A` to publish `Event X` again.
* **Fix**: Use Orchestration to manage complex workflows, or enforce unidirectional event flows.

### 2. Compensation Fails Due to Target Service Outage
* **Symptom**: System state is left inconsistent (e.g., inventory reservation failed, but refund fails because `PaymentService` database is down).
* **Root Cause**: The network or database for a compensating step is offline.
* **Fix**:
  * Implement retry topics for compensating commands.
  * Use dead-letter topics with alerts to notify operators for manual review.

### 3. Out-of-Order Compensation Events
* **Symptom**: A compensating event (e.g., `CancelReservation`) arrives before the primary event (`ReserveStock`) has been processed.
* **Root Cause**: Message delays or consumer concurrency caused the cancellation to overtake the reservation.
* **Fix**: If a cancellation is received for a transaction that does not exist in the database, write a "Cancel Marker" record to the database first. When the reservation event eventually arrives, check for the marker and skip processing.

---

## 4. Socratic Review Questions

### Question 1
*Why is a compensating transaction NOT the same as a database rollback?*
* **Answer**: Because a database rollback undoes uncommitted data changes inside a single database session. In a Saga, each local transaction commits immediately. A compensating transaction is a *new, separate commit* that logically reverses the business effect of the previously committed transaction.

### Question 2
*How does an orchestrator track the current state of a multi-step Saga during service crashes?*
* **Answer**: The orchestrator must persist its state to a local database (a "Saga Log") before sending any command. When it recovers from a crash, it reads the log to see which commands were sent and resumes from that step.

### Question 3
*What is the "Semantic Lock" countermeasure in Sagas, and why is it needed?*
* **Answer**: Since Sagas commit local transactions early, intermediate states are visible to other transactions. A semantic lock marks updated data (e.g., setting account balance status to `PENDING_DECISION`) so other services know the value is dirty and cannot alter it until the Saga completes.

### Question 4
*What is the main drawback of Choreography-based Sagas as the number of microservices increases?*
* **Answer**: Debugging and dependency mapping. Since there is no central orchestrator, tracing the execution path of a transaction across 20 services requires parsing logs from all 20 containers. It also increases the risk of circular loops.

### Question 5
*How can we use Kafka partition keys to ensure Saga steps do not suffer from race conditions?*
* **Answer**: Use the unique Saga ID (e.g., `sagaId` or `orderId`) as the Kafka partition key for all commands and events. This guarantees all steps for a single transaction are processed by the same consumer partition in chronological order.

---

## 5. Hands-on Labs

### Lab 11.1 — Choreography Listener Flow

#### Scenario
We will configure choreography listeners for an order workflow. `PaymentService` listens for `OrderCreated`, and `InventoryService` listens for `PaymentAuthorized`.

#### Complete Choreography Java Code
Create the file [ChoreographyServices.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/src/main/java/com/springkafka/course/consumer/ChoreographyServices.java) with the following content:

```java
package com.springkafka.course.consumer;

import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Service;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

@Service
public class ChoreographyServices {
    private static final Logger log = LoggerFactory.getLogger(ChoreographyServices.class);

    private final KafkaTemplate<String, String> kafkaTemplate;

    public ChoreographyServices(KafkaTemplate<String, String> kafkaTemplate) {
        this.kafkaTemplate = kafkaTemplate;
    }

    // 1. Payment Service Listener
    @KafkaListener(id = "choreography-payment", topics = "order-created")
    public void handleOrderCreated(String orderJson) {
        log.info("PAYMENT SERVICE -> Received OrderCreated: {}. Authorizing funds...", orderJson);
        
        // Simulate payment success
        String paymentEvent = "{\"orderId\":\"123\",\"status\":\"PAID\"}";
        log.info("PAYMENT SERVICE -> Payment successful. Publishing PaymentAuthorized.");
        kafkaTemplate.send("payment-authorized", "123", paymentEvent);
    }

    // 2. Inventory Service Listener
    @KafkaListener(id = "choreography-inventory", topics = "payment-authorized")
    public void handlePaymentAuthorized(String paymentJson) {
        log.info("INVENTORY SERVICE -> Received PaymentAuthorized: {}. Reserving stock...", paymentJson);
        
        // Simulate inventory success
        String inventoryEvent = "{\"orderId\":\"123\",\"status\":\"RESERVED\"}";
        log.info("INVENTORY SERVICE -> Stock reserved. Publishing StockReserved.");
        kafkaTemplate.send("stock-reserved", "123", inventoryEvent);
    }
}
```

---

### Lab 11.2 — Orchestration Saga Coordinator

#### Scenario
We will write a centralized `SagaOrchestrator` service that coordinates an order workflow by publishing commands and tracking responses.

#### Complete Orchestrator Java Code
Create the file [SagaOrchestrator.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/src/main/java/com/springkafka/course/service/SagaOrchestrator.java) with the following content:

```java
package com.springkafka.course.service;

import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Service;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

@Service
public class SagaOrchestrator {
    private static final Logger log = LoggerFactory.getLogger(SagaOrchestrator.class);

    private final KafkaTemplate<String, String> kafkaTemplate;

    public SagaOrchestrator(KafkaTemplate<String, String> kafkaTemplate) {
        this.kafkaTemplate = kafkaTemplate;
    }

    // 1. Start Saga workflow
    public void startSaga(String orderId, String payload) {
        log.info("ORCHESTRATOR -> Starting Saga ID: {}", orderId);
        
        // Persist Saga status locally to DB (Saga Log)
        log.info("ORCHESTRATOR -> Saga Log updated: State=PAYMENT_PENDING");
        
        // Send command to Payment Service
        kafkaTemplate.send("payment-commands", orderId, "CHARGE_CARD:" + payload);
    }

    // 2. Listen for replies from Payment Service
    @KafkaListener(id = "orch-payment-replies", topics = "payment-replies")
    public void handlePaymentReply(String reply) {
        String[] parts = reply.split(":");
        String orderId = parts[0];
        String status = parts[1];

        if ("SUCCESS".equals(status)) {
            log.info("ORCHESTRATOR -> Payment succeeded. Transitioning to STOCK_PENDING.");
            // Send command to Inventory Service
            kafkaTemplate.send("inventory-commands", orderId, "RESERVE_STOCK");
        } else {
            log.error("ORCHESTRATOR -> Payment failed. Starting compensating transaction refund flow.");
            startCompensation(orderId);
        }
    }

    private void startCompensation(String orderId) {
        log.warn("ORCHESTRATOR -> Triggering Compensation refund events for Saga ID: {}", orderId);
        kafkaTemplate.send("payment-commands", orderId, "REFUND_CARD");
    }
}
```

---

### Lab 11.3 — Compensating Refund Workflow

#### Scenario
We will implement the compensating action handler inside `PaymentService` that reverses a card charge when receiving a `REFUND_CARD` command.

#### Complete Payment Compensation Java Code
Create the file [PaymentCompensationService.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/src/main/java/com/springkafka/course/service/PaymentCompensationService.java) with the following content:

```java
package com.springkafka.course.service;

import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Service;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

@Service
public class PaymentCompensationService {
    private static final Logger log = LoggerFactory.getLogger(PaymentCompensationService.class);

    private final KafkaTemplate<String, String> kafkaTemplate;

    public PaymentCompensationService(KafkaTemplate<String, String> kafkaTemplate) {
        this.kafkaTemplate = kafkaTemplate;
    }

    // 1. Process payment commands including compensations
    @KafkaListener(id = "payment-cmd-consumer", topics = "payment-commands")
    public void handlePaymentCommand(String commandMessage) {
        String[] parts = commandMessage.split(":");
        String command = parts[0];
        
        if ("REFUND_CARD".equals(command)) {
            log.warn("PAYMENT COMPENSATION -> REFUND_CARD command received.");
            
            // Execute refund logic (e.g. call Stripe API / update database)
            executeRefund();
            
            log.info("PAYMENT COMPENSATION -> Refund completed. Sending confirmation.");
            kafkaTemplate.send("payment-replies", "123", "123:REFUNDED");
        } else {
            log.info("PAYMENT SERVICE -> Processing default charge card command...");
        }
    }

    private void executeRefund() {
        log.info("Database record updated: Account credited +$50.00.");
    }
}
```

---

### Step-by-Step Code Walkthrough & Parameter Configuration Tables

#### Step-by-Step Code Walkthrough

##### Lab 11.1 Walkthrough
1. **Choreography Flow**: There is no orchestrator. `PaymentService` and `InventoryService` listen for event triggers directly. Each service executes its business rules and publishes events.

##### Lab 11.2 Walkthrough
1. **`SagaOrchestrator`**: Coordinates the steps. It uses command topics (`payment-commands`, `inventory-commands`) to direct action and reply topics to receive responses.
2. **`startCompensation`**: Triggered when a step fails. It issues commands to undo previously completed steps.

##### Lab 11.3 Walkthrough
1. **Compensating Command**: The service monitors `payment-commands` for the compensation action `"REFUND_CARD"` and runs the database credit logic to reverse the transaction.

---

### Configuration Parameter Tables

#### Saga Pattern Architecture Terminology

| Term | Category | Description |
| :--- | :--- | :--- |
| **Saga Log** | Database | A database table managed by the Orchestrator to track the active status of each Saga transaction. |
| **Compensating Transaction**| Application | A transaction step that undoes the business impact of a previously completed step. |
| **Saga ID** | Header / Payload | A unique ID carried in all events and commands to correlate steps across microservices. |
| **Local Transaction** | Database | A standard database ACID transaction executed within the boundary of a single service. |

