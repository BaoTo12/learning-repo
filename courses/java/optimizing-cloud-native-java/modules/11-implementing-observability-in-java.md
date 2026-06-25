# Implementing Observability in Java

In this chapter, you will see how to use the rules and ideas of the last chapter in real, live Java/JVM systems. This will include the three pillars of metrics, traces, and logs.

We will use three main technologies for our examples—**Micrometer**, **Prometheus**, and **OpenTelemetry**. However, you should clearly understand that these technologies are used in different areas. In practice, many real systems will use some or all of them together to give a complete observability setup.

There are also many other technologies used in this field, and some are more developed than others. In fact, one of the difficult problems in observability is managing the complexity of different setups.

A second, related problem: observability is designed to help us understand complex software systems and different designs (architectures).

> [!NOTE]
> While new patterns are appearing, there is no single "right" way to set up observability. The best solution for a specific software system depends on the details.

In this chapter, we'll be using **Fighting Animals**, from Chapter 8, as our example application.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//3031e6fa-bfd9-4fd2-8e35-15742ccf93ca/markdown_3/imgs/img_in_image_box_164_991_265_1090.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A13Z%2F-1%2F%2Fa1d933907bbcb89d210ee28e874e0865526949bb6b63be1d1b23b8092f7419d3" alt="Image" width="10%" /></div>

> [!NOTE]
> The design choices we make for watching Fighting Animals are not always the best choices for other applications. Much depends on the details of the application design and the environment where it is run.

Let's start looking at the Micrometer library to see how we can use it in our example application.

---

## Introducing Micrometer

At the time of writing (August 2024), one of the most common and effective Java metrics libraries is **Micrometer**. It was first created as part of the Spring project, but now it is standalone. It is a Java/JVM project, so teams that want to use the same library across a mixed design (heterogeneous architecture) will need to look at other options.

The project is best described as a vendor-neutral application metrics facade, though it has other subprojects that also handle other observability data types, such as tracing.

Micrometer integrates with a large number of metrics data sources and backends, including:
* Azure Monitor
* CloudWatch
* Datadog
* Dynatrace
* Elastic
* JMX
* New Relic
* OpenTelemetry Protocol (OTLP)
* Prometheus
* SignalFx
* StatsD

It is a library designed for application developers to use. Because of this, it expects the developer to intentionally create and record the metrics they want to collect.

### Meters and Registries

Micrometer provides a core library as a **Service Provider Interface** (SPI) and uses pluggable metric consumers. These consumers are service implementations that export data to different vendor and open-source solutions. This is similar to how a logging framework works (both are examples of the **facade pattern**). This structure lets the framework handle any differences between metrics systems by passing (delegating) any needed changes to the consumers that export the data.

We saw some of these differences in "Architectural Patterns for Metrics" (Chapter 10), and Micrometer’s interface is designed to be general enough to handle them. For example, not all metrics systems support adding dimensions to measurements. Instead, they use hierarchical naming.

There is also the question of how to group (aggregate) the data, which decides how metrics are created from individual samples. There are two general approaches, and different metrics systems make different decisions about which one to use:

#### Client-side
Separate samples are changed to a fixed rate (grouped) before they are sent to the server.

#### Server-side
All samples are sent over the network, and grouping happens at the server.

Metrics systems also differ in how the data is sent (or published) to the server. There are two main options:

#### Client push
The application exporter connects to the server and sends updates to it.

#### Server poll
The metrics backend connects to a standard port (usually HTTP) and scrapes data from the application.

These details are properties of the exporters, and Micrometer hides (abstracts) them. As a result, a developer who wants to write Java code can focus on the Micrometer API. They do not need to worry about the details of the metrics backend when adding metrics to their code.

In this API, the `Meter` is the main interface for collecting metrics. The different types of meters (the instrument types) are shown by instances of classes that implement different subinterfaces of `Meter`. Meters are named using all-lowercase letters with dot separators. This name is changed, if needed, into the native naming style when exporting metrics.

Each meter lives in a specific registry, such as these examples:

* `SimpleMeterRegistry`: In-memory only, used for development and unit testing.
* `LoggingMeterRegistry`: Also for development and testing, but logs meters periodically.
* `CompositeMeterRegistry`: Holds multiple registries (multipub).
* `Metrics.globalRegistry`: Static global registry.

Micrometer automatically connects (autowires) a test registry (`SimpleMeterRegistry`) when used in Spring applications. Non-Spring applications can simply create an instance of it (and the same is true for `LoggingMeterRegistry`):

```java
// for testing non-Spring applications
MeterRegistry myRegistry = new SimpleMeterRegistry();
// produces some output
MeterRegistry withOutput = new LoggingMeterRegistry();
```

In our Fighting Animals example (from the `micrometer_only` branch), we want to use a `LoggingMeterRegistry` at first. We connect this by providing a Spring bean in the application class, like this:

```java
@SpringBootApplication
public class AnimalApplication {

    @Bean
    public MeterRegistry basicRegistry() {
        return new LoggingMeterRegistry();
    }

    public static void main(String[] args) {
        SpringApplication.run(AnimalApplication.class, args);
    }
}
```

This will create a new `LoggingMeterRegistry` and make it available to connect (autowire) in the controller. This will log the metrics to the console, which is a good way to get started with Micrometer. Later, you'll see how to build something more advanced that is similar to what we would actually use in a live system.

> [!NOTE]
> This setup work must be done for each of the `*Application` classes, because the different microservices run in different containers.

Micrometer supports a wide range of instrument types that cover most common use cases:
* **Counter**: Count of all events.
* **Gauge**: Single metric value.
* **Timer**: Count and total time of all timed events.
* **DistributionSummary**: Tracks the spread (distribution) of non-timed events (histograms).

Less common instruments include `LongTaskTimer`, `TimeGauge`, `FunctionCounter`, and `FunctionTimer`.

In Micrometer, dimensions are shown as `Tag` objects. Tags are also named using a dotted lowercase style and must have non-null values.

### Counter

Let's look at a simple Micrometer code example that uses a counter:

```java
@RestController
public class AnimalController {
    // ...

    private final Counter battlesTotal;
    private final MeterRegistry registry;

    public AnimalController(MeterRegistry registry) {
        this.registry = registry;
        this.battlesTotal = this.registry.counter("battles.total");
    }

    @GetMapping("/battle")
    public String makeBattle() throws IOException, InterruptedException {
        battlesTotal.increment();
        // ...
    }
}
```

A Micrometer `Counter` shows a monotonic value—one that can only increase over time. This makes it a good fit for a metric that shows the number of battles that have been fought.

You can create them using the `counter()` method on the registry or by using a builder and `register()`:

```java
this.battlesTotal = Counter
    .builder("battles.total")
    .description("Total number of battles fought")
    .register(this.registry);
```

The final step in creating a counter is to register it with the registry. There are also some optional methods—such as setting the units and any tags.

### Gauges

Let's look at another example, this time using a `Gauge`. The gauge is a little more complex than the counter, because it needs to be able to change both up and down, rather than just increasing.

In this case, we want to track the percentage of feline animals that we have seen over time. For this, we need a class that holds a changeable (mutable) double value. There is nothing suitable in the JDK, so we create our own class, `FelinePercent`, which extends `java.lang.Number`.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//47d90e1f-cef5-48dc-9814-b17b4b262bff/markdown_2/imgs/img_in_image_box_163_1009_266_1107.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A21Z%2F-1%2F%2F1c42ec075685f31a0fb130d31345a973ccd16311f1447bffb73db9d1b0c68e15" alt="Image" width="10%" /></div>

> [!NOTE]
> The Java concurrency libraries do not provide an `AtomicDouble` class. This would have been an obvious choice for its changeable nature rather than its concurrency features.

The resulting code for the controller looks like this (details are shortened to make the observability code clearer):

```java
@RestController
public class MammalController {
    // ...
    private final FelinePercent felinePercent;
    private int felineCount = 0;
    private int mustelidCount = 0;
    private final MeterRegistry registry;

    public MammalController(MeterRegistry registry) {
        this.registry = registry;
        felinePercent = this.registry.gauge("battles.felinePercent", new FelinePercent(0.5));
    }

    @GetMapping("/getAnimal")
    public String getAnimal() throws IOException, InterruptedException {
        // ...
        var id = (int) (SERVICES.size() * Math.random());
        if (id == 0) {
            mustelidCount += 1;
        } else {
            felineCount += 1;
        }
        felinePercent.setValue((double) felineCount / (double) (felineCount + mustelidCount));
        // ...
    }
}
```

In this example, the main call is to `registry.gauge()`. This creates a new `Gauge` instance and registers it with the registry. In the Micrometer `MeterRegistry` class, the simplest form of the `gauge()` method is this:

```java
@Nullable
public <T extends Number> T gauge(String name, T number) {
    return this.gauge((String)name, (Iterable)Collections.emptyList(), (Number)number);
}
```

Note that the generics require the gauge class to extend `Number`, so we use this simple class definition:

```java
public final class FelinePercent extends Number {
    private volatile double value;

    public FelinePercent(double v) {
        if (v < 0.0 || v > 1.0) {
            throw new IllegalArgumentException("Require 0 < felinePercent < 1");
        }
        value = v;
    }

    public void setValue(double v) {
        if (v < 0.0 || v > 1.0) {
            throw new IllegalArgumentException("Require 0 < felinePercent < 1");
        }
        value = v;
    }

    @Override
    public int intValue() {
        return (int) value;
    }

    @Override
    public long longValue() {
        return (long) value;
    }

    @Override
    public float floatValue() {
        return (float) value;
    }

    @Override
    public double doubleValue() {
        return value;
    }
}
```

When you pass an instance of `FelinePercent` to the `gauge()` method, it creates a watcher for the state (the percentage of feline animals that we have seen).

The programmer only needs to update the gauge value, and the rest of the metrics system is hidden. The watcher updates the gauge value whenever needed. Note that this happens on demand, so the system does not see every single change. It only sees the current value at the time the update is needed.

### Meter Filters

Micrometer also uses **meter filters**. These give you more control over:
* How and when meters are registered.
* What kinds of statistics they send out.

As a first example, you can use filters to adapt metrics to a new (or old) set of styles without making many code changes.

Meter filters provide three basic functions:
1. Deny or accept meters being registered.
2. Change meters (change metric names, tags, units, and so on).
3. Configure distribution statistics.

Note that you can only set up the last function for the right meter types (timers and distribution summaries). We will explain this last function in more detail later in this section when we look at the instrument types that use it.

Filters are written as implementations of the `MeterFilter` interface. You can add them in your code, often by using a factory method, like this:

```java
// This next line prevents the internal metrics from being published
this.registry.config()
    .meterFilter(MeterFilter.denyNameStartsWith("internal"));
```

We do not actually have any internal metrics in our example, but this is a good show of how to use a filter. Preventing internal metrics from being published is a common use case.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//ee1943a9-2215-4532-bb79-2e4c01a915e9/markdown_0/imgs/img_in_image_box_176_593_252_693.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A10%3A53Z%2F-1%2F%2Fe9a6c12d0087fbd433493131f1733427e4e8f24268bec71e2348d44b567d4657" alt="Image" width="7%" /></div>

> [!NOTE]
> `MeterFilter` is an interface, but it is not a functional interface. This is because it has three non-static methods, and all of them are default methods. It has no mandatory methods at all.

We can also build filter objects directly. For example, the filter from the previous example does the same thing as this code:

```java
new MeterFilter() {
    @Override
    public MeterFilterReply accept(Meter.Id id) {
        if (id.getName().startsWith("internal")) {
            return MeterFilterReply.DENY;
        }
        return MeterFilterReply.NEUTRAL;
    }
}
```

The enum `MeterFilterReply` has three possible values: `DENY`, `NEUTRAL`, and `ACCEPT`. The `DENY` value stops the meter from being registered. The `ACCEPT` value registers it immediately, without looking at any other filters. `NEUTRAL` means that the filter has no opinion on the meter. In this case, the system will check the next filter for this metric, if there is one.

Adding filters with `meterFilter()` is additive, so the developer should think about the order of filters in the chain.

You can also use filters for more advanced cases, such as using them to customize a `CompositeMeterRegistry`. This lets you do things like sending a part of your metrics to a secondary backend. This can be very useful in live systems, but a full discussion of this is outside the scope of this book.

### Timers

Timers are a more complex data type that store at least three values inside:
* The sum of all recorded values.
* A count of the values that have been recorded.
* The largest value seen within a time window, as a gauge.

You can configure timers to send out extra statistics, such as histogram data, pre-calculated percentiles, or even service level objective (SLO) boundaries.

Let's look at an example and focus on the timer code on the `micrometer_only` branch. Here is the code for the timer in the `AnimalController`:

```java
@RestController
public class AnimalController {
    // ...
    private final Timer responseTimer;
    private final MeterRegistry registry;
    // ...

    public AnimalController(MeterRegistry registry) {
        this.registry = registry;
        // ...
        this.responseTimer = Timer
            .builder("response.time")
            .description("Response time")
            .register(registry);
    }

    @GetMapping("/battle")
    public String makeBattle() throws Exception {
        Callable<String> callable = () -> {
            // Send the two requests and return the response body as the response
            var good = fetchRandomAnimal();
            var evil = fetchRandomAnimal();
            return String.format("""
            { "good": "%s", "evil": "%s" }
            """, good, evil);
        };

        // ...
        return responseTimer.recordCallable(callable);
    }
}
```

In this code, we set up a block of code as a `Callable` and then pass it to the `recordCallable()` method of the timer. This will run the code block and record the time it takes to finish.

Timers can also handle code written as `Runnable` and `Supplier`. The correct Timer method is called `record()` in these cases. This is because of a conflict (signature collision) between `Callable` and `Supplier`.

To end our discussion of Micrometer timers, we should point out that, in general, timers are not the best way to measure method performance in a distributed system. Distributed tracing, like the one used by OpenTelemetry, is usually a much better way. We will discuss this method later in this chapter.

Next, let's discuss the last instrument type we want to look at: the Distribution Summary.

### Distribution Summaries

We have just looked at timers. They provide statistics on the spread (distribution) of the times they have seen. In fact, they are a special case of the broader concept of distribution summaries.

A **distribution summary** is an instrument used to summarize a whole set of values. They need more memory than a simple counter because they must store more data. However, they are still a simplified (lossy) representation of the overall distribution.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//ee1943a9-2215-4532-bb79-2e4c01a915e9/markdown_2/imgs/img_in_image_box_168_1011_254_1127.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A10%3A54Z%2F-1%2F%2F107de6a03555c6f1427e2f3158faec8785f2c98738fbfa55fba1f5ab59a73b29" alt="Image" width="8%" /></div>

> [!IMPORTANT]
> You should use distribution summaries for things that are not timed. If the measured amount is a duration (time), you should use a timer instead.

Let's look at an example and introduce a `DistributionSummary` into our `AnimalController`:

```java
@RestController
public class AnimalController {
    // ...
    private static final Random random = new Random();
    private final DistributionSummary winSummary;
    private final MeterRegistry registry;

    public AnimalController(MeterRegistry registry) {
        this.registry = registry;
        // Summarizes the size of the attacker's strength when it wins
        this.winSummary = registry.summary("attacker.win.size");
        // ...
    }
}
```

To show how a summary works, we will also add some code for a `resolveFight()` method in the `AnimalController`. The goal is to simulate a fight between two animals and return the winner. We set the defender's strength to 0.5 and then use a random number for the attacker's strength to find the winner:

```java
@GetMapping("/fight/{a}/{d}")
public String resolveFight(
    @PathVariable("a") String attacker, @PathVariable("d") String defender) {
    final String winner;
    // Defender's strength is taken to be 0.5
    var attackerStrength = random.nextDouble();
    if (attackerStrength > 0.5) {
        winner = attacker;
        // Add to the distribution summary
        winSummary.record(attackerStrength);
    } else {
        winner = defender;
    }
    return String.format("""
    { "winner": "%s" }
    """, winner);
}
```

If the attacker wins, their “strength” is recorded in the distribution summary. This should create a flat (uniform) distribution of values between 0.5 and 1.0, which the `DistributionSummary` will then summarize.

We will use the `LoggingMeterRegistry` for this example, and the output looks like this:

```
animal-service_1 | 2024-01-14T08:27:31.748Z INFO 1 --- [trics-publisher] i.m.c.i.logging.LoggingMeterRegistry : attacker.win.size{} throughput=0.183333/s mean=0.699785 max=0.98829
```

The default setup for distribution summaries is good enough for many purposes, but you can use metric filters to set up more advanced configurations. The main way to do this is with the third non-static method in the `MeterFilter` interface, `configure()`, which is written like this:

```java
@Nullable
default DistributionStatisticConfig configure(Meter.Id id, DistributionStatisticConfig config) {
    return config;
}
```

The default implementation does not change the configuration. However, a custom implementation will usually merge the new configuration with the input configuration.

By writing a custom filter that overrides this method, you can set up optional distribution statistics (along with the basics of count, total, and max). These extra statistics can include pre-calculated percentiles, SLOs, and histograms.

For example, to set up pre-calculated "long-tail" percentiles (which we saw in Chapter 2) for all JVM metrics, we could use a filter like this:

```java
new MeterFilter() {
    @Override
    public DistributionStatisticConfig configure(Meter.Id id, DistributionStatisticConfig config) {
        if (id.getName().startsWith("jvm")) {
            return DistributionStatisticConfig.builder()
                .publishPercentiles(0.9, 0.99, 0.999, 0.9999)
                .build()
                .merge(config);
        }
        return config;
    }
};
```

This will add the 90th, 99th, 99.9th, and 99.99th percentiles to all JVM metrics. This is very useful for watching the uneven (non-normal) distribution of many JVM metrics.

> [!WARNING]
> You must note that count, sum, and some other data from distribution summaries can be grouped again (reaggregated) across dimensions or instances. However, you cannot group pre-calculated percentile values again. Trying to do this is a serious and very common mistake.

The reason is that the way percentiles are created makes them unique to each dataset. To get accurate percentiles across the whole dataset, you must combine the original datasets and then calculate the percentiles. Once percentiles are calculated, some data is already lost. Grouping the percentiles again will not give the correct result, except in very rare, unusual cases.

To end this discussion of Micrometer, let's take a quick look at the JVM metrics support that the library provides out of the box.

### Runtime Metrics

Along with metrics defined by the programmer, Micrometer can collect and export a set of metrics from the JVM and other parts of the running application. You can collect several different sets of these metrics.

The main interface for this is `MeterBinder`, which is written like this:

```java
public interface MeterBinder {
    void bindTo(@NonNull MeterRegistry registry);
}
```

Two of the most important implementations of this are the JVM memory metrics and the processor metrics, as shown in this example:

```java
@RestController
public class AnimalController {
    // ...
    private final MeterRegistry registry;
    // ...

    public AnimalController(MeterRegistry registry) {
        this.registry = registry;

        new ProcessorMetrics().bindTo(this.registry);
        new JvmMemoryMetrics().bindTo(this.registry);
    }
    // ...
}
```

The main part of this is the `bindTo()` method, which makes the registry aware of the JVM-level metrics. This is not strictly required for Spring Boot applications because the framework installs them automatically. However, for other applications, you must turn them on explicitly. You can collect other sets of metrics too, but these are some of the most common ones.

As specific examples, the `JvmMemoryMetrics` class provides metrics such as `jvm.memory.used` and `jvm.memory.max`. The `ProcessorMetrics` class provides metrics like `system.cpu.usage` and `system.load.average.1m`. Another important case is metrics from an `ExecutorService`. You can turn these on like this: `new ExecutorServiceMetrics(executor, executorServiceName, tags).bindTo(registry)`. This lets you easily monitor thread pools.

Now that we have seen the basic instruments and features of Micrometer, let's look at Prometheus and see how we can connect it with Micrometer.

---

## Introducing Prometheus for Java Developers

We introduced Prometheus very briefly in Chapter 8 and referred to it several times in the last chapter, but we did not explain the technology fully. In this section, we will discuss it in more detail, especially how Java developers and projects can use it.

### Prometheus Architecture Overview

To review, **Prometheus** is a CNCF project (first created at SoundCloud) that provides a metrics backend, a collection method, and different integrations. It is designed to handle only numeric, regular time series data. It is not meant for logs or traces.

Of the metrics design options discussed before, Prometheus uses **server poll**, which it calls **scraping**. This means that every service you want to watch using Prometheus must provide an HTTP endpoint. The Prometheus scraper will collect metrics from this endpoint. In turn, this means that Prometheus depends on services being known or easy to find (discoverable). This can cause issues for short-lived jobs.

To handle these challenges, and to work better with technologies like OpenTelemetry that send data directly (use push-based designs), Prometheus also includes a remote write feature. This also fits better with the security model of systems like Kubernetes.

The complete architecture of a complex Prometheus setup is shown in Figure 11-1.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//1a6bdc4a-672c-4e4a-b3ab-3d600dfd193e/markdown_2/imgs/img_in_image_box_145_110_862_575.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A10%3A57Z%2F-1%2F%2Ffbed202a2139c58bf5a74b34827515b987085b25a3c92df766cd36e674e8517c" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 11-1. Prometheus architecture (source: Prometheus documentation)</div> </div>

As the diagram shows, there are many parts, and the exact combination depends on the design choices you make. Therefore, it is important to ask for details when people say they are “using Prometheus.”

Prometheus provides a query language called **PromQL**, which is used to write queries for the collected data. Despite the name, PromQL is not SQL. Instead, it is a domain-specific language (DSL) designed to query time series data rather than old relational data. You can then view the queried data in several different ways.

Prometheus includes a basic UI, but this is often not enough for live production use. Instead, it is more common to use other tools on top of Prometheus. The open source Grafana graphing tools are a popular choice.

In general, developers and DevOps engineers usually interact with Prometheus in two ways: through the UI, or by calling metrics code in their application code. However, knowing the general architecture of Prometheus (including how it stores data) is useful. It helps you understand how Prometheus fits into the whole observability picture, even if you are not directly responsible for running it.

### Using Prometheus with Micrometer

In our first examples, we used the `LoggingMeterRegistry` to send metrics to the console. This is, of course, not a realistic setup for a live system. In this section, we will see how to use Prometheus as a metrics backend for Micrometer.

Remember that we want to use a facade pattern to hide the details of the metrics backend. The idea is that there should be no Prometheus-specific code in our application. This makes testing easier, because we can run tests with a dummy or fake (mocked) metrics dependency.

People sometimes say that using facades lets you swap components, like replacing Prometheus with another metrics backend without changing application code. This ability to change the observability setup without changing the application can be very important. Indeed, it is one of the main reasons for standardization.

However, there are often details that make this harder in practice. Vendor lock-in can be more hidden than we expect. Also, in many cases, a major change of components gives us a chance to review the whole design and make other changes too.

Still, the facade design of Micrometer makes using Prometheus as a metrics backend quite simple. To use Prometheus in our applications, we can use the SPI design of the Micrometer library. We only need to add another dependency to our project:

```xml
<dependency>
    <groupId>io.micrometer</groupId>
    <artifactId>micrometer-registry-prometheus</artifactId>
    <scope>runtime</scope>
</dependency>
```

This provides an extra exporter to send metrics to Prometheus.

To see this in Fighting Animals, we need to make a few changes. To make this clearer, we did this on a separate branch (`micrometer_with_prom`).

We need to add this line to `application.properties`:

```properties
management.endpoints.web.exposure.include=health,info,prometheus
```

We are using Micrometer to show the metrics from the application directly as a scrapeable endpoint that Prometheus can connect to.

You can also remove the logging registry to reduce the amount of detail in the logs:

```java
// Remove this bean to reduce log noise
@Bean
public MeterRegistry basicRegistry() {
    return new LoggingMeterRegistry();
}
```

The design here is still quite simple, as shown in Figure 11-2.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//1a6bdc4a-672c-4e4a-b3ab-3d600dfd193e/markdown_4/imgs/img_in_image_box_143_220_865_631.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A10%3A58Z%2F-1%2F%2F1d5fe8bb726a98195828fc64f0dc5905ab9c2c3aa3a4cf05a40d86376db66424" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 11-2. Fighting Animals with Prometheus</div> </div>

To configure Prometheus for this setup, we need to add a new service to our `docker-compose.yml` file:

```yaml
prometheus:
  container_name: prometheus
  image: prom/prometheus
  command:
    - "--config.file=/config/prometheus.yml"
  ports:
    - "9090:9090"
  user: root
  volumes:
    - "./config:/config"
    - "./target/data/prometheus:/prometheus"
```

This refers to a new configuration file, `prometheus.yml`. The basic parts of this file look like this:

```yaml
global:
  # Set the scrape interval to every 15 seconds. Default is every 1 minute.
  scrape_interval: 15s
  # Evaluate rules every 15 seconds. The default is every 1 minute.
  evaluation_interval: 15s
  # scrape_timeout is set to the global default (10s)

# ...

scrape_configs:
  - job_name: prometheus
    metrics_path: /metrics
    scheme: http
    static_configs:
      - targets:
        - localhost:9090

  - job_name: animal
    metrics_path: /actuator/prometheus
    scrape_interval: 5s
    static_configs:
      - targets:
        - animal-service:8080
```

This is a simple configuration, but it has been tested to work across a real network instead of having everything run on localhost. This is very intentional because many examples on the internet only work on localhost, not in a real network environment.

With our config, each service will show its metrics on the same URI (`/actuator/prometheus`) on a different port, and Prometheus will scrape them all. Normal Prometheus output looks like this (from the animal service, running at a URL like `http://<Target IP>:8080/actuator/prometheus`):

```
# HELP system_load_average_1m The sum of the number of runnable entities queued to available processors and the number of runnable entities running on the available processors averaged over a period of time
# TYPE system_load_average_1m gauge
system_load_average_1m 0.2
# HELP process_files_open_files The open file descriptor count
# TYPE process_files_open_files gauge
process_files_open_files 34.0
# HELP jvm_classes_loaded_classes The number of classes that are currently loaded in the Java virtual machine
# TYPE jvm_classes_loaded_classes gauge
jvm_classes_loaded_classes 8934.0
# HELP tomcat_sessions_active_current_sessions
# TYPE tomcat_sessions_active_current_sessions gauge
tomcat_sessions_active_current_sessions 0.0
# HELP jvm_memory_committed_bytes The amount of memory in bytes that is committed for the Java virtual machine to use
# TYPE jvm_memory_committed_bytes gauge
jvm_memory_committed_bytes{area="nonheap",id="CodeHeap 'profiled nmethods'",} 9109504.0
jvm_memory_committed_bytes{area="heap",id="G1 Survivor Space",} 4194304.0
# ... Other JVM metrics omitted for brevity ...
jvm_memory_committed_bytes{area="nonheap",id="CodeHeap 'non-profiled nmethods'",} 3145728.0
```

Note that many of these metrics are JVM metrics instead of application metrics. If we look further down the output, we can see some of our custom metrics:

```
# HELP battles_total
# TYPE battles_total counter
battles_total 5.0
```

Prometheus monitors itself using the same method, so we can see the Prometheus metrics too at `http://<Target IP>:9090/metrics`:

```
# HELP go_gc_duration_seconds A summary of the pause duration of garbage collection cycles.
# TYPE go_gc_duration_seconds summary
go_gc_duration_seconds{quantile="0"} 3.5e-05
go_gc_duration_seconds{quantile="0.25"} 7.8507e-05
go_gc_duration_seconds{quantile="0.5"} 9.9292e-05
go_gc_duration_seconds{quantile="0.75"} 0.000132907
go_gc_duration_seconds{quantile="1"} 0.000325268
go_gc_duration_seconds_sum 0.018079852
go_gc_duration_seconds_count 164
# HELP go_goroutines Number of goroutines that currently exist.
# TYPE go_goroutines gauge
go_goroutines 47
# HELP go_threads Number of OS threads created.
# TYPE go_threads gauge
go_threads 18
# HELP go_info Information about the Go environment.
# TYPE go_info gauge
go_info{version="go1.17.5"} 1
# ...
# HELP net_conntrack_dialer_conn_attempted_total Total number of connections attempted by the given dialer a given name.
# TYPE net_conntrack_dialer_conn_attempted_total counter
net_conntrack_dialer_conn_attempted_total{dialer_name="alertmanager"} 0
net_conntrack_dialer_conn_attempted_total{dialer_name="animal"} 42
net_conntrack_dialer_conn_attempted_total{dialer_name="default"} 0
net_conntrack_dialer_conn_attempted_total{dialer_name="feline"} 41
net_conntrack_dialer_conn_attempted_total{dialer_name="fish"} 41
net_conntrack_dialer_conn_attempted_total{dialer_name="mammal"} 42
net_conntrack_dialer_conn_attempted_total{dialer_name="mustelid"} 42
net_conntrack_dialer_conn_attempted_total{dialer_name="prometheus"} 2
```

The first group of metrics are the Go runtime metrics, including GC metrics and goroutine counts. As you can see, Prometheus is written in Go. The Go language supports goroutines, which are lightweight threads managed by the Go runtime. These are very similar to the Java concept of virtual threads, which we will discuss in Chapter 14.

This is an example of an important design rule that Prometheus shows. The systems that support and send observability signals should themselves be observable and well-designed for observability.

The basic Prometheus UI can be found at `http://<Target IP>:9090/graph` and is shown in Figure 11-3.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//706780f6-6115-4489-aa04-97b30110dc12/markdown_2/imgs/img_in_image_box_144_326_863_746.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A33Z%2F-1%2F%2F4132ef330357e7294c5b6958c26156d0505f308110d164eeb739586812b63d3b" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 11-3. Prometheus query UI</div> </div>

Our query string here is `process_cpu_usage{job="animal"}[6h]`. This is a PromQL query that asks for all the data points showing the CPU usage of the animal job over the last six hours. This is called a **range vector** because it returns a series of data over a range of time.

Note that the UI shows this in the Table view in this format: `<value> @ <time stamp>`. If we switch to the graph view, we must change the query because graphing requires an expression that is an **instant vector**.

The data for the query `process_cpu_usage{job="m.*"}` is shown as a graph in Figure 11-4. This query returns the CPU metric for jobs that start with the letter m (in our case, mammal and mustelid). This uses the Prometheus regular expression support, `=~`, which is very useful for choosing metrics.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//706780f6-6115-4489-aa04-97b30110dc12/markdown_3/imgs/img_in_chart_box_149_112_860_503.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A34Z%2F-1%2F%2F25ccbb1a145c1ed0085f02ef91e7a8f9dff81cb226dd52243402a554e32f4c14" alt="Image" width="70%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 11-4. Prometheus graphs</div> </div>

A full discussion of PromQL is outside the scope of this book. You should read the Prometheus documentation for serious work, as well as the documentation for extra components like Grafana.

Instead, let's move on to discuss the third, and probably most important, of our observability technologies: OpenTelemetry.

---

## Introducing OpenTelemetry

In this section, we will introduce **OpenTelemetry** (also called **OTel**), a new open standard from the CNCF for observability data. We mentioned OTel in Chapter 8. The project was created by merging the OpenTracing (tracing) and OpenCensus (metrics) projects. It is now an open standard that is quickly growing and being used by many.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//706780f6-6115-4489-aa04-97b30110dc12/markdown_3/imgs/img_in_image_box_176_933_253_1034.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A34Z%2F-1%2F%2F013e7c99985c0672ed4f13a3c681d7fb3d0fad94ad9675e3cae6eb9943d6a73f" alt="Image" width="7%" /></div>

> [!WARNING]
> OpenTracing and OpenCensus are now deprecated, and you should do all new work using OpenTelemetry.

This growth is even more impressive when you consider that the project is only a few years old. It reached its 1.0 release in 2023. The project is now stable and ready for live production use. Many companies and teams have already started using it, and this trend is likely to continue.

You can use OTel in many different situations. However, it is most useful in cloud-deployed, microservice-based applications, and it is generally suitable for multi-language, distributed systems. $^{1}$

### What Is OpenTelemetry?

One of the main strengths of OTel is that it does not try to solve every problem. Instead, it focuses on its main area. OTel is not a data collection system or an observability backend. Therefore, it is only one part of a complete observability system.

As we mentioned briefly in Chapter 10, OTel focuses on adding instrumentation to applications and sending data to a separate, outside observability system.

The main project areas of OpenTelemetry are shown in Figure 11-5.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//706780f6-6115-4489-aa04-97b30110dc12/markdown_4/imgs/img_in_image_box_142_432_864_736.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A36Z%2F-1%2F%2Fab91a041db2b5ad3e971cd46590ce26020b8bde4ecf22c90b175c0ea99108c1d" alt="Image" width="71%" /></div>

* **Specification**: Explains the requirements and expectations for all languages.
* **Instrumentation**: Makes every library and application observable out of the box.
* **Collector**: A vendor-neutral tool used to receive, process, and send (export) telemetry data.

<div style="text-align: center;"><div style="text-align: center;">Figure 11-5. Concerns of OpenTelemetry project</div> </div>

The specification defines formats and styles (conventions) for metrics, logs, and traces in a way that works for any language. It also defines a protocol for sending the data to the observability backend.

The different language versions provide a set of APIs and SDKs to add instrumentation to applications written in almost any common language. They also provide connections to a wide range of frameworks. The Java version also includes a Java agent to instrument applications without needing to change any code.

Finally, the **OpenTelemetry Collector** is a useful tool that can collect data from applications. It can send this data to many different backends, after processing and improving the data. You can think of it as a router or “switching station” that can also translate protocols for observability data.

These design choices let OTel support different ways to structure observability data. It is meant to be useful in many situations and does not force a single way of working.

At the software level, the parts used for instrumentation are shown in Figure 11-6.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//932103cb-368c-4559-9650-7ac96c89ac85/markdown_0/imgs/img_in_image_box_143_234_865_683.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A10%3A54Z%2F-1%2F%2Fbd8bedcfdcb5609f1f6095e923c62567105093ca9ed73c116724ba1f209eaaad" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 11-6. OpenTelemetry APIs and SDKs</div> </div>

The SDK is the main part of OpenTelemetry that users will work with. It has two main parts:
* Constructors used by application owners to set up their systems.
* Interfaces used by plug-in writers to write integrations.

This is the part that teams will use when setting up OpenTelemetry out of the box.

The API contains interfaces used by developers to write custom instrumentation for their apps and libraries.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//932103cb-368c-4559-9650-7ac96c89ac85/markdown_0/imgs/img_in_image_box_176_1007_253_1109.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A10%3A54Z%2F-1%2F%2F5241761884d3c10f3f952a671effc257c78bc6e46b93e36623aff6f464017fa1" alt="Image" width="7%" /></div>

> [Tip]
> If an engineer wants to help write code for the OpenTelemetry project, the best starting point is usually writing some new instrumentation for an open source library or framework that does not have OTel support yet.

OTel cares a lot about stability and backward compatibility. The code follows semantic versioning rules and gives, at least, long-term support for the stable versions of the API and SDK: $^{2}$
* **API**: Three-year support guarantee.
* **Plug-in interfaces**: One-year support guarantee.
* **Constructors**: One-year support guarantee.

For Java, there are four main projects under the GitHub `open-telemetry` group:
* `opentelemetry-java`: Core parts, including the API and SDK.
* `opentelemetry-java-instrumentation`: Library instrumentation and the auto-instrumentation agent.
* `opentelemetry-java-contrib`: Helpful and standalone libraries.
* `opentelemetry-java-examples`: Examples of manual instrumentation. $^{3}$

The Java version at first focused on traces and metrics, and logs reached version 1.0 in late 2023.

### Why Choose OTel?

In the past, the application performance monitoring (APM) market was controlled by commercial vendors. Like many other market areas, people wanted open source alternatives. This was to reduce vendor lock-in, cut costs, and give more flexibility.

We have already seen some of these open source projects, such as Jaeger for traces, Prometheus for metrics, and the ELK stack for logging.

A second market trend is more hidden but just as important: the growing complexity of software systems. As software continues to become more complex, and as more languages and frameworks become popular, it takes more work to write good instrumentation libraries.

For commercial observability products, this trend creates duplicate work and inefficiency because each separate company must maintain its own set of instrumentation libraries. This double effort means that, in the end, it makes more sense for observability vendors to work together on a single set of open source libraries instead of each keeping its own. The value that an observability vendor gives is then in the user experience, backend features, and cost, rather than the instrumentation code itself.

This shows a change from commercial to open source—at least for the code that runs inside the customer's application. In recent years, we have seen several commercial vendors switch to an open source model.

This can be seen as a way for APM vendors to call themselves observability providers. At the same time, a growing number of new observability companies (startups) have appeared, and they have always worked closely with the open source model.

The protocol and instrumentation stack that vendors are choosing to use is, of course, OpenTelemetry.

People have criticized the standard for being slow to change. However, the benefit of having stable, common naming rules and related semantic rules is huge. Because of this, it is no surprise that more and more companies and teams are starting to use OpenTelemetry.

### OTLP

A main part of the OpenTelemetry project is the **OpenTelemetry Protocol** (OTLP). OTLP does not try to define the whole protocol space. Instead, it focuses on its main concerns:
* Encoding
* Transport
* Delivery

Performance is a very important goal for OTLP. It is usually set up (implemented) using HTTP/2 or gRPC. gRPC is basically a remote procedure call (RPC) framework that uses the binary Protocol Buffers (protobuf) format over HTTP/2. $^{4}$ The main Java version can use either format, and defaults to HTTP/protobuf.

Before we start looking at the Java libraries that provide the SDK and APIs for OTel, we need to introduce a very important component—the OpenTelemetry Collector.

### The Collector

The OTel Collector is a network service that works with streams of observability data. It can receive, process, and send out (export) any or all of the three main types of observability data.

The simple design of the Collector is made to be easy to extend, and it is vendor-neutral. It is written in Go and is run by an open source team from several different companies. Despite the name, it also works with many different data formats, not just OTLP.

You configure the Collector using YAML, and it runs on `http://localhost:4317` by default. The main configuration sections for the Collector are:
* `receivers`: Data sources from which the Collector will get data.
* `processors`: Changes (transformations) that the Collector will apply to the data.
* `connectors`: Optional parts that change one type of telemetry data into another.
* `exporters`: Where to send the data after it is changed.
* `extensions`: Any optional parts (such as health-checking).

There is also a `service` section used to configure the pipelines of the Collector. It has separate sections for each observability signal we want to handle. For example, this service section shows a simple trace pipeline:

```yaml
service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [otlphttp]
```

The Collector will accept data from the `otlp` receiver, process it with the `batch` processor, and then send it to the `otlphttp` exporter. The data is grouped into batches before it is sent. Note that, just like Prometheus, the Collector creates telemetry data about itself in the `telemetry` section under `service`.

The main design rules of the Collector are:
* **Usability**: Good default settings so that it works out of the box.
* **Performance**: Works fast under different loads and configurations.
* **Observability**: A good example of a service that can be watched.
* **Extensibility**: You can customize it without changing the core code.
* **Unified**: A single codebase supports traces, metrics, and logs.

In Figure 11-7, we show a sample design that uses OpenTelemetry to handle both metrics and traces. We can see that here, the Collector acts as a middle layer (shim) between application processes (including short-lived ones) and data storage for metrics and traces.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//932103cb-368c-4559-9650-7ac96c89ac85/markdown_4/imgs/img_in_image_box_144_581_863_974.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A10%3A56Z%2F-1%2F%2F46c60f677afa3f7260cd516257f5f82f02eb5feeee1e19fac4ec87be4c403f34" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 11-7. OpenTelemetry example architecture</div> </div>

In this example, the Collector receives data from multiple processes and shows a single endpoint. For metrics, this keeps your design choices flexible. Prometheus either knows where the collectors are, or the collectors can be set up to use remote-write.

The Collector is a quite simple but very flexible part to configure and run. We will return to it after we introduce the Java libraries that send data to it.

---

## OpenTelemetry Tracing in Java

As we discussed before, OTel focuses on its main area: instrumentation and sending data out (exfiltration). These are low-level concerns. While OpenTelemetry does provide APIs for users, there are several ways to use OpenTelemetry. Some of these ways avoid linking your code directly to those APIs.

Also, OTel does not try to provide a single, combined API for all the different types of observability data in Java. Instead, where possible, it tries to work with Java parts that already exist and are widely used.

As we will see later, good patterns and high-level APIs already exist for logs, and the best practice is to use them. For traces, however, there is no existing tool of good enough quality. Therefore, OpenTelemetry provides two different solutions: manual or automatic tracing.

Before we look at these two ways, a quick word about the OpenTelemetry design. It is designed to be used in a live production system, so you must set up some configuration. This means a certain amount of extra complexity cannot be avoided.

The next section on manual tracing is longer than it should be. This is because it must introduce infrastructure parts (like the Collector) and changes to the POM file to bring in the needed OTel dependencies.

### Manual Tracing

As the name suggests, manual instrumentation requires the developer to add direct calls to the tracing library by hand. This means that while you can use it for tracing, in practice, anything more than a very simple example quickly becomes too complex to manage.

This is best shown with an example. Let's look at how we use manual tracing in Fighting Animals. In this section, we will look at code from the `manual_tracing` branch.

First, we must add direct dependencies on the OpenTelemetry libraries in our project. The needed changes to the POM file are quite large. The main part is adding the `<dependencyManagement>` section and using a BOM to manage the dependencies as a group:

```xml
<dependencyManagement>
    <dependencies>
        <dependency>
            <groupId>io.opentelemetry</groupId>
            <artifactId>opentelemetry-bom</artifactId>
            <version>1.40.0</version>
            <type>pom</type>
            <scope>import</scope>
        </dependency>
    </dependencies>
</dependencyManagement>
```

We can then pull in extra OTel dependencies as needed. We need the `opentelemetry-api`, `opentelemetry-sdk`, `opentelemetry-sdk-extension-autoconfigure`, and `opentelemetry-exporter-otlp` dependencies for this example.

We have also added an auto-configured OpenTelemetry bean in `AnimalApplication`, like this:

```java
@Bean
public OpenTelemetry openTelemetry() {
    return AutoConfiguredOpenTelemetrySdk.initialize().getOpenTelemetrySdk();
}
```

This `OpenTelemetry` object is now available to use in our code, by passing it into the constructor of the service controllers.

Now, let's look at the code changes needed to add tracing to the main HTTP path in the `AnimalController` class:

```java
@GetMapping("/battle")
public String makeBattle() throws IOException, InterruptedException {
    // Extract the propagated context from the request. In this case,
    // no context will be extracted from the request - this is the root span
    var extractedContext = extractContext(httpServletRequest, EXTRACTOR);

    try (var scope = extractedContext.makeCurrent()) {
        // Start a span
        var span = serverSpan("/battle", HttpMethod.GET.name(),
                     AnimalController.class.getName(), "animal-service:8080");

        // Send the two requests and return the response body as the response
        // and end the root span.
        try {
            var good = fetchRandomAnimal(span);
            var evil = fetchRandomAnimal(span);
            return String.format("""
            { "good": "%s", "evil": "%s" }
            """, good, evil);
        } finally {
            span.end();
        }
    }
}
```

This is only one service, of course. You must add very similar tracing code to every service to avoid gaps in our tracing coverage. For example, we need to change `MammalController` like this:

```java
@GetMapping("/getAnimal")
public String makeBattle() throws IOException, InterruptedException {
    // Context will be extracted from that propagated from the Animal Service.
    var extractedContext = extractContext(httpServletRequest, EXTRACTOR);

    try (var scope = extractedContext.makeCurrent()) {
        var span = serverSpan("/getAnimal", HttpMethod.GET.name(), MammalController.class.getName(), "mammal-service:8081");

        // Send the sub-request, return the response and end the span
        try {
            return fetchRandomAnimal(span);
        } finally {
            span.end();
        }
    }
}
```

Both of these controllers use the `serverSpan()` method, which is written in the `Misc` helper class in our application:

```java
public static Span serverSpan(Tracer tracer, String path, String method, String serviceName) {
    return tracer
        .spanBuilder(path)
        .setSpanKind(SpanKind.SERVER)
        .setAttribute(SemanticAttributes.HTTP_METHOD, method)
        .setAttribute(SemanticAttributes.HTTP_SCHEME, "http")
        .setAttribute(SemanticAttributes.HTTP_HOST, serviceName)
        .setAttribute(SemanticAttributes.HTTP_TARGET, path)
        .startSpan();
}
```

The `Tracer` object is like a logger, so it is best to set it up once in the constructor. Now that we have created spans, we need a place to send them. In our `docker-compose.yml` file, we have a Collector service set up to receive them and forward them to Jaeger:

```yaml
# Jaeger
# Local GRPC port (4317) needs to be remapped to appear as 14317
# to avoid a clash with the OTel collector's GRPC port
jaeger-all-in-one:
  image: jaegertracing/all-in-one:1.52.0
  ports:
    - "16686:16686"
    - "14317:4317" # OTLP gRPC receiver
    - "4318:4318" # OTLP HTTP receiver

# Collector
otel-collector:
  image: otel/opentelemetry-collector:0.91.0
  command: ["--config=/etc/otel-collector-config.yaml"]
  volumes:
    - ./otel-collector-config.yaml:/etc/otel-collector-config.yaml
  ports:
    - "13133:13133" # Health_check extension
    - "4317:4317" # OTLP gRPC receiver
    - "55681:55681" # OTLP HTTP receiver alternative port
  depends_on:
    - jaeger-all-in-one
```

> [!NOTE]
> As explained in “A Word About Version Numbers” (Chapter 8), we use exact version numbers to make sure the example works as it is. For real production use, you should update to a newer version of these parts before running them, because older images might have security bugs or other errors.

We also need to configure the Collector to send the spans to Jaeger, which we do in `otel-collector-config.yaml`:

```yaml
receivers:
  otlp:
    protocols:
      grpc:
      http:

exporters:
  otlphttp:
    endpoint: http://jaeger-all-in-one:4318

processors:
  batch:

extensions:
  health_check:

service:
  extensions: [health_check]
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [otlphttp]
```

These parts are basically infrastructure. They are not part of the application code, but are instead part of the observability systems. This also gives a useful point of separation. The operations team can change the configuration of the Collector without needing to change the application.

We also need to tell the microservices where to find the Collector, because it is now running in its own container. In our example, we do this using a Java command-line setting to set a system property: `-Dotel.exporter.otlp.endpoint=http://otel-collector:4317/`, which we put in the Dockerfile. You can also set this configuration using environment variables, like `OTEL_EXPORTER_OTLP_ENDPOINT`. You could also set these in the Dockerfile.

Just from the two controller classes we saw in this section, we can see that the amount of code needed to add tracing to our application is quite large. This is a good example of what we said in “Manual Versus Automatic Instrumentation” (Chapter 10): the complexity of manual tracing quickly becomes too hard for a programmer to manage.

The solution to this kind of boring, detailed complexity is the same as always: we make the computer do it instead.

### Automatic Tracing

This brings us to **automatic instrumentation**. For OpenTelemetry, this usually means running your application with an agent that works with any Java 8+ application. You can also attach the agent dynamically while the app is running, which might be better in some situations. Finally, some frameworks, like Quarkus, have built-in support. They do not need and should not use the agent.

> [!NOTE]
> As we discussed briefly in Chapter 3, a Java agent is a special JAR file that contains code to run before the `main` method is called. Building these agents is an advanced topic, and you should read specialist guides if you want to learn more.

The agent adds extra bytecode to get the timings of methods and other information needed to build a trace. Especially, this includes the trace ID and the span IDs, which are used to link the spans together into a trace. The system stores the spans in memory temporarily, and then the OpenTelemetry exporters send them to the backend.

> [!NOTE]
> Along with the instrumentation of core code and exporting done by the agent, the `opentelemetry-java-instrumentation` project has parts (modules) that support over 100 of the most popular libraries and frameworks out of the box.

The branch `auto_tracing_only` of Fighting Animals shows an example of automatic tracing in action. It includes a prebuilt agent JAR file in the repository. You must pass the path of this JAR file to the JVM as a command-line argument, which you can see in the Dockerfile.

One big advantage of automatic tracing is that it is much easier to use than manual tracing. It also keeps the project code free of direct compile-time dependencies on OTel. You can see this by looking at this branch: there are no direct dependencies on OTel in the POM file, and no direct code to create spans.

By default, the agent uses an OTLP exporter and points to `http://localhost:4317`, where it expects a local OpenTelemetry Collector to run.

However, on this branch, the Collector setup is exactly the same as for manual tracing, so we will not repeat it here. Just as we did for manual tracing, we must add a command-line setting to tell the application where to find the collector:

```
-Dotel.exporter.otlp.endpoint=http://otel-collector:4317/
```

Using automatic tracing is a good example of separating concerns. The application code does not care about the details or even the existence of tracing. The tracing feature is provided entirely by the Java agent and some infrastructure settings.

Before we move on from the subject of distributed tracing, there's one practical aspect that we still need to discuss—sampling.

### Sampling Traces

In “Interpretation of Statistics” (Chapter 2), we saw the “hat/elephant” problem, which is a funny name for a very real problem: not all response types contain the same amount of useful information. For example, unless there are clear drops in response time, successful responses are not very interesting.

The same is true for traces. The vast majority of traces are successful, so they are not very interesting. On the other hand, traces that are slow or fail are much more interesting, and we want to be able to see them.

> All happy families are alike; each unhappy family is unhappy in its own way.
> 
> — Leo Tolstoy, *Anna Karenina*

One solution that the community uses is to change the rate of **sampling** for traces, depending on the response code and the number of transactions a service handles. In general, we always want to collect all errors (both 4xx and 5xx errors) and then sample a small percentage of successful traces. For very busy (high-volume) services, this can be as low as 1% of successful traces.

This works because, if we have a busy service, we will still get a large enough sample of successful traces. This means any performance drops (regressions) will still be visible in the sampled data.

---

## OpenTelemetry Metrics in Java

Let's look at OTel metrics. There is a manual API for handling metrics using the low-level OTel structures. We will see how this compares to Micrometer soon. But to be complete, let's look at a quick example from the `otel_metrics_raw_api` branch of Fighting Animals.

This branch has direct dependencies on OTel libraries, just like manual tracing. So, the POM changes are similar, and we also need `opentelemetry-sdk-metrics` to be available.

Note that we have also removed the `spring-boot-starter-actuator` dependency. This is needed to avoid conflicts with Spring Boot's built-in Micrometer. We also removed the bean that provides a `MeterRegistry`. Instead, we are using the `OpenTelemetry` bean, just as we did for manual tracing.

In the code, we are using the instruments from the OTel metrics API in the package `io.opentelemetry.api.metrics` to handle our metrics. Let's look at an example in the `AnimalController`, which uses a `LongCounter` and an `ObservableDoubleGauge`.

First, let's declare our fields (a copy of the `OpenTelemetry` bean and the metrics we want to use):

```java
public class AnimalController {
    // ...
    private final OpenTelemetry sdk;
    private final Meter appMeter;
    private final Meter memoryMeter;
    private final LongCounter battlesTotal;
    private final ObservableDoubleGauge cpuTotal;
}
```

Next, in the constructor, we save the `OpenTelemetry` bean in a field, and then use it to create the metrics we want to use:

```java
public AnimalController(OpenTelemetry sdk) {
    this.sdk = sdk;

    Meter appMeter = sdk.getMeter(INSTRUMENTATION_SCOPE + ".app");
    this.appMeter = appMeter;
    this.battlesTotal = createCounter(appMeter);

    Meter memoryMeter = sdk.getMeter(INSTRUMENTATION_SCOPE + ".memory");
    this.memoryMeter = memoryMeter;
    this.cpuTotal = createGauge(memoryMeter);
}
```

We create these two metrics using static methods:

```java
static LongCounter createCounter(Meter meter) {
    return meter
        .counterBuilder("battles.total")
        .setDescription("Counts total battles fought.")
        .build();
}

static ObservableDoubleGauge createGauge(Meter meter) {
    return meter
        .gaugeBuilder("jvm.memory.total")
        .setDescription("Reports JVM memory usage.")
        .setUnit("By")
        .buildWithCallback(
            result -> result.record(Runtime.getRuntime().totalMemory(), Attributes.empty())
        );
}
```

The counter is very similar to the Micrometer counter we saw before. When a new battle is fought, we simply increase it, like this: `battlesTotal.add(1)`.

However, the gauge is a little different.

As we can see, the method that actually creates the gauge (`buildWithCallback()`) takes a callback function. This function is used to record the value of the gauge. It is only called when the gauge is watched (observed). The order in which the system runs callbacks for different gauges is not guaranteed.

On this branch, we send metrics to the OTel Collector only from the `animal_service` because this reduces noise in the logs and makes a clearer example.

We only set up the debug exporter for the collector's metrics pipeline to avoid needing a metrics backend.

OTel metrics also support JVM-level metrics, and you can collect these from JMX. There is also support for JFR (Java Flight Recorder) integration.

You can use the OTel metrics API directly, but many teams prefer the ease and flexibility of using a facade like Micrometer. That is our next topic.

On the `micrometer_with_otel` branch, we show an example of using Micrometer with an OTel exporter. This branch depends on the `micrometer-registry-otlp` library, which provides an OTel exporter for Micrometer:

```xml
<dependency>
    <groupId>io.micrometer</groupId>
    <artifactId>micrometer-registry-otlp</artifactId>
    <scope>runtime</scope>
</dependency>
```

However, because the Micrometer libraries provide this, we do not need the OTel BOM. There is also no direct link to OTel in the POM file. In fact, the code for `AnimalController` on this branch is exactly the same as the code on the `micrometer_only` branch.

Note that we configure the Micrometer registry in `application.properties`:

```properties
management.otlp.metrics.export.url=http://otel-collector:4318/v1/metrics
management.otlp.metrics.export.step=10s
```

At the time of writing, this registry only supports compressed HTTP, not gRPC. Therefore, we must make sure the Collector is set up to accept OTLP over HTTP by adding this to the ports section of `docker-compose.yml`:

```yaml
- "4318:4318" # OTLP http receiver
```

This exposes the HTTP port as well as the gRPC port, which matches the setting in `application.properties`. The configuration shown so far is basic, but it gives a good starting point for metrics and traces. However, we have not said anything about how to send logs from the application into OTel. Let's discuss that next.

---

## OpenTelemetry Logs in Java

The development of log support in OpenTelemetry was done with the design idea that logs should follow the facade patterns that Java developers already know.

Therefore, we will handle logs differently from traces and metrics. For those, we showed the low-level "raw" OTel API before discussing other ways.

To be clear, OpenTelemetry does provide a “Logs Bridge” API, which lets logs go into the OTel pipeline. However, most teams should not use this method because it requires too many changes to existing habits and code. Instead, one of the following options is usually a much better fit for your needs:

* Write logs from your service to a file using a file-based appender, and have the OpenTelemetry Collector scrape this file. The Collector then forwards the logs to your logging backend using OTLP.
* Use an OTel instrumentation library to send (export) logs from your chosen logging framework to the Collector. This is usually done along with traces and metrics. $^{5}$

There are pros and cons to both ways. The first way seems to keep the system design independent, but in practice, it is not very flexible. The second way requires more work at the start, but it usually takes less effort to maintain over time.

In this section, we will focus on the second option. You should read the OTel logging documentation if you want to study the first design option.

Unlike agent-based tracing or Micrometer-based metrics, there is no SPI or facade API for logs that does not require a direct dependency on OTel.

We must add direct dependencies on the OTel libraries in our POM file. Just like for metrics, we need to make an OpenTelemetry bean available to connect (autowire). We will also need to set up the Collector to receive logs, but this is a small detail.

The template code looks like this:

```java
@ConditionalOnClass(LoggerContext.class)
@ConditionalOnProperty(name="otel.instrumentation.logback.enabled", matchIfMissing=true)
@Configuration
static class LogbackAppenderConfig {
    @Bean
    ApplicationListener<ApplicationReadyEvent> logbackOtelAppenderInitializer(openTelemetry openTelemetry) {
        return event -> OpenTelemetryAppender.install(openTelemetry);
    }
}
```

We need a very similar Collector configuration to the one before. You can find the details on the `logging_only` branch.

We are using the Logback appender, which we must include in the POM file:

```xml
<dependency>
    <groupId>io.opentelemetry.instrumentation</groupId>
    <artifactId>opentelemetry-logback-appender-1.0</artifactId>
    <version>2.0.0-alpha</version>
</dependency>
```

and we configure it in `logback.xml` like this:

```xml
<appender name="OpenTelemetry" class="io.opentelemetry.instrumentation.logback.appender.v1_0.OpenTelemetryAppender">
    <captureExperimentalAttributes>true</captureExperimentalAttributes>
    <captureValuePairAttributes>true</captureValuePairAttributes>
</appender>
```

and we include a line in `application.properties`:

```properties
otel.instrumentation.logback.enabled=true
```

to turn on the conditional beans in the `AnimalApplication` class.

With this setup, developers can continue to use SLF4J and Logback as normal. The logs are sent to the OTel Collector, which forwards them to the logging backend.

When we bring together the different ways to handle traces, metrics, and logs, we can see that the recommended set of tools (stack) for Java applications might look like:
* OTel agent for traces and JVM metrics.
* Micrometer with OTLP registry for application metrics.
* SLF4J with Logback OTLP logging appender for logs.

The path for each of these signals could be:
* **Traces**: Java agent → OTLP Exporter → OTel Collector → Jaeger
* **Metrics**: Micrometer → OTLP Exporter → OTel Collector → Prometheus
* **Logs**: SLF4J/Logback → OTLP Exporter → OTel Collector → Loki

Using a local OTel Collector—usually one per cluster—gives a useful point of separation. This makes changing the design much easier, and it also shields developers from the details of how the observability system is built.

Of course, this is not the only design choice. There are many different combinations of parts you can use to build an observability system. For example, OTel tracing can be manual or automatic. Prometheus can be set up to scrape from the OTel Collector, or it can receive data directly via remote-write from the Collector.

In the end, it is about understanding the complete design of the system as a whole, both now and how it might grow in the future. From this starting point, the team can make design and setup choices that work well for their specific needs.

---

## Summary

In this chapter, we have taken a deep look at the practical details of setting up observability in Java cloud applications.

We have introduced some of the most important technologies in this field (Micrometer, Prometheus, and OpenTelemetry) and shown how you can use them together to build a complete open source observability system. We have also discussed some of the design rules that guide decisions about setting up observability systems for Java applications.

Where possible, we have tried to show ways that do not change how the development team already works. For example, we used the OpenTelemetry agent to provide automatic tracing, and the Micrometer registry for OTel to provide metrics.

This chapter also included a look at parts like the OpenTelemetry Collector and using the OTLP protocol to send observability data.

One important topic we left out of this chapter is application profiling. This is a very important subject, but it is also a very large one, and it does not fit easily into the observability framework we just introduced. In fact, it deserves a separate chapter of its own, and that is where we will look next.

---

$^{1}$ OpenTelemetry provides APIs and SDKs for C++, .NET, Go, Java, JavaScript, Python, Rust, Swift, and other languages.
$^{2}$ This stability model is designed to reassure enterprise users who want to avoid frequent breaking changes.
$^{3}$ The repositories are under the `open-telemetry` group on GitHub.
$^{4}$ Protocol Buffers is a binary serialization format developed by Google.
$^{5}$ This approach is often called "log appender instrumentation" or "direct export."
