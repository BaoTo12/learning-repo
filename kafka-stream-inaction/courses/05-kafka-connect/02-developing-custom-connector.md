# Module 02: Developing Custom Connectors & Dynamic Task Management

When off-the-shelf connectors on Confluent Hub do not meet your business requirements (e.g., integrating with a proprietary HTTP service, parsing custom binary protocols, or executing custom API logic), you can implement your own connector using the Kafka Connect API. 

This module guides you through building a custom **Source Connector** in Java, implementing a **Dynamic Monitoring Thread** to handle runtime state changes, and writing a robust **Source Task** with throttling and offset tracking.

---

## 1. Custom Connector Lifecycle & Configuration

A connector is responsible for defining its configuration options, parsing input properties, managing its tasks' configurations, and routing lifecycle actions. To create a source connector, extend the abstract `org.apache.kafka.connect.source.SourceConnector` class.

### 1.1 Defining Configurations with `ConfigDef`
The connector uses a `ConfigDef` to declare config parameters, types, default values, validations, and importance levels. If a required configuration is missing, the Connect runtime throws a `ConfigException` and halts deployment.

### 1.2 Distributing Partitions via `ConnectorUtils.groupPartitions`
The connector must split the workload (e.g., a set of tables or a list of API symbols) into multiple tasks. If the configuration dictates `tasks.max = 2`, but the connector monitors 10 resources, it should split them into two batches of 5 resources each.

### 1.3 Custom Connector Implementation Example

```java
package com.enterprise.connect.ticker;

import org.apache.kafka.common.config.ConfigDef;
import org.apache.kafka.common.config.ConfigException;
import org.apache.kafka.connect.connector.ConnectorContext;
import org.apache.kafka.connect.connector.Task;
import org.apache.kafka.connect.source.SourceConnector;
import org.apache.kafka.connect.util.ConnectorUtils;

import java.util.*;

public class StockTickerSourceConnector extends SourceConnector {

    public static final String API_URL_CONFIG = "api.url";
    public static final String TOPIC_CONFIG = "topic";
    public static final String TOKEN_CONFIG = "api.token";
    public static final String TASK_BATCH_SIZE_CONFIG = "tasks.batch.size";
    public static final String TICKER_SYMBOL_CONFIG = "ticker.symbols";
    public static final String MONITOR_INTERVAL_MS = "monitor.interval.ms";

    private static final ConfigDef CONFIG_DEF = new ConfigDef()
        .define(API_URL_CONFIG, ConfigDef.Type.STRING, ConfigDef.Importance.HIGH, "URL of the ticker API endpoint")
        .define(TOPIC_CONFIG, ConfigDef.Type.STRING, ConfigDef.Importance.HIGH, "Kafka topic to publish stock events to")
        .define(TOKEN_CONFIG, ConfigDef.Type.PASSWORD, ConfigDef.Importance.HIGH, "API access token")
        .define(TASK_BATCH_SIZE_CONFIG, ConfigDef.Type.INT, 100, ConfigDef.Importance.MEDIUM, "Maximum batch size per task fetch")
        .define(TICKER_SYMBOL_CONFIG, ConfigDef.Type.STRING, ConfigDef.Importance.HIGH, "Comma-separated stock symbols to monitor")
        .define(MONITOR_INTERVAL_MS, ConfigDef.Type.LONG, 30000L, ConfigDef.Importance.LOW, "Interval to poll API for symbol changes");

    private Map<String, String> configProperties;
    private StockTickerMonitorThread monitorThread;

    @Override
    public void start(Map<String, String> props) {
        this.configProperties = props;
        try {
            // Validate config
            new ConfigDef().parse(props);
        } catch (ConfigException e) {
            throw new ConfigException("Failed to start StockTickerSourceConnector due to configuration error", e);
        }

        // Initialize and start the dynamic metadata monitoring thread
        long interval = Long.parseLong(props.getOrDefault(MONITOR_INTERVAL_MS, "30000"));
        String symbolsUrl = props.get(API_URL_CONFIG) + "/symbols";
        String token = props.get(TOKEN_CONFIG);

        monitorThread = new StockTickerMonitorThread(context(), interval, symbolsUrl, token);
        monitorThread.start();
    }

    @Override
    public Class<? extends Task> taskClass() {
        return StockTickerSourceTask.class;
    }

    @Override
    public List<Map<String, String>> taskConfigs(int maxTasks) {
        List<Map<String, String>> taskConfigs = new ArrayList<>();
        // Read the current list of symbols from the monitor thread (which dynamically updates)
        List<String> symbols = monitorThread.getCurrentSymbols();
        
        int numTasks = Math.min(symbols.size(), maxTasks);
        if (numTasks == 0) {
            return Collections.emptyList();
        }

        // Balance the symbol tracking load across tasks
        List<List<String>> groupedSymbols = ConnectorUtils.groupPartitions(symbols, numTasks);

        for (List<String> symbolGroup : groupedSymbols) {
            Map<String, String> taskConfig = new HashMap<>(configProperties);
            taskConfig.put(TICKER_SYMBOL_CONFIG, String.join(",", symbolGroup));
            taskConfigs.add(taskConfig);
        }
        return taskConfigs;
    }

    @Override
    public void stop() {
        if (monitorThread != null) {
            monitorThread.shutdown();
            try {
                monitorThread.join(5000);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        }
    }

    @Override
    public ConfigDef config() {
        return CONFIG_DEF;
    }

    @Override
    public String version() {
        return "2.0.0";
    }
}
```

---

## 2. Implementing a Dynamic Monitoring Thread

In production systems, configurations are rarely static. Database tables are added, directories receive new files, or the list of stock symbols users subscribe to changes. 

Instead of requiring operators to manually reissue REST configurations to reallocate tasks, a custom connector can run a background **Monitoring Thread** to discover configuration drift and trigger task reconfiguration automatically.

```java
package com.enterprise.connect.ticker;

import org.apache.kafka.connect.connector.ConnectorContext;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.util.*;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

public class StockTickerMonitorThread extends Thread {
    private static final Logger log = LoggerFactory.getLogger(StockTickerMonitorThread.class);

    private final ConnectorContext context;
    private final long pollIntervalMs;
    private final String symbolsUrl;
    private final String apiToken;
    private final HttpClient httpClient;
    private final CountDownLatch shutdownLatch;

    private List<String> currentSymbols;

    public StockTickerMonitorThread(ConnectorContext context, long pollIntervalMs, String symbolsUrl, String apiToken) {
        this.context = context;
        this.pollIntervalMs = pollIntervalMs;
        this.symbolsUrl = symbolsUrl;
        this.apiToken = apiToken;
        this.httpClient = HttpClient.newHttpClient();
        this.shutdownLatch = new CountDownLatch(1);
        this.currentSymbols = new ArrayList<>();
    }

    public synchronized List<String> getCurrentSymbols() {
        return new ArrayList<>(currentSymbols);
    }

    @Override
    public void run() {
        log.info("Starting stock ticker monitoring thread");
        while (shutdownLatch.getCount() > 0) {
            try {
                if (hasSymbolsChanged()) {
                    log.info("Change in ticker symbols detected. Requesting task reconfiguration from Connect Runtime.");
                    // Request the worker cluster to re-evaluate task configurations via taskConfigs()
                    context.requestTaskReconfiguration();
                }
                
                boolean stopSignal = shutdownLatch.await(pollIntervalMs, TimeUnit.MILLISECONDS);
                if (stopSignal) {
                    break;
                }
            } catch (InterruptedException e) {
                log.warn("Monitor thread interrupted", e);
                Thread.currentThread().interrupt();
                break;
            } catch (Exception e) {
                log.error("Error checking symbols list", e);
            }
        }
    }

    private boolean hasSymbolsChanged() throws Exception {
        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(symbolsUrl))
                .header("Authorization", "Bearer " + apiToken)
                .GET()
                .build();

        HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
        if (response.statusCode() != 200) {
            log.error("Failed to query ticker symbols API. Code: {}", response.statusCode());
            return false;
        }

        // Parse CSV response
        List<String> newSymbols = Arrays.stream(response.body().split(","))
                .map(String::trim)
                .filter(s -> !s.isEmpty())
                .sorted()
                .toList();

        synchronized (this) {
            if (!newSymbols.equals(currentSymbols)) {
                currentSymbols = newSymbols;
                return true;
            }
        }
        return false;
    }

    public void shutdown() {
        log.info("Shutting down stock ticker monitoring thread");
        shutdownLatch.countDown();
    }
}
```

---

## 3. Implementing the Source Task

The task does the actual work of pulling data and pushing it into Kafka. To implement this, extend `org.apache.kafka.connect.source.SourceTask`.

### 3.1 Throttling
APIs frequently apply strict rate-limiting. Within `poll()`, calculate the time since the last call and enforce a backoff using a precise time calculation.

### 3.2 Offset Tracking (Partition & Offset Map)
Kafka Connect tracks the source offset. We pass two maps to each `SourceRecord`:
1.  **Source Partition Map**: Identifies *what* datastore partition is being read (e.g., `{"symbol": "AAPL"}`).
2.  **Source Offset Map**: Identifies the *position* read in that source partition (e.g., `{"timestamp": 1718210344000}`).

On startup, call `context.offsetStorageReader().offset(partitionMap)` to retrieve the last committed offset and resume where the task left off.

```java
package com.enterprise.connect.ticker;

import org.apache.kafka.connect.data.Schema;
import org.apache.kafka.connect.data.SchemaBuilder;
import org.apache.kafka.connect.data.Struct;
import org.apache.kafka.connect.source.SourceRecord;
import org.apache.kafka.connect.source.SourceTask;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Instant;
import java.util.*;
import java.util.concurrent.atomic.AtomicLong;

public class StockTickerSourceTask extends SourceTask {
    private static final Logger log = LoggerFactory.getLogger(StockTickerSourceTask.class);

    private String apiUrl;
    private String apiToken;
    private String topic;
    private List<String> symbolsToMonitor;
    private long lastPollTime;
    private long pollIntervalMs = 5000L; // Throttle: 5 seconds
    private HttpClient httpClient;

    // Schema definition for the records we produce
    private static final Schema VALUE_SCHEMA = SchemaBuilder.struct()
            .name("com.enterprise.connect.ticker.StockQuote")
            .field("symbol", Schema.STRING_SCHEMA)
            .field("price", Schema.FLOAT64_SCHEMA)
            .field("volume", Schema.INT64_SCHEMA)
            .field("timestamp", Schema.INT64_SCHEMA)
            .build();

    @Override
    public String version() {
        return "2.0.0";
    }

    @Override
    public void start(Map<String, String> props) {
        this.apiUrl = props.get(StockTickerSourceConnector.API_URL_CONFIG);
        this.apiToken = props.get(StockTickerSourceConnector.TOKEN_CONFIG);
        this.topic = props.get(StockTickerSourceConnector.TOPIC_CONFIG);
        this.symbolsToMonitor = Arrays.asList(props.get(StockTickerSourceConnector.TICKER_SYMBOL_CONFIG).split(","));
        this.httpClient = HttpClient.newHttpClient();
        this.lastPollTime = 0;

        log.info("Starting Source Task monitoring symbols: {}", symbolsToMonitor);
    }

    @Override
    public List<SourceRecord> poll() throws InterruptedException {
        // Enforce throttling
        long now = Instant.now().toEpochMilli();
        long sleepTime = pollIntervalMs - (now - lastPollTime);
        if (sleepTime > 0) {
            Thread.sleep(sleepTime);
        }

        List<SourceRecord> records = new ArrayList<>();
        lastPollTime = Instant.now().toEpochMilli();

        for (String symbol : symbolsToMonitor) {
            // 1. Define source partition map
            Map<String, Object> sourcePartition = Collections.singletonMap("symbol", symbol);

            // 2. Fetch the offset where this specific task previously left off
            Map<String, Object> lastOffset = context.offsetStorageReader().offset(sourcePartition);
            long sinceTimestamp = 0;
            if (lastOffset != null && lastOffset.containsKey("timestamp")) {
                sinceTimestamp = (Long) lastOffset.get("timestamp");
            }

            try {
                // Fetch data from endpoint
                String queryUrl = String.format("%s/quotes?symbol=%s&since=%d", apiUrl, symbol, sinceTimestamp);
                HttpRequest request = HttpRequest.newBuilder()
                        .uri(URI.create(queryUrl))
                        .header("Authorization", "Bearer " + apiToken)
                        .GET()
                        .build();

                HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
                if (response.statusCode() == 200) {
                    // Simulating record extraction from body
                    double price = 100.0 + (new Random().nextDouble() * 50);
                    long volume = 1000 + new Random().nextInt(5000);
                    long recordTimestamp = Instant.now().toEpochMilli();

                    // Define the offset representing this record
                    Map<String, Object> sourceOffset = Collections.singletonMap("timestamp", recordTimestamp);

                    // Build value struct
                    Struct struct = new Struct(VALUE_SCHEMA)
                            .put("symbol", symbol)
                            .put("price", price)
                            .put("volume", volume)
                            .put("timestamp", recordTimestamp);

                    SourceRecord sourceRecord = new SourceRecord(
                            sourcePartition,
                            sourceOffset,
                            topic,
                            Schema.STRING_SCHEMA, // Key schema
                            symbol,               // Key
                            VALUE_SCHEMA,         // Value schema
                            struct                // Value Struct
                    );
                    records.add(sourceRecord);
                }
            } catch (Exception e) {
                log.error("Error fetching quotes for symbol: {}", symbol, e);
            }
        }

        // Return null if no new data was fetched to yield execution to the worker runtime thread.
        return records.isEmpty() ? null : records;
    }

    @Override
    public void stop() {
        log.info("Stopping Source Task");
    }
}
```

> [!CAUTION]
> If a task has no new data to return during a poll cycle, it **must return `null`** or an empty list rather than blocking indefinitely inside the `poll()` loop. Returning control to the worker runtime thread allows the Connect framework to check if the task has been paused, stopped, or scheduled for a configuration change.
