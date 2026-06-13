# Module 04: Temporal Joins & Versioned KTables

In stream-table joins, timing is crucial. If records arrive out of order, a standard `KTable` join can produce incorrect results because it only looks up the *latest* state. To achieve temporally correct joins for late-arriving events, Kafka Streams provides **Versioned KTables**.

This module details the out-of-order data hazard, how versioned state stores resolve it, and how to configure them in your topologies.

---

## 1. The Out-of-Order Data Hazard in Stream-Table Joins

In a standard `KTable` join, lookups query only the current value stored in the state store. If events arrive out-of-order, this introduces calculation errors.

#### Case Study: Late-Arriving Orders vs. Price Changes
Suppose we track commodity prices in a `KTable` and client orders in a `KStream`.
1.  **Time T1**: Price of Item X is **$6**.
2.  **Time T2**: Customer places an order for 8 units of Item X (expected cost: 8 * $6 = **$48**).
3.  **Time T3**: Price of Item X updates to **$9**.
4.  **Network Delay**: The order record from Time T2 is delayed in transit and arrives at Kafka Streams *after* the T3 price update has already been applied to the table.

```
                   CHRONOLOGICAL HISTORY
  T1 ($6 Price) ──► T2 (Order Placed) ──► T3 ($9 Price)

                   RUNTIME JOIN SEQUENCE
  KTable Store:   [ T1: $6 ] ──► (T3 Update) ──► [ T3: $9 ]
                                                     │
  KStream Order:  [ T2 Order (Late) ] ───────────────┼──► (Joins against $9)
                                                          Result: $72 (Incorrect!)
```

Using a standard `KTable`, the T2 order joins against the T3 price ($9), charging the customer $72 instead of $48. Because standard state stores discard history upon receiving updates, the T2 price ($6) is lost.

---

## 2. Resolving the Hazard with Versioned KTables

A **Versioned KTable** maintains historical versions of records by associating each state update with a validity timestamp range: `[validFrom, validTo]`.

```
  Versioned Store State for Key "X":
  ┌─────────────────────────────────────────────────────────────┐
  │ Version 1: Value = $6, Validity = [T1 to T3]                │
  │ Version 2: Value = $9, Validity = [T3 to Long.MAX_VALUE]    │
  └─────────────────────────────────────────────────────────────┘

  Late-Arriving Join Execution:
  Late Order (Timestamp = T2) queries Versioned Store.
  T2 falls within [T1 to T3] range ──► Retrieves $6 price.
  Result: $48 (Temporally correct!)
```

When a late record with timestamp `T` arrives on the stream, Kafka Streams queries the versioned store, finds the record version valid at timestamp `T`, and executes the joiner, producing the correct result.

---

## 3. Configuring Versioned State Stores

To enable versioned state store lookups, you must:
1.  Create a versioned `StoreSupplier` using the `Stores` factory.
2.  Plug the supplier into the `builder.table()` definition using the `Materialized` builder.

### 3.1 Creating the Store Supplier
Use `Stores.persistentVersionedKeyValueStore(String name, Duration historyRetention)`.

*   **`historyRetention`**: Specifies how far back in history updates are retained (e.g., 30 minutes, 24 hours). If a stream record arrives with a timestamp older than the history retention threshold, the lookup will return `null` or fail to join.

---

### 3.2 Complete Versioned KTable Join Example

Below is the code configuration for joining a transaction stream against a versioned prices table.

##### Domain Models:
```java
public record CommodityOrder(String commodityCode, long quantity, long timestamp) {}
public record CommodityPrice(String commodityCode, double price, long timestamp) {}
public record BilledOrder(String commodityCode, long quantity, double totalCost) {}
```

##### Topology Code:
```java
package com.enterprise.streams.versioned;

import org.apache.kafka.common.serialization.Serde;
import org.apache.kafka.common.serialization.Serdes;
import org.apache.kafka.streams.StreamsBuilder;
import org.apache.kafka.streams.Topology;
import org.apache.kafka.streams.kstream.*;
import org.apache.kafka.streams.state.KeyValueBytesStoreSupplier;
import org.apache.kafka.streams.state.Stores;

import java.time.Duration;

public class VersionedTableJoinTopology {

    public Topology buildTopology(
            Serde<CommodityOrder> orderSerde,
            Serde<CommodityPrice> priceSerde,
            Serde<BilledOrder> billedSerde) {

        StreamsBuilder builder = new StreamsBuilder();
        Serde<String> stringSerde = Serdes.String();

        // 1. Create a versioned store supplier with a 24-hour history retention window
        KeyValueBytesStoreSupplier versionedStoreSupplier = Stores.persistentVersionedKeyValueStore(
                "versioned-commodity-prices-store",
                Duration.ofHours(24)
        );

        // 2. Load the price topic into a KTable backed by the versioned store supplier
        KTable<String, CommodityPrice> priceTable = builder.table(
                "commodity-prices",
                Consumed.with(stringSerde, priceSerde),
                Materialized.as(versionedStoreSupplier)
        );

        // 3. Consume the order stream
        KStream<String, CommodityOrder> orderStream = builder.stream(
                "commodity-orders",
                Consumed.with(stringSerde, orderSerde)
        );

        // 4. Perform the Stream-Table Join
        // Since priceTable is versioned, Kafka Streams automatically queries the price active
        // at the time of orderStream's record timestamp.
        KStream<String, BilledOrder> billedStream = orderStream.join(
                priceTable,
                (order, price) -> {
                    double unitPrice = (price != null) ? price.price() : 0.0;
                    double cost = order.quantity() * unitPrice;
                    return new BilledOrder(order.commodityCode(), order.quantity(), cost);
                },
                Joined.with(stringSerde, orderSerde, priceSerde)
        );

        // 5. Output results
        billedStream.to("billed-orders", Produced.with(stringSerde, billedSerde));

        return builder.build();
    }
}
```
