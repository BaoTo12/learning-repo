# Chapter 8: Interprocess Communication (RPI, gRPC, and Asynchronous Messaging)

In a microservices architecture, services run as independent processes on multiple host machines. In-memory method calls are replaced by remote interprocess communication (IPC) over the network. Selecting, designing, and evolving these IPC mechanisms is a critical architectural decision that directly impacts application availability, performance, and transactional boundaries.

This chapter covers the conceptual and technical architectures of interprocess communication. We will classify client-service interaction styles along two dimensions: cardinality (one-to-one vs. one-to-many) and synchronicity (synchronous vs. asynchronous). We will explore the mechanics and trade-offs of Remote Procedure Invocation (RPI) using RESTful APIs and binary **gRPC/Protocol Buffers** protocols. Finally, we will transition to asynchronous **Message-Based IPC**, detailing message channel topologies, consumer horizontal scaling, duplicate message detection (idempotent consumers), and the transactional messaging pipeline.

---

## Learning Objectives

By the end of this chapter, you will be able to:
1. Classify interprocess communication styles along the dimensions of cardinality and synchronicity.
2. Design and document RESTful APIs following the Richardson Maturity Model (Levels 0–3).
3. Build declarative binary APIs using **gRPC** and **Protocol Buffers** IDL definitions.
4. Explain how synchronous communication reduces overall application availability.
5. Construct asynchronous message structures containing headers and payloads mapped to point-to-point and publish-subscribe channels.
6. Implement consumer scaling while preserving strict message ordering using partitioned channels.
7. Design **Idempotent Consumers** to detect and discard duplicate messages.
8. Compare the **Transactional Outbox**, **Polling Publisher**, and **Transaction Log Tailing** patterns to reliably publish messages as part of a database transaction.

---

## 8.1 Interprocess Communication (IPC) Overview

An application's services must collaborate to handle client requests. Because service instances are separate processes running on multiple machines, they must interact using IPC.

### Interaction Styles
Before selecting a specific IPC technology, you must determine the style of interaction between a service and its clients:

| Dimension | Synchronous | Asynchronous |
| :--- | :--- | :--- |
| **One-to-One** | **Request/Response**: A client makes a request to a service and blocks waiting for a timely response (e.g. REST, gRPC). | **Asynchronous Request/Response**: A client sends a request; the service replies asynchronously without blocking the client.<br>**One-Way Notifications**: A client sends a request; no reply is expected or sent. |
| **One-to-Many** | — | **Publish/Subscribe**: A client publishes a message consumed by zero or more interested services.<br>**Publish/Asynchronous Responses**: A client publishes a request and waits for responses from interested services. |

*Note: Synchronous request/response is orthogonal to the underlying protocol. A client can execute a synchronous request/response call over a message broker by blocking its thread until a response message arrives.*

The client and service implement the asynchronous request/response style interaction by exchanging a pair of messages:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//a81e311a-23a4-4240-b92c-a08fb31cdb1e/markdown_2/imgs/img_in_image_box_184_463_912_835.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A55%3A56Z%2F-1%2F%2F5dad92e6f7afa2301e1d04762245a20eadb1914913017ef4be89ca493c1e5195" alt="Image" width="68%" /></div>
<div style="text-align: center;">Figure 3.8: Implementing asynchronous request/response by including a reply channel and message identifier in the request message. The receiver processes the message and sends the reply to the specified reply channel.</div>

---

### The Importance of API-First Design
APIs or interfaces are central to software development. A well-designed interface exposes useful functionality while hiding the implementation details. In a microservice architecture, API-first design is essential:
1. **Interface First**: You first write the interface definition (using Swagger/OpenAPI or gRPC proto files).
2. **Developer Alignment**: Review the interface definition with client and consumer developers.
3. **Iterative Development**: Only after iterating and agreeing on the API definition do you implement the service.

Without this upfront alignment, frontend and backend development teams can build incompatible models, resulting in integration failures during deployment.

---

### API Evolution and Semantic Versioning (SemVer)
APIs change over time as features are added, modified, or deprecated. In a microservices environment, you cannot force all clients to upgrade in lockstep with the service.

We manage API evolution using the Semantic Versioning specification, which defines version numbers as `MAJOR.MINOR.PATCH`:
* **MAJOR**: Incremented when you make an incompatible, breaking change to the API.
* **MINOR**: Incremented when you add backward-compatible enhancements.
* **PATCH**: Incremented when you make backward-compatible bug fixes.

#### 1. Managing Minor, Backward-Compatible Changes
Minor changes should be additive:
* Adding optional fields to requests.
* Adding new fields to responses.
* Adding new operations.

According to the **Robustness Principle** ("Be conservative in what you do, be liberal in what you accept"), services should provide default values for missing request attributes, and clients should ignore extra attributes in responses.

#### 2. Managing Major, Breaking Changes
When major, incompatible changes must be made, a service must support old and new versions simultaneously. For REST, embed the major version in the URL path (e.g., `/v1/...` and `/v2/...`) or use HTTP content negotiation via the `Accept` header:
```http
GET /orders/123 HTTP/1.1
Accept: application/vnd.ftgo.order+json; version=1
```

---

### Message Formats: Text vs. Binary
The choice of message format impacts serialization efficiency, network usage, and ease of API evolution:

| Format Type | Examples | Advantages | Disadvantages |
| :--- | :--- | :--- | :--- |
| **Text-Based** | JSON, XML | Human-readable, self-describing, easy to inspect and debug, highly flexible for schema changes. | Verbose payloads (header overhead), high CPU overhead for parsing large files. |
| **Binary** | Protocol Buffers, Avro | Highly compact payloads, fast serialization/deserialization, strong type checks, forces API-first design. | Harder to debug (requires decoding), requires IDL compilation steps. |

---

## 8.2 Communicating Using Synchronous RPI

Under the Remote Procedure Invocation (RPI) pattern, a client sends a request to a service, and the service processes the request and returns a response.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//81ca3f40-c83a-47e9-990c-43c2e1ed4a79/markdown_2/imgs/img_in_image_box_202_103_931_449.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A55%3A34Z%2F-1%2F%2F1b58ba4673da56194cc2fe977ad7cef966ce7af12ce9a1aee6ecd315c326815a" alt="Image" width="68%" /></div>
<div style="text-align: center;">Figure 3.1: The client's business logic invokes an interface that is implemented by an RPI proxy adapter class. The RPI proxy class makes a request to the service. The RPI server adapter class handles the request by invoking the service's business logic.</div>

---

### 1. RESTful APIs
REST is an RPI style that uses HTTP. A key concept is a **Resource**, representing a business object (e.g., `Consumer`, `Order`). REST uses HTTP verbs to manipulate these resources:
* `GET`: Retrieves the representation of a resource.
* `POST`: Creates a new resource.
* `PUT`: Updates an existing resource.
* `DELETE`: Removes a resource.

#### The Richardson Maturity Model
The maturity of a REST API is classified into four levels:
* **Level 0**: Clients make HTTP `POST` requests to a single service endpoint, specifying the action, target object, and parameters in the payload.
* **Level 1**: Supports individual resources. Clients make requests to unique URLs targeting specific resources, using `POST` for all actions.
* **Level 2**: Uses HTTP verbs to perform actions (`GET` to retrieve, `POST` to create, `PUT` to update). This enables using standard web infrastructure, such as HTTP caching for `GET` requests.
* **Level 3**: Implements HATEOAS (Hypermedia As The Engine Of Application State). Resource representations returned by `GET` requests contain links for performing actions on that resource (e.g., a link to cancel an order).

#### Challenges of REST:
* **Resource Aggregation**: Retrieving multiple related objects (e.g. an order and its consumer) requires multiple HTTP round-trips, introducing network latency. This is resolved by using query parameters (like `?expand=consumer`) or GraphQL.
* **Mapping Operations**: It can be difficult to map complex business operations (like canceling an order) to HTTP verbs. This is resolved by defining sub-resources (e.g., `POST /orders/{id}/cancel`).

---

### 2. Binary RPC with gRPC and Protocol Buffers
gRPC is a high-performance, binary RPC framework. Clients and servers exchange compact binary messages using HTTP/2, defining APIs using Google's **Protocol Buffers** IDL.

#### Protocol Buffer API Definition: `order.proto`
Create the following contract definition inside `order-service/src/main/proto/order.proto`:

```protobuf
syntax = "proto3";

option java_multiple_files = true;
option java_package = "com.ftgo.order.grpc";
option java_outer_classname = "OrderProto";

package order;

// The Order Service contract definition
service OrderService {
  rpc createOrder(CreateOrderRequest) returns (CreateOrderReply) {}
  rpc cancelOrder(CancelOrderRequest) returns (CancelOrderReply) {}
}

message CreateOrderRequest {
  int64 restaurantId = 1; // Field tag 1
  int64 consumerId = 2;   // Field tag 2
  repeated LineItem lineItems = 3;
}

message LineItem {
  string menuItemId = 1;
  int32 quantity = 2;
}

message CreateOrderReply {
  int64 orderId = 1;
}

message CancelOrderRequest {
  int64 orderId = 1;
}

message CancelOrderReply {
  string status = 1;
}
```

gRPC generates client stubs and server skeletons from this definition. Because Protocol Buffers use tagged fields (numbers mapped to fields), the API can evolve while maintaining backward compatibility.

---

### Handling Partial Failure and Service Degradation
A client must protect itself from cascading failures by ensuring unresponsive remote services are decoupled using timeouts and circuit breakers:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//d7399ab1-c0e7-4567-92f1-c4ac37015a58/markdown_2/imgs/img_in_image_box_183_458_908_729.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A56%3A20Z%2F-1%2F%2Fda6a5001a52da8899e7684df2239c8e5cfee1b80fef5fb044d22fe3a9800a275" alt="Image" width="68%" /></div>
<div style="text-align: center;">Figure 3.2: An API gateway must protect itself from unresponsive services, such as the Order Service.</div>

For operations such as API composition, the caller can execute a fallback strategy if a non-essential service degrades, returning cached or default values instead of throwing an error:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//d7399ab1-c0e7-4567-92f1-c4ac37015a58/markdown_4/imgs/img_in_image_box_183_104_906_473.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A56%3A23Z%2F-1%2F%2Fec00edd443c3fdee038cc31158ee1627d53b64f1bd7061cb08e0ce3a6e76a0b5" alt="Image" width="68%" /></div>
<div style="text-align: center;">Figure 3.3: The API gateway implements the GET /orders/{orderId} endpoint using API composition. It calls several services, aggregates their responses, and sends a response to the mobile app. The code that implements the endpoint must have a strategy for handling the failure of each service that it calls.</div>

---

### RPI Availability and Service Discovery
Because client and service communicate directly without an intermediary, synchronous communication reduces availability. The system is only available when all services involved are running.

Furthermore, because containers are assigned dynamic IP addresses upon startup, RPI client applications must use a dynamic service discovery engine.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//5e42ca28-114a-40af-9a9c-3f73a66cd7f1/markdown_0/imgs/img_in_image_box_200_103_748_512.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A55%3A33Z%2F-1%2F%2F3385da887bb7f6c9103160ba09dd3d7a71df5cc58218e9de130d10b3cd87ccfc" alt="Image" width="51%" /></div>
<div style="text-align: center;">Figure 3.4: Service instances have dynamically assigned IP addresses.</div>

#### 1. Client-Side Discovery
The client queries the service registry directly to get a list of active IPs, selects an instance using a load-balancing algorithm (like round-robin or random), and routes the request:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//5e42ca28-114a-40af-9a9c-3f73a66cd7f1/markdown_1/imgs/img_in_image_box_184_108_910_646.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A55%3A34Z%2F-1%2F%2Fd640a27c2c32e5018733fbb9a04573191e00f0a97bb036150f01a29f749261b2" alt="Image" width="68%" /></div>
<div style="text-align: center;">Figure 3.5: The service registry keeps track of the service instances. Clients query the service registry to find network locations of available service instances.</div>

#### 2. Server-Side Discovery (Platform-provided)
The client routes requests to a request router or load balancer. The router queries the registry and forwards the call to a healthy service instance. Registration and discovery are handled entirely by the deployment platform:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//5e42ca28-114a-40af-9a9c-3f73a66cd7f1/markdown_3/imgs/img_in_image_box_180_108_909_737.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A55%3A35Z%2F-1%2F%2Fd6395f4b32b3b5f5d0d22eded01e9edb0cb49f06a9b3e6c23020127eee64653c" alt="Image" width="68%" /></div>
<div style="text-align: center;">Figure 3.6: The platform is responsible for service registration, discovery, and request routing. Service instances are registered with the service registry by the registrar. Each service has a network location, a DNS name/virtual IP address. A client makes a request to the service's network location. The router queries the service registry and load balances requests across the available service instances.</div>

---

## 8.3 Asynchronous Message-Based IPC

Under the **Messaging pattern**, services communicate by exchanging messages asynchronously over channels.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//a81e311a-23a4-4240-b92c-a08fb31cdb1e/markdown_1/imgs/img_in_image_box_130_104_948_419.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A55%3A56Z%2F-1%2F%2F662387c2c9873f7635d25079878d453234acb9f34b323f83801a6a99590bb6a6" alt="Image" width="77%" /></div>
<div style="text-align: center;">Figure 3.7: The business logic in the sender invokes a sending port interface, which is implemented by a message sender adapter. The message sender sends a message to a receiver via a message channel. The message channel is an abstraction of messaging infrastructure. A message handler adapter in the receiver is invoked to handle the message. It invokes the receiving port interface implemented by the receiver's business logic.</div>

### Message and Channel Topologies
* **Message**: Contains metadata headers (key-value pairs for correlation IDs, message types, and reply channel information) and a message body payload (text or binary data):

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//a81e311a-23a4-4240-b92c-a08fb31cdb1e/markdown_4/imgs/img_in_image_box_184_107_904_400.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A55%3A57Z%2F-1%2F%2Faee7a76022b9420e7c1dddcec925fb5e2452a653dceb88f0e5762f310970a913" alt="Image" width="67%" /></div>
<div style="text-align: center;">Figure 3.9: A service's asynchronous API consists of message channels and command, reply, and event message types.</div>

* **Message Channel**: A logical channel in the messaging system:
  * **Point-to-Point Channel**: Delivers a message to exactly one consumer (e.g. command channels).
  * **Publish-Subscribe Channel**: Delivers a message to all registered consumers (e.g. event channels).

These channels run on a dedicated message broker (e.g., Apache Kafka, RabbitMQ) that acts as an intermediary, buffering messages and increasing service decoupling compared to brokerless architectures (e.g., ZeroMQ):

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//333d8654-337e-423c-88d7-3f2ec0138b19/markdown_0/imgs/img_in_image_box_203_103_914_491.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A55%3A31Z%2F-1%2F%2F52924b46d62acbaa93de9a030a64e781b9b00ceecb0c5dd943ad5c4a4e92f0c7" alt="Image" width="66%" /></div>
<div style="text-align: center;">Figure 3.10: The services in brokerless architecture communicate directly, whereas the services in a broker-based architecture communicate via a message broker.</div>

---

### Scaling Consumers and Preserving Message Ordering
To handle high message volumes, you can scale out by running multiple instances of a message consumer in parallel.

* **The Problem**: If a broker distributes messages from a single queue across multiple concurrent consumers, message order can be lost. For example, a `DeliveryUpdated` message could be processed before a `DeliveryCreated` message.
* **The Solution**: Use partitioned channels (like Kafka topics). The broker divides a topic into multiple partitions. The publisher assigns messages a partition key (e.g. `orderId`). The broker routes all messages with the same partition key to the same partition, and assigns each partition to a single consumer instance within a consumer group, guaranteeing ordered processing.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//333d8654-337e-423c-88d7-3f2ec0138b19/markdown_4/imgs/img_in_image_box_129_110_946_387.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A55%3A33Z%2F-1%2F%2F0331a44440aedf8baa6ae0746db588302d8f36c2d311e6ef4f2d68d0aebfd607" alt="Image" width="76%" /></div>
<div style="text-align: center;">Figure 3.11: Scaling consumers while preserving message ordering by using a sharded (partitioned) message channel. The sender includes the shard key in the message. The message broker writes the message to a shard determined by the shard key. The message broker assigns each partition to an instance of the replicated receiver.</div>

---

### Designing Idempotent Consumers
A message broker guarantees message delivery, but network disruptions can cause duplicate deliveries. A message consumer must be **idempotent**, meaning processing a duplicate message yields the same system state as processing it once.

#### Idempotence Mechanisms:
1. **Natural Idempotence**: The message handler performs an operation that can be repeated safely (e.g. setting an order status to `DELIVERED`).
2. **Message Deduplication Table**: If the operation is not naturally idempotent (e.g. incrementing a bank balance), the consumer tracks processed messages. It saves the message ID to a database table as part of the local transaction. If the ID is already present, the transaction is discarded:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//15587205-e233-49e7-b7de-025c6aa49fe8/markdown_0/imgs/img_in_image_box_183_704_901_976.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A56%3A03Z%2F-1%2F%2F82be0a8d9d236e0dbceaf6d991ae5f42b45b1a3543f23a46c9abf1f223b8aa21" alt="Image" width="67%" /></div>
<div style="text-align: center;">Figure 3.12: A consumer detects and discards duplicate messages by recording the IDs of processed messages in a database table. If a message has been processed before, the INSERT into the PROCESSED_MESSAGES table will fail.</div>

```java
package com.ftgo.order.messaging;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.stereotype.Component;

@Component
public class IdempotentMessageConsumer {

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @Transactional
    public void processMessage(String messageId, Runnable businessLogic) {
        try {
            // Attempt to insert the message ID into a deduplication table
            jdbcTemplate.update(
                "INSERT INTO processed_messages (message_id, processed_at) VALUES (?, NOW())",
                messageId
            );
            // Execute business logic if the insert succeeds
            businessLogic.run();
        } catch (org.springframework.dao.DuplicateKeyException ex) {
            // Log and discard the message if it has already been processed
            System.out.println("Duplicate message detected and discarded: " + messageId);
        }
    }
}
```

---

## 8.4 Synchronous Communication Availability and Decoupling

Using synchronous interprocess communication like REST degrades system availability, because it requires all participating microservices to be online simultaneously:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//6957d5d0-b23e-4340-87aa-764020234ce7/markdown_2/imgs/img_in_image_box_201_916_924_1116.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A55%3A45Z%2F-1%2F%2Fd42cf7064580a186f1c474fbf351a09139d473adc548a4abe85305346f3e3a2d" alt="Image" width="68%" /></div>
<div style="text-align: center;">Figure 3.15: The Order Service invokes other services using REST. It's straightforward, but it requires all the services to be simultaneously available, which reduces the availability of the API.</div>

To decouple these systems and improve availability, architectures can employ three strategies:

### 1. Asynchronous Interaction Styles
Communicate entirely via messages buffer-loaded by a broker. Senders and receivers remain independent, avoiding synchronous blocking:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//6957d5d0-b23e-4340-87aa-764020234ce7/markdown_4/imgs/img_in_image_box_129_178_948_424.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A55%3A47Z%2F-1%2F%2F630764301d5a203fa200cdedc3b38c2f4316ee1e1a9428e4fafdb248997c472e" alt="Image" width="77%" /></div>
<div style="text-align: center;">Figure 3.16: The FTGO application has higher availability if its services communicate using asynchronous messaging instead of synchronous calls.</div>

### 2. Replicate Data
Services replicate and store relevant consumer or menu datasets locally, responding to HTTP requests without calling downstream dependencies:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//3ecfb6e2-520e-42e0-9832-66bdc694ab7c/markdown_0/imgs/img_in_image_box_110_116_932_530.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A55%3A57Z%2F-1%2F%2Ffa78b07ed3585707765d8a70095116c35fdf16ac7f89b04b2423367bddd512cc" alt="Image" width="77%" /></div>
<div style="text-align: center;">Figure 3.17: Order Service is self-contained because it has replicas of the consumer and restaurant data.</div>

### 3. Finish Processing After Returning a Response
Construct resources in a `PENDING` state and return the ID immediately, completing the transaction asynchronously:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//3ecfb6e2-520e-42e0-9832-66bdc694ab7c/markdown_1/imgs/img_in_image_box_133_107_947_637.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A55%3A58Z%2F-1%2F%2F7b28893d3d5ea658c2f230d0db43c520f2fa1acbe8999ebe6e567d360ff53fbb" alt="Image" width="76%" /></div>
<div style="text-align: center;">Figure 3.18: Order Service creates an order without invoking any other service. It then asynchronously validates the newly created Order by exchanging messages with other services, including Consumer Service and Restaurant Service.</div>

---

## 8.5 The Transactional Messaging Pipeline

A microservice often needs to update its database and publish a message to a broker within the same transaction. For example, when creating an order, the database write and the `OrderCreated` event must occur atomically:

If the service updates the database but crashes before publishing the message, downstream services will not be notified, leaving the system in an inconsistent state.

To solve this, we use the **Transactional Outbox** pattern, which writes messages to a dedicated database table as part of the local database transaction, guaranteeing atomicity.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//15587205-e233-49e7-b7de-025c6aa49fe8/markdown_1/imgs/img_in_image_box_130_780_948_1126.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A56%3A04Z%2F-1%2F%2Fc6393d22940e40d379dd772fa3b1f440bed7e4b73c00b0c94e2edb9656c63b0a" alt="Image" width="77%" /></div>
<div style="text-align: center;">Figure 3.13: A service reliably publishes a message by inserting it into an OUTBOX table as part of the transaction that updates the database. The Message Relay reads the OUTBOX table and publishes the messages to a message broker.</div>

---

### Database Outbox Schema
```sql
CREATE TABLE outbox (
    message_id VARCHAR(100) PRIMARY KEY,
    payload VARCHAR(2000) NOT NULL,
    destination VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

We move messages from the outbox table to the broker using one of two patterns:

### 1. Polling Publisher Pattern
The message relay periodically queries the `outbox` table for unpublished messages, publishes them to the broker, and deletes them from the table:

```java
package com.ftgo.order.messaging;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import java.util.List;

@Component
public class PollingMessageRelay {

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @Autowired
    private MessageBrokerClient brokerClient;

    @Scheduled(fixedDelay = 2000) // Polls every 2 seconds
    public void pollAndPublish() {
        // Retrieve unpublished messages
        List<OutboxMessage> messages = jdbcTemplate.query(
            "SELECT message_id, payload, destination FROM outbox ORDER BY created_at ASC LIMIT 10",
            (rs, rowNum) -> new OutboxMessage(
                rs.getString("message_id"),
                rs.getString("payload"),
                rs.getString("destination")
            )
        );

        for (OutboxMessage message : messages) {
            try {
                // Publish to the message broker (e.g. Kafka)
                brokerClient.publish(message.getDestination(), message.getPayload());
                // Delete the message from the outbox table on success
                jdbcTemplate.update("DELETE FROM outbox WHERE message_id = ?", message.getMessageId());
            } catch (Exception ex) {
                System.err.println("Failed to publish message: " + message.getMessageId());
                break; // Stop processing batch to preserve order
            }
        }
    }
}
```

---

### 2. Transaction Log Tailing Pattern
A more performant approach is to tail the database transaction log (e.g., MySQL binary log, PostgreSQL Write-Ahead Log). A log reader (such as **Debezium** or LinkedIn Databus) monitors the log for insertions into the `outbox` table and publishes the corresponding events directly to the message broker. This avoids polling queries and reduces database overhead.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//15587205-e233-49e7-b7de-025c6aa49fe8/markdown_3/imgs/img_in_image_box_200_396_831_852.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A56%3A05Z%2F-1%2F%2Fe1e7e98c77253826a923f473ee73f19591bfab7bf339111937b4da6c9eba4d52" alt="Image" width="59%" /></div>
<div style="text-align: center;">Figure 3.14: A service publishes messages inserted into the OUTBOX table by mining the database's transaction log.</div>

## 8.6 Implementing a gRPC Server in Java

To implement the Protocol Buffer contract defined in Section 8.2, we build a gRPC server adapter within the `order-service`. The server skeleton extends the generated base class, processes client requests, interacts with local repositories, and handles errors:

```java
package com.ftgo.order.grpc;

import io.grpc.stub.StreamObserver;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import com.ftgo.order.domain.Order;
import com.ftgo.order.repository.OrderRepository;

@Service
public class OrderGrpcService extends OrderServiceGrpc.OrderServiceImplBase {

    private static final Logger logger = LoggerFactory.getLogger(OrderGrpcService.class);

    @Autowired
    private OrderRepository orderRepository;

    @Override
    @Transactional
    public void createOrder(CreateOrderRequest request, StreamObserver<CreateOrderReply> responseObserver) {
        logger.info("Received gRPC createOrder request for Consumer [{}]", request.getConsumerId());
        
        try {
            // 1. Create order domain entity from request details
            Order order = new Order(request.getConsumerId(), request.getRestaurantId());
            
            // Populate line items
            request.getLineItemsList().forEach(item -> 
                order.addLineItem(item.getMenuItemId(), item.getQuantity())
            );

            // Save to PostgreSQL database
            Order savedOrder = orderRepository.save(order);

            // 2. Build the proto reply message
            CreateOrderReply reply = CreateOrderReply.newBuilder()
                    .setOrderId(savedOrder.getId())
                    .build();

            // 3. Send response and complete gRPC stream
            responseObserver.onNext(reply);
            responseObserver.onCompleted();
            logger.info("Successfully created order [{}] via gRPC", savedOrder.getId());

        } catch (IllegalArgumentException e) {
            logger.error("Invalid arguments in request", e);
            responseObserver.onError(io.grpc.Status.INVALID_ARGUMENT
                    .withDescription(e.getMessage())
                    .asRuntimeException());
        } catch (Exception e) {
            logger.error("Internal error during gRPC order creation", e);
            responseObserver.onError(io.grpc.Status.INTERNAL
                    .withDescription("Internal database error: " + e.getMessage())
                    .asRuntimeException());
        }
    }

    @Override
    @Transactional
    public void cancelOrder(CancelOrderRequest request, StreamObserver<CancelOrderReply> responseObserver) {
        logger.info("Received gRPC cancelOrder request for Order ID [{}]", request.getOrderId());
        
        try {
            Order order = orderRepository.findById(request.getOrderId())
                    .orElseThrow(() -> new IllegalArgumentException("Order not found with ID: " + request.getOrderId()));

            order.cancel();
            orderRepository.save(order);

            CancelOrderReply reply = CancelOrderReply.newBuilder()
                    .setStatus("CANCELLED")
                    .build();

            responseObserver.onNext(reply);
            responseObserver.onCompleted();

        } catch (IllegalArgumentException e) {
            responseObserver.onError(io.grpc.Status.NOT_FOUND
                    .withDescription(e.getMessage())
                    .asRuntimeException());
        } catch (Exception e) {
            responseObserver.onError(io.grpc.Status.INTERNAL
                    .withDescription("Cancellation failed: " + e.getMessage())
                    .asRuntimeException());
        }
    }
}
```

---

## 8.7 Calling a gRPC Service from a Client

Clients invoke the gRPC server using stub classes generated from the Protocol Buffer contract. To manage connection details efficiently, we define a client configuration helper class:

```java
package com.ftgo.kitchen.client;

import io.grpc.ManagedChannel;
import io.grpc.ManagedChannelBuilder;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import com.ftgo.order.grpc.OrderServiceGrpc;
import java.util.concurrent.TimeUnit;

@Configuration
public class OrderGrpcClientConfig {

    @Value("${order.service.grpc.host:localhost}")
    private String host;

    @Value("${order.service.grpc.port:50051}")
    private int port;

    @Bean(destroyMethod = "shutdown")
    public ManagedChannel grpcChannel() {
        return ManagedChannelBuilder.forAddress(host, port)
                .usePlaintext() // Use plaintext for development testing; SSL is enabled for staging/production
                .keepAliveTime(30, TimeUnit.SECONDS)
                .keepAliveTimeout(5, TimeUnit.SECONDS)
                .build();
    }

    @Bean
    public OrderServiceGrpc.OrderServiceBlockingStub orderServiceBlockingStub(ManagedChannel channel) {
        return OrderServiceGrpc.newBlockingStub(channel);
    }
}
```

The client service uses the auto-wired stub to make synchronous RPC calls:

```java
package com.ftgo.kitchen.service;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import com.ftgo.order.grpc.OrderServiceGrpc;
import com.ftgo.order.grpc.CreateOrderRequest;
import com.ftgo.order.grpc.CreateOrderReply;

@Service
public class OrderClientService {

    @Autowired
    private OrderServiceGrpc.OrderServiceBlockingStub orderStub;

    public long triggerOrderCreation(long consumerId, long restaurantId) {
        CreateOrderRequest request = CreateOrderRequest.newBuilder()
                .setConsumerId(consumerId)
                .setRestaurantId(restaurantId)
                .build();

        // Perform synchronous network invocation
        CreateOrderReply reply = orderStub.createOrder(request);
        return reply.getOrderId();
    }
}
```

---

## 8.8 Architectural Comparison: REST vs. gRPC vs. Messaging

Choosing the correct IPC mechanism requires balancing availability, coupling, latency, and performance:

| Parameter | REST (HTTP/1.1) | gRPC (HTTP/2) | Asynchronous Messaging (Kafka/RabbitMQ) |
| :--- | :--- | :--- | :--- |
| **Communication Style** | Synchronous Request/Response | Synchronous Request/Response | Asynchronous Event/Notification |
| **Payload Protocol** | Text-based (JSON/XML) | Binary (Protocol Buffers) | Binary or Text-based |
| **Latency Cost** | High (TCP connection overhead) | Low (Multiplexed streams over HTTP/2) | Moderate (Message broker buffering delay) |
| **Type Verification** | Runtime validation (No compile-time check) | Compile-time IDL verification | Runtime serialization checks |
| **Client/Server Coupling** | High (Target URLs, active IP needed) | High (Client stub bound to Server port) | Low (Coupled only to topic names, not hosts) |
| **Availability Dependency**| Low (Both systems must be online) | Low (Both systems must be online) | High (Sender can publish even if receiver is down) |

---

## 8.9 Implementing Distributed Idempotent Consumers with Redis

When duplicate messages are published concurrently, a local SQL deduplication table might fail to prevent race conditions due to dirty reads or isolation limits. To guarantee absolute idempotence at high concurrency, we combine database deduplication with a **Redis-based distributed lock** using **Redisson**:

```java
package com.ftgo.order.messaging;

import org.redisson.api.RLock;
import org.redisson.api.RedissonClient;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;
import java.util.concurrent.TimeUnit;

@Component
public class DistributedIdempotentConsumer {

    private static final Logger logger = LoggerFactory.getLogger(DistributedIdempotentConsumer.class);

    @Autowired
    private RedissonClient redissonClient;

    @Autowired
    private JdbcTemplate jdbcTemplate;

    public void processMessage(String messageId, Runnable businessLogic) {
        String lockKey = "lock:message:" + messageId;
        RLock lock = redissonClient.getLock(lockKey);

        try {
            // Attempt to acquire lock with 5-second lease time and 10-second wait time
            if (lock.tryLock(10, 5, TimeUnit.SECONDS)) {
                try {
                    // Check deduplication table
                    Integer count = jdbcTemplate.queryForObject(
                        "SELECT COUNT(*) FROM processed_messages WHERE message_id = ?",
                        Integer.class,
                        messageId
                    );

                    if (count != null && count > 0) {
                        logger.warn("Duplicate message detected in database: {}", messageId);
                        return;
                    }

                    // Execute business transaction
                    businessLogic.run();

                    // Log processed message
                    jdbcTemplate.update(
                        "INSERT INTO processed_messages (message_id, processed_at) VALUES (?, NOW())",
                        messageId
                    );

                } finally {
                    lock.unlock();
                }
            } else {
                logger.error("Could not acquire lock for message [{}]. Message is already being processed.", messageId);
            }
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            logger.error("Process interrupted while waiting for lock", e);
        } catch (Exception e) {
            logger.error("Failed to process message safely", e);
        }
    }
}
```

---

## 8.10 Publishing Messages with Apache Kafka in Spring Boot

To serialize business events and publish them to a partitioned broker topology, we implement a dedicated Kafka event publisher class. This class uses Spring's `KafkaTemplate` to dispatch event payloads and include metadata headers:

```java
package com.ftgo.order.messaging;

import org.apache.kafka.clients.producer.ProducerRecord;
import org.apache.kafka.common.header.internals.RecordHeader;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.support.SendResult;
import org.springframework.stereotype.Component;
import java.nio.charset.StandardCharsets;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;

@Component
public class KafkaMessagePublisher {

    private static final Logger logger = LoggerFactory.getLogger(KafkaMessagePublisher.class);

    @Autowired
    private KafkaTemplate<String, String> kafkaTemplate;

    /**
     * Publishes an event payload to a specified Kafka topic with routing keys and headers.
     */
    public void publish(String topic, String key, String payload, String eventType) {
        String messageId = UUID.randomUUID().toString();
        
        // 1. Create a producer record with partition key and payload
        ProducerRecord<String, String> record = new ProducerRecord<>(topic, key, payload);

        // 2. Populate metadata headers for correlation and routing
        record.headers().add(new RecordHeader("message_id", messageId.getBytes(StandardCharsets.UTF_8)));
        record.headers().add(new RecordHeader("event_type", eventType.getBytes(StandardCharsets.UTF_8)));
        record.headers().add(new RecordHeader("published_at", String.valueOf(System.currentTimeMillis()).getBytes(StandardCharsets.UTF_8)));

        logger.info("Dispatching message [{}] to topic [{}] with key [{}]", messageId, topic, key);

        // 3. Publish asynchronously and handle completion callbacks
        CompletableFuture<SendResult<String, String>> future = kafkaTemplate.send(record);
        
        future.whenComplete((result, ex) -> {
            if (ex != null) {
                logger.error("Failed to publish message [{}] due to exception: {}", messageId, ex.getMessage(), ex);
            } else {
                logger.info("Message [{}] successfully published. Metadata: Partition [{}], Offset [{}]", 
                        messageId, 
                        result.getRecordMetadata().partition(), 
                        result.getRecordMetadata().offset());
            }
        });
    }
}
```

---

## 8.11 Spring Boot Producer Configurations

Configure the Apache Kafka producer parameters inside `order-service/src/main/resources/application.yml` to specify partitioning serializers, acknowledgment policies, and retry behaviors:

```yaml
spring:
  kafka:
    bootstrap-servers: localhost:9092
    producer:
      # Serializer classes for keys and values
      key-serializer: org.apache.kafka.common.serialization.StringSerializer
      value-serializer: org.apache.kafka.common.serialization.StringSerializer
      # Wait for local broker partition acknowledgment
      acks: all # Wait for full replicas sync to guarantee durability
      retries: 3
      properties:
        enable.idempotence: true # Enforce producer idempotence
        max.in.flight.requests.per.connection: 5
      batch-size: 16384 # Batch records to optimize network bandwidth
      buffer-memory: 33554432
```



---

## 8.12 Resilient Kafka Consumers and Dead Letter Topics

To ensure that processing failures do not block partitioned queue consumption, resilient message listeners route poison-pill records to a **Dead Letter Topic (DLT)**. 

We configure a custom Kafka listener container factory in Java with a retry backoff error handler:

```java
package com.ftgo.order.config;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.kafka.config.ConcurrentKafkaListenerContainerFactory;
import org.springframework.kafka.core.ConsumerFactory;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.listener.DeadLetterPublishingRecoverer;
import org.springframework.kafka.listener.DefaultErrorHandler;
import org.springframework.util.backoff.FixedBackOff;

@Configuration
public class ResilientKafkaConsumerConfig {

    private static final Logger logger = LoggerFactory.getLogger(ResilientKafkaConsumerConfig.class);

    @Bean
    public ConcurrentKafkaListenerContainerFactory<String, String> kafkaListenerContainerFactory(
            ConsumerFactory<String, String> consumerFactory,
            KafkaTemplate<String, String> kafkaTemplate) {

        ConcurrentKafkaListenerContainerFactory<String, String> factory =
                new ConcurrentKafkaListenerContainerFactory<>();
        factory.setConsumerFactory(consumerFactory);

        // 1. Establish a recovery publisher that routes failures to .DLT topics
        DeadLetterPublishingRecoverer recoverer = new DeadLetterPublishingRecoverer(kafkaTemplate,
                (record, ex) -> {
                    logger.error("Failed to process record in partition [{}], sending to Dead Letter. Error: {}", 
                            record.partition(), ex.getMessage());
                    return new org.apache.kafka.common.TopicPartition(record.topic() + ".DLT", record.partition());
                });

        // 2. Configure default error handler with 3 retry attempts and a 2-second delay
        DefaultErrorHandler errorHandler = new DefaultErrorHandler(recoverer, new FixedBackOff(2000L, 3L));
        factory.setCommonErrorHandler(errorHandler);

        return factory;
    }
}
```

---

## Chapter Summary

* **Interprocess communication** styles are defined along two dimensions: cardinality (one-to-one, one-to-many) and synchronicity (synchronous, asynchronous).
* **RESTful APIs** map resources to HTTP verbs, classified by the Richardson Maturity Model (Levels 0–3).
* **gRPC** uses HTTP/2 and Protocol Buffers to define structured, high-performance binary contracts.
* **Synchronous communication** reduces system availability because the caller must block waiting for downstream responses.
* **Asynchronous messaging** uses message channels to buffer requests. Consumer scaling is managed using partitioned channels to preserve message ordering.
* Network disruptions can cause duplicate messages. Consumers must be **idempotent**, using natural idempotence or deduplication tables to discard duplicate deliveries.
* The **Transactional Outbox** pattern writes messages to an `outbox` table within a local database transaction. A message relay publishes the messages using either a **Polling Publisher** or **Transaction Log Tailing**.
* **gRPC Servers & Clients** implement compiled protobuf stubs (`OrderGrpcService.java`) utilizing multiplexed HTTP/2 streams (`OrderGrpcClientConfig.java`).
* **IPC Trade-offs** contrast REST connection overhead, gRPC binary type validation speed, and Kafka decoupling.
* **Redisson Idempotence Locks** prevent race conditions during concurrent consumer executions.
* **Kafka Event Publishers** dispatch structured events (`KafkaMessagePublisher.java`) with correlation headers to partitioned Kafka brokers.
* **Resilient Consumer Listeners** establish container factories (`ResilientKafkaConsumerConfig.java`) routing unprocessable payloads to Dead Letter Topics (.DLT).



