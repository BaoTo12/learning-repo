# Module 01: Processor API Architecture & Topologies

The Kafka Streams DSL provides a quick way to assemble processing flows, but it abstracts away the underlying directed acyclic graph (DAG) structure. When you need absolute control over record routing, node execution, and metadata extraction, the **Processor API** is the tool of choice.

This module details how the Processor API is structured, how to build a manual `Topology` DAG, and how to control record routing.

---

## 1. High-Level DSL vs. Low-Level Processor API

Choosing between the DSL and the Processor API is a classic engineering trade-off:

| Aspect | Kafka Streams DSL | Processor API |
|---|---|---|
| **Abstractions** | `KStream`, `KTable`, `GlobalKTable` | `Topology`, `Processor`, `StateStore` |
| **Wiring** | Implicit (generated nodes and topic names) | Explicit (nodes named manually and connected via parent-child strings) |
| **Routing** | Automated (repartitioning, joins) or limited branching | Explicit (forward to specific named downstream nodes) |
| **Punctuation** | Tied to cache flush intervals and windowing boundaries | Fully custom scheduling (event-time or system wallclock) |
| **Code Verbosity** | Low (functional, fluent syntax) | High (requires verbose class structures and wiring) |

---

## 2. Programmatically Defining a Topology DAG

To build a topology with the Processor API, you instantiate the `org.apache.kafka.streams.Topology` class. You then add three types of nodes:
1. **Source Nodes**: Consume bytes from a Kafka topic, deserialize them into Java objects, and pass them to child processors.
2. **Processor Nodes**: Accept records, execute custom logic, interact with state stores, and optionally forward records downstream.
3. **Sink Nodes**: Serialize Java objects into bytes and write them to target Kafka topics.

```
                  [Source Node: beer-source]
                              |
                  [Processor Node: beer-processor]
                 /                                \
[Sink Node: domestic-sink]               [Sink Node: international-sink]
```

Here is a complete, production-ready topology definition for routing and converting brewery purchases:

```java
import org.apache.kafka.common.serialization.Serdes;
import org.apache.kafka.streams.Topology;
import org.apache.kafka.streams.processor.UsePartitionTimeOnInvalidTimestamp;
import java.util.Map;

public class BreweryTopologyBuilder {

    public Topology build() {
        Topology topology = new Topology();

        String sourceName = "beer-purchase-source";
        String processorName = "beer-purchase-processor";
        String domesticSinkName = "domestic-beer-sink";
        String internationalSinkName = "international-beer-sink";

        // 1. Add Source Node
        topology.addSource(
            Topology.AutoOffsetReset.LATEST,
            sourceName,
            new UsePartitionTimeOnInvalidTimestamp(), // Fallback extractor
            Serdes.String().deserializer(),
            new BeerPurchaseDeserializer(),
            "pops-hops-purchases" // Input topic
        );

        // 2. Add Processor Node (routing logic)
        Map<String, Double> conversionRates = Map.of("EUR", 1.10, "GBP", 1.30);
        topology.addProcessor(
            processorName,
            () -> new BeerPurchaseProcessor(domesticSinkName, internationalSinkName, conversionRates),
            sourceName // Parent node name
        );

        // 3. Add Sink Nodes (linked to the processor)
        topology.addSink(
            domesticSinkName,
            "domestic-sales", // Target topic
            Serdes.String().serializer(),
            new BeerPurchaseSerializer(),
            processorName // Parent node name
        );

        topology.addSink(
            internationalSinkName,
            "international-sales", // Target topic
            Serdes.String().serializer(),
            new BeerPurchaseSerializer(),
            processorName // Parent node name
        );

        return topology;
    }
}
```

---

## 3. Explicit Record Routing

In the Processor API, you forward records downstream using the `ProcessorContext` (usually accessible via the `context()` method in contextual classes). 

By default, calling `context().forward(record)` sends the record to **all** registered child nodes. However, you can achieve high-performance routing by specifying a target child node name:

```java
import org.apache.kafka.streams.processor.api.ContextualProcessor;
import org.apache.kafka.streams.processor.api.Record;
import java.util.Map;

public class BeerPurchaseProcessor extends ContextualProcessor<String, BeerPurchase, String, BeerPurchase> {

    private final String domesticSalesNode;
    private final String internationalSalesNode;
    private final Map<String, Double> conversionRates;

    public BeerPurchaseProcessor(String domesticSalesNode, String internationalSalesNode, Map<String, Double> conversionRates) {
        this.domesticSalesNode = domesticSalesNode;
        this.internationalSalesNode = internationalSalesNode;
        this.conversionRates = conversionRates;
    }

    @Override
    public void process(Record<String, BeerPurchase> record) {
        BeerPurchase purchase = record.value();
        String currency = purchase.getCurrency();

        if ("USD".equalsIgnoreCase(currency)) {
            // Forward directly to the domestic sink node
            context().forward(record, domesticSalesNode);
        } else {
            // Convert currency to USD
            double rate = conversionRates.getOrDefault(currency.toUpperCase(), 1.0);
            BeerPurchase convertedPurchase = new BeerPurchase(
                purchase.getId(),
                purchase.getBeerName(),
                purchase.getVolume(),
                purchase.getAmount() * rate,
                "USD"
            );

            Record<String, BeerPurchase> convertedRecord = new Record<>(
                record.key(),
                convertedPurchase,
                record.timestamp()
            );

            // Forward directly to the international sink node
            context().forward(convertedRecord, internationalSalesNode);
        }
    }
}
```

---

## 4. Architectural Safeguards

### Stringly-Typed Wiring Warnings
Connecting parent and child nodes in the topology relies on literal string identifiers. Misspelling a node ID in `.addProcessor()` or `.addSink()` will throw a `TopologyException` during application initialization.
* **Best Practice**: Use central constants or a configurations class to define node names rather than hardcoded string literals.

### Graph Validation
Kafka Streams validates the graph when `builder.build()` or `new Topology()` is constructed. It checks for:
* **Cycles**: The topology must be a Directed Acyclic Graph. Cycles will result in an immediate initialization failure.
* **Orphan Nodes**: Every processor/sink must have at least one parent node (except source nodes).
* **Missing State Stores**: If a processor references a state store that has not been defined or wired to it, an exception is thrown.
