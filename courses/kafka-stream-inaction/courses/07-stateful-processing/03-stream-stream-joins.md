# Module 03: Stream-Stream Joins & Co-partitioning

In event-driven architectures, completing a business process often requires correlating and enriching records from separate streams. In Kafka Streams, this is accomplished using a **Stream-Stream Join**. 

This module details the different join types, value joiners, windowing constraints, internal state store lookup mechanics, and the strict rules of co-partitioning.

---

## 1. Stream-Stream Join Types

Stream-Stream joins require a common key and a time-based window. Kafka Streams offers three join semantics:

| Join Type | DSL Method | Output Structure | Use Case |
| :--- | :--- | :--- | :--- |
| **Inner Join** | `join()` | `Left-Value + Right-Value` | Emitted **only** if records from both streams arrive with the same key within the time window. |
| **Left-Outer Join** | `leftJoin()` | `Left-Value + Right-Value`<br>or `Left-Value + null` | Emitted for every record on the left (calling) stream. If no match is found on the right, the right value is null. |
| **Outer Join** | `outerJoin()` | `Left + Right` or `Left + null`<br>or `null + Right` | Emitted whenever a record arrives on either stream. If the opposite side is missing, it is represented as null. |

---

## 2. Value Joiners

To combine records, implement `ValueJoiner<V1, V2, R>` or `ValueJoinerWithKey<K, V1, V2, R>`.

### 2.1 The ValueJoiner Callback
The `ValueJoiner` receives the values from both streams and returns the enriched object.

#### Case Study: Retail Loyalty Promotion
A customer club loyalty points bonus is awarded if a customer purchases a drink from the embedded store Cafe *and* buys retail items from the main store within 30 minutes.

##### Domain Models:
```java
public record CoffeePurchase(String customerId, String drink, double price) {}
public record RetailPurchase(String customerId, double totalSpend) {}
public record Promotion(String customerId, String drink, double totalPoints) {}
```

##### ValueJoiner Implementation:
```java
package com.enterprise.streams.joins;

import org.apache.kafka.streams.kstream.ValueJoiner;

public class PromotionJoiner implements ValueJoiner<CoffeePurchase, RetailPurchase, Promotion> {

    @Override
    public Promotion apply(CoffeePurchase coffee, RetailPurchase retail) {
        // Handle null values for outer/left joins safely
        double coffeePrice = (coffee != null) ? coffee.price() : 0.0;
        double retailSpend = (retail != null) ? retail.totalSpend() : 0.0;
        String drinkName = (coffee != null) ? coffee.drink() : "None";

        double points = coffeePrice + retailSpend;
        if (retailSpend > 50.00) {
            points += 50.00; // Bonus loyalty points
        }

        String customerId = (retail != null) ? retail.customerId() : coffee.customerId();
        return new Promotion(customerId, drinkName, points);
    }
}
```

---

## 3. Join Windows

Because stream events are continuous and unbounded, a join cannot wait indefinitely. You must define a **`JoinWindows`** limit specifying how close the timestamps of the records must be.

*   **`ofTimeDifferenceWithNoGrace(Duration)`**: Specifies a symmetric window where records can arrive within the duration before or after.
*   **Asymmetric Windows (`before` and `after`)**: You can specify order of arrival constraints:
    *   `JoinWindows.ofTimeDifferenceWithNoGrace(Duration.ofMinutes(30)).after(Duration.ofMinutes(5))`: The right-stream record must arrive at least 30 minutes before, but no more than 5 minutes after the left-stream record.
    *   `JoinWindows.of(Duration.ofMinutes(0)).after(Duration.ofMinutes(30))`: The right-stream record must arrive *after* the left-stream record, up to a maximum of 30 minutes.

---

## 4. Join Internals

To execute the join, Kafka Streams builds a state store for each side of the join.

```
Incoming Coffee Event ──► [ Left Join Processor ] 
                                │ (1. Writes Coffee to Left Store)
                                │ (2. Queries Right Store by key/window)
                                ▼
                       [ Right State Store ]
                                │
                                ├── Match Found? ──► [ ValueJoiner.apply() ] ──► [ Forward Result ]
                                └── No Match? ──────► (Left-Outer/Outer emits left+null, Inner drops)
```

1.  **Ingestion & State Insertion**: When a record arrives on the left stream, the left join processor writes it to the **Left State Store** (a windowed state store).
2.  **Cross-Store Querying**: The left join processor immediately queries the **Right State Store** by the record key and checks if there are records whose timestamps fall within the `JoinWindow`.
3.  **Callback and Forward**: For every matching record found in the right store, the processor executes `ValueJoiner.apply(leftValue, rightValue)` and forwards the resulting record downstream.
4.  **Reciprocal Action**: When a record arrives on the right stream, the right join processor executes the same sequence, writing to its store and querying the left store.

---

## 5. The Co-Partitioning Rule

For a join to execute successfully, the join participants **must be co-partitioned**. 

> [!IMPORTANT]
> **Co-partitioning requirements**:
> 1. Both input topics must have the **same number of partitions**.
> 2. Both streams must have keys of the **same data type**.
> 3. Both producers must use the **same partitioner class** (default MurmurHash2 or sticky partitioning).

If these rules are violated, records with identical keys will reside on different partition indices. Since join tasks are isolated by partition number (e.g. Task `0_1` only joins partition 1 of stream A with partition 1 of stream B), the tasks will never see the matching keys, resulting in **zero join matches**.

### 5.1 Resolving Partition Mismatches
If you must join a topic with 3 partitions with a topic that has 6 partitions, you can use the `repartition` operator to dynamically realign the partition count of the smaller topic:

```java
KStream<String, CoffeePurchase> coffeeStream = builder.stream("coffee-purchases", Consumed.with(stringSerde, coffeeSerde));
KStream<String, RetailPurchase> retailStream = builder.stream("retail-purchases", Consumed.with(stringSerde, retailSerde));

// Repartition coffeeStream to match retailStream's 6 partitions
KStream<String, CoffeePurchase> repartitionedCoffee = coffeeStream.repartition(
    Repartitioned.<String, CoffeePurchase>as("coffee-join-aligner")
                 .withNumberOfPartitions(6)
                 .withKeySerde(stringSerde)
                 .withValueSerde(coffeeSerde)
);

// Perform join
KStream<String, Promotion> promoStream = repartitionedCoffee.join(
    retailStream,
    new PromotionJoiner(),
    JoinWindows.ofTimeDifferenceWithNoGrace(Duration.ofMinutes(30)),
    StreamJoined.with(stringSerde, coffeeSerde, retailSerde)
                .withName("promo-join-processor")
                .withStoreName("promo-join-stores")
);
```
