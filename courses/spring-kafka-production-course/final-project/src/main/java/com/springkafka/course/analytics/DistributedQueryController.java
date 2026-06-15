package com.springkafka.course.analytics;

import org.apache.kafka.common.serialization.Serdes;
import org.apache.kafka.streams.KafkaStreams;
import org.apache.kafka.streams.KeyQueryMetadata;
import org.apache.kafka.streams.StoreQueryParameters;
import org.apache.kafka.streams.state.HostInfo;
import org.apache.kafka.streams.state.QueryableStoreTypes;
import org.apache.kafka.streams.state.ReadOnlyKeyValueStore;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseEntity;
import org.springframework.kafka.config.StreamsBuilderFactoryBean;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

@RestController
@RequestMapping("/api/analytics")
public class DistributedQueryController {
    private static final Logger log = LoggerFactory.getLogger(DistributedQueryController.class);

    private final StreamsBuilderFactoryBean streamsFactory;
    private final WebClient.Builder webClientBuilder;

    @Value("${spring.kafka.properties.application.server}")
    private String localApplicationServer;

    public DistributedQueryController(StreamsBuilderFactoryBean streamsFactory, WebClient.Builder webClientBuilder) {
        this.streamsFactory = streamsFactory;
        this.webClientBuilder = webClientBuilder;
    }

    // 1. Point lookup endpoint with distributed metadata-routing
    @GetMapping("/spend/{accountId}")
    public Mono<ResponseEntity<Double>> getCustomerSpend(@PathVariable String accountId) {
        KafkaStreams streams = streamsFactory.getKafkaStreams();
        if (streams == null || streams.state() != KafkaStreams.State.RUNNING) {
            log.warn("INTERACTIVE QUERIES -> Streams app is not in RUNNING state.");
            return Mono.just(ResponseEntity.status(503).build());
        }

        try {
            // Find partition metadata for the requested key (accountId)
            KeyQueryMetadata metadata = streams.queryMetadataForKey(
                    "customer-spend-store", 
                    accountId, 
                    Serdes.String().serializer()
            );

            if (metadata == null || metadata.activeHost() == null) {
                return Mono.just(ResponseEntity.notFound().build());
            }

            HostInfo activeHost = metadata.activeHost();
            String host = activeHost.host();
            int port = activeHost.port();
            String hostString = host + ":" + port;

            log.info("INTERACTIVE QUERIES -> Key {} resides on host location: {}", accountId, hostString);

            // If key belongs to local node, fetch from local RocksDB instance
            if (hostString.equals(localApplicationServer) || hostString.contains("localhost")) {
                log.info("INTERACTIVE QUERIES -> Querying local RocksDB store for account: {}", accountId);
                Double localValue = queryLocalStore(accountId);
                return Mono.just(ResponseEntity.ok(localValue));
            }

            // Otherwise, forward request to the correct remote node
            String forwardUrl = String.format("http://%s/api/analytics/local/%s", hostString, accountId);
            log.info("INTERACTIVE QUERIES -> Routing query dynamically to remote node location: {}", forwardUrl);

            return webClientBuilder.build()
                    .get()
                    .uri(forwardUrl)
                    .retrieve()
                    .bodyToMono(Double.class)
                    .map(ResponseEntity::ok)
                    .onErrorResume(e -> {
                        log.error("INTERACTIVE QUERIES -> Remote query failed for URL: " + forwardUrl, e);
                        // Fallback: search local database in case of connection drop
                        return Mono.just(ResponseEntity.ok(queryLocalStore(accountId)));
                    });

        } catch (Exception e) {
            log.error("INTERACTIVE QUERIES -> Metadata lookup failure", e);
            return Mono.just(ResponseEntity.internalServerError().build());
        }
    }

    // 2. Direct local point lookup endpoint called by remote nodes
    @GetMapping("/local/{accountId}")
    public ResponseEntity<Double> getLocalSpend(@PathVariable String accountId) {
        log.info("INTERACTIVE QUERIES -> Remote node requesting local spend lookup for account: {}", accountId);
        Double value = queryLocalStore(accountId);
        return ResponseEntity.ok(value);
    }

    private Double queryLocalStore(String accountId) {
        KafkaStreams streams = streamsFactory.getKafkaStreams();
        if (streams == null) return 0.0;
        try {
            ReadOnlyKeyValueStore<String, Double> store = streams.store(
                    StoreQueryParameters.fromNameAndType("customer-spend-store", QueryableStoreTypes.keyValueStore())
            );
            Double total = store.get(accountId);
            return (total != null) ? total : 0.0;
        } catch (Exception e) {
            log.error("INTERACTIVE QUERIES -> Failed to read local RocksDB key", e);
            return 0.0;
        }
    }
}
