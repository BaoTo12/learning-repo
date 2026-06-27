# Chapter 9: Saga Transactions: Choreography and Orchestration

Maintaining data consistency across multiple databases is a major challenge in a microservices architecture. In this environment, traditional distributed transactions (2-Phase Commit / XA) are not viable due to locking overhead and dependency constraints. To maintain consistency at scale, we use the **Saga Pattern**. A saga coordinates a series of local transactions across services using asynchronous messages.

This chapter covers the conceptual and technical implementation of the Saga pattern. We will examine the mechanics of sagas and compare **Choreography-based** (decentralized) and **Orchestration-based** (centralized) coordination models. We will implement compensating transactions to roll back changes, analyze the structure of the Create Order Saga using both coordination styles, and write a functional saga orchestrator in Java.

---

## Learning Objectives

By the end of this chapter, you will be able to:
1. Explain why traditional distributed transactions (2PC) fail in modern microservices.
2. Outline the lifecycle of a saga and explain how it coordinates local transactions.
3. Design **Compensating Transactions** to roll back changes when a step fails.
4. Classify the three types of transactions in a saga: compensatable, pivot, and retriable.
5. Implement a **Choreography-based Saga** using asynchronous events.
6. Implement an **Orchestration-based Saga** using a centralized orchestrator state machine.
7. Write a functional **Saga Orchestrator** in Java using message channels.

---

## 9.1 Sagas: Maintaining Data Consistency Without Distributed Transactions

In a monolithic application, maintaining data consistency is handled by local database transactions. In a microservices architecture, however, data is scattered across multiple databases:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//7bb20bdd-5007-4287-88e2-85e2fde7cfb8/markdown_2/imgs/img_in_image_box_200_103_930_727.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A55%3A45Z%2F-1%2F%2Fadce4705956ebce0b346c0d794e09522621db5c98ee485c1bb047d06fa751ca6" alt="Image" width="68%" /></div>
<div style="text-align: center;">Figure 4.1: The createOrder() operation updates data in several services. It must use a mechanism to maintain data consistency across those services.</div>

Because SQL queries and transactional locks cannot span network boundaries, the application must coordinate transaction steps manually.

---

### The Saga Pattern Model
A saga coordinates a series of local transactions. Each step executes a local transaction, updates its local database, and publishes a message to trigger the next step:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//7bb20bdd-5007-4287-88e2-85e2fde7cfb8/markdown_4/imgs/img_in_image_box_203_106_926_416.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A55%3A46Z%2F-1%2F%2F270b79ae71a2968a0a21f220014bf00b8655070ac020088a4e82975c3faa854b" alt="Image" width="68%" /></div>
<div style="text-align: center;">Figure 4.2: Creating an Order using a saga. The createOrder() operation is implemented by a saga that consists of local transactions in several services.</div>

---

### Sagas vs. ACID Transactions
Sagas differ from standard ACID database transactions in key ways:
* **Isolation (Lack thereof)**: Sagas are ACD (Atomicity, Consistency, Durability) and lack **Isolation**. Each local transaction commits its changes immediately. Intermediate states are visible to concurrent transactions, which can introduce concurrency anomalies.
* **Rollback via Compensation**: Sagas cannot roll back updates automatically. If a step fails, the saga must execute compensating transactions in reverse order to undo updates made by previous steps:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//9ff028d7-cd7e-4721-a366-f9424c4a53a3/markdown_0/imgs/img_in_image_box_184_335_910_585.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A55%3A43Z%2F-1%2F%2Fc5e86944991bd3b194528070283b34134f793936ffe9b1f82b55811fa6d364d9" alt="Image" width="68%" /></div>
<div style="text-align: center;">Figure 4.3: When a step of a saga fails because of a business rule violation, the saga must explicitly undo the updates made by previous steps by executing compensating transactions.</div>

---

### Classification of Saga Transactions
We classify the local transactions in a saga into three categories:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//eede2155-2455-4a18-b633-99214ad6b8d6/markdown_3/imgs/img_in_image_box_202_239_927_583.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A55%3A38Z%2F-1%2F%2F49e1c4d7f4b399808e1b76490001b509ce267f04b6d71e5866756e1e959e64f2" alt="Image" width="68%" /></div>
<div style="text-align: center;">Figure 4.8: A saga consists of three different types of transactions: compensatable transactions, which can be rolled back, so have a compensating transaction, a pivot transaction, which is the saga's go/no-go point, and retriable transactions, which are transactions that don't need to be rolled back and are guaranteed to complete.</div>

1. **Compensatable Transactions**: Transactions that can be rolled back using compensating transactions (e.g., creating a pending order).
2. **Pivot Transaction**: The decision point of the saga. If the pivot transaction commits, the saga will run to completion. If it fails, the saga executes compensating transactions to roll back the previous steps.
3. **Retriable Transactions**: Transactions that occur after the pivot transaction and are guaranteed to succeed, retrying indefinitely if they fail due to transient errors (e.g. approving the order).

---

### The Create Order Saga Steps
Let's analyze the forward and compensating steps of the Create Order Saga:

| Step | Service | Transaction (Forward) | Compensating Transaction (Undo) | Classification |
| :--- | :--- | :--- | :--- | :--- |
| **1** | Order Service | Create Order in `APPROVAL_PENDING` state. | Reject the Order (set state to `REJECTED`). | Compensatable |
| **2** | Consumer Service | Verify that the consumer is allowed to place orders. | None (Read-only query). | Compensatable |
| **3** | Kitchen Service | Validate order details and create a Ticket in `PENDING` state. | Reject the Ticket (set state to `REJECTED`). | Compensatable |
| **4** | Accounting Service | Authorize the consumer's credit card. | None (If this fails, the saga rolls back). | **Pivot Transaction** |
| **5** | Kitchen Service | Change the state of the Ticket to `ACCEPTED`. | None (Guaranteed to succeed). | Retriable |
| **6** | Order Service | Change the state of the Order to `APPROVED`. | None (Guaranteed to succeed). | Retriable |

If card authorization fails (Step 4), the saga executes compensating transactions to reject the ticket (Step 3) and the order (Step 1).

---

## 9.2 Coordination Styles: Choreography vs. Orchestration

Sagas are coordinated using one of two models: Choreography (decentralized) or Orchestration (centralized).

---

### 1. Choreography-Based Sagas (Decentralized)
Under the choreography model, services interact without a centralized point of control. Each service subscribes to events published by other services and executes its local transaction:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//9ff028d7-cd7e-4721-a366-f9424c4a53a3/markdown_2/imgs/img_in_image_box_112_596_931_1127.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A55%3A45Z%2F-1%2F%2Fbfc792d54c768a66c8006e501e62008c54210856fe5669130f3c13690e6a5b2e" alt="Image" width="77%" /></div>
<div style="text-align: center;">Figure 4.4: Implementing the Create Order Saga using choreography. The saga participants communicate by exchanging events.</div>

1. **Order Service** creates an order in `PENDING` state and publishes an `OrderCreated` event.
2. **Consumer Service** consumes the `OrderCreated` event, verifies the consumer, and publishes a `ConsumerVerified` event.
3. **Kitchen Service** consumes the `ConsumerVerified` event, validates the order, and publishes a `TicketCreated` event.
4. **Accounting Service** consumes the `TicketCreated` event, charges the credit card, and publishes a `CardAuthorized` event.
5. **Order Service** consumes the `CardAuthorized` event and changes the order state to `APPROVED`.

If credit card authorization fails, Accounting Service publishes a failure event to trigger compensations in reverse order:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//9ff028d7-cd7e-4721-a366-f9424c4a53a3/markdown_4/imgs/img_in_image_box_110_109_931_639.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A55%3A46Z%2F-1%2F%2F6cfdbe04c19b6d786ab2b68d5f660ba0139ddd1911bae6890c618e471ea54358" alt="Image" width="77%" /></div>
<div style="text-align: center;">Figure 4.5: The sequence of events in the Create Order Saga when the authorization of the consumer's credit card fails. Accounting Service publishes the Credit Card Authorization Failed event, which causes Kitchen Service to reject the Ticket, and Order Service to reject the Order.</div>

#### Interservice Choreography Handlers
Here is how a choreography-based event listener is implemented in the **Kitchen Service**:

```java
package com.ftgo.kitchen.messaging;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

@Component
public class KitchenChoreographyEventHandler {

    @Autowired
    private TicketService ticketService;

    @Autowired
    private EventPublisher eventPublisher;

    public void handleConsumerVerified(ConsumerVerifiedEvent event) {
        try {
            // Create a pending ticket in the database
            Ticket ticket = ticketService.createPendingTicket(event.getOrderId(), event.getLineItems());
            // Publish the success event to trigger the next step
            eventPublisher.publish(new TicketCreatedEvent(event.getOrderId(), ticket.getId()));
        } catch (Exception ex) {
            // Publish a failure event to trigger rollbacks
            eventPublisher.publish(new TicketReservationFailedEvent(event.getOrderId()));
        }
    }
}
```

#### Pros:
* **Simplicity**: Easy to implement for small, simple sagas.
* **Loose Coupling**: Services only interact by publishing and subscribing to events, without direct knowledge of other services' internals.

#### Cons:
* **Understanding Complexity**: It can be difficult to understand how a saga works because its logic is scattered across multiple services.
* **Cyclic Dependencies**: Services must subscribe to each other's events, which can introduce cyclic dependencies.
* **Tight Coupling**: Services must understand and subscribe to all events published by other participants.

---

### 2. Orchestration-Based Sagas (Centralized)
Under the orchestration model, you define a dedicated **Saga Orchestrator** class. The orchestrator acts as a state machine, sending command messages to saga participants and processing their replies:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//00553c34-873c-4d76-885d-14c596cc600d/markdown_1/imgs/img_in_image_box_188_457_910_1081.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A55%3A36Z%2F-1%2F%2F3e0c9ca43704324d2f08518c1350b26a67a06fc4d9377fc188c4fe1b9e54ae7e" alt="Image" width="67%" /></div>
<div style="text-align: center;">Figure 4.6: Implementing the Create Order Saga using orchestration. Order Service implements a saga orchestrator, which invokes the saga participants using asynchronous request/response.</div>

1. **Order Service** creates an order in `PENDING` state and instantiates the `CreateOrderSaga` orchestrator.
2. The orchestrator sends a `CreateTicket` command to the **Kitchen Service**.
3. **Kitchen Service** creates the ticket and returns a `TicketCreated` reply message.
4. The orchestrator receives the reply and sends an `AuthorizeCard` command to the **Accounting Service**.
5. **Accounting Service** authorizes the card and returns a `CardAuthorized` reply message.
6. The orchestrator sends an `AcceptTicket` command to the **Kitchen Service** and an `ApproveOrder` command to the **Order Service**.

#### Modeling Saga Orchestrators as State Machines
A saga orchestrator is defined as a state machine to cleanly manage all possible positive and rollback execution workflows:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//00553c34-873c-4d76-885d-14c596cc600d/markdown_3/imgs/img_in_image_box_106_109_933_753.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A55%3A39Z%2F-1%2F%2F1977274767f10a8520b80b815ec180ef9e4f9254662da0f428596e7b3ea0a173" alt="Image" width="77%" /></div>
<div style="text-align: center;">Figure 4.7: The state machine model for the Create Order Saga.</div>

#### Pros:
* **Centralized Logic**: The saga workflow is defined in a single class, making it easy to understand and maintain.
* **Reduced Coupling**: Saga participants only implement command handlers and return replies, without knowledge of the overall saga workflow.
* **No Cyclic Dependencies**: The orchestrator invokes participants, but participants do not invoke each other.

#### Cons:
* **Orchestrator Bloat**: There is a risk of concentrating too much business logic inside the orchestrator, turning it into a god class. Keep the orchestrator focused strictly on workflow coordination.

---

## 9.3 Implementing an Orchestration-Based Saga in Java

To implement sagas cleanly in Java, services employ a dedicated orchestrator design architecture:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//a08a4cfb-f234-4297-95b1-7a62217a38a1/markdown_1/imgs/img_in_image_box_105_422_931_1162.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A55%3A47Z%2F-1%2F%2F292aca18ce9bffdcc5a010ba47bac17c28029fd3d17d2623806bfa8889bca1b8" alt="Image" width="77%" /></div>
<div style="text-align: center;">Figure 4.9: The design of the Order Service and its sagas.</div>

The `OrderService` class is a domain service responsible for initiating the Order Saga manager:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//a08a4cfb-f234-4297-95b1-7a62217a38a1/markdown_2/imgs/img_in_image_box_202_795_764_1100.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A55%3A47Z%2F-1%2F%2Fad42539886cc286652b5a5d270b5fd489bb8fd16842a09bb5210a3f85e36cb9a" alt="Image" width="52%" /></div>
<div style="text-align: center;">Figure 4.10: OrderService creates and updates Orders, invokes the OrderRepository to persist Orders, and creates sagas, including the CreateOrderSaga.</div>

Orchestration frameworks (like Eventuate Tram Saga) coordinate interactions by defining a DSL for the state machine, mapping commands and replies to participant proxies:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//a08a4cfb-f234-4297-95b1-7a62217a38a1/markdown_4/imgs/img_in_image_box_199_113_930_888.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A55%3A48Z%2F-1%2F%2Fe363ca1d8647abaa8c3fa9623ee4b2864b25bf2d3b298b48a282d6845f422722" alt="Image" width="68%" /></div>
<div style="text-align: center;">Figure 4.11: The OrderService's sagas, such as Create Order Saga, are implemented using the Eventuate Tram Saga framework.</div>

The Orchestration engine relies on underlying transactional messaging abstractions:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//1c29baf5-3f77-465d-98e5-8e5de45c1bc6/markdown_4/imgs/img_in_image_box_183_228_912_822.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A55%3A47Z%2F-1%2F%2F38d26c999c6aae3555e152a0b568cd4d13eff603937383f139e38a32dbe61784" alt="Image" width="68%" /></div>
<div style="text-align: center;">Figure 4.12: Eventuate Tram Saga is a framework for writing both saga orchestrators and saga participants.</div>

### 1. The Saga State Representation
Define the states of the `CreateOrderSaga` orchestrator:

```java
package com.ftgo.order.saga;

public enum CreateOrderSagaState {
    CREATING_ORDER,
    RESERVING_TICKET,
    AUTHORIZING_CARD,
    CONFIRMING_TICKET,
    APPROVING_ORDER,
    REJECTING_TICKET,
    REJECTING_ORDER,
    SAGA_COMPLETED,
    SAGA_FAILED
}
```

---

### 2. The Saga Data Holder Class: `CreateOrderSagaData.java`
This POJO stores the state and variables of the running saga instance:

```java
package com.ftgo.order.saga;

import java.util.List;

public class CreateOrderSagaData {
    private String sagaId;
    private Long orderId;
    private Double amount;
    private List<String> lineItems;
    private CreateOrderSagaState state;

    public CreateOrderSagaData(String sagaId, Long orderId, Double amount, List<String> lineItems) {
        this.sagaId = sagaId;
        this.orderId = orderId;
        this.amount = amount;
        this.lineItems = lineItems;
        this.state = CreateOrderSagaState.CREATING_ORDER;
    }

    // Getters and Setters
    public String getSagaId() { return sagaId; }
    public Long getOrderId() { return orderId; }
    public Double getAmount() { return amount; }
    public List<String> getLineItems() { return lineItems; }
    public CreateOrderSagaState getState() { return state; }
    public void setState(CreateOrderSagaState state) { this.state = state; }
}
```

---

### 3. The Saga Orchestrator Class
Implement the orchestrator state machine, which manages the saga state and sends commands to services:

```java
package com.ftgo.order.saga;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

@Component
public class CreateOrderSagaOrchestrator {

    @Autowired
    private SagaMessageProducer producer;

    @Autowired
    private SagaRepository sagaRepository;

    @Transactional
    public void start(CreateOrderSagaData data) {
        // Initialize saga data and state
        data.setState(CreateOrderSagaState.RESERVING_TICKET);
        sagaRepository.save(data);

        // Send the first command to Kitchen Service
        producer.sendCommand(
            "kitchen-service-channel",
            data.getSagaId(),
            new CreateTicketCommand(data.getOrderId(), data.getLineItems())
        );
    }

    @Transactional
    public void handleReply(String sagaId, SagaReply reply) {
        CreateOrderSagaData data = sagaRepository.findById(sagaId);
        
        switch (data.getState()) {
            case RESERVING_TICKET:
                if (reply.isSuccess()) {
                    // Transition to card authorization on success
                    data.setState(CreateOrderSagaState.AUTHORIZING_CARD);
                    sagaRepository.save(data);
                    
                    producer.sendCommand(
                        "accounting-service-channel",
                        sagaId,
                        new AuthorizeCardCommand(data.getOrderId(), data.getAmount())
                    );
                } else {
                    // Fail fast and reject order if ticket reservation fails
                    rollbackSaga(data, "Ticket reservation failed.");
                }
                break;

            case AUTHORIZING_CARD:
                if (reply.isSuccess()) {
                    // Confirm ticket and approve order if card authorization succeeds
                    data.setState(CreateOrderSagaState.CONFIRMING_TICKET);
                    sagaRepository.save(data);
                    
                    producer.sendCommand(
                        "kitchen-service-channel",
                        sagaId,
                        new ConfirmTicketCommand(data.getOrderId())
                    );
                } else {
                    // Execute compensating transactions if card authorization fails
                    rollbackSaga(data, "Card authorization failed.");
                }
                break;

            case CONFIRMING_TICKET:
                // Complete the saga once the ticket is confirmed
                data.setState(CreateOrderSagaState.SAGA_COMPLETED);
                sagaRepository.save(data);
                
                producer.sendCommand(
                    "order-service-channel",
                    sagaId,
                    new ApproveOrderCommand(data.getOrderId())
                );
                break;

            case REJECTING_TICKET:
                // Move to order rejection after the ticket is rejected
                data.setState(CreateOrderSagaState.REJECTING_ORDER);
                sagaRepository.save(data);
                
                producer.sendCommand(
                    "order-service-channel",
                    sagaId,
                    new RejectOrderCommand(data.getOrderId())
                );
                break;

            case REJECTING_ORDER:
                data.setState(CreateOrderSagaState.SAGA_FAILED);
                sagaRepository.save(data);
                System.out.println("Saga rollback complete. Saga ID: " + sagaId);
                break;
        }
    }

    private void rollbackSaga(CreateOrderSagaData data, String reason) {
        System.err.println("Rolling back saga: " + data.getSagaId() + ". Reason: " + reason);
        data.setState(CreateOrderSagaState.REJECTING_TICKET);
        sagaRepository.save(data);

        // Send compensating command to Kitchen Service
        producer.sendCommand(
            "kitchen-service-channel",
            data.getSagaId(),
            new RejectTicketCommand(data.getOrderId())
        );
    }
}
```

#### Lifecycle Execution Pipelines
When a saga starts, the orchestrator writes the saga state to the database and initiates communication commands:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//b2d4a281-1ce0-4cfc-bd36-34b4e6919f77/markdown_0/imgs/img_in_image_box_129_106_944_435.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A56%3A16Z%2F-1%2F%2F3252dfe46cdea6a2e379164ce7ecb496d7310f38703f1ae206b9d62afbae1eef" alt="Image" width="76%" /></div>
<div style="text-align: center;">Figure 4.13: The sequence of events when OrderService creates an instance of Create Order Saga.</div>

When replies are received, the orchestrator persists updates and sends the subsequent pipeline commands:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//b2d4a281-1ce0-4cfc-bd36-34b4e6919f77/markdown_0/imgs/img_in_image_box_128_677_945_1007.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A56%3A16Z%2F-1%2F%2F6874f378cc4ae357deed7b2ec5ab6edfea85a3c05c22436bfe09d081fcc99eae" alt="Image" width="76%" /></div>
<div style="text-align: center;">Figure 4.14: The sequence of events when the SagaManager receives a reply message from a saga participant.</div>

---

## 9.4 Lack of Isolation in Sagas: Anomalies and SRE Countermeasures

Sagas differ from ACID transactions because they commit changes immediately in local databases. This lack of isolation can introduce three database anomalies:

* **Lost Updates**: One saga overwrites updates made by another concurrent saga without reading the intermediate changes.
* **Dirty Reads**: A transaction reads data that has been modified by a running saga but has not yet committed its pivot transaction. If the saga subsequently fails and rolls back, the transaction has read invalid data.
* **Non-repeatable Reads**: A transaction reads the same record twice but gets different values because a concurrent saga updated the record between the two reads.

---

### 1. Countermeasures to Enforce Isolation
To prevent these anomalies, we implement design countermeasures:

#### Semantic Lock
A step of a saga sets a locking flag on the target record (e.g. `state = APPROVAL_PENDING`). If another saga attempts to modify the record, it must either fail or block until the lock is released:

```java
// Enforcing semantic locks when updating orders
public void updateOrder(Order order) {
    if (order.getState() == OrderState.APPROVAL_PENDING) {
        throw new OrderLockedException("Order is currently locked by a running Saga transaction.");
    }
    // Proceed with modification...
}
```

#### Commutative Updates
Design database updates to be commutative, meaning they can be executed in any order without changing the final state (e.g. subtracting from account balances, rather than setting absolute values).

#### Pessimistic View
Reorder the steps of a saga to minimize business risk. If a step carries high risk (e.g. credit card charging), execute it first to avoid writing large compensating transactions.

#### Reread Value
Before updating a record, reread the values to verify that no concurrent saga has modified the data in the meantime. If the values have changed, fail the transaction and trigger rollbacks.

#### Version File
Record all updates in a separate version log, allowing the application to reconstruct previous states if compensating rollbacks are triggered out of order.

---

## 9.5 Transactional Messaging: The Outbox Pattern

To prevent sagas from entering inconsistent states, database updates and message publishing must occur **atomically**. 

If a service updates its database but crashes before publishing the command message to the queue, the saga will hang indefinitely.

To solve this, we use the **Outbox Pattern**:
1. The local transaction writes the application data *and* the message to an `OUTBOX` database table.
2. A separate message relay service polls the `OUTBOX` table and publishes the messages to the broker.
3. Once published, the relay deletes or marks the database message as processed.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//1c29baf5-3f77-465d-98e5-8e5de45c1bc6/markdown_4/imgs/img_in_image_box_183_228_912_822.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A55%3A47Z%2F-1%2F%2F38d26c999c6aae3555e152a0b568cd4d13eff603937383f139e38a32dbe61784" alt="Image" width="68%" /></div>

<div style="text-align: center;">Figure 4.12: The Outbox pattern database integration model inside Eventuate Tram</div>

Below is the Java implementation of the transactional message publisher:

```java
package com.ftgo.order.messaging;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

@Component
public class TransactionalOutboxPublisher {

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @Autowired
    private ObjectMapper objectMapper;

    @Transactional
    public void publish(String destination, String sagaId, Object payload) {
        try {
            String jsonPayload = objectMapper.writeValueAsString(payload);
            
            // Insert the message into the outbox table as part of the local transaction
            jdbcTemplate.update(
                "INSERT INTO outbox (destination, saga_id, payload, processed) VALUES (?, ?, ?, false)",
                destination, sagaId, jsonPayload
            );
        } catch (Exception ex) {
            throw new RuntimeException("Failed to serialize message payload", ex);
        }
    }
}
```

---

## 9.6 Implement Saga Participant: Kitchen Command Handlers

Participants in an orchestration saga must define command handlers to process requests from the orchestrator and return corresponding reply messages:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//b2d4a281-1ce0-4cfc-bd36-34b4e6919f77/markdown_1/imgs/img_in_image_box_183_666_912_1146.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A56%3A16Z%2F-1%2F%2F2f0aee020341576b7b39ebe0332bffefc1331131724ef9ee157921e9872659aa" alt="Image" width="68%" /></div>

<div style="text-align: center;">Figure 4.15: Saga participant handler routing topology diagram</div>

Below is the Java implementation of the command handlers in the **Kitchen Service**:

```java
package com.ftgo.kitchen.messaging;

import io.eventuate.tram.commands.consumer.CommandHandlers;
import io.eventuate.tram.commands.consumer.CommandMessage;
import io.eventuate.tram.messaging.common.Message;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import static io.eventuate.tram.commands.consumer.CommandHandlerSteps.withReturnValue;
import static io.eventuate.tram.commands.consumer.CommandHandlersBuilder.fromChannel;

@Component
public class KitchenServiceCommandHandlers {

    @Autowired
    private TicketService ticketService;

    public CommandHandlers getCommandHandlers() {
        return fromChannel("kitchen-service-channel")
                .onMessage(CreateTicketCommand.class, this::handleCreateTicket)
                .onMessage(ConfirmTicketCommand.class, this::handleConfirmTicket)
                .onMessage(RejectTicketCommand.class, this::handleRejectTicket)
                .build();
    }

    private Message handleCreateTicket(CommandMessage<CreateTicketCommand> cm) {
        CreateTicketCommand command = cm.getCommand();
        try {
            // Invoke the domain entity to create a pending ticket
            Ticket ticket = ticketService.createTicket(command.getOrderId(), command.getLineItems());
            return withReturnValue(new CreateTicketReply(ticket.getId(), true));
        } catch (Exception ex) {
            // Return failure status in case of validation failures
            return withReturnValue(new CreateTicketReply(null, false));
        }
    }

    private Message handleConfirmTicket(CommandMessage<ConfirmTicketCommand> cm) {
        ConfirmTicketCommand command = cm.getCommand();
        ticketService.confirmTicket(command.getOrderId());
        return withReturnValue(new SuccessReply());
    }

    private Message handleRejectTicket(CommandMessage<RejectTicketCommand> cm) {
        RejectTicketCommand command = cm.getCommand();
        ticketService.rejectTicket(command.getOrderId());
        return withReturnValue(new SuccessReply());
    }
}
```

---

## 9.7 Declarative Saga Definitions: The Eventuate Tram Saga DSL

In production microservices, instead of writing nested `switch` block orchestrators (as shown in Section 9.3), developers use a **Saga DSL** (Domain Specific Language) to define the state machine declaratively.

Below is the Java implementation of the `CreateOrderSaga` definition using the Eventuate Tram Saga DSL:

```java
package com.ftgo.order.saga;

import io.eventuate.tram.sagas.simple.SimpleSaga;
import io.eventuate.tram.sagas.simple.SagaDefinition;
import org.springframework.stereotype.Component;

@Component
public class CreateOrderSaga implements SimpleSaga<CreateOrderSagaData> {

    private final SagaDefinition<CreateOrderSagaData> sagaDefinition;

    public CreateOrderSaga() {
        this.sagaDefinition = step()
                .withCompensation(this::rejectOrder) // Compensating transaction for Step 1
                .step()
                .invokeParticipant(this::verifyConsumer) // Forward Step 2
                .step()
                .invokeParticipant(this::createTicket) // Forward Step 3
                .withCompensation(this::rejectTicket) // Compensating transaction for Step 3
                .step()
                .invokeParticipant(this::authorizeCard) // Forward Step 4 (Pivot)
                .step()
                .invokeParticipant(this::confirmTicket) // Forward Step 5
                .step()
                .invokeParticipant(this::approveOrder) // Forward Step 6
                .build();
    }

    @Override
    public SagaDefinition<CreateOrderSagaData> getSagaDefinition() {
        return this.sagaDefinition;
    }

    // DSL Helper methods to produce command messages...
    private CommandWithDestination rejectOrder(CreateOrderSagaData data) {
        return send(new RejectOrderCommand(data.getOrderId())).to("order-service-channel");
    }

    private CommandWithDestination verifyConsumer(CreateOrderSagaData data) {
        return send(new VerifyConsumerCommand(data.getOrderId())).to("consumer-service-channel");
    }

    private CommandWithDestination createTicket(CreateOrderSagaData data) {
        return send(new CreateTicketCommand(data.getOrderId(), data.getLineItems())).to("kitchen-service-channel");
    }

    private CommandWithDestination rejectTicket(CreateOrderSagaData data) {
        return send(new RejectTicketCommand(data.getOrderId())).to("kitchen-service-channel");
    }

    private CommandWithDestination authorizeCard(CreateOrderSagaData data) {
        return send(new AuthorizeCardCommand(data.getOrderId(), data.getAmount())).to("accounting-service-channel");
    }

    private CommandWithDestination confirmTicket(CreateOrderSagaData data) {
        return send(new ConfirmTicketCommand(data.getOrderId())).to("kitchen-service-channel");
    }

    private CommandWithDestination approveOrder(CreateOrderSagaData data) {
        return send(new ApproveOrderCommand(data.getOrderId())).to("order-service-channel");
    }
}
```

---

## 9.8 Technical Comparison: XA/2PC vs. Saga Transactions

To help architects select the correct transaction model, we compare standard distributed database transactions against sagas:

| Feature Dimension | Two-Phase Commit (XA/2PC) | Saga Transaction Pattern |
| :--- | :--- | :--- |
| **Transaction Model** | Synchronous, blocking 2PC. | Asynchronous, non-blocking local transactions series. |
| **Isolation Level** | Serializable (locks are held until commit). | None (intermediate states commit immediately and are visible). |
| **Resource Locks** | Long-held locks over network boundaries. | Short-lived local locks (released at the end of each local step). |
| **Failure Rollback** | Automatic database rollback. | Manual execution of compensating transactions. |
| **Database Support** | Strict ACID SQL databases. | Agnostic (SQL, MongoDB, Cassandra, Kafka brokers). |
| **Throughput Capacity** | Low (degrades exponentially as instances scale). | High (non-blocking, scales horizontally). |

---

## 9.9 Idempotence in Saga Participants: Handling At-Least-Once Delivery

Because message brokers use **At-least-once delivery** guarantees, saga participants may receive the same command message multiple times.

To prevent data corruption (e.g. charging a card twice), participant command handlers must be **Idempotent**.

Below is the Java implementation of the **Idempotent Command Handler** pattern using message deduplication tables:

```java
package com.ftgo.kitchen.messaging;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

@Component
public class IdempotentCommandDispatcher {

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @Transactional
    public boolean executeIdempotently(String messageId, Runnable commandTask) {
        try {
            // 1. Insert message ID into processed_messages table
            // This table has a UNIQUE constraint on message_id
            jdbcTemplate.update(
                "INSERT INTO processed_messages (message_id, processed_at) VALUES (?, NOW())",
                messageId
            );
            
            // 2. If insert succeeds, execute the core command logic
            commandTask.run();
            return true;
        } catch (DuplicateKeyException ex) {
            // Duplicate detected, return false to skip execution
            System.out.println("Duplicate message skipped: " + messageId);
            return false;
        }
    }
}
```

---

## 9.10 Non-Blocking Orchestrator Thread Management

Because microservice interactions occur over asynchronous networks, a saga orchestrator must never block execution threads while waiting for participant replies.

### 1. Yielding Threads
If the orchestrator blocked its thread pool waiting for a reply from the Kitchen Service (which could take minutes if kitchen staff are busy), the orchestrator's thread pool would saturate within seconds under high load. Instead, the orchestrator yields the thread back to the pool immediately after writing the command message to the Outbox table.

When a reply message is received on the reply channel:
1. A message listener thread borrows a thread from the pool.
2. It fetches the saga state from the database.
3. It applies the DSL state transition and sends the next command.
4. It yields the thread back to the pool.

This non-blocking architecture allows a single thread pool (e.g. 20 threads) to coordinate thousands of active, concurrent saga instances.

---

## 9.11 Telemetry and Observability in Saga Orchestration

Because sagas span multiple services and execute asynchronously, troubleshooting failures requires dedicated SRE observability metrics.

### 1. Prometheus SLA Metrics for Sagas
The saga orchestrator registers custom metrics with Micrometer to track transaction health:

* **Saga Duration (Histogram)**: Tracks the end-to-end execution latency:
  ```promql
  # Query P95 saga execution latency
  histogram_quantile(0.95, sum(rate(saga_duration_seconds_bucket{saga_type="CreateOrderSaga"}[5m])) by (le))
  ```
* **Active Instances (Gauge)**: Tracks the number of sagas currently in-flight:
  ```promql
  # Monitor active instances to detect hung sagas
  saga_active_instances{saga_type="CreateOrderSaga"}
  ```
* **Failure Ratio (Counter)**: Tracks failed sagas to identify business or technical issues:
  ```promql
  # Calculate saga failure percentage
  sum(rate(saga_failures_total[5m])) / sum(rate(saga_completed_total[5m]))
  ```

### 2. Distributed Tracing Propagation
To trace a saga across network boundaries, the orchestrator propagates trace contexts inside message headers. 

Below is the Java message decorator class illustrating how trace headers are injected into outgoing saga commands:

```java
package com.ftgo.order.tracing;

import io.opentelemetry.api.trace.Span;
import io.opentelemetry.api.trace.SpanContext;
import io.opentelemetry.context.Context;
import org.springframework.messaging.Message;
import org.springframework.messaging.support.MessageBuilder;
import org.springframework.stereotype.Component;

@Component
public class SagaMessageTraceDecorator {

    public <T> Message<T> injectTraceHeaders(MessageBuilder<T> builder) {
        Span currentSpan = Span.current();
        if (currentSpan == null || !currentSpan.getSpanContext().isValid()) {
            return builder.build(); // No active trace context
        }

        SpanContext spanContext = currentSpan.getSpanContext();
        
        // Inject W3C traceparent context headers
        String traceparent = String.format("00-%s-%s-01", 
                spanContext.getTraceId(), 
                spanContext.getSpanId()
        );

        return builder
                .setHeader("traceparent", traceparent)
                .setHeader("saga-root-span-id", spanContext.getSpanId())
                .build();
    }
}
```

---


## 9.12 Summary of Saga Transactions and Orchestration

This table summarizes the configurations, rules, and patterns used to implement sagas:

| Saga Element | Term / Config | Main Implementation Target | Scope Location |
| :--- | :--- | :--- | :--- |
| **Outbox Table** | `outbox` table | Resolves atomic database and message operations. | Database Schema |
| **Saga DSL** | `SimpleSaga` builder | Defines state transitions and compensations. | Orchestrator |
| **Deduplicator** | `processed_messages` | Filters out duplicate messages at the receiver. | Command Handler |
| **Semantic Lock** | `APPROVAL_PENDING` | Prevents dirty reads and lost updates. | Domain Entity |
| **Choreography Event**| `OrderCreated` | Decentralized trigger for next steps. | Message Broker |
| **Orchestration Cmd** | `CreateTicket` | Centralized command message dispatched to channel. | Message Broker |
| **Thread Yielding** | Callback registration | Prevents orchestrator thread pool exhaustion. | Orchestrator |

---

## Chapter Summary

* Sagas maintain data consistency in a microservices architecture without relying on distributed transactions (2PC), which are not supported by modern NoSQL databases and message brokers.
* A saga coordinates a series of **local transactions**. Each step executes a local transaction and publishes a message to trigger the next step.
* If a step fails due to a business rule violation, the saga executes **compensating transactions** in reverse order to undo the changes made by previous steps.
* Local transactions are classified as **compensatable** (can be rolled back), **pivot** (the decision point of the saga), and **retriable** (guaranteed to succeed).
* **Choreography-based sagas** coordinate workflows using decentralized events. They are simple to implement for small sagas but can be difficult to manage as complexity grows.
* **Orchestration-based sagas** use a centralized orchestrator to coordinate workflows. They centralize the saga logic, reducing coupling and cyclic dependencies between services.
* Sagas lack Isolation, which can introduce anomalies like Lost Updates, Dirty Reads, and Non-repeatable Reads.
* SREs use countermeasures like Semantic Locks (e.g., pending states), Commutative Updates, and Pessimistic Views to enforce isolation.
* Apply the Outbox pattern to write outbound messages to a database table as part of the local transaction, ensuring atomic messaging.
* Write idempotent command handlers in participant services using deduplication tables to filter out duplicate messages under at-least-once delivery guarantees.
* Use declarative DSL configurations inside the orchestrator to build a readable and maintainable state machine.
* Compare XA/2PC vs. Sagas: 2PC is synchronous and blocks resource locks, whereas Sagas are asynchronous and execute non-blocking local transactions.
* Yield execution threads back to the pool while waiting for asynchronous replies to protect the orchestrator from resource saturation.
* Track saga end-to-end execution durations using Prometheus histograms to measure SLI metrics.
* Monitor active saga instances in-flight using gauges to detect hung orchestration transactions.
* Propagate OpenTelemetry W3C traceparents headers inside command and reply messages to trace sagas across services.
* Map Eventuate Tram tables (such as `message` and `received_messages`) to relational databases to implement the Outbox pattern.
* Differentiate between compensating transactions (used to rollback compensatable steps) and retriable steps (which are guaranteed to succeed eventually).
* Implement asynchronous reply handling using consumer channel proxies to process reply payloads.
* Integrate sagas with business logic services by using SagaManager components to instantiate orchestrators.
* Test saga flows by mocking message channels to verify state machine transitions and compensations.



