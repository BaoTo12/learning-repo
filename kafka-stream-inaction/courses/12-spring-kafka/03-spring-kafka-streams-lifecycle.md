# Module 03: Spring Kafka Streams Lifecycle Management

When building stream processing applications inside a Spring container, you can let Spring Boot manage the lifecycle of your `KafkaStreams` instances automatically, or you can take manual control of creation and cleanup while leveraging Spring strictly for dependency injection.

This module covers the configurations, lifecycle hooks, and customization interfaces used to manage Kafka Streams in an enterprise Spring Boot application.

---

## 1. Managed Lifecycle with `@EnableKafkaStreams`

To enable automatic lifecycle management, annotate a `@Configuration` class with **`@EnableKafkaStreams`**. Spring Boot will automatically scan for a configuration bean named `defaultKafkaStreamsConfig` and instantiate a `StreamsBuilderFactoryBean` to manage the topology lifecycle.

### Step 1: Configuration Bean Definition

```java
import org.apache.kafka.streams.StreamsConfig;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.kafka.annotation.EnableKafka;
import org.springframework.kafka.annotation.EnableKafkaStreams;
import org.springframework.kafka.annotation.KafkaStreamsDefaultConfiguration;
import org.springframework.kafka.config.KafkaStreamsConfiguration;
import java.util.HashMap;
import java.util.Map;

@Configuration
@EnableKafka
@EnableKafkaStreams
public class SpringStreamsConfig {

    @Value("${spring.kafka.bootstrap-servers}")
    private String bootstrapServers;

    // The method name MUST match the constant defaultKafkaStreamsConfig
    @Bean(name = KafkaStreamsDefaultConfiguration.DEFAULT_STREAMS_CONFIG_BEAN_NAME)
    public KafkaStreamsConfiguration kafkaStreamsConfiguration() {
        Map<String, Object> props = new HashMap<>();
        props.put(StreamsConfig.APPLICATION_ID_CONFIG, "spring-loan-processor");
        props.put(StreamsConfig.BOOTSTRAP_SERVERS_CONFIG, bootstrapServers);
        props.put(StreamsConfig.DEFAULT_KEY_SERDE_CLASS_CONFIG, org.apache.kafka.common.serialization.Serdes.String().getClass().getName());
        props.put(StreamsConfig.DEFAULT_VALUE_SERDE_CLASS_CONFIG, org.apache.kafka.common.serialization.Serdes.Double().getClass().getName());
        
        return new KafkaStreamsConfiguration(props);
    }
}
```

### Step 2: Injecting the Managed `StreamsBuilder`
Once `@EnableKafkaStreams` is active, Spring manages a singleton `StreamsBuilder` instance. You inject it using `@Autowired` on a method that returns `void`:

```java
import org.apache.kafka.streams.StreamsBuilder;
import org.apache.kafka.streams.kstream.KStream;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

@Component
public class LoanStreamsTopology {

    @Autowired
    public void buildTopology(StreamsBuilder streamsBuilder) {
        KStream<String, Double> input = streamsBuilder.stream("loan-requests");
        
        // Define topology operators...
        input.mapValues(v -> v * 1.10).to("loan-adjustments");
        
        // No return statement or builder.build() call needed!
        // Spring gathers the builder settings and invokes build() automatically at startup.
    }
}
```

---

## 2. Customizing the Managed `KafkaStreams` Instance

Sometimes you need access to the underlying `KafkaStreams` object before it starts running, e.g., to set a `StateListener` or query thread metadata. You can configure this using customizer beans:

```java
import org.apache.kafka.streams.KafkaStreams;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.kafka.config.KafkaStreamsCustomizer;
import org.springframework.kafka.config.StreamsBuilderFactoryBeanCustomizer;

@Configuration
public class StreamsCustomizerConfig {

    // 1. Define the customizer for the KafkaStreams instance
    @Bean
    public KafkaStreamsCustomizer kafkaStreamsCustomizer() {
        return kafkaStreams -> {
            kafkaStreams.setStateListener((newState, oldState) -> {
                System.out.printf("Kafka Streams state transitioned from %s to %s%n", oldState, newState);
                if (newState == KafkaStreams.State.RUNNING) {
                    // Log local tasks metadata
                    kafkaStreams.metadataForLocalThreads().forEach(threadMetadata ->
                        System.out.println("Active Tasks: " + threadMetadata.activeTasks())
                    );
                }
            });
        };
    }

    // 2. Register the customizer with the factory bean
    @Bean
    public StreamsBuilderFactoryBeanCustomizer streamsBuilderFactoryBeanCustomizer(
            KafkaStreamsCustomizer customizer) {
        return factoryBean -> factoryBean.setKafkaStreamsCustomizer(customizer);
    }
}
```

---

## 3. Manual Lifecycle Management

If you prefer to have absolute control over when the streams application starts and stops (rather than relying on Spring's factory hooks), you can manage the lifecycle manually:

### Step 1: Define a Topology Provider Bean

```java
import org.apache.kafka.streams.StreamsBuilder;
import org.apache.kafka.streams.Topology;
import org.springframework.stereotype.Component;

@Component
public class ManualStreamsTopology {

    public Topology createTopology() {
        StreamsBuilder builder = new StreamsBuilder();
        builder.stream("manual-input-topic").to("manual-output-topic");
        return builder.build();
    }
}
```

### Step 2: Implement the Lifecycle Container Bean
Use Spring's `@PostConstruct` and `@PreDestroy` annotations to start and gracefully stop the application:

```java
import jakarta.annotation.PostConstruct;
import jakarta.annotation.PreDestroy;
import org.apache.kafka.streams.KafkaStreams;
import org.apache.kafka.streams.Topology;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.kafka.config.KafkaStreamsConfiguration;
import org.springframework.stereotype.Component;
import java.time.Duration;

@Component
public class CustomStreamsLifecycleContainer {

    private final ManualStreamsTopology topologyProvider;
    private final KafkaStreamsConfiguration streamsConfigs;
    private KafkaStreams kafkaStreams;

    @Autowired
    public CustomStreamsLifecycleContainer(ManualStreamsTopology topologyProvider,
                                          KafkaStreamsConfiguration streamsConfigs) {
        this.topologyProvider = topologyProvider;
        this.streamsConfigs = streamsConfigs;
    }

    @PostConstruct
    public void start() {
        Topology topology = topologyProvider.createTopology();
        
        // Manually instantiate the client
        this.kafkaStreams = new KafkaStreams(topology, streamsConfigs.asProperties());
        
        // Start the client threads
        this.kafkaStreams.start();
        System.out.println("Kafka Streams manual client started successfully.");
    }

    @PreDestroy
    public void stop() {
        if (this.kafkaStreams != null) {
            // Gracefully shutdown client threads within a 10-second timeout
            this.kafkaStreams.close(Duration.ofSeconds(10));
            System.out.println("Kafka Streams manual client stopped gracefully.");
        }
    }
}
```
