# Module 02: Stateless Transformations & Stream Processing

Stateless transformations are stream processing operations that act on individual events in isolation. They do not require a state store or memory of previously processed records. 

This module details the stateless operators available in the Kafka Streams DSL, explaining key preservation vs. mutation, repartitioning side effects, and how to chain these transformations in a production pipeline.

---

## 1. Stateless Operators in Kafka Streams DSL

The high-level DSL provides several stateless operators. These are categorized based on whether they modify the record key.

### 1.1 Map vs. MapValues
*   **`mapValues(ValueMapper)`**: Retains the original key while modifying the value.
    *   **Partition Stability**: Because the key is unchanged, the records preserve their partitioning structure. No repartitioning is triggered downstream.
*   **`map(KeyValueMapper)`**: Modifies both the key and the value, returning a new `KeyValue` object.
    *   **Repartitioning Trigger**: Since the key is mutated, Kafka Streams **cannot guarantee** that subsequent key-based operators (like aggregations, groups, or joins) will map to the same partitions. Downstream stateful operations will trigger the creation of internal repartition topics (`-repartition`), incurring I/O overhead.

> [!TIP]
> Always prefer `mapValues` over `map` unless you explicitly need to change the record key. Preserving the key avoids writing records back to an intermediate repartition topic in Kafka, resulting in much higher throughput.

### 1.2 Filter vs. FilterNot
*   **`filter(Predicate)`**: Evaluates each record against a boolean predicate. If the predicate returns `true`, the record is forwarded; if `false`, the record is dropped.
*   **`filterNot(Predicate)`**: The logical inverse of `filter`. Records that return `false` are forwarded; records returning `true` are dropped.

### 1.3 FlatMap vs. FlatMapValues
*   **`flatMapValues(ValueMapper)`**: Takes a single record and returns an `Iterable` of values. It flattens the collection, producing zero, one, or multiple records for the same key. Key is preserved.
*   **`flatMap(KeyValueMapper)`**: Takes a single record and returns an `Iterable` of `KeyValue` objects. Both key and value can be modified. This triggers downstream repartitioning.

```
Input Record: 
  Key: "ZMart-90210", Value: ["Apple", "Orange", "Banana"]

After flatMapValues:
  Key: "ZMart-90210", Value: "Apple"
  Key: "ZMart-90210", Value: "Orange"
  Key: "ZMart-90210", Value: "Banana"
```

### 1.4 SelectKey
*   **`selectKey(KeyValueMapper)`**: Modifies only the key while leaving the value intact. Useful when you need to group data by a value field (e.g., grouping user logins by country). Like `map`, this marks the stream for repartitioning.

---

## 2. Partition Stability & Downstream Repartitioning

Understanding the operational impact of key changes is vital for distributed system performance:

```
               [ Input Stream ]
                      │
                      ▼
             [ mapValues() ] (Preserves Key)
                      │
                      ▼
             [ Aggregation / Join ]
             (Executes in-memory directly)
```

```
               [ Input Stream ]
                      │
                      ▼
             [ map() or selectKey() ] (Mutates Key)
                      │
                      ▼
             (Forces Repartitioning)
                      │
                      ▼
             [ Repartition Topic ] (Writes to Kafka Brokers)
                      │
                      ▼
             [ Aggregation / Join ] (Consumes from new topic)
```

If your topology changes the key, Kafka Streams must ensure co-partitioning before a stateful join or aggregation occurs. It handles this by writing the records back to a broker-managed repartition topic, partitioned by the new key. 

---

## 3. Case Study: The ZMart Transaction Pipeline

To see these operators in action, let's build the **ZMart Transaction Pipeline** based on the following requirements:
1.  **Mask Credit Card Numbers**: Mask the credit card fields of incoming purchases (`mapValues`).
2.  **Filter Rewards**: Drop purchases under $10 from the rewards calculation stream (`filter`).
3.  **Deconstruct Items**: Extract items from a single purchase basket and route them as individual records keyed by zip code to track regional purchase trends (`flatMap`).

### 3.1 Domain Objects
```java
public record PurchasedItem(String itemId, double price, int quantity) {}
public record RetailPurchase(String customerId, String zipCode, String creditCardNumber, List<PurchasedItem> items) {}
public record PurchasePattern(String zipCode, String itemId) {}
public record RewardAccumulator(String customerId, double points) {}
```

### 3.2 Topology Pipeline Code

```java
package com.enterprise.streams.zmart;

import org.apache.kafka.common.serialization.Serde;
import org.apache.kafka.common.serialization.Serdes;
import org.apache.kafka.streams.KeyValue;
import org.apache.kafka.streams.StreamsBuilder;
import org.apache.kafka.streams.Topology;
import org.apache.kafka.streams.kstream.Consumed;
import org.apache.kafka.streams.kstream.KStream;
import org.apache.kafka.streams.kstream.Produced;

import java.util.ArrayList;
import java.util.List;

public class ZMartTransactionTopology {

    public Topology buildTopology(
            Serde<RetailPurchase> purchaseSerde,
            Serde<PurchasePattern> patternSerde,
            Serde<RewardAccumulator> rewardSerde) {

        StreamsBuilder builder = new StreamsBuilder();
        Serde<String> stringSerde = Serdes.String();

        // 1. Consume transaction streams from ZMart stores
        KStream<String, RetailPurchase> purchaseStream = builder.stream(
                "transactions",
                Consumed.with(stringSerde, purchaseSerde)
        );

        // 2. MapValues: Mask Credit Cards (Preserves partitioning - NO repartitioning)
        KStream<String, RetailPurchase> maskedStream = purchaseStream.mapValues(purchase -> {
            String cc = purchase.creditCardNumber();
            String maskedCc = "xxxx-xxxx-xxxx-" + cc.substring(cc.length() - 4);
            return new RetailPurchase(purchase.customerId(), purchase.zipCode(), maskedCc, purchase.items());
        });

        // 3. FlatMap: Emit individual PurchasedItems keyed by ZipCode for regional analysis
        // Since we return KeyValue pairs with new keys (zipCode), this triggers repartitioning if grouped later.
        KStream<String, PurchasePattern> patternStream = maskedStream.flatMap((key, purchase) -> {
            List<KeyValue<String, PurchasePattern>> output = new ArrayList<>();
            for (PurchasedItem item : purchase.items()) {
                output.add(KeyValue.pair(purchase.zipCode(), new PurchasePattern(purchase.zipCode(), item.itemId())));
            }
            return output;
        });

        patternStream.to("purchase-patterns", Produced.with(stringSerde, patternSerde));

        // 4. Filter & MapValues: Calculate rewards for purchases with total value > $10.00
        KStream<String, RewardAccumulator> rewardsStream = maskedStream
                .filter((key, purchase) -> {
                    double total = purchase.items().stream()
                            .mapToDouble(item -> item.price() * item.quantity())
                            .sum();
                    return total > 10.00;
                })
                .mapValues(purchase -> {
                    double total = purchase.items().stream()
                            .mapToDouble(item -> item.price() * item.quantity())
                            .sum();
                    double points = total * 0.10; // 10% cash back in points
                    return new RewardAccumulator(purchase.customerId(), points);
                });

        rewardsStream.to("member-rewards", Produced.with(stringSerde, rewardSerde));

        // 5. Output copy of masked purchases to database sync topic
        maskedStream.to("masked-purchases", Produced.with(stringSerde, purchaseSerde));

        return builder.build();
    }
}
```

> [!CAUTION]
> When using `flatMap` or `selectKey`, design your partitions carefully. Changing the key shifts the workload balance. If you change a key from a high-cardinality value (like `customerId`) to a low-cardinality value (like `countryCode`), you risk creating **skewed partitions**, where a single thread processes the majority of cluster events.
