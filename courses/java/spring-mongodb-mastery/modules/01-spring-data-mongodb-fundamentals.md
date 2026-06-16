# Module 01: Spring Data MongoDB Fundamentals

Welcome class. Today we analyze the core configuration architectures of **Spring Data MongoDB (CS-530)**.

When building enterprise applications on top of a document database, you must map Java domain objects (POJOs) to BSON documents. Today we study object conversion, Spring Data mapping annotations, custom type converters, auditing, and class metadata optimizations.

---

## 1. Academic Lecture: Object Serialization & Auditing

### Basic Level: Object Mapping Abstraction
When saving a Java object (like a `Customer` class instance) to MongoDB, you do not write raw database commands. Instead, Spring Data MongoDB intercepts your call, serializes your Java object into a BSON document, and sends it to the database. This process is called Object-Document Mapping (ODM).

### Intermediate Level: Mapping Annotations & Custom Converters
We configure mappings using declarative Spring Data annotations:
*   `@Document(collection = "customers")`: Marks the class as a persistent database collection record.
*   `@Id`: Specifies the primary key field. Can map to standard Strings or ObjectIds.
*   `@Field("first_name")`: Maps a Java variable to a custom BSON key on disk.
*   **Custom Converters**: Spring Data MongoDB doesn't store native Java `ZonedDateTime` timezone information (BSON dates are only UTC milliseconds). We write custom writing (`Converter<ZonedDateTime, Document>`) and reading (`Converter<Document, ZonedDateTime>`) converters to store timezone metadata in the database.
*   **Auditing**: Annotations like `@CreatedDate` and `@LastModifiedDate` auto-populate timestamps during document conversion events.

### Advanced Level: `MappingMongoConverter` Context & `_class` Field Optimization
*   **The Converter Engine**: Under the hood, Spring Data uses the `MappingMongoConverter` class. During startup, it scans target entities and populates the `MappingContext` metadata cache. During persistence operations, it executes registered custom converters, transforms POJOs to BSON `Document` maps, and hands them to the MongoDB Java Driver.
*   **The `_class` Overhead**: By default, Spring Data appends a `_class` field containing the fully qualified class name to every BSON document (e.g. `"com.masterclass.mongodb.domain.Customer"`). This allows Spring to resolve class inheritance during reads. In collections holding millions of documents, this metadata wastes gigabytes of RAM cache and disk space.
*   **Aliasing & Disabling**: We can optimize storage by overriding the default type mapper in our config to use short aliases (`@TypeAlias("cust")`) or disabling the `_class` field entirely if polymorphism is not required.

```mermaid
graph TD
    A[Spring Application Layer] --> B[MongoRepository]
    A --> C[MongoTemplate]
    B -->|Generates Query| C
    C -->|Invokes Mapping Engine| D[MappingMongoConverter]
    D -->|Look up Type Mapping Context| E[MappingContext]
    D -->|Executes Custom Converters| F[Custom Converters Provider]
    D -->|Transforms POJO to Document| G[BSON org.bson.Document]
    G --> H[MongoDB Java Driver]
    H -->|Wire Protocol| I[(MongoDB Replica Set)]
```

---

## 2. Theory vs. Production Trade-offs

Compare data mapping options:

| Mapping Configuration | Storage Overhead | Polymorphic Reads Support | Query Latency | Implementation Complexity |
| :--- | :--- | :--- | :--- | :--- |
| **Default `_class` Tracking** | High (Stores full package class path) | Fully Supported (Subclasses resolved automatically) | Low | Low (Default configuration) |
| **Class Aliases (`@TypeAlias`)** | Low (Stores short string value) | Fully Supported | Low | Moderate |
| **Disabled Type Mapping** | Zero (No `_class` metadata) | Not Supported (Casts all reads to base class) | Low | High (Requires custom mapping beans) |

---

## 3. How to Use: Configuring Custom Converters in Spring

Let us configure Spring Data. We contrast a default, un-optimized config (saving class metadata) with a hardened configuration that registers custom converters and disables the `_class` field.

### A. The Default Un-optimized Configuration (Anti-Pattern)
Avoid leaving default settings active in high-scale collections:

```java
// DANGER: Storing the default class path in every document wastes storage:
// { "_id": "1", "name": "Alice", "_class": "com.masterclass.mongodb.domain.Customer" }
@Configuration
public class DefaultMongoConfig {
    // No custom converters or type mapping optimizations defined
}
```

### B. The Production-Grade Custom Converter Configuration (Production Pattern)
Create custom converters and override the default type mapping settings inside a configuration bean:

```java
import org.bson.Document;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.data.convert.ReadingConverter;
import org.springframework.data.convert.WritingConverter;
import org.springframework.core.convert.converter.Converter;
import org.springframework.data.mongodb.config.EnableMongoAuditing;
import org.springframework.data.mongodb.core.convert.DefaultDbRefResolver;
import org.springframework.data.mongodb.core.convert.DefaultMongoTypeMapper;
import org.springframework.data.mongodb.core.convert.MappingMongoConverter;
import org.springframework.data.mongodb.core.convert.MongoCustomConversions;
import org.springframework.data.mongodb.core.mapping.MongoMappingContext;
import org.springframework.data.mongodb.MongoDatabaseFactory;
import java.time.ZonedDateTime;
import java.time.ZoneId;
import java.util.Date;
import java.util.List;

@Configuration
@EnableMongoAuditing
public class MongoConfig {

    private final MongoDatabaseFactory mongoDbFactory;

    public MongoConfig(MongoDatabaseFactory mongoDbFactory) {
        this.mongoDbFactory = mongoDbFactory;
    }

    @Bean
    public MongoCustomConversions customConversions() {
        return new MongoCustomConversions(List.of(
            new ZonedDateTimeWriteConverter(),
            new ZonedDateTimeReadConverter()
        ));
    }

    @Bean
    public MappingMongoConverter mappingMongoConverter(MongoMappingContext context, MongoCustomConversions conversions) {
        var resolver = new DefaultDbRefResolver(mongoDbFactory);
        var converter = new MappingMongoConverter(resolver, context);
        converter.setCustomConversions(conversions);
        
        // Remove "_class" metadata from documents to optimize storage
        converter.setTypeMapper(new DefaultMongoTypeMapper(null));
        return converter;
    }

    @WritingConverter
    public static class ZonedDateTimeWriteConverter implements Converter<ZonedDateTime, Document> {
        @Override
        public Document convert(ZonedDateTime source) {
            return new Document()
                    .append("date", Date.from(source.toInstant()))
                    .append("zone", source.getZone().getId());
        }
    }

    @ReadingConverter
    public static class ZonedDateTimeReadConverter implements Converter<Document, ZonedDateTime> {
        @Override
        public ZonedDateTime convert(Document source) {
            Date date = source.getDate("date");
            String zone = source.getString("zone");
            return ZonedDateTime.ofInstant(date.toInstant(), ZoneId.of(zone));
        }
    }
}
```

### Line-by-Line Code Explanation:
1.  `@EnableMongoAuditing`: Enables Spring Data's auditing lifecycle interceptors.
2.  `MongoCustomConversions(...)`: Registers the custom converters with the Spring converter registry.
3.  `converter.setTypeMapper(new DefaultMongoTypeMapper(null))`: Overrides the default type mapper, telling the converter engine to omit the `_class` field during serialization.
4.  `ZonedDateTimeWriteConverter`: Extracts the UTC date instant and timezone string, storing them inside a nested document.

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Non-Blocking Context Violations in Auditing
*   **Why it fails**: When using Reactive Spring Data, auditing requires fetching the user context asynchronously (e.g. from reactive Spring Security). If you implement auditing using blocking operations (like querying a database on the main thread), you block the Netty event loop, crashing application throughput.
*   **Mitigation**: Use `ReactiveAuditorAware` to retrieve the current auditor asynchronously via Reactor `Mono` publishers.

---

## 5. Socratic Review Questions

### Question 1
Why does Spring Data MongoDB require custom converter classes to handle timezone-aware date objects?

#### Answer
The standard BSON date specification maps dates to UTC Unix milliseconds since the epoch, which does not store timezone offsets. If you insert a Java `ZonedDateTime` directly, the driver discards the timezone metadata and stores only the UTC time. When read back, the timezone defaults to the server's local zone. Writing custom converters to store dates as nested documents (holding the timestamp and the timezone ID) preserves the timezone offset.

---

## 6. Hands-on Challenge: Custom Document Converter

### The Challenge
In this challenge, you will implement a custom Spring Data Converter to handle a value object.
Your task:
1. Complete `MoneyWriteConverter` and `MoneyReadConverter` classes.
2. `Money` is a value object holding `amount` (BigDecimal) and `currency` (String).
3. The write converter must serialize `Money` to a string formatted as `"currency:amount"` (e.g., `"USD:19.99"`).
4. The read converter must parse the database string back into a `Money` instance.

Complete the implementation stub:

```java
package com.masterclass.mongodb.miniproject.converter;

import org.springframework.core.convert.converter.Converter;
import java.math.BigDecimal;

public class MoneyConverters {

    public static class Money {
        private final BigDecimal amount;
        private final String currency;
        
        public Money(BigDecimal amount, String currency) {
            this.amount = amount;
            this.currency = currency;
        }
        public BigDecimal getAmount() { return amount; }
        public String getCurrency() { return currency; }
    }

    public static class MoneyWriteConverter implements Converter<Money, String> {
        @Override
        public String convert(Money source) {
            // TODO: Serialize to currency:amount
            return null;
        }
    }

    public static class MoneyReadConverter implements Converter<String, Money> {
        @Override
        public Money convert(String source) {
            // TODO: Parse back to Money object
            return null;
        }
    }
}
```

### Verification Test
Verify your code with this JUnit 5 test class:

```java
package com.masterclass.mongodb.miniproject.converter;

import org.junit.jupiter.api.Test;
import java.math.BigDecimal;
import static org.junit.jupiter.api.Assertions.*;

class MoneyConvertersTest {

    @Test
    void testWriteAndReadConverters() {
        var money = new MoneyConverters.Money(new BigDecimal("99.95"), "USD");
        var writer = new MoneyConverters.MoneyWriteConverter();
        var reader = new MoneyConverters.MoneyReadConverter();

        String serialized = writer.convert(money);
        assertEquals("USD:99.95", serialized);

        var deserialized = reader.convert(serialized);
        assertNotNull(deserialized);
        assertEquals(new BigDecimal("99.95"), deserialized.getAmount());
        assertEquals("USD", deserialized.getCurrency());
    }
}
```
