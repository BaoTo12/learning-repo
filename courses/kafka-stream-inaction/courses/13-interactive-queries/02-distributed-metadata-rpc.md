# Module 02: Distributed State Metadata & RPC Routing

In a distributed production environment, state is partitioned and spread across multiple independent application instances. A single node only contains the state corresponding to its assigned partitions. To build a unified API layer, your application must route queries dynamically to the instance holding the requested key.

This module details how to query cluster metadata to find key ownership, construct an RPC forwarding layer, and execute failover lookups using standby tasks.

---

## 1. Finding Key Ownership with `KeyQueryMetadata`

When a client queries a key, you must determine which application instance owns the partition containing that key. Kafka Streams makes this possible by distributing host metadata during consumer group rebalances.

To look up partition metadata for a key:
1. Configure `application.server` in `StreamsConfig` with a unique `host:port` combination for each instance.
2. Call `kafkaStreams.queryMetadataForKey(storeName, key, keySerializer)`.

```java
import org.apache.kafka.common.serialization.Serializer;
import org.apache.kafka.streams.KafkaStreams;
import org.apache.kafka.streams.KeyQueryMetadata;
import org.apache.kafka.streams.state.HostInfo;

public class KeyMetadataFinder {

    private final KafkaStreams kafkaStreams;
    private final String storeName;

    public KeyMetadataFinder(KafkaStreams kafkaStreams, String storeName) {
        this.kafkaStreams = kafkaStreams;
        this.storeName = storeName;
    }

    public KeyQueryMetadata findMetadata(String key, Serializer<String> serializer) {
        // Returns active host info, standby host info, and partition ID
        KeyQueryMetadata metadata = kafkaStreams.queryMetadataForKey(storeName, key, serializer);
        
        if (metadata == null || metadata.equals(KeyQueryMetadata.NOT_AVAILABLE)) {
            throw new IllegalStateException("Metadata not available. Is the cluster rebalancing?");
        }
        return metadata;
    }
}
```

---

## 2. Implementing the RPC Routing Layer

By combining metadata retrieval with Spring's REST template, we can construct an automatic query router. If the key is local, process it; if it is remote, forward it via HTTP to the correct sibling node.

```java
import org.apache.kafka.common.serialization.Serdes;
import org.apache.kafka.streams.KafkaStreams;
import org.apache.kafka.streams.KeyQueryMetadata;
import org.apache.kafka.streams.state.HostInfo;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.client.RestTemplate;
import jakarta.annotation.PostConstruct;

@RestController
@RequestMapping("/loan-app-iq")
public class LoanApplicationController {

    private final KafkaStreams kafkaStreams;
    private final RestTemplate restTemplate;
    private final String storeName;
    private final String applicationServer; // Configured as host:port

    private HostInfo thisHostInfo;

    @Autowired
    public LoanApplicationController(
            KafkaStreams kafkaStreams,
            RestTemplate restTemplate,
            @Value("${store.name}") String storeName,
            @Value("${application.server}") String applicationServer) {
        this.kafkaStreams = kafkaStreams;
        this.restTemplate = restTemplate;
        this.storeName = storeName;
        this.applicationServer = applicationServer;
    }

    @PostConstruct
    public void init() {
        String[] parts = applicationServer.split(":");
        this.thisHostInfo = new HostInfo(parts[0], Integer.parseInt(parts[1]));
    }

    @GetMapping("/loantype/{category}")
    public QueryResponse<LoanAppRollup> getCategoryRollup(@PathVariable String category) {
        // 1. Locate the owner metadata for the key
        KeyQueryMetadata metadata = kafkaStreams.queryMetadataForKey(
            storeName, category, Serdes.String().serializer());

        if (metadata == null) {
            return QueryResponse.withError("Metadata not available.");
        }

        HostInfo activeHost = metadata.activeHost();

        // 2. Route Query: Is the key local or remote?
        if (activeHost.equals(thisHostInfo)) {
            // Local Lookup (from RockDB)
            LoanAppRollup localResult = queryLocalStore(category, metadata.partition());
            return QueryResponse.withResult(localResult);
        } else {
            // Remote Lookup (forward via HTTP REST call)
            String remoteUrl = String.format("http://%s:%d/loan-app-iq/loantype/%s", 
                activeHost.host(), activeHost.port(), category);
            
            try {
                return restTemplate.getForObject(remoteUrl, QueryResponse.class);
            } catch (Exception ex) {
                // If active host fails, try standby lookups (see Section 4)
                return queryStandbyHosts(metadata, category);
            }
        }
    }
}
```

---

## 3. Querying All Instances (Range Queries)

Unlike key queries, a **Range Query** cannot target a single instance because keys matching the range are spread across all task partitions. To resolve a range query, you must query **every instance** in the cluster and merge the results:

```java
import org.apache.kafka.streams.state.StreamsMetadata;
import java.util.ArrayList;
import java.util.Collection;
import java.util.List;

public List<LoanAppRollup> getRangeAcrossCluster(String lowerKey, String upperKey) {
    List<LoanAppRollup> combinedResults = new ArrayList<>();

    // 1. Fetch metadata for all instances containing the store
    Collection<StreamsMetadata> clusterMetadata = kafkaStreams.streamsMetadataForStore(storeName);

    // 2. Iterate and query each instance (locally or via REST)
    for (StreamsMetadata instanceMetadata : clusterMetadata) {
        HostInfo host = instanceMetadata.hostInfo();
        
        if (host.equals(thisHostInfo)) {
            combinedResults.addAll(queryLocalRange(lowerKey, upperKey));
        } else {
            String remoteUrl = String.format("http://%s:%d/loan-app-iq/range?lower=%s&upper=%s", 
                host.host(), host.port(), lowerKey, upperKey);
            
            List<LoanAppRollup> remoteResult = restTemplate.getForObject(remoteUrl, List.class);
            if (remoteResult != null) {
                combinedResults.addAll(remoteResult);
            }
        }
    }
    return combinedResults;
}
```

---

## 4. Querying Standby Tasks for High Availability

When a cluster node goes offline, the partitions it owned are offline until consumer groups finish rebalancing. To prevent API downtime during rebalances, configure **standby tasks** (`num.standby.replicas` in properties). Standby tasks maintain local, replicated copies of states.

If querying the active host fails, fall back to querying the standby hosts:

```java
private QueryResponse<LoanAppRollup> queryStandbyHosts(KeyQueryMetadata metadata, String category) {
    // Retrieve standby hosts assigned to the partition containing this key
    Collection<HostInfo> standbyHosts = metadata.standbyHosts();
    
    if (standbyHosts.isEmpty()) {
        return QueryResponse.withError("Active host failed and no standbys are available.");
    }

    for (HostInfo standbyHost : standbyHosts) {
        String remoteUrl = String.format("http://%s:%d/loan-app-iq/loantype/%s", 
            standbyHost.host(), standbyHost.port(), category);
        
        try {
            // Standby query (sacrifices strict consistency for high availability)
            return restTemplate.getForObject(remoteUrl, QueryResponse.class);
        } catch (Exception ex) {
            // Log warning and try next standby
        }
    }
    return QueryResponse.withError("Active and all standby hosts failed.");
}
```
> [!IMPORTANT]
> Querying a standby task represents a trade-off: **Availability over Consistency**. Standby tasks consume changelogs asynchronously, meaning they might be slightly behind the active partition. The returned results are eventually consistent.
