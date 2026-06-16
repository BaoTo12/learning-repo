# Module 13 — Kafka Streams Interactive Queries

In this module, we will explore Kafka Streams Interactive Queries (IQ). We will learn how to query state stores directly from your application. We will examine why Interactive Queries matter, turning a stream processing application into a queryable data store without needing an external database. We will cover the different read-only state store types (`ReadOnlyKeyValueStore`, `ReadOnlyWindowStore`, `ReadOnlySessionStore`) and how to obtain references to them. We will discuss the challenges of distributed state, where partition stores are sharded across multiple application instances, and how to use `StreamsMetadata` and `KeyQueryMetadata` to locate keys. Finally, we will build a production-grade Spring Boot REST API that uses IQ to query local state stores and dynamically route requests to remote instances when necessary. We will close with Socratic review questions, hands-on labs with complete code structures, and detailed configuration tables.

---

## 1. Academic Lecture: State Store Querying & REST Routing

### Basic Level: Interactive Queries Concept & Key Lookups

#### What are Interactive Queries (IQ)?
In standard stream processing, the pipeline consumes events, updates local state stores, and writes outputs to a downstream Kafka topic. If an external service wants to know the current state of a key (for example, a customer's total purchase count), it must read from the output topic and write the values into an external database like PostgreSQL, Redis, or Elasticsearch, which is then queried by a REST API.

```text
  Standard Architecture:
  [Kafka Topic] ──► [Kafka Streams] ──► [Output Topic] ──► [Sync Job] ──► [External DB] ──► [REST API]
```

**Interactive Queries (IQ)** bypass this complexity. They allow you to query the state stores inside your Kafka Streams application directly from external APIs.

```text
  Interactive Queries Architecture:
  [Kafka Topic] ──► [Kafka Streams (State Store)] ◄── Query Directly ──◄ [REST API]
```

#### Why Interactive Queries Matter
By using IQ, you turn your Kafka Streams application into a queryable database.
* **No Database Sync Latency**: Query results represent the real-time state of the stream processor immediately.
* **Simplified Infrastructure**: You do not need to configure, license, or manage a separate external database cluster (like Redis or Cassandra) just to serve point lookups.
* **Cost Efficiency**: Reduces data replication and disk storage overhead.

#### Querying a Local State Store
To query a state store, you retrieve a read-only view of it using the `KafkaStreams` runtime instance. You use **`StoreQueryParameters`** to specify the name of the store and the query type:

```java
ReadOnlyKeyValueStore<String, Long> store = kafkaStreams.store(
    StoreQueryParameters.fromNameAndType(
        "purchase-counts",
        QueryableStoreTypes.keyValueStore()
    )
);
```

Once you have the store reference, you can perform standard lookup operations like `store.get("key")`.

---

### Intermediate Level: Read-Only Store Types & Distributed Metadata

#### State Store Types and Query APIs
Kafka Streams provides specialized interfaces depending on the type of state store you are querying:

##### 1. `ReadOnlyKeyValueStore<K, V>`
* **Usage**: Point lookups and range scans on standard key-value state stores.
* **Methods**:
  * `store.get(key)`: Retrieves the value for a specific key.
  * `store.range(fromKey, toKey)`: Scans all keys between two boundaries lexicographically.
  * `store.all()`: Opens an iterator over all records in the store.

##### 2. `ReadOnlyWindowStore<K, V>`
* **Usage**: Querying time-windowed aggregations.
* **Methods**:
  * `store.fetch(key, timeFrom, timeTo)`: Retrieves all window values for a specific key within a time range.
  * `store.fetchAll(timeFrom, timeTo)`: Scans all window aggregates across all keys within a time range.

##### 3. `ReadOnlySessionStore<K, V>`
* **Usage**: Querying active user session windows.
* **Methods**:
  * `store.fetch(key)`: Retrieves all active sessions recorded for a specific key.

#### The Challenge of Distributed State
If you run multiple instances of your application to scale processing, your input topic partitions are distributed among these instances. A state store is **sharded** accordingly: each instance only holds the state for the partitions it is actively consuming.

If an API request arrives at Instance A asking for the state of Key `X`, but Key `X` is mapped to a partition consumed by Instance B, Instance A cannot find Key `X` in its local state store.

```text
  Incoming HTTP request for Key: "customer-100" ──► [Instance A (Partitions 1 & 2)] (Not found!)
                                                          │
                                                    Route Remote
                                                          │
                                                          ▼
                                                    [Instance B (Partitions 3 & 4)] (Found!)
```

#### Key Metadata Discovery
To solve the distributed state problem, Kafka Streams provides metadata APIs that allow instances to discover the network locations of all running application tasks:
* **`StreamsMetadata`**: Contains information about an instance, including its host, port, and the partitions it owns.
* **`KeyQueryMetadata`**: Pinpoints exactly which host instance currently owns the partition containing a specific key.

```java
KeyQueryMetadata metadata = kafkaStreams.queryMetadataForKey(
    "purchase-counts",
    customerId,
    new StringSerializer()
);
```

Using the returned `metadata.activeHost()`, Instance A can check if the key is local. If it is not, Instance A reads the remote host's IP and port, and forwards the HTTP request directly to Instance B.

---

### Advanced Level: Spring Boot Integration & Cross-Instance Routing

#### Configuring Server Discovery
For instances to discover each other's network addresses, you must configure the **`application.server`** configuration property in your Kafka Streams properties. This property tells the Kafka coordinator the public host and port of the running instance:

```properties
application.server=localhost:8080
```
*If this configuration is missing, metadata queries will return `HostInfo.unavailable()`, and cross-instance routing will fail.*

#### Spring Boot Integration
When building a Spring Boot application, you retrieve the `KafkaStreams` client from the Spring framework using the `StreamsBuilderFactoryBean`:

```java
@Autowired
private StreamsBuilderFactoryBean streamsBuilderFactoryBean;

public KafkaStreams getStreams() {
    return streamsBuilderFactoryBean.getKafkaStreams();
}
```

#### Cross-Instance Routing Logic
Inside your REST controller, you implement routing logic:
1. Fetch the `KeyQueryMetadata` for the requested key.
2. Compare the active host returned by the metadata against the current instance's host address.
3. If they match, query the local state store and return the result.
4. If they do not match, construct the forwarding URL and fetch the result from the remote instance using an HTTP client (like `RestTemplate` or WebClient).

---

## 2. Theory & Production Best Practices

### Read-Only Store Types Comparison

| Store Type | Query Method | Returned Iterator Type | Temporal Support | Primary Use Case |
| :--- | :--- | :--- | :--- | :--- |
| **KeyValue** | `get()`, `range()`, `all()` | `KeyValueIterator<K, V>` | None | Real-time user profiles, key-based counts. |
| **Window** | `fetch(K, long, long)` | `WindowStoreIterator<V>` | Yes | Rolling metrics, hourly transaction views. |
| **Session** | `fetch(K)` | `KeyValueIterator<Windowed<K>, V>`| Yes | User web browsing activity sessions. |

### Production REST Routing Considerations

* **Host Name Consistency**: Ensure the `application.server` property uses hostnames that are resolvable by all instances in the network (e.g., use container hostnames like `kstreams-node-1` instead of `localhost` when deploying to Docker or Kubernetes).
* **Caching vs. Read Freshness**: If your topology has state caching enabled (`CACHE_MAX_BYTES_BUFFERING_CONFIG > 0`), updates are held in memory before flushing. Interactive queries bypass the cache and read directly from the underlying state store. If you need strictly fresh reads, disable the cache or force a flush.
* **Rebalance Grace Period**: During consumer group rebalances, partition ownership shifts between instances. IQ lookups during a rebalance may return stale data or throw exceptions. Implement a retry mechanism in your REST API to handle transient rebalance states.

---

## 3. Common Errors & Troubleshooting

### 1. `InvalidStateStoreException: The state store is still initializing`
* **Symptom**: REST endpoints fail with this exception during application boot.
* **Root Cause**: The application has started, but Kafka Streams has not finished restoring the state store from the changelog topic.
* **Fix**: Catch the exception and return a HTTP `503 Service Unavailable` status, or verify that the streams state is `RUNNING` before executing queries.

### 2. HTTP Forwarding Infinite Loops
* **Symptom**: Forwarded requests stack up, causing CPU spikes and timeouts.
* **Root Cause**: If Instance A believes Instance B owns the key, and Instance B believes Instance A owns the key, they will forward requests back and forth forever. This happens when the metadata partition maps are out of sync during a rebalance.
* **Fix**: Add a query parameter flag (e.g., `?localOnly=true`) to forwarded requests. If an instance receives a request with this flag, it is forbidden from forwarding it further and must return whatever is in its local store.

### 3. RocksDB File Lock / Memory Leaks
* **Symptom**: The application runs out of file descriptors or memory after many queries.
* **Root Cause**: Iterators returned by `store.all()` or `store.range()` read directly from off-heap RocksDB iterators. If you do not close them, they leak native memory and file locks.
* **Fix**: Always open iterators inside a try-with-resources block:
  ```java
  try (KeyValueIterator<String, Long> iter = store.all()) {
      // Loop here
  }
  ```

---

## 4. Socratic Review Questions

### Question 1
*Why must we call `close()` on the iterators returned by `store.range()` and `store.all()`, but not on the result of `store.get()`?*
* **Answer**: `store.get()` returns a single deserialized Java object and immediately releases any native database references. `store.range()` and `store.all()` return a stream-like iterator connected to active, native RocksDB read handles. If you do not close the iterator, the native native memory and filesystem locks are kept open, eventually causing memory leaks and operating system crashes.

### Question 2
*Under what scenario can `StreamsMetadata` return an IP address and port that causes a `ConnectException` during forwarding?*
* **Answer**: This occurs when `application.server` is configured incorrectly (for example, set to `localhost:8080` inside a Docker container). While the metadata query returns a valid address, other containers running on separate hosts cannot resolve `localhost` to the target container, causing connection failures. The property must be set to a DNS hostname or IP address that is routable across the entire cluster network.

### Question 3
*How does state store caching configuration affect the results returned by Interactive Queries?*
* **Answer**: Interactive Queries read directly from the underlying RocksDB or in-memory state store. Since caching holds updates in memory before flushing them to the store, there can be a delay between a record entering the topology and its updated value appearing in an IQ lookup. If your application requires absolute read consistency, you must set caching size to 0.

### Question 4
*What happens if you query a key using `queryMetadataForKey` but the topic partition is currently unassigned due to a rebalance?*
* **Answer**: The metadata query will return `null` or a metadata object with `HostInfo.unavailable()`. Your REST API must handle this by checking for empty active host info and returning a retriable error status (such as HTTP 503) to the client.

### Question 5
*Can you use Interactive Queries to modify data inside a state store?*
* **Answer**: No. Interactive Queries only expose read-only interfaces (`ReadOnlyKeyValueStore`, `ReadOnlyWindowStore`, etc.). State stores can only be modified internally by record processors running within the topology tasks. This maintains strict data isolation and partition thread safety.

---

## 5. Hands-on Labs

### Lab 13.1 — Query a local state store

#### Scenario
We will create a utility helper class named `LocalStoreQueryApp` that uses the `KafkaStreams` instance to locate and read from a local state store named `"purchase-counts"`.

#### Complete Java Code
Create the file [LocalStoreQueryApp.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/kafka-streams-in-action/modules/src/main/java/com/kafkastreams/course/labs/LocalStoreQueryApp.java) with the following content:

```java
package com.kafkastreams.course.labs;

import org.apache.kafka.common.serialization.Serdes;
import org.apache.kafka.streams.KafkaStreams;
import org.apache.kafka.streams.StoreQueryParameters;
import org.apache.kafka.streams.StreamsBuilder;
import org.apache.kafka.streams.StreamsConfig;
import org.apache.kafka.streams.Topology;
import org.apache.kafka.streams.kstream.Consumed;
import org.apache.kafka.streams.kstream.Materialized;
import org.apache.kafka.streams.state.QueryableStoreTypes;
import org.apache.kafka.streams.state.ReadOnlyKeyValueStore;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.Properties;

public class LocalStoreQueryApp {
    private static final Logger log = LoggerFactory.getLogger(LocalStoreQueryApp.class);

    public static Properties getConfig() {
        Properties props = new Properties();
        props.put(StreamsConfig.APPLICATION_ID_CONFIG, "local-query-group");
        props.put(StreamsConfig.BOOTSTRAP_SERVERS_CONFIG, "localhost:9092");
        props.put(StreamsConfig.DEFAULT_KEY_SERDE_CLASS_CONFIG, Serdes.String().getClass().getName());
        props.put(StreamsConfig.DEFAULT_VALUE_SERDE_CLASS_CONFIG, Serdes.Long().getClass().getName());
        return props;
    }

    public static void main(String[] args) throws Exception {
        log.info("Bootstrapping Local Query App...");

        StreamsBuilder builder = new StreamsBuilder();
        
        // 1. Consume from a purchases topic and aggregate counts in a materialized store
        builder.stream("purchases", Consumed.with(Serdes.String(), Serdes.String()))
            .groupByKey()
            .count(Materialized.as("purchase-counts"));

        Topology topology = builder.build();
        KafkaStreams streams = new KafkaStreams(topology, getConfig());
        streams.start();

        // Wait for store initialization
        Thread.sleep(5000);

        // 2. Query the local state store using StoreQueryParameters
        ReadOnlyKeyValueStore<String, Long> localStore = streams.store(
            StoreQueryParameters.fromNameAndType(
                "purchase-counts",
                QueryableStoreTypes.keyValueStore()
            )
        );

        // 3. Perform point lookups
        String targetCustomer = "customer-001";
        Long purchaseCount = localStore.get(targetCustomer);
        log.info("Query finished -> Customer: {} | Local Purchase Count: {}", targetCustomer, purchaseCount);

        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            log.info("Stopping local query app...");
            streams.close();
        }));
    }
}
```

#### Step-by-Step Code Walkthrough
1. **Materialization**: The topology reads a stream of purchase events and groups them by customer key. The `.count(Materialized.as("purchase-counts"))` operator instantiates a local RocksDB state store named `"purchase-counts"`.
2. **`streams.store()`**: After starting the streams client, we query the runtime for the store reference. We pass `StoreQueryParameters.fromNameAndType(...)`, defining our store name and specifying that we want a read-only **KeyValue** query type.
3. **`localStore.get()`**: We execute a standard lookup for key `"customer-001"`. If the key exists, it returns the aggregated total; otherwise, it returns `null`.

---

### Lab 13.2 — Build a Spring Boot REST controller with routing

#### Scenario
We will build a Spring Boot REST Controller that exposes our state store data. The controller uses `KeyQueryMetadata` to check if a requested key is hosted locally. If it is, the controller queries the local store. If it is hosted on a remote instance, the controller forwards the request to the correct instance using a HTTP client.

#### Complete Controller Java Code
Create the file [PurchaseQueryController.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/kafka-streams-in-action/modules/src/main/java/com/kafkastreams/course/labs/PurchaseQueryController.java) with the following content:

```java
package com.kafkastreams.course.labs;

import org.apache.kafka.common.serialization.StringSerializer;
import org.apache.kafka.streams.KafkaStreams;
import org.apache.kafka.streams.KeyQueryMetadata;
import org.apache.kafka.streams.StoreQueryParameters;
import org.apache.kafka.streams.state.QueryableStoreTypes;
import org.apache.kafka.streams.state.ReadOnlyKeyValueStore;
import org.apache.kafka.streams.state.HostInfo;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.client.RestTemplate;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

@RestController
@RequestMapping("/api/purchases")
public class PurchaseQueryController {
    private static final Logger log = LoggerFactory.getLogger(PurchaseQueryController.class);

    private final KafkaStreams kafkaStreams;
    private final HostInfo localHostInfo;
    private final RestTemplate restTemplate;

    public PurchaseQueryController(KafkaStreams kafkaStreams, HostInfo localHostInfo) {
        this.kafkaStreams = kafkaStreams;
        this.localHostInfo = localHostInfo;
        this.restTemplate = new RestTemplate();
    }

    @GetMapping("/count/{customerId}")
    public ResponseEntity<Long> getCount(
            @PathVariable String customerId,
            @RequestParam(required = false, defaultValue = "false") boolean localOnly) {
        
        log.info("Received request for Customer ID: {} (LocalOnly: {})", customerId, localOnly);

        // 1. Locate the instance owning the key
        KeyQueryMetadata metadata = kafkaStreams.queryMetadataForKey(
            "purchase-counts",
            customerId,
            new StringSerializer()
        );

        if (metadata == null || metadata.activeHost() == null) {
            log.warn("Metadata unavailable for Key: {}", customerId);
            return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE).build();
        }

        HostInfo activeHost = metadata.activeHost();

        // 2. Query locally if the current instance is the owner
        if (activeHost.host().equals(localHostInfo.host()) && activeHost.port() == localHostInfo.port()) {
            log.info("Key is owned locally. Accessing local state store...");
            try {
                ReadOnlyKeyValueStore<String, Long> store = kafkaStreams.store(
                    StoreQueryParameters.fromNameAndType(
                        "purchase-counts",
                        QueryableStoreTypes.keyValueStore()
                    )
                );
                Long val = store.get(customerId);
                return ResponseEntity.ok(val != null ? val : 0L);
            } catch (Exception e) {
                log.error("Failed to query local store", e);
                return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).build();
            }
        }

        // 3. Prevent forwarding loop if localOnly is flag is set to true
        if (localOnly) {
            log.warn("Request was forwarded but target instance did not find key locally.");
            return ResponseEntity.status(HttpStatus.NOT_FOUND).build();
        }

        // 4. Forward HTTP request to the remote instance owning the key
        String url = String.format("http://%s:%d/api/purchases/count/%s?localOnly=true",
            activeHost.host(),
            activeHost.port(),
            customerId
        );

        log.info("Key is hosted remotely on {}:{}. Forwarding request...", activeHost.host(), activeHost.port());
        try {
            Long remoteCount = restTemplate.getForObject(url, Long.class);
            return ResponseEntity.ok(remoteCount);
        } catch (Exception e) {
            log.error("Failed to fetch count from remote instance at URL: {}", url, e);
            return ResponseEntity.status(HttpStatus.BAD_GATEWAY).build();
        }
    }
}
```

#### Step-by-Step Code Walkthrough
1. **Metadata Query**: We call `kafkaStreams.queryMetadataForKey(...)`, passing the state store name, the key, and a Serializer to compute the key hash. This returns a `KeyQueryMetadata` object containing the host address owning that partition.
2. **Local Address Check**: We compare the returned host and port details against `localHostInfo` (which represents the server running this controller).
3. **Local Store Retrieval**: If they match, we query our local memory using `kafkaStreams.store()` and retrieve the value. If the value is missing, we return a fallback count of `0`.
4. **Preventing Loops**: If we receive a forwarded request (identified by `localOnly=true`) but our metadata check says the key belongs elsewhere, we return `404 Not Found` to prevent infinite routing cycles during group rebalances.
5. **HTTP Forwarding**: If the owner is remote, we construct a URL using the metadata address, append `?localOnly=true`, execute an HTTP request using `RestTemplate`, and forward the returned result back to our client.

---

### Lab 13.3 — Range scan: get customer counts

#### Scenario
We will perform a range scan query on a read-only key-value store to retrieve and log counts for all customers within a specific range of IDs.

#### Complete Java Code
Create the file [RangeScanSpendApp.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/kafka-streams-in-action/modules/src/main/java/com/kafkastreams/course/labs/RangeScanSpendApp.java) with the following content:

```java
package com.kafkastreams.course.labs;

import org.apache.kafka.common.serialization.Serdes;
import org.apache.kafka.streams.KafkaStreams;
import org.apache.kafka.streams.StoreQueryParameters;
import org.apache.kafka.streams.StreamsBuilder;
import org.apache.kafka.streams.Topology;
import org.apache.kafka.streams.kstream.Consumed;
import org.apache.kafka.streams.kstream.Materialized;
import org.apache.kafka.streams.state.KeyValueIterator;
import org.apache.kafka.streams.state.QueryableStoreTypes;
import org.apache.kafka.streams.state.ReadOnlyKeyValueStore;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.Properties;

public class RangeScanSpendApp {
    private static final Logger log = LoggerFactory.getLogger(RangeScanSpendApp.class);

    public static void main(String[] args) throws Exception {
        log.info("Starting Range Scan App...");

        StreamsBuilder builder = new StreamsBuilder();
        builder.stream("purchases", Consumed.with(Serdes.String(), Serdes.String()))
            .groupByKey()
            .count(Materialized.as("purchase-counts"));

        Topology topology = builder.build();
        KafkaStreams streams = new KafkaStreams(topology, LocalStoreQueryApp.getConfig());
        streams.start();

        Thread.sleep(5000);

        ReadOnlyKeyValueStore<String, Long> localStore = streams.store(
            StoreQueryParameters.fromNameAndType(
                "purchase-counts",
                QueryableStoreTypes.keyValueStore()
            )
        );

        // 1. Execute range query between key boundary filters
        String startKey = "customer-001";
        String endKey = "customer-099";

        log.info("Scanning customer counts in range [{} - {}]...", startKey, endKey);
        
        // 2. Iterate safely using try-with-resources to ensure native resource cleanup
        try (KeyValueIterator<String, Long> iterator = localStore.range(startKey, endKey)) {
            while (iterator.hasNext()) {
                var entry = iterator.next();
                log.info("Range Scan Results -> Customer: {} | Purchase Count: {}", entry.key, entry.value);
            }
        }

        streams.close();
    }
}
```

#### Step-by-Step Code Walkthrough
1. **Range Definition**: We define lower and upper boundaries (`"customer-001"` and `"customer-099"`).
2. **`localStore.range()`**: This executes a lexicographical scan on the state store. It returns a `KeyValueIterator`.
3. **Closing Iterators**: Because RocksDB operates outside the Java heap, it is critical to call `.close()` on the iterator once finished. We wrap the iterator initialization inside a try-with-resources statement. This guarantees that `iterator.close()` is called automatically, freeing the file descriptors and preventing native memory leaks.
