# Module 01 — Welcome to the Kafka Event Streaming Platform

Welcome to the first module of the course. In this module, we will explore the basic concepts of event streaming. We will look at what an event is, how an event stream works, and the different parts of the Apache Kafka ecosystem. We will also trace a simple order flow for an online shop. Finally, we will set up a local Kafka environment using Docker Compose and try it out using command-line interface (CLI) tools.

---

## 1. Academic Lecture: Event Streaming Platform Foundations

### Basic Level: What is Event Streaming & Event Anatomy

#### What is Event Streaming and Why It Matters
In older systems, databases stored data in quiet, static tables. If an app wanted to know if data had changed, it had to keep asking the database over and over (this is called **polling**). This was slow and used a lot of computer resources.

**Event streaming** is a newer way of working. It captures data as it happens in real-time. For example, every time a user clicks a button, a machine records a log, or a customer buys an item, it creates an "event." An event-streaming platform lets you:
1.  **Publish (send)** and **subscribe (listen)** to streams of events.
2.  **Store** these events safely for as long as you need.
3.  **Process** these events immediately as they arrive.

##### Analogy: The Newspaper Publisher
> Think of event streaming like a newspaper subscription. The newspaper company prints news (this is **publishing**). Customers subscribe to the paper (this is **subscribing**). Every day, the news is sent to subscribers. In Kafka, the publisher is a **producer**, the subscriber is a **consumer**, and the newspaper name is a **topic**.

#### What is an Event?
An **event** is just a record of "something that happened." It has a key and a value, along with some extra details:

```text
┌─────────────────────────────────────────────────────────┐
│                        EVENT                            │
├───────────────────┬─────────────────────────────────────┤
│ Key (Bytes)       │ Identification (e.g. Customer C100) │
├───────────────────┼─────────────────────────────────────┤
│ Value (Bytes)     │ Data payload (e.g. Item & Amount)   │
├───────────────────┼─────────────────────────────────────┤
│ Timestamp (8B)    │ When it happened (epoch millis)     │
├───────────────────┼─────────────────────────────────────┤
│ Headers (Metadata)│ Extra tags (e.g. transaction ID)    │
└───────────────────┴─────────────────────────────────────┘
```

##### Analogy: A Physical Mail Envelope
> Think of an event like a letter sent in the mail:
> *   **The Key** is the mailing address written on the outside. It determines where the letter goes. In Kafka, the key ensures that events with the same key go to the same storage folder, keeping them in order.
> *   **The Value** is the actual letter inside the envelope. This is the main data payload (like the items ordered).
> *   **The Timestamp** is the date stamp showing when the envelope was mailed.
> *   **The Headers** are like custom stamps or priority labels stuck to the outside of the envelope, helping apps route or inspect it without opening the letter.

*   **Key**: Used to group events. Events with the same key are guaranteed to go to the same storage slice (partition) in order.
*   **Value**: The main information body. It can be written in plain text, JSON, or special binary formats (Avro, Protobuf).
*   **Timestamp**: The time when the event was created or stored.
*   **Headers**: Optional extra tags (like security tokens) added without changing the value payload.

#### Anatomy of an Event Stream
An **event stream** is a continuous sequence of events. It has three main rules:
1.  **Continuous**: It has no end. Events keep coming as long as the business is running.
2.  **Ordered**: Within a storage partition, events are stored in the exact order they arrive.
3.  **Replayable**: Events are written safely to disk. Unlike traditional message queues, they are not deleted after they are read. You can go back and read them again.

##### Analogy: A Notebook vs. a Sticky Note
> A traditional queue is like a sticky note. You read it, and then you throw it in the trash.
> Kafka is like a notebook. You write lines on pages. Once you read a line, you don't erase it. It stays there forever. If you want to check something from last week, you can just turn the pages back and read it again.

---

### Intermediate Level: The Apache Kafka Ecosystem & Retail Order Flow

#### The Apache Kafka Ecosystem
Apache Kafka is made of several friendly parts that work together:

```text
  ┌─────────────────┐             ┌─────────────────┐
  │  Kafka Connect  │             │  Kafka Connect  │
  │ (Source System) │             │  (Sink System)  │
  └────────┬────────┘             └────────▲────────┘
           │ (Writes)                      │ (Reads)
           ▼                               │
  ┌─────────────────┐    (Checks)      ┌───┴─────────────┐
  │  Kafka Producer │◄────────────────►│ Schema Registry │
  └────────┬────────┘                  └───▲─────────────┘
           │ (Writes Bytes)                │ (Resolves)
           ▼                               │
 ┌──────────────────────────────────────────┴───────────────┐
 │                      KAFKA BROKERS                       │
 │    (Simple Storage Servers that store event logs)        │
 └──────────────────┬───────────────────────────────────────┘
                    │ (Reads Bytes)
                    ▼
   ┌────────────────┴──────────────────┐
   │          Kafka Consumer           │
   │  (Apps, Streams API, ksqlDB SQL)  │
   └───────────────────────────────────┘
```

1.  **Kafka Brokers**: The servers that store the events on disk and send them to clients.
2.  **Schema Registry**: A rules coordinator that keeps track of what events should look like, ensuring they are valid.
3.  **Producers and Consumers**: The client libraries that apps use to send data (produce) or read data (consume).
4.  **Kafka Connect**: Pre-built bridges to copy data automatically between databases and Kafka.
5.  **Kafka Streams**: A library for processing streams of events inside Java applications.
6.  **ksqlDB**: A database that lets you process streams using simple SQL queries.

#### Retail Order Flow: Concrete Example
Let's see how events travel through an online retail store (ZMart):
1.  **Jane buys a book**: The cash register app (Producer) sends a `sale` event to the `sales-transactions` topic.
2.  **Point masking**: A Kafka Connect tool automatically masks Jane's credit card number before writing it to disk.
3.  **Rewards Service**: A loyalty app (Consumer) reads the event. If Jane has spent enough money, it writes a `reward-notification` event to send her a coupon.
4.  **Real-time Dashboard**: A Kafka Streams app consumes the transaction to update store sales trends instantly on a screen.

---

### Advanced Level: Serialization, Zero-Copy Reads, and Client Pull Mechanisms

#### Data Serialization
Because Kafka brokers only store raw bytes, clients must turn objects into bytes before sending them. This is called **serialization**. Turning bytes back into objects is called **deserialization**. Using binary schemas (like Avro or Protobuf) makes the data very small and efficient, saving network space.

#### OS Zero-Copy Reads
When a consumer requests data, Kafka brokers do not copy data into JVM application memory. Instead, they use a Linux kernel trick called `sendfile`. This transfers file pages directly from the OS storage cache to the network card. This avoids memory copy overhead and makes reads extremely fast.

#### Client Pull Model
Traditional message queues push messages to consumers. If a consumer is slow, the queue can overload it. Kafka uses a pull model: consumers ask for batches of data when they are ready. This prevents overload and allows consumers to control their own speed.

---

## 2. Theory vs. Production Trade-offs

Let's compare Kafka with traditional messaging queues (like RabbitMQ):

| Feature | Traditional Messaging (RabbitMQ) | Event Streaming (Apache Kafka) |
| :--- | :--- | :--- |
| **Data Delivery** | Broker pushes data to client. | Client pulls data from broker. |
| **Data Storage** | Messages are deleted once read. | Messages are kept on disk durably. |
| **Replaying Data** | Not possible. | Fully supported (just reset the offset). |
| **Throughput (Speed)**| Moderate (broker tracks individual locks). | Massive (uses page cache and zero-copy). |

---

## 3. Common Errors & Pitfalls

### Pitfall 1: Out-of-Order Messages Under Retries
*   **Why it fails**: If the network drops, a producer might retry sending a failed batch. If a newer batch was already written, the retried batch will land out of order.
*   **How to fix**: Set `enable.idempotence=true` in client configurations. This assigns sequence numbers to batches so the broker always writes them in the correct order.

### Pitfall 2: Scanning Kafka for Single-Record Lookups
*   **Why it fails**: Kafka topics are linear log files. Searching for a specific customer ID requires scanning the file from beginning to end, which is very slow.
*   **How to fix**: Export the data to a search database (like MongoDB or Elasticsearch) using Kafka Connect, or use a Kafka Streams state store.

---

## 4. Socratic Review Questions

### Question 1
Why does Kafka use a client-pull model instead of pushing data to consumers?

#### Answer
A client-pull model allows consumers to process data at their own pace. If the consumer is slow, it will not be overwhelmed with data. Additionally, it simplifies the broker's job because it doesn't need to track which messages have been acknowledged by which client; the client tracks its own position (offset).

### Question 2
What is the advantage of keeping events on disk instead of deleting them immediately after they are read?

#### Answer
Keeping events on disk allows new applications to read the historical data from the beginning. It also makes debugging easy; if a service has a bug, you can patch the code, reset the offset, and replay the stream to fix the data.

---

## Hands-on Lab: Setting Up a Local Kafka Cluster

In this lab, we will start a local Kafka broker using Docker Compose and interact with it using CLI tools.

### 1. Create the `docker-compose.yml` File
Create a new file named `docker-compose.yml` and paste this content:

```yaml
version: '3.8'
services:
  broker:
    image: confluentinc/cp-kafka:7.6.0
    container_name: kafka-broker
    ports:
      - "9092:9092"
    environment:
      KAFKA_NODE_ID: 1
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: 'CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT,PLAINTEXT_HOST:PLAINTEXT'
      KAFKA_ADVERTISED_LISTENERS: 'PLAINTEXT://broker:29092,PLAINTEXT_HOST://localhost:9092'
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
      KAFKA_GROUP_INITIAL_REBALANCE_DELAY_MS: 0
      KAFKA_TRANSACTION_STATE_LOG_MIN_ISR: 1
      KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR: 1
      KAFKA_PROCESS_ROLES: 'broker,controller'
      KAFKA_CONTROLLER_QUORUM_VOTERS: '1@broker:29093'
      KAFKA_LISTENERS: 'PLAINTEXT://0.0.0.0:29092,CONTROLLER://0.0.0.0:29093,PLAINTEXT_HOST://0.0.0.0:9092'
      KAFKA_INTER_BROKER_LISTENER_NAME: 'PLAINTEXT'
      KAFKA_CONTROLLER_LISTENER_NAMES: 'CONTROLLER'
      KAFKA_LOG_DIRS: '/tmp/kraft-combined-logs'
      CLUSTER_ID: 'MkU3OEVBNTcwNTJENDM2Qk'

  schema-registry:
    image: confluentinc/cp-schema-registry:7.6.0
    container_name: schema-registry
    depends_on:
      - broker
    ports:
      - "8081:8081"
    environment:
      SCHEMA_REGISTRY_HOST_NAME: schema-registry
      SCHEMA_REGISTRY_KAFKASTORE_BOOTSTRAP_SERVERS: 'PLAINTEXT://broker:29092'
      SCHEMA_REGISTRY_LISTENERS: 'http://0.0.0.0:8081'
```

---

### Detailed Breakdown of the `docker-compose.yml` Configurations

Here is what each environment configuration line actually does in plain English:

#### Broker Service Configuration Rules:
*   `KAFKA_NODE_ID: 1`: The unique number identifying this broker in the cluster.
*   `KAFKA_LISTENER_SECURITY_PROTOCOL_MAP`: Maps connection names to security protocols. It tells Kafka that the `CONTROLLER`, `PLAINTEXT`, and `PLAINTEXT_HOST` channels will use plain unencrypted text (`PLAINTEXT`) for simplicity.
*   `KAFKA_ADVERTISED_LISTENERS`: The connection addresses the broker broadcasts to clients. The registry connects using `broker:29092` (inside Docker), and local apps connect using `localhost:9092` (outside Docker).
*   `KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1`: Sets how many copies of the internal offset tracking topic are stored. Since we only have 1 broker, we store 1 copy.
*   `KAFKA_GROUP_INITIAL_REBALANCE_DELAY_MS: 0`: The delay before consumer groups rebalance their layout on startup. We set this to 0 milliseconds to start consuming immediately.
*   `KAFKA_TRANSACTION_STATE_LOG_MIN_ISR: 1`: The minimum number of replica nodes that must write transaction records before they are considered successful.
*   `KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR: 1`: Number of replica copies of the transaction state log topic. Set to 1 for a single broker.
*   `KAFKA_PROCESS_ROLES: 'broker,controller'`: Tells Kafka that this process will act both as a broker (to save data) and a controller (to manage metadata coordinates).
*   `KAFKA_CONTROLLER_QUORUM_VOTERS: '1@broker:29093'`: Defines the voting addresses for metadata elections. Here, Node 1 is listening on port 29093.
*   `KAFKA_LISTENERS`: The exact socket addresses and ports where the broker listens for incoming network connections.
*   `KAFKA_INTER_BROKER_LISTENER_NAME: 'PLAINTEXT'`: Tells Kafka which channel to use when brokers talk to each other.
*   `KAFKA_CONTROLLER_LISTENER_NAMES: 'CONTROLLER'`: Tells Kafka which channel is dedicated to controller metadata signals.
*   `KAFKA_LOG_DIRS: '/tmp/kraft-combined-logs'`: The folder path on disk where the broker writes all incoming event log files.
*   `CLUSTER_ID: 'MkU3OEVBNTcwNTJENDM2Qk'`: A base64-encoded string identifying this cluster instance. All brokers in a cluster must use the same ID.

#### Schema Registry Service Configuration Rules:
*   `SCHEMA_REGISTRY_HOST_NAME: schema-registry`: Sets the container network name.
*   `SCHEMA_REGISTRY_KAFKASTORE_BOOTSTRAP_SERVERS: 'PLAINTEXT://broker:29092'`: The connection address Schema Registry uses to write its schema rules to the internal `_schemas` Kafka topic.
*   `SCHEMA_REGISTRY_LISTENERS: 'http://0.0.0.0:8081'`: The address and port where the Schema Registry REST API listens for curl queries (port 8081).

---

### 2. Start the Cluster
Run this command in your terminal to start the containers in the background:

```bash
docker-compose up -d
```

**Expected Output:**
```text
Creating network "kafka-network" with the default driver
Creating kafka-broker ... done
Creating schema-registry ... done
```

### 3. Verify Cluster Health
Ensure the container processes are active and running:

```bash
docker ps
```

**Expected Output:**
```text
CONTAINER ID   IMAGE                                   COMMAND                  STATUS         PORTS                              NAMES
a8b7c6d5e4f3   confluentinc/cp-schema-registry:7.6.0   "/etc/confluent/dock…"   Up 5 seconds   0.0.0.0:8081->8081/tcp             schema-registry
f3e4d5c6b7a8   confluentinc/cp-kafka:7.6.0             "/etc/confluent/dock…"   Up 7 seconds   0.0.0.0:9092->9092/tcp, 29092/tcp  kafka-broker
```

### 4. Create Your First Topic
Open a shell on the broker container and create a topic named `zmart-orders` with 1 partition:

```bash
docker exec -it kafka-broker kafka-topics --create --topic zmart-orders --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1
```

**Expected Output:**
```text
Created topic zmart-orders.
```

### 5. Produce Messages with Keys
Start the console producer, passing keys separated by a colon (`:`):

```bash
docker exec -it kafka-broker kafka-console-producer --topic zmart-orders --bootstrap-server localhost:9092 --property parse.key=true --property key.separator=:
```

When the command runs, type the following lines and press enter after each to publish:

```text
C100:{"order_id":"ORD-991","amount":89.50}
C101:{"order_id":"ORD-992","amount":120.00}
C100:{"order_id":"ORD-993","amount":45.20}
```

Press `Ctrl+C` to terminate the producer when done.

### 6. Consume Messages from the Start
Open a consumer process to read the key-value messages from the beginning:

```bash
docker exec -it kafka-broker kafka-console-consumer --topic zmart-orders --bootstrap-server localhost:9092 --from-beginning --property print.key=true --property key.separator=" -> "
```

**Expected Output:**
```text
C100 -> {"order_id":"ORD-991","amount":89.50}
C101 -> {"order_id":"ORD-992","amount":120.00}
C100 -> {"order_id":"ORD-993","amount":45.20}
```
