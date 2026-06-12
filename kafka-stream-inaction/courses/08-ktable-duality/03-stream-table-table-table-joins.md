# Module 03: Stream-Table, Table-Table & Foreign-Key Joins

In complex data models, enrichment requires joining multiple data entities. The Kafka Streams DSL supports multiple table join operations: **Stream-Table Joins**, **Table-Table Joins**, and **Foreign-Key Table Joins**.

This module explains the behavior, partitioning rules, and internal execution paths of these join patterns.

---

## 1. Stream-Table Joins

A **Stream-Table Join** enriches a high-velocity event stream with slow-moving dimension data (e.g. joining web clicks against a user profiles table).

### 1.1 Trigger Semantics and Windowing
*   **Non-Reciprocal**: Only records arriving on the **KStream (Left)** trigger join evaluations. Records updating the **KTable (Right)** update the local state store but do not emit join results.
*   **Non-Windowed**: Lookups are performed immediately against the latest state of the table. No time-based windows are enforced (except when versioned tables are explicitly configured).
*   **Co-Partitioning**: Both the stream topic and the table topic **must** have matching partition counts.

```java
// Inner Stream-Table Join
KStream<String, EnrichedClick> enriched = clickStream.join(
    userTable,
    (click, user) -> new EnrichedClick(click.userId(), click.url(), user.country()),
    Joined.with(Serdes.String(), clickSerde, userSerde)
);
```

---

## 2. Table-Table Joins

A **Table-Table Join** correlates updates between two change logs (e.g., joining an `Employees` table with a `Departments` table by department ID).

*   **Reciprocal Triggers**: Updates on **either** table trigger a join evaluation. If Table A receives an update, it queries Table B's store; if Table B updates, it queries Table A's store.
*   **Partition Matching**: Both tables must be co-partitioned on their primary keys.

```java
KTable<String, Employee> empTable = builder.table("employees");
KTable<String, Department> deptTable = builder.table("departments");

// Primary Key Join
KTable<String, DepartmentAssignment> assignmentTable = empTable.join(
    deptTable,
    (employee, department) -> new DepartmentAssignment(employee.name(), department.name()),
    Materialized.as("emp-dept-join-store")
);
```

---

## 3. Foreign-Key Table-Table Joins

When two tables do not share the same primary key, a standard join fails. However, if the value of the left table contains a field matching the primary key of the right table, you can execute a **Foreign-Key Join**.

```
  Left Table: Contracts                     Right Table: Prices
  ┌─────────────────────────────┐           ┌───────────────────────┐
  │ Primary Key: Contract ID    │           │ Primary Key: Item ID  │
  │ Value: { Item: "AAPL", qty }│ ────────► │ Value: { Price: $152 }│
  └─────────────────────────────┘           └───────────────────────┘
          (Foreign Key)
```

### 3.1 Mechanics of a Foreign-Key Join
To coordinate foreign-key joins across distributed workers, Kafka Streams runs a complex coordination workflow:

```
[Left Table Update] ──► Hashes Value ──► [Internal Repartition Topic]
                                                   │
                                                   ▼ (Keyed by Foreign Key)
                                         [Right Table Agent Lookup]
                                                   │
                                                   ▼
                                         [Internal Result Topic]
                                                   │ (Keyed by Left Primary Key)
                                                   ▼
                                         [Left Table Hash Validation] ──► [Emit Join]
```

1.  **Extraction & Hashing**: When a record updates the left table, the framework extracts the foreign key using a user-supplied `foreignKeyExtractor` and computes a cryptographic hash of the left value.
2.  **Foreign Key Repartitioning**: The framework writes the record to an internal repartition topic. The key of this topic is the extracted **Foreign Key**, and the value contains the left primary key and the value hash. This topic is co-partitioned with the right table.
3.  **Right-Side Lookup**: An internal consumer (representing the right-side agent) consumes the repartition records, performs a lookup on the right-side table using the foreign key, and writes the results to a second internal result topic.
4.  **Hashed Validation**: The left-side agent consumes from the result topic, performs a key lookup on the left table, and compares the new value hash against the result topic hash. If they match, it emits the join record. If they mismatch (meaning the left value changed concurrently), it discards the record to prevent race conditions.
5.  **Composite Key Store & Updates**: To handle updates on the right table (e.g. a price changes, which affects multiple contracts), the right-side agent maintains a local state store containing composite keys: `RightKey-LeftKey`. When a right-side record updates, the task executes a **prefix scan** on the composite key store to identify and trigger updates for all associated left-side records.

---

### 3.2 Foreign-Key Join Implementation Example

We will join a client contracts table (keyed by Client ID, value contains Commodity Code) with a commodity prices table (keyed by Commodity Code).

##### Domain Models:
```java
public record Contract(String clientId, String commodityCode, long quantity) {}
public record CommodityPrice(String commodityCode, double price) {}
public record EnrichedContract(String clientId, String commodityCode, double totalCost) {}
```

##### Topology Code:
```java
package com.enterprise.streams.joins;

import org.apache.kafka.common.serialization.Serde;
import org.apache.kafka.common.serialization.Serdes;
import org.apache.kafka.streams.StreamsBuilder;
import org.apache.kafka.streams.Topology;
import org.apache.kafka.streams.kstream.Consumed;
import org.apache.kafka.streams.kstream.KTable;
import org.apache.kafka.streams.kstream.Materialized;
import org.apache.kafka.streams.kstream.Produced;

import java.util.function.Function;

public class ForeignKeyJoinTopology {

    public Topology buildTopology(
            Serde<Contract> contractSerde,
            Serde<CommodityPrice> priceSerde,
            Serde<EnrichedContract> enrichedSerde) {

        StreamsBuilder builder = new StreamsBuilder();
        Serde<String> stringSerde = Serdes.String();

        // Left Table: Key = Client ID
        KTable<String, Contract> contractTable = builder.table(
                "client-contracts",
                Consumed.with(stringSerde, contractSerde)
        );

        // Right Table: Key = Commodity Code
        KTable<String, CommodityPrice> priceTable = builder.table(
                "commodity-prices",
                Consumed.with(stringSerde, priceSerde)
        );

        // 1. Define Foreign Key Extractor: Extracts "commodityCode" from the Contract value
        Function<Contract, String> foreignKeyExtractor = contract -> contract.commodityCode();

        // 2. Execute Foreign-Key Join (No co-partitioning required)
        KTable<String, EnrichedContract> enrichedTable = contractTable.join(
                priceTable,
                foreignKeyExtractor,
                (contract, price) -> {
                    double cost = (price != null) ? contract.quantity() * price.price() : 0.0;
                    return new EnrichedContract(contract.clientId(), contract.commodityCode(), cost);
                },
                Materialized.as("enriched-contract-store")
        );

        // 3. Output results
        enrichedTable.toStream().to("enriched-contracts", Produced.with(stringSerde, enrichedSerde));

        return builder.build();
    }
}
```
