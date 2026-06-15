# Module 08 — The KTable API

In this module, we will explore the KTable and GlobalKTable abstractions in the Kafka Streams API. We will examine the core differences between a `KStream` (an event stream of independent facts) and a `KTable` (a changelog stream of updates, representing a materialized view). We will study the semantics of upsert updates and tombstone deletions. We will explore how KTables read from compacted topics and cover the techniques for converting between `KStream` and `KTable` using `toStream()` and `toTable()`. We will analyze KTable aggregations using grouping keys and the required adder and subtractor aggregators. We will contrast the partitioned `KTable` with the globally replicated `GlobalKTable` (no co-partitioning required) for reference lookups. Finally, we will dive into joins including Stream-Table, Stream-GlobalKTable, Table-Table (including foreign-key joins), versioned KTables for temporal consistency, and compile comprehensive hands-on labs with complete code structures and config tables.

---

## 1. Academic Lecture: Changelogs, Replicated Tables & Table Joins

### Basic Level: KTable Abstraction, Tombstones & Conversion Semantics

#### KTable vs. KStream: Update Stream vs. Event Stream
In Kafka Streams, there are two primary ways to interpret a partition topic stream:
* **`KStream` (Event Stream / Log)**: Treats every incoming record as an independent, append-only event. Even if multiple records arrive with the same key, they are all processed and kept.
  * *Database Analogy*: A history ledger of cash register receipts (inserts).
* **`KTable` (Update Stream / Changelog)**: Treats every incoming record as an **upsert** (Update or Insert). A record with key `K` and value `V` overwrites any previous value stored for key `K`.
  * *Database Analogy*: A materialized view showing the current account balance for each customer (primary key update).

```text
  Topic Input:      (Key: "user-1", Val: "Gold") ──► (Key: "user-1", Val: "Platinum")
  
  KStream View:     [ "user-1": "Gold" ]          ──► [ "user-1": "Platinum" ]  (Both events kept)
  
  KTable View:      [ "user-1": "Gold" ]          ──► [ "user-1": "Platinum" ]  (Only latest kept)
```

#### Changelog Semantics: Upserts and Tombstones
A `KTable` is backed by a local state store database. Its updates follow these rules:
* **Insert / Update (Upsert)**: If a record with key `K` and a non-null value `V` arrives:
  * If key `K` does not exist in the state store, it is inserted.
  * If key `K` already exists, its value is updated to `V`.
* **Delete (Tombstone)**: If a record with key `K` and a **null value** arrives:
  * This acts as a **Tombstone** marker. Kafka Streams removes the key `K` from the local state store and propagates the deletion downstream.
  * Tombstones are compacted eventually by the broker to clean up disk storage.

#### How KTable Reads from a Compacted Topic
On the Kafka broker, topics can be configured with log compaction (`cleanup.policy=compact`). Compacted topics periodically purge older records with duplicate keys, keeping only the latest value.
When a `KTable` consumes from a compacted topic:
* It reads the partition sequentially.
* Because the broker has already removed historical records, the `KTable` initializes faster, consuming a smaller log file.
* Once caught up, the `KTable` continues to receive real-time updates and tombstones directly.

#### Converting KStream ↔ KTable
You can convert between these two representations in the DSL:
* **`KStream` to `KTable`**: Call `KStream.toTable()`. This changes the semantic interpretation of the stream. Subsequent records with the same key will now be treated as updates rather than independent events. It materializes a state store automatically.
* **`KTable` to `KStream`**: Call `KTable.toStream()`. This converts the table updates back into a continuous stream of events. Each time the table is updated, the new value is emitted downstream as an append-only event.

---

### Intermediate Level: KTable Operations, Adders/Subtractors & GlobalKTables

#### KTable DSL Operations
The KTable API supports standard functional transformations:
* **`filter(Predicate)`**: Filters out records that do not match the predicate. If a record is filtered out, a **tombstone (null value)** is generated and written to the table to delete the key.
* **`mapValues(ValueMapper)`**: Transforms the value of table entries while keeping the key the same. Since the key is not changed, the record remains on the same partition.
* **`groupBy(KeyValueMapper)`**: Groups the table records by a new key (and potentially a new value) to prepare for aggregation.
  * *Important*: Grouping by a new key **always** triggers partition repartitioning.

#### KTable Aggregations: KGroupedTable
Aggregating a `KTable` is conceptually different from aggregating a `KStream`.
* In a `KStream`, records are append-only. You only need to **add** the new values to the running total.
* In a `KTable`, records are updates. When a record for key `K` changes its grouping category from "Category A" to "Category B", you must **subtract the old value** from Category A's total and **add the new value** to Category B's total.

Therefore, `KGroupedTable.aggregate()` requires two functional interfaces:
1. **Adder Aggregator (`Adder<K, V, VA>`)**: Adds the new value of the updated record to the aggregate.
2. **Subtractor Aggregator (`Subtractor<K, V, VA>`)**: Subtracts the previous value of the updated record from the aggregate.

```text
  Update: customer-1 moves from "Tier: Gold (10 points)" to "Tier: Platinum (20 points)"
  
  Aggregation Steps:
  1. Subtractor: Subtracts 10 points from the Gold aggregate total.
  2. Adder:      Adds 20 points to the Platinum aggregate total.
```

#### GlobalKTable
A standard `KTable` is **sharded**. Each application task instance only consumes a subset of partitions of the topic, containing a fraction of the total database.
A **`GlobalKTable`** is **fully replicated**. Every application task instance across all servers consumes **all partitions** of the topic, maintaining a complete, identical copy of the database.

##### When to Use GlobalKTable
* **Reference Data / Lookups**: Best for static or slow-changing datasets that are relatively small (e.g., user profile metadata, product catalogs, zip code indexes).
* **Bypassing Co-partitioning**: Since every instance has the entire table, you can join any partition of a `KStream` with the `GlobalKTable` without needing the streams to share the same partition count or key type.

##### Limitations of GlobalKTable
* **Disk & Memory Overhead**: Because the database is fully replicated on every server, it consumes significantly more disk space.
* **No Windowing**: Does not support windowed aggregations or temporal operations.
* **Heap Space Pressure**: If not using RocksDB, large global tables will quickly saturate the JVM heap.

---

### Advanced Level: Join Semantics, Table-Table Foreign Key Joins & Versioned KTables

#### Stream-Table Join Semantics (KStream-KTable)
* **Lookup Join**: When a record arrives on the `KStream` (left side), Kafka Streams does a key lookup in the `KTable` (right side) state store.
* **Asymmetric Trigger**: **Only stream-side updates trigger a join.** If a new record arrives on the table, it updates the database but **does not** trigger a join or emit a new output downstream.
* **Windowing**: Stateless lookup. No time window constraint is applied.

#### Table-Table Join Semantics (KTable-KTable)
* **Symmetric Trigger**: **Updates to either side trigger a join.** If Table A is updated, it looks up the match in Table B and emits. If Table B is updated, it looks up the match in Table A and emits.
* **Materialized Views**: The result of a Table-Table join is another `KTable` representing the continuously updated merged view.

#### Table-Table Foreign Key Joins
When you join two tables, they typically must share the same primary key. However, Kafka Streams supports joining tables with different keys using a **Foreign Key Join**.
For example, joining a `UserTable` (keyed by `UserId`) with a `CompanyTable` (keyed by `CompanyId`), where the `UserTable` value contains a `companyId` field (the foreign key).

##### Under the Hood Mechanics
1. **Foreign Key Extraction**: The application uses a `KeyValueMapper` to extract the foreign key (`companyId`) and calculates a hash of the original user value.
2. **Subscription Repartition**: It writes the foreign key as the record key to an internal subscription topic, co-partitioned with the `CompanyTable`.
3. **Lookup & State Storage**: An internal processor consumes the subscription topic, looks up the company details, and stores the user key + value hash in a joint state store.
4. **Validation Response**: It writes the lookup result to a result topic. The original `UserTable` processor consumes this, verifies the current user value hash matches the original, and forwards the merged record downstream. This prevents race conditions.

```text
  [ UserTable (UserId) ] ──► Extract CompanyId ──► [ Subscription Topic ] ──► Lookup ──► [ CompanyTable (CompanyId) ]
                                                                                               │
                                                                                               ▼
  [ Output Stream ] ◄─────── Verify Hash ◄──────── [ Result Topic ] ◄──────────────────────────┘
```

#### Versioned KTables
In standard `KTable` lookups, Kafka Streams only retains the latest value in the state store. If a `KStream` event arrives **out of order** (with a delayed timestamp $T_{delayed}$), it will join against the *current* state of the table, yielding an incorrect result (e.g., using a product price updated at $T_{now}$ for an order placed at $T_{delayed}$).

To solve this, configure a **Versioned KTable** (using `persistentVersionedKeyValueStore`):
* Retains historical records and their timestamps for a configured **history retention period** (e.g., 24 hours).
* When a stream record with timestamp $T_{delayed}$ arrives, the versioned store retrieves the value that was active in the table at $T_{delayed}$, ensuring **temporal correctness**.

---

## 2. Theory & Production Best Practices

### Join Semantics Comparison Matrix
Understand the structural differences between join types:

| Join Type | Trigger Source | Windowed? | Co-partitioning Needed? | Result Type |
| :--- | :--- | :--- | :--- | :--- |
| **Stream-Stream** | Matched updates on **either** stream. | **Yes** (mandatory window). | **Yes** | `KStream` |
| **Stream-Table** | Stream updates **only**. | **No** (stateless lookup). | **Yes** | `KStream` |
| **Stream-GlobalTable**| Stream updates **only**. | **No** (stateless lookup). | **No** | `KStream` |
| **Table-Table** | Table updates on **either** side. | **No** (materialized lookup).| **Yes** (except Foreign Key). | `KTable` |

---

## 3. Common Errors & Troubleshooting

### 1. `TopologyException` in Foreign Key Joins
* **Symptom**: Startup failure with `TopologyException: State store names must be unique`.
* **Root Cause**: When performing a foreign key join, Kafka Streams creates multiple internal topics and stores. If you chain multiple joins without naming them explicitly using `TableJoined.as()`, name conflicts occur.
* **Fix**: Always name your foreign key joins:
  ```java
  tableA.join(tableB, keyExtractor, valueJoiner, TableJoined.as("my-fk-join"));
  ```

### 2. Stream-Table Join Yielding Empty Output
* **Symptom**: The join runs but outputs nothing.
* **Root Cause**: The source topics are not co-partitioned. If Topic A has 3 partitions and Topic B has 6 partitions, matching keys are hashed to different partition indices and never meet on the same task thread.
* **Fix**: Recreate the topics with identical partition counts. If you cannot modify the broker topics, use a proactive `repartition()` step in your code to force co-partitioning.

---

## 4. Hands-on Labs

### Lab 8.1 — Build a KTable from a purchases compacted topic

#### Scenario
We will consume retail transactions from a compacted topic (`purchases-compacted`) and materialize the latest purchase for each customer key in a named RocksDB state store `latest-purchase-store`.

#### Complete Java Code
Create the file [CompactPurchaseTableApp.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/kafka-streams-in-action/modules/src/main/java/com/kafkastreams/course/labs/CompactPurchaseTableApp.java) with the following content:

```java
package com.kafkastreams.course.labs;

import org.apache.kafka.common.serialization.Serdes;
import org.apache.kafka.streams.KafkaStreams;
import org.apache.kafka.streams.StreamsBuilder;
import org.apache.kafka.streams.StreamsConfig;
import org.apache.kafka.streams.Topology;
import org.apache.kafka.streams.kstream.Consumed;
import org.apache.kafka.streams.kstream.KTable;
import org.apache.kafka.streams.kstream.Materialized;
import org.apache.kafka.streams.kstream.Produced;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.Properties;

public class CompactPurchaseTableApp {
    private static final Logger log = LoggerFactory.getLogger(CompactPurchaseTableApp.class);

    public static Properties getConfig() {
        Properties props = new Properties();
        props.put(StreamsConfig.APPLICATION_ID_CONFIG, "compact-purchase-group");
        props.put(StreamsConfig.BOOTSTRAP_SERVERS_CONFIG, "localhost:9092");
        props.put(StreamsConfig.DEFAULT_KEY_SERDE_CLASS_CONFIG, Serdes.String().getClass().getName());
        props.put(StreamsConfig.DEFAULT_VALUE_SERDE_CLASS_CONFIG, JsonSerde.class.getName());
        props.put(StreamsConfig.CACHE_MAX_BYTES_BUFFERING_CONFIG, 0); // View changes immediately
        return props;
    }

    public static void main(String[] args) {
        log.info("Starting Compact Purchase Table App...");

        StreamsBuilder builder = new StreamsBuilder();
        JsonSerde<Purchase> purchaseSerde = new JsonSerde<>();

        // 1. Consume compacted topic directly into a KTable and name the state store
        KTable<String, Purchase> latestPurchasePerCustomer = builder.table(
            "purchases-compacted",
            Consumed.with(Serdes.String(), purchaseSerde),
            Materialized.as("latest-purchase-store")
        );

        // 2. Convert to Stream to print values and output to console/topic
        latestPurchasePerCustomer.toStream()
            .peek((key, value) -> log.info("Update detected for Customer: {} | Latest Purchase: {}", key, value))
            .to("latest-purchase-output", Produced.with(Serdes.String(), purchaseSerde));

        Topology topology = builder.build();
        KafkaStreams streams = new KafkaStreams(topology, getConfig());

        streams.cleanUp();
        streams.start();
        log.info("Compact Purchase Table App is active!");

        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            log.info("Stopping application...");
            streams.close();
            log.info("Application stopped.");
        }));
    }
}
```

#### Configuration Details
The following table explains what each line of the configuration properties does:

| Property Name | Value | Purpose |
| :--- | :--- | :--- |
| `StreamsConfig.APPLICATION_ID_CONFIG` | `"compact-purchase-group"` | Serves as the consumer group coordination namespace and sets local RocksDB directory targets. |
| `StreamsConfig.BOOTSTRAP_SERVERS_CONFIG` | `"localhost:9092"` | Locates the Kafka cluster bootstrap brokers. |
| `StreamsConfig.DEFAULT_KEY_SERDE_CLASS_CONFIG` | `Serdes.String()...` | Registers String as the default key serialization. |
| `StreamsConfig.DEFAULT_VALUE_SERDE_CLASS_CONFIG`| `JsonSerde.class...` | Configures default value de/serialization to use our custom JSON serializer. |
| `StreamsConfig.CACHE_MAX_BYTES_BUFFERING_CONFIG`| `0` | Disables internal buffer cache to ensure downstream writes happen on every message immediately. |

---

### Lab 8.2 — Enrich a purchase stream with customer profiles via GlobalKTable

#### Scenario
We will join a high-throughput stream of `purchases` with reference data loaded from `customer-profiles` via a `GlobalKTable`. Because we are using a `GlobalKTable`, we do not need to worry about partition matching.

#### CustomerProfile Model Class
Create the file [CustomerProfile.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/kafka-streams-in-action/modules/src/main/java/com/kafkastreams/course/labs/CustomerProfile.java) with the following content:

```java
package com.kafkastreams.course.labs;

import java.io.Serializable;

public class CustomerProfile implements Serializable {
    private static final long serialVersionUID = 1L;

    private String customerId;
    private String name;
    private String email;
    private String tier;

    public CustomerProfile() {}

    public CustomerProfile(String customerId, String name, String email, String tier) {
        this.customerId = customerId;
        this.name = name;
        this.email = email;
        this.tier = tier;
    }

    public String getCustomerId() { return customerId; }
    public void setCustomerId(String customerId) { this.customerId = customerId; }

    public String getName() { return name; }
    public void setName(String name) { this.name = name; }

    public String getEmail() { return email; }
    public void setEmail(String email) { this.email = email; }

    public String getTier() { return tier; }
    public void setTier(String tier) { this.tier = tier; }

    @Override
    public String toString() {
        return "CustomerProfile{" +
                "customerId='" + customerId + ''' +
                ", name='" + name + ''' +
                ", email='" + email + ''' +
                ", tier='" + tier + ''' +
                '}';
    }
}
```

#### EnrichedPurchaseProfile Model Class
Create the file [EnrichedPurchaseProfile.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/kafka-streams-in-action/modules/src/main/java/com/kafkastreams/course/labs/EnrichedPurchaseProfile.java) with the following content:

```java
package com.kafkastreams.course.labs;

import java.io.Serializable;

public class EnrichedPurchaseProfile implements Serializable {
    private static final long serialVersionUID = 1L;

    private Purchase purchase;
    private CustomerProfile profile;

    public EnrichedPurchaseProfile() {}

    public EnrichedPurchaseProfile(Purchase purchase, CustomerProfile profile) {
        this.purchase = purchase;
        this.profile = profile;
    }

    public Purchase getPurchase() { return purchase; }
    public void setPurchase(Purchase purchase) { this.purchase = purchase; }

    public CustomerProfile getProfile() { return profile; }
    public void setProfile(CustomerProfile profile) { this.profile = profile; }

    @Override
    public String toString() {
        return "EnrichedPurchaseProfile{" +
                "purchase=" + purchase +
                ", profile=" + profile +
                '}';
    }
}
```

#### Main Application Class
Create the file [ProfileEnrichmentApp.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/kafka-streams-in-action/modules/src/main/java/com/kafkastreams/course/labs/ProfileEnrichmentApp.java) with the following content:

```java
package com.kafkastreams.course.labs;

import org.apache.kafka.common.serialization.Serdes;
import org.apache.kafka.streams.KafkaStreams;
import org.apache.kafka.streams.StreamsBuilder;
import org.apache.kafka.streams.StreamsConfig;
import org.apache.kafka.streams.Topology;
import org.apache.kafka.streams.kstream.Consumed;
import org.apache.kafka.streams.kstream.GlobalKTable;
import org.apache.kafka.streams.kstream.KStream;
import org.apache.kafka.streams.kstream.Produced;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.Properties;

public class ProfileEnrichmentApp {
    private static final Logger log = LoggerFactory.getLogger(ProfileEnrichmentApp.class);

    public static Properties getConfig() {
        Properties props = new Properties();
        props.put(StreamsConfig.APPLICATION_ID_CONFIG, "profile-enrichment-group");
        props.put(StreamsConfig.BOOTSTRAP_SERVERS_CONFIG, "localhost:9092");
        props.put(StreamsConfig.DEFAULT_KEY_SERDE_CLASS_CONFIG, Serdes.String().getClass().getName());
        props.put(StreamsConfig.DEFAULT_VALUE_SERDE_CLASS_CONFIG, JsonSerde.class.getName());
        return props;
    }

    public static void main(String[] args) {
        log.info("Launching Profile Enrichment App...");

        StreamsBuilder builder = new StreamsBuilder();
        JsonSerde<Purchase> purchaseSerde = new JsonSerde<>();
        JsonSerde<CustomerProfile> profileSerde = new JsonSerde<>();
        JsonSerde<EnrichedPurchaseProfile> enrichedSerde = new JsonSerde<>();

        // 1. Consume customer profiles into a GlobalKTable
        GlobalKTable<String, CustomerProfile> customerProfiles = builder.globalTable(
            "customer-profiles",
            Consumed.with(Serdes.String(), profileSerde)
        );

        // 2. Consume purchases stream
        KStream<String, Purchase> purchases = builder.stream(
            "purchases",
            Consumed.with(Serdes.String(), purchaseSerde)
        );

        // 3. Join purchases stream with GlobalKTable
        KStream<String, EnrichedPurchaseProfile> enrichedStream = purchases.join(
            customerProfiles,
            (purchaseKey, purchase) -> purchaseKey, // Key extractor: mapping stream key to global table key
            (purchase, profile) -> {
                log.info("Enriching purchase for Customer ID: {} | Profile matched: {}", purchase.getCustomerId(), profile);
                return new EnrichedPurchaseProfile(purchase, profile);
            }
        );

        // 4. Output results to output topic
        enrichedStream.to(
            "enriched-purchases",
            Produced.with(Serdes.String(), enrichedSerde)
        );

        Topology topology = builder.build();
        KafkaStreams streams = new KafkaStreams(topology, getConfig());

        streams.cleanUp();
        streams.start();
        log.info("Profile Enrichment App is active!");

        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            log.info("Shutting down enrichment app...");
            streams.close();
            log.info("Enrichment app stopped.");
        }));
    }
}
```

---

### Lab 8.3 — Table-Table join: merge two KTables

#### Scenario
We will merge two database views:
1. `customer-profiles` (keyed by customer ID).
2. `customer-addresses` (keyed by customer ID).

We will join these two KTables into a single `FullCustomerRecord` output table.

#### Address Model Class
Create the file [Address.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/kafka-streams-in-action/modules/src/main/java/com/kafkastreams/course/labs/Address.java) with the following content:

```java
package com.kafkastreams.course.labs;

import java.io.Serializable;

public class Address implements Serializable {
    private static final long serialVersionUID = 1L;

    private String customerId;
    private String street;
    private String city;
    private String zipcode;

    public Address() {}

    public Address(String customerId, String street, String city, String zipcode) {
        this.customerId = customerId;
        this.street = street;
        this.city = city;
        this.zipcode = zipcode;
    }

    public String getCustomerId() { return customerId; }
    public void setCustomerId(String customerId) { this.customerId = customerId; }

    public String getStreet() { return street; }
    public void setStreet(String street) { this.street = street; }

    public String getCity() { return city; }
    public void setCity(String city) { this.city = city; }

    public String getZipcode() { return zipcode; }
    public void setZipcode(String zipcode) { this.zipcode = zipcode; }

    @Override
    public String toString() {
        return "Address{" +
                "customerId='" + customerId + ''' +
                ", street='" + street + ''' +
                ", city='" + city + ''' +
                ", zipcode='" + zipcode + ''' +
                '}';
    }
}
```

#### FullCustomerRecord Model Class
Create the file [FullCustomerRecord.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/kafka-streams-in-action/modules/src/main/java/com/kafkastreams/course/labs/FullCustomerRecord.java) with the following content:

```java
package com.kafkastreams.course.labs;

import java.io.Serializable;

public class FullCustomerRecord implements Serializable {
    private static final long serialVersionUID = 1L;

    private CustomerProfile profile;
    private Address address;

    public FullCustomerRecord() {}

    public FullCustomerRecord(CustomerProfile profile, Address address) {
        this.profile = profile;
        this.address = address;
    }

    public CustomerProfile getProfile() { return profile; }
    public void setProfile(CustomerProfile profile) { this.profile = profile; }

    public Address getAddress() { return address; }
    public void setAddress(Address address) { this.address = address; }

    @Override
    public String toString() {
        return "FullCustomerRecord{" +
                "profile=" + profile +
                ", address=" + address +
                '}';
    }
}
```

#### Join Application Class
Create the file [TableTableJoinApp.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/kafka-streams-in-action/modules/src/main/java/com/kafkastreams/course/labs/TableTableJoinApp.java) with the following content:

```java
package com.kafkastreams.course.labs;

import org.apache.kafka.common.serialization.Serdes;
import org.apache.kafka.streams.KafkaStreams;
import org.apache.kafka.streams.StreamsBuilder;
import org.apache.kafka.streams.StreamsConfig;
import org.apache.kafka.streams.Topology;
import org.apache.kafka.streams.kstream.Consumed;
import org.apache.kafka.streams.kstream.KTable;
import org.apache.kafka.streams.kstream.Materialized;
import org.apache.kafka.streams.kstream.Produced;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.Properties;

public class TableTableJoinApp {
    private static final Logger log = LoggerFactory.getLogger(TableTableJoinApp.class);

    public static Properties getConfig() {
        Properties props = new Properties();
        props.put(StreamsConfig.APPLICATION_ID_CONFIG, "table-table-join-group");
        props.put(StreamsConfig.BOOTSTRAP_SERVERS_CONFIG, "localhost:9092");
        props.put(StreamsConfig.DEFAULT_KEY_SERDE_CLASS_CONFIG, Serdes.String().getClass().getName());
        props.put(StreamsConfig.DEFAULT_VALUE_SERDE_CLASS_CONFIG, JsonSerde.class.getName());
        props.put(StreamsConfig.CACHE_MAX_BYTES_BUFFERING_CONFIG, 0);
        return props;
    }

    public static void main(String[] args) {
        log.info("Launching Table-Table Join App...");

        StreamsBuilder builder = new StreamsBuilder();
        JsonSerde<CustomerProfile> profileSerde = new JsonSerde<>();
        JsonSerde<Address> addressSerde = new JsonSerde<>();
        JsonSerde<FullCustomerRecord> mergedSerde = new JsonSerde<>();

        // 1. Load profiles table
        KTable<String, CustomerProfile> profiles = builder.table(
            "customer-profiles",
            Consumed.with(Serdes.String(), profileSerde),
            Materialized.as("profiles-table-store")
        );

        // 2. Load addresses table
        KTable<String, Address> addresses = builder.table(
            "customer-addresses",
            Consumed.with(Serdes.String(), addressSerde),
            Materialized.as("addresses-table-store")
        );

        // 3. Perform Table-Table join
        KTable<String, FullCustomerRecord> mergedTable = profiles.join(
            addresses,
            (profile, address) -> {
                log.info("Merging matched tables for customer! Profile: {} | Address: {}", profile.getCustomerId(), address.getCity());
                return new FullCustomerRecord(profile, address);
            },
            Materialized.as("merged-customer-store")
        );

        // 4. Output results to output topic
        mergedTable.toStream().to(
            "full-customer-records",
            Produced.with(Serdes.String(), mergedSerde)
        );

        Topology topology = builder.build();
        KafkaStreams streams = new KafkaStreams(topology, getConfig());

        streams.cleanUp();
        streams.start();
        log.info("Table-Table Join App is active!");

        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            log.info("Stopping table-table join...");
            streams.close();
            log.info("App stopped.");
        }));
    }
}
```

---

### Lab 8.4 — Versioned KTable: query historical versions

#### Scenario
We will create a KTable backed by a **Versioned State Store** to maintain a 24-hour history of transaction values.

#### Complete Java Code
Create the file [VersionedKTableApp.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/kafka-streams-in-action/modules/src/main/java/com/kafkastreams/course/labs/VersionedKTableApp.java) with the following content:

```java
package com.kafkastreams.course.labs;

import org.apache.kafka.common.serialization.Serdes;
import org.apache.kafka.common.utils.Bytes;
import org.apache.kafka.streams.KafkaStreams;
import org.apache.kafka.streams.StreamsBuilder;
import org.apache.kafka.streams.StreamsConfig;
import org.apache.kafka.streams.Topology;
import org.apache.kafka.streams.kstream.Consumed;
import org.apache.kafka.streams.kstream.KTable;
import org.apache.kafka.streams.kstream.Materialized;
import org.apache.kafka.streams.kstream.Produced;
import org.apache.kafka.streams.state.KeyValueStore;
import org.apache.kafka.streams.state.Stores;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.time.Duration;
import java.util.Properties;

public class VersionedKTableApp {
    private static final Logger log = LoggerFactory.getLogger(VersionedKTableApp.class);

    public static Properties getConfig() {
        Properties props = new Properties();
        props.put(StreamsConfig.APPLICATION_ID_CONFIG, "versioned-table-group");
        props.put(StreamsConfig.BOOTSTRAP_SERVERS_CONFIG, "localhost:9092");
        props.put(StreamsConfig.DEFAULT_KEY_SERDE_CLASS_CONFIG, Serdes.String().getClass().getName());
        props.put(StreamsConfig.DEFAULT_VALUE_SERDE_CLASS_CONFIG, JsonSerde.class.getName());
        return props;
    }

    public static void main(String[] args) {
        log.info("Starting Versioned KTable App...");

        StreamsBuilder builder = new StreamsBuilder();
        JsonSerde<Purchase> purchaseSerde = new JsonSerde<>();

        // 1. Define KTable backed by a persistent versioned store (24 hours retention)
        KTable<String, Purchase> versionedPurchaseTable = builder.table(
            "purchases-compacted",
            Consumed.with(Serdes.String(), purchaseSerde),
            Materialized.<String, Purchase, KeyValueStore<Bytes, byte[]>>as(
                Stores.persistentVersionedKeyValueStore("latest-purchase-store-v2", Duration.ofHours(24))
            )
        );

        // 2. Stream results to console
        versionedPurchaseTable.toStream()
            .peek((key, value) -> log.info("Versioned record update -> Key: {} | Value: {}", key, value))
            .to("versioned-purchases-output", Produced.with(Serdes.String(), purchaseSerde));

        Topology topology = builder.build();
        KafkaStreams streams = new KafkaStreams(topology, getConfig());

        streams.cleanUp();
        streams.start();
        log.info("Versioned KTable App is running!");

        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            log.info("Stopping versioned app...");
            streams.close();
            log.info("App stopped.");
        }));
    }
}
```
