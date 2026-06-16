package com.springkafka.course.analytics;

import com.springkafka.course.avro.BalanceHoldEvent;
import io.confluent.kafka.streams.serdes.avro.SpecificAvroSerde;
import org.apache.kafka.common.serialization.Serdes;
import org.apache.kafka.common.utils.Bytes;
import org.apache.kafka.streams.KeyValue;
import org.apache.kafka.streams.StreamsBuilder;
import org.apache.kafka.streams.kstream.*;
import org.apache.kafka.streams.state.KeyValueStore;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.util.Collections;
import java.util.Map;

@Component
public class AnalyticsTopology {
    private static final Logger log = LoggerFactory.getLogger(AnalyticsTopology.class);

    @Value("${spring.kafka.properties.schema.registry.url}")
    private String schemaRegistryUrl;

    @Autowired
    public void buildSpendPipeline(StreamsBuilder streamsBuilder) {
        log.info("ANALYTICS STREAMS -> Initializing Stateful spend aggregation pipeline");

        // Set up Avro Serde for reading from Kafka topic
        SpecificAvroSerde<BalanceHoldEvent> balanceHoldSerde = new SpecificAvroSerde<>();
        balanceHoldSerde.configure(
                Collections.singletonMap("schema.registry.url", schemaRegistryUrl), 
                false
        );

        // Consume events from balance-replies
        KStream<String, BalanceHoldEvent> balanceRepliesStream = streamsBuilder.stream(
                "balance-replies",
                Consumed.with(Serdes.String(), balanceHoldSerde)
        );

        // Process stream: re-key by Account ID, filter only active money holds, aggregate total spend
        balanceRepliesStream
                .filter((key, event) -> event != null && "HELD".equals(event.getStatus().toString()))
                .map((key, event) -> {
                    String accountId = event.getAccountId().toString();
                    double amount = event.getAmount();
                    log.info("ANALYTICS STREAMS -> Mapping hold event for account: {} amount: ${}", accountId, amount);
                    return new KeyValue<>(accountId, amount);
                })
                .groupByKey(Grouped.with(Serdes.String(), Serdes.Double()))
                .aggregate(
                        () -> 0.0, // Initial value
                        (key, nextVal, currentSum) -> currentSum + nextVal, // Accumulator logic
                        Materialized.<String, Double, KeyValueStore<Bytes, byte[]>>as("customer-spend-store")
                                .withKeySerde(Serdes.String())
                                .withValueSerde(Serdes.Double())
                );
    }
}
