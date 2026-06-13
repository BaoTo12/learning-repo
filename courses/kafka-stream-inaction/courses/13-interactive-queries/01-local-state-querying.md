# Module 01: Materializing & Querying Local State

Interactive Queries (IQ) convert your streaming application instances into a high-performance, distributed key-value database. Instead of exporting aggregated values to a database like MySQL or Elasticsearch just to serve UI requests, you query the local RocksDB or in-memory state stores directly.

This module covers the prerequisites for exposing state stores, the modern IQv2 query types, and how to query local task partitions using a Spring Boot `@RestController`.

---

## 1. Prerequisites: Naming Materialized State Stores

To query a state store, you must configure a materialization name. If you do not provide a name, Kafka Streams assigns a random internal identifier (e.g. `KSTREAM-AGGREGATE-STATE-STORE-0000000002`) which changes every time the topology is rebuilt, making it impossible to target in queries.

### Naming a Store in the DSL

```java
import org.apache.kafka.common.serialization.Serdes;
import org.apache.kafka.streams.kstream.Materialized;
import org.apache.kafka.streams.state.Stores;

// Option A: Let Kafka Streams use the default persistent (RocksDB) store type with a name
Materialized.<String, Long, KeyValueStore<Bytes, byte[]>>as("purchase-count-store")
    .withKeySerde(Serdes.String())
    .withValueSerde(Serdes.Long());

// Option B: Manually specify an In-Memory store type with a name
Materialized.<String, Long, KeyValueStore<Bytes, byte[]>>as(
    Stores.inMemoryKeyValueStore("purchase-count-store")
)
.withKeySerde(Serdes.String())
.withValueSerde(Serdes.Long());
```

---

## 2. Introducing the Modern IQv2 API

Historically, Kafka Streams used different, siloed APIs for querying stores (e.g., `ReadOnlyKeyValueStore`, `ReadOnlyWindowStore`). The modern **Interactive Queries v2 (IQv2)** API unifies querying under a single `query()` method on the `KafkaStreams` class.

### The Unified Query Interfaces
IQv2 introduces four distinct query classes implementing the `org.apache.kafka.streams.query.Query` interface:

1. **`KeyQuery<K, V>`**: Fetches the value associated with a single key in a key-value store.
2. **`RangeQuery<K, V>`**: Scans a range of keys (from lower bounds to upper bounds) in a key-value store.
3. **`WindowKeyQuery<K, V>`**: Fetches windowed records for a single key over a time range.
4. **`WindowRangeQuery<K, V>`**: Fetches windowed records across a range of keys over a time range.

---

## 3. Querying the State Store Locally

To perform a local lookup, you:
1. Construct the query instance (e.g. `KeyQuery.withKey(key)`).
2. Wrap it inside a `StateQueryRequest` targeting the materialized store name.
3. Execute it using `kafkaStreams.query(request)`.

```java
import org.apache.kafka.streams.KafkaStreams;
import org.apache.kafka.streams.query.KeyQuery;
import org.apache.kafka.streams.query.StateQueryRequest;
import org.apache.kafka.streams.query.StateQueryResult;
import org.apache.kafka.streams.query.QueryResult;

public class LocalStoreQueryService {

    private final KafkaStreams kafkaStreams;

    public LocalStoreQueryService(KafkaStreams kafkaStreams) {
        this.kafkaStreams = kafkaStreams;
    }

    public LoanAppRollup getLocalRollup(String storeName, String loanType, int partitionId) {
        // 1. Build the KeyQuery
        KeyQuery<String, LoanAppRollup> keyQuery = KeyQuery.withKey(loanType);

        // 2. Build the request, narrowing it down to the partition we know is local
        StateQueryRequest<LoanAppRollup> request = StateQueryRequest
            .inStore(storeName)
            .withQuery(keyQuery)
            .withPartitions(Collections.singleton(partitionId));

        // 3. Execute the query against the KafkaStreams client
        StateQueryResult<LoanAppRollup> result = kafkaStreams.query(request);

        // 4. Retrieve the single partition result
        QueryResult<LoanAppRollup> partitionResult = result.getOnlyPartitionResult();
        
        return partitionResult.getResult();
    }
}
```

---

## 4. Exposing State via a Spring Boot REST Controller

By deploying our Kafka Streams application inside a Spring Boot environment, we can expose RocksDB query states to client devices over HTTP endpoints.

```java
import org.apache.kafka.streams.KafkaStreams;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/loan-app-iq")
public class LoanApplicationController {

    private final KafkaStreams kafkaStreams;
    private final String storeName;

    @Autowired
    public LoanApplicationController(
            KafkaStreams kafkaStreams,
            @Value("${store.name}") String storeName) {
        this.kafkaStreams = kafkaStreams;
        this.storeName = storeName;
    }

    // Exposing the local lookup over a REST endpoint
    @GetMapping("/local/loantype/{category}/{partition}")
    public LoanAppRollup getLocalRollup(
            @PathVariable String category,
            @PathVariable int partition) {
        
        LocalStoreQueryService queryService = new LocalStoreQueryService(kafkaStreams);
        return queryService.getLocalRollup(storeName, category, partition);
    }
}
```

---

## 5. Architectural Considerations

### Single Partition Results vs. Multi-Partition Maps
If you use `stateQueryResult.getOnlyPartitionResult()` on a query that spans multiple partitions (like `RangeQuery` or a query where you didn't restrict partitions), the client will throw a `RuntimeException`. 
* **Safe Pattern**: For single key queries, use `getOnlyPartitionResult()`. For range scans, extract the map using `stateQueryResult.getPartitionResults()` and iterate over partition keys.

### Query Latency & Threading
Interactive queries are executed on the calling HTTP thread, not on the StreamThread. RocksDB fetches are off-heap, bypassing JVM garbage collection limits. This ensures sub-millisecond latencies, making interactive queries safe to use inside high-performance user APIs.
* **Caution**: Do not perform massive range scans or full table iterations inside a REST API endpoint, as it blocks the web thread and consumes heavy filesystem resources.
