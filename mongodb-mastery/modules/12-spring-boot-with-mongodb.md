# Module 12: Spring Boot with MongoDB

## 1. What Problem This Module Solves
Integrating Spring Boot applications with MongoDB requires a deep understanding of Spring Data mapping conventions, connection pooling, transactional state management, and repository design patterns. 

A senior engineer must understand the internal mechanics of Spring Data's `MappingContext`, custom converters, MongoTemplate query abstractions, entity lifecycle callbacks, and transaction configurations. Failing to configure these components correctly can lead to memory leaks in connection pools, incorrect BSON serialization, transaction rollbacks that fail silently, and inefficient database queries.

---

## 2. Why This Topic Matters
Spring Data MongoDB provides abstractions that simplify database operations. However, using these abstractions blindly can introduce performance bottlenecks. For example, relying on automatic schema mapping for complex, deeply nested entities can cause high serialization overhead. 

Furthermore, configuring Spring's declarative transaction management (`@Transactional`) without establishing a `MongoTransactionManager` bean renders transactions inactive, leaving your application vulnerable to partial writes. This module provides the technical details required to build secure, high-performance integration layers between Spring Boot applications and MongoDB.

---

## 3. Core Concepts & Internals

### 3.1 Spring Data Mapping & Template Internals
Spring Data MongoDB maps Java domain objects to BSON documents.

```
  [Java Entity Object]
          │
          ▼
   [MappingContext] ── (Analyzes metadata: @Id, @Document, @Field)
          │
          ▼
 [Custom Converter Registry] ── (Translates custom Java types to BSON)
          │
          ├──────────────────────────┐
          ▼ (Via MongoTemplate)      ▼ (Via MongoRepository)
 [Low-Level BSON Document]   [Standard CRUD Abstractions]
          │                          │
          └────────────┬─────────────┘
                       ▼
               [WiredTiger Engine]
```

#### Mapping Components:
*   **`MappingContext`**: Stores metadata about mapped entities (e.g. key names, index rules, field mappings). This metadata is analyzed during application startup, reducing runtime reflection overhead.
*   **`MongoTemplate`**: The core gateway for interacting with MongoDB in Spring. It provides low-level query, update, and aggregation builders, offering fine-grained control over execution options.
*   **`MongoRepository`**: Extends CRUD abstractions, generating query implementations dynamically from method signatures (e.g. `findByEmailAndStatus`).

---

### 3.2 Entity Lifecycle Callbacks & Events
Spring Data MongoDB triggers events before and after database operations, allowing you to run custom hooks (like auditing or ID generation).

#### Standard Lifecycle Callbacks:
1.  **`BeforeConvertCallback`**: Triggered before an entity is mapped to a BSON document. This is useful for generating custom unique IDs.
2.  **`BeforeSaveCallback`**: Triggered after mapping to BSON, but before the document is written to the database. This is the preferred place to update auditing fields (like `lastModifiedDate`).
3.  **`AfterSaveCallback`**: Triggered after the document is written to the database.
4.  **`AfterLoadCallback`**: Triggered after a document is fetched from the database, but before it is mapped to a Java entity.

---

### 3.3 Transaction Propagation & Session Coordination
Declarative transaction coordination in Spring Boot uses Spring's AOP (Aspect-Oriented Programming) wrappers around MongoDB driver sessions.

#### How `@Transactional` Works Under the Hood:
1.  **Session Checkout**: When a method annotated with `@Transactional` is invoked, the `MongoTransactionManager` checks out a client session (`ClientSession`) from the connection factory.
2.  **Thread Binding**: The session is bound to the current execution thread using a `ThreadLocal` storage context.
3.  **Command Interception**: Any operations executed via `MongoTemplate` or `MongoRepository` check for a thread-bound session. If found, the driver executes the operation using that session ID, routing all writes to the primary node within the transaction.
4.  **Commit/Abort**:
    *   If the method completes successfully, the transaction manager commits the transaction and releases the session.
    *   If a runtime exception is thrown, the transaction manager aborts the transaction, rolling back all uncommitted writes.

---

### 3.4 Custom BSON Converter Registrations
Spring Data allows registering custom converters to translate complex Java objects (like custom value objects or binary formats) to BSON-compatible data types.

#### Write Converter (Java to BSON):
Maps custom data types to BSON representations.

#### Read Converter (BSON to Java):
Maps BSON types back to Java domain objects.

---

## 4. Practical Examples

### Comprehensive Spring Boot Project Code Listings (Multi-class)
This section provides a complete, production-ready implementation of a product sales tracking service, using custom repository interfaces, Custom Converters, and unit testing hooks.

#### 1. Custom Converter: `ZonedDateTimeConverter.java`
```java
package com.ecommerce.common.convert;

import org.springframework.core.convert.converter.Converter;
import org.springframework.data.convert.ReadingConverter;
import org.springframework.data.convert.WritingConverter;
import java.time.ZoneId;
import java.time.ZonedDateTime;
import java.util.Date;

public class ZonedDateTimeConverter {

    @WritingConverter
    public enum ZonedDateTimeToWriteConverter implements Converter<ZonedDateTime, Date> {
        INSTANCE;
        @Override
        public Date convert(ZonedDateTime source) {
            return Date.from(source.toInstant());
        }
    }

    @ReadingConverter
    public enum ZonedDateTimeToReadConverter implements Converter<Date, ZonedDateTime> {
        INSTANCE;
        @Override
        public ZonedDateTime convert(Date source) {
            return ZonedDateTime.ofInstant(source.toInstant(), ZoneId.of("UTC"));
        }
    }
}
```

---

#### 2. Configuration: `MongoConfig.java`
```java
package com.ecommerce.common.config;

import com.ecommerce.common.convert.ZonedDateTimeConverter.ZonedDateTimeToReadConverter;
import com.ecommerce.common.convert.ZonedDateTimeConverter.ZonedDateTimeToWriteConverter;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.data.mongodb.MongoDatabaseFactory;
import org.springframework.data.mongodb.MongoTransactionManager;
import org.springframework.data.mongodb.core.convert.MongoCustomConversions;
import java.util.ArrayList;
import java.util.List;

@Configuration
public class MongoConfig {

    @Bean
    public MongoTransactionManager transactionManager(MongoDatabaseFactory dbFactory) {
        return new MongoTransactionManager(dbFactory);
    }

    @Bean
    public MongoCustomConversions customConversions() {
        List<Object> converters = new ArrayList<>();
        converters.add(ZonedDateTimeToWriteConverter.INSTANCE);
        converters.add(ZonedDateTimeToReadConverter.INSTANCE);
        return new MongoCustomConversions(converters);
    }
}
```

---

#### 3. Configuration: `application.yml`
```yaml
spring:
  data:
    mongodb:
      uri: mongodb://mongo-primary:27017,mongo-secondary1:27017/shop_db?replicaSet=rs0
      write-concern: majority
      read-concern: majority
      auto-index-creation: true # Disable in production, manage index builds via CI/CD
  task:
    execution:
      pool:
        core-size: 10
        max-size: 50

logging:
  level:
    org.springframework.data.mongodb.core.MongoTemplate: DEBUG # Log database queries
```

---

#### 4. Domain Entity Class: `ProductOrder.java`
```java
package com.ecommerce.domain.order;

import org.springframework.data.annotation.Id;
import org.springframework.data.annotation.Version;
import org.springframework.data.mongodb.core.index.Indexed;
import org.springframework.data.mongodb.core.mapping.Document;
import org.springframework.data.mongodb.core.mapping.Field;
import java.time.ZonedDateTime;

@Document(collection = "product_orders")
public class ProductOrder {

    @Id
    private String id;

    @Indexed(unique = true)
    @Field("order_reference")
    private String orderReference;

    @Field("product_id")
    private String productId;

    @Field("amount")
    private double amount;

    @Field("status")
    private String status;

    @Version
    private Long version; // Optimistic Concurrency Lock version

    @Field("created_at")
    private ZonedDateTime createdAt;

    // Getters and Setters
    public String getId() { return id; }
    public void setId(String id) { this.id = id; }
    public String getOrderReference() { return orderReference; }
    public void setOrderReference(String ref) { this.orderReference = ref; }
    public String getProductId() { return productId; }
    public void setProductId(String pid) { this.productId = pid; }
    public double getAmount() { return amount; }
    public void setAmount(double amount) { this.amount = amount; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    public Long getVersion() { return version; }
    public ZonedDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(ZonedDateTime createdAt) { this.createdAt = createdAt; }
}
```

---

#### 5. Custom Repository Interface: `CustomOrderRepository.java`
```java
package com.ecommerce.domain.order;

import java.util.Map;

public interface CustomOrderRepository {
    Map<String, Double> calculateSalesTotals();
}
```

---

#### 6. Custom Repository Implementation: `CustomOrderRepositoryImpl.java`
```java
package com.ecommerce.domain.order;

import org.springframework.data.mongodb.core.MongoTemplate;
import org.springframework.data.mongodb.core.aggregation.Aggregation;
import org.springframework.data.mongodb.core.aggregation.AggregationResults;
import org.springframework.data.mongodb.core.query.Criteria;
import java.util.HashMap;
import java.util.Map;

public class CustomOrderRepositoryImpl implements CustomOrderRepository {

    private final MongoTemplate mongoTemplate;

    public CustomOrderRepositoryImpl(MongoTemplate mongoTemplate) {
        this.mongoTemplate = mongoTemplate;
    }

    @Override
    public Map<String, Double> calculateSalesTotals() {
        Aggregation aggregation = Aggregation.newAggregation(
            Aggregation.match(Criteria.where("status").is("COMPLETED")),
            Aggregation.group("productId").sum("amount").as("totalSales")
        );

        AggregationResults<SalesResult> results = mongoTemplate.aggregate(
            aggregation, "product_orders", SalesResult.class
        );

        Map<String, Double> totals = new HashMap<>();
        for (SalesResult result : results.getMappedResults()) {
            totals.put(result.getId(), result.getTotalSales());
        }
        return totals;
    }

    public static class SalesResult {
        private String id;
        private double totalSales;

        public String getId() { return id; }
        public void setId(String id) { this.id = id; }
        public double getTotalSales() { return totalSales; }
        public void setTotalSales(double totalSales) { this.totalSales = totalSales; }
    }
}
```

---

#### 7. Jpa-style Mongo Repository: `OrderRepository.java`
```java
package com.ecommerce.domain.order;

import org.springframework.data.mongodb.repository.MongoRepository;
import org.springframework.stereotype.Repository;
import java.util.List;

@Repository
public interface OrderRepository extends MongoRepository<ProductOrder, String>, CustomOrderRepository {
    List<ProductOrder> findByStatus(String status);
}
```

---

#### 8. Service Layer with Transaction Annotation: `OrderService.java`
```java
package com.ecommerce.domain.order;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import java.time.ZonedDateTime;
import java.util.Map;
import java.util.UUID;

@Service
public class OrderService {

    private final OrderRepository orderRepository;

    public OrderService(OrderRepository orderRepository) {
        this.orderRepository = orderRepository;
    }

    @Transactional // Enforces multi-document transaction boundary
    public ProductOrder createOrder(String productId, double amount) {
        ProductOrder order = new ProductOrder();
        order.setOrderReference(UUID.randomUUID().toString());
        order.setProductId(productId);
        order.setAmount(amount);
        order.setStatus("PENDING");
        order.setCreatedAt(ZonedDateTime.now());

        return orderRepository.save(order);
    }

    public Map<String, Double> getSalesAnalytics() {
        return orderRepository.calculateSalesTotals();
    }
}
```

---

#### 9. Rest Controller Interface: `OrderController.java`
```java
package com.ecommerce.domain.order;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import java.util.Map;

@RestController
@RequestMapping("/api/orders")
public class OrderController {

    private final OrderService orderService;

    public OrderController(OrderService orderService) {
        this.orderService = orderService;
    }

    @PostMapping
    public ResponseEntity<ProductOrder> placeOrder(
            @RequestParam String productId,
            @RequestParam double amount) {
        ProductOrder order = orderService.createOrder(productId, amount);
        return ResponseEntity.ok(order);
    }

    @GetMapping("/analytics")
    public ResponseEntity<Map<String, Double>> getAnalytics() {
        Map<String, Double> stats = orderService.getSalesAnalytics();
        return ResponseEntity.ok(stats);
    }
}
```

---

#### 10. Entity Lifecycle Auditor: `BeforeSaveAuditor.java`
```java
package com.ecommerce.domain.order;

import org.springframework.data.mongodb.core.mapping.event.BeforeSaveCallback;
import org.springframework.stereotype.Component;
import org.bson.Document;
import java.time.Instant;

@Component
public class BeforeSaveAuditor implements BeforeSaveCallback<ProductOrder> {

    @Override
    public ProductOrder onBeforeSave(ProductOrder entity, Document document, String collection) {
        document.put("updated_at", Instant.now());
        return entity;
    }
}
```

---

## 5. Trade-offs & Alternatives

Choosing a Spring Data MongoDB architectural pattern requires aligning abstraction levels and customization:

| Approach | Performance | Implementation Complexity | Query Flexibility | Primary Use Case |
| :--- | :--- | :--- | :--- | :--- |
| **`MongoRepository`** (DSL Methods) | **High**: Queries are generated at startup, minimizing overhead. | **Low**: No manual implementation required. | **Low**: Restricted to method signature structures. | Simple CRUD operations, simple filters. |
| **`MongoTemplate`** | **High**: Bypasses repository abstractions, compiling queries directly. | **Medium**: Requires writing query and criteria builders. | **High**: Supports complex criteria, limits, and projection configurations. | Dynamic searches, bulk write tasks. |
| **Custom Repository Implementation** | **High**: Combines repository abstractions and template flexibility. | **High**: Requires writing custom interfaces and implementation classes. | **Maximum** | Aggregation pipelines, complex calculations. |

---

## 6. Common Mistakes & Anti-patterns
*   **Executing `@Transactional` without a Transaction Manager Bean**: Declaring `@Transactional` annotations on service methods without configuring a `MongoTransactionManager` bean. Spring will execute operations outside of transaction sessions silently, losing consistency guarantees.
*   **Neglecting Index Auditing**: Setting `spring.data.mongodb.auto-index-creation` to `true` in production configurations. If a new application instance starts, it may run index builds in the foreground, locking collections and causing latency spikes. Set it to `false` and manage index builds via CI/CD pipelines.
*   **Overusing Object Mappings for Aggregations**: Mapping raw BSON aggregation outputs to complex Java objects when only a few fields are needed. This increases memory allocation overhead. Use projection classes (like `SalesResult`) to map only required fields.

---

## 7. Hands-on Exercises
1.  Deploy a Spring Boot application using the configuration in Section 4.
2.  Enable logging for MongoTemplate and observe the BSON queries generated in console logs during database operations.
3.  Write a test case to verify that modifying the same document concurrently triggers an `OptimisticLockingFailureException` (due to `@Version` field checks).
4.  Implement a lifecycle callback to audit user changes and verify that fields are updated in BSON before being written to disk.

---

## 8. Mini-Project: Transaction Propagation Test
**Scenario**: Verify Spring transaction propagation and rollback behavior.

1.  Write a Spring service method that inserts a document in a `product_orders` collection, then throws a runtime exception.
2.  Run the code without a transaction manager configured. Verify that the document remains in the database.
3.  Add the `MongoTransactionManager` bean, apply `@Transactional` to the service method, and verify that the write rolls back on exceptions, leaving no documents in the database.

---

## 9. Interview Questions

### Q1: How does Spring Data MongoDB implement optimistic concurrency control?
**Answer**: Spring Data uses the `@Version` annotation on entity fields to implement optimistic concurrency control. When saving an entity, Spring Data matches the document `_id` and the current `version` in its query filter: `{ _id: id, version: currentVersion }`. If the document version has changed (due to an update by another process), the query fails to match, and Spring throws an `OptimisticLockingFailureException`. The application must catch this exception and retry the update.

### Q2: What is the purpose of the `BeforeSaveCallback` interface, and how does it differ from `BeforeConvertCallback`?
**Answer**:
*   `BeforeConvertCallback` is triggered before the Java entity is converted into a BSON document. It is the preferred place to generate custom unique IDs.
*   `BeforeSaveCallback` is triggered after conversion to BSON, but before the document is written to the database. It is the preferred place to audit document fields directly by modifying the raw BSON document.

### Q3: Why is disabling automatic index creation recommended for production Spring Boot applications?
**Answer**: If automatic index creation is enabled, Spring Data attempts to build indexes declared in `@Document` entities during application startup. If a collection contains millions of records, building these indexes can consume substantial CPU and disk IOPS, locking the database and causing write timeouts. In production, index builds must be executed out-of-band using hybrid, non-blocking builders.

---

---

## 10. Production Runbook & Deployment Guidelines

### 1. Connection Pool Sizing in Spring Boot
Configure the connection pool properties inside `application.yml` dynamically:
```yaml
spring:
  data:
    mongodb:
      uri: mongodb://localhost:27017/shop_db?maxPoolSize=50&retryWrites=true
```

### 2. Monitoring Spring Transaction Execution
Enable transaction execution logs in Spring to debug rollback states:
```yaml
logging:
  level:
    org.springframework.transaction: DEBUG
    org.springframework.data.mongodb.core.MongoTemplate: DEBUG
```

## 11. Appendix: Advanced Troubleshooting & Operational Failure Modes

### 1. Spring Declarative Transaction Rollback Misalignment
*   **Failure Mode**: By default, Spring's `@Transactional` only rolls back on **unchecked exceptions** (`RuntimeException` and `Error`). If your service throws a checked exception (e.g., `IOException`), the database write commits, breaking transactional consistency.
*   **Resolution**: Explicitly declare rollback rules in the annotation definition:
    ```java
    @Transactional(rollbackFor = Exception.class) // Enforce rollbacks on checked exceptions
    public void executeTransferLedger(...) throws Exception {
        // ...
    }
    ```

### 2. Startup Blocked by Automatic Index Building
*   **Failure Mode**: If a large collection is missing an index declared in a Java `@Document` annotation, Spring Boot will attempt to build the index during startup. This foreground build locks the collection and blocks application boot for minutes or hours, eventually causing server deployment timeouts.
*   **Resolution**: Set index creation to false and build indexes out-of-band using migrations:
    ```yaml
    spring:
      data:
        mongodb:
          auto-index-creation: false
    ```

### 3. MongoCustomConversions Mapping Leak
*   **Failure Mode**: Defining custom converters inside dynamic runtime methods rather than static singleton beans causes Spring to recreate the conversion mapping registry on every query, exhausting JVM heap memory.
*   **Resolution**: Register all custom converters inside a static configuration class annotated with `@Configuration`, ensuring they are instantiated as singletons.

---

## 12. Summary
Spring Boot integration with MongoDB requires aligning repository abstractions, lifecycle callbacks, and transaction boundaries. By deploying transaction managers, managing index builds, leveraging templates, and auditing document mappings, senior engineers build reliable, scalable Java applications.

---

## 11. Enterprise Case Study: Spring Data Mapping Overhead & N+1 Query Cascade

### 1. Scenario Description
An enterprise catalog system uses Spring Boot with Spring Data MongoDB. After a catalog expansion, catalog listing page loads slowed down from 80ms to over 3,000ms. CPU usage on the application server hit 100%, but database CPU usage remained below 10%, indicating a client-side serialization bottleneck.

### 2. Analytical Diagnostic Investigation
The developers ran a thread profiler on the Spring Boot JVM and inspected logging statements:
```yaml
logging:
  level:
    org.springframework.data.mongodb.core.MongoTemplate: DEBUG
```
They observed that querying a single catalog item triggered multiple database requests to load related entities (the N+1 Query Pattern):
```text
DEBUG o.s.d.m.core.MongoTemplate : Finding document for query: { "_id" : 123 } in collection: catalog_items
DEBUG o.s.d.m.core.MongoTemplate : Finding document for query: { "itemId" : 123 } in collection: catalog_images
DEBUG o.s.d.m.core.MongoTemplate : Finding document for query: { "itemId" : 123 } in collection: inventories
DEBUG o.s.d.m.core.MongoTemplate : Finding document for query: { "_id" : 124 } in collection: catalog_items
```
**Diagnostic Findings**:
*   The entity model used `@DBRef` with lazy loading enabled.
*   When iterating through catalog items to build the response DTO, calling getters on child fields triggered database round-trips for each record, degrading response time.
*   Additionally, Spring Data MongoDB's default mapping converts BSON byte buffers to Java objects using reflection, generating massive heap allocations and garbage collection cycles.

### 3. Step-by-Step Resolution Runbook
1.  **Remove `@DBRef` Mappings**:
    Replace lazy reference relations with embedded documents or query-based lookup aggregations.
2.  **Rewrite Catalog Fetch using MongoDB Aggregation**:
    Use `MongoTemplate` to execute an aggregation pipeline that joins the image and inventory collections using `$lookup` stages in a single query.
3.  **Implement Custom Spring Data Converters**:
    Implement custom BSON-to-object converters to bypass reflection mapping rules and speed up response generation.

### 4. Code Artifact: Java Optimized Aggregation Repository
Save this class as `CustomCatalogRepositoryImpl.java` to join related collections efficiently:
```java
package com.example.catalog;

import org.bson.Document;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.mongodb.core.MongoTemplate;
import org.springframework.data.mongodb.core.aggregation.Aggregation;
import org.springframework.data.mongodb.core.aggregation.AggregationResults;
import org.springframework.data.mongodb.core.query.Criteria;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public class CustomCatalogRepositoryImpl implements CustomCatalogRepository {

    @Autowired
    private MongoTemplate mongoTemplate;

    @Override
    public List<CatalogDto> fetchOptimizedCatalog(String category) {
        Aggregation aggregation = Aggregation.newAggregation(
            Aggregation.match(Criteria.where("category").is(category)),
            // Left outer join to images collection
            Aggregation.lookup("catalog_images", "_id", "itemId", "images"),
            // Left outer join to inventory collection
            Aggregation.lookup("inventories", "_id", "itemId", "inventory"),
            Aggregation.project("name", "price", "images", "inventory")
        );

        AggregationResults<CatalogDto> results = mongoTemplate.aggregate(
            aggregation, "catalog_items", CatalogDto.class
        );
        return results.getMappedResults();
    }
}
```

### 5. Architectural Trade-offs & Lessons Learned
*   **Avoid `@DBRef` in High-Throughput Services**: `@DBRef` forces an application-level query join. Use embedded structures or manual `$lookup` aggregations to minimize database round-trips.
*   **Object Mapping Overhead**: Java serialization of large BSON objects generates heavy heap churn. Select only required fields inside query projection clauses to minimize mapping steps.

---

## 12. Hands-on Lab Exercise: Custom Spring Boot Latency Metrics Collector

### 1. Objective and Scenario
Create a Spring Boot class that intercepts MongoTemplate queries and measures execution times to detect performance problems.

### 2. Code Implementation: `MongoMetricsInterceptor.java`
Create a file named `MongoMetricsInterceptor.java` and paste the following code:
```java
package com.example.metrics;

import org.bson.Document;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.data.mongodb.core.mapping.event.AfterLoadEvent;
import org.springframework.data.mongodb.core.mapping.event.BeforeSaveEvent;
import org.springframework.data.mongodb.core.mapping.event.AbstractMongoEventListener;
import org.springframework.stereotype.Component;

@Component
public class MongoMetricsInterceptor extends AbstractMongoEventListener<Object> {
    private static final Logger log = LoggerFactory.getLogger(MongoMetricsInterceptor.class);
    private final ThreadLocal<Long> startTime = new ThreadLocal<>();

    @Override
    public void onBeforeSave(BeforeSaveEvent<Object> event) {
        startTime.set(System.currentTimeMillis());
    }

    public void onAfterSaveComplete() {
        Long start = startTime.get();
        if (start != null) {
            long duration = System.currentTimeMillis() - start;
            log.info("Database Save Operation completed in {} ms.", duration);
            startTime.remove();
        }
    }

    @Override
    public void onAfterLoad(AfterLoadEvent<Object> event) {
        Document document = event.getDocument();
        if (document != null) {
            log.debug("Document loaded from DB collection: {}", event.getCollectionName());
        }
    }
}
```

### 3. Lab Verification Steps
1.  Add the custom metrics interceptor to your Spring Boot project context.
2.  Verify output logs to check timing assertions for template write tasks.

---

## 13. Spring Data Configuration & Logging Reference

### 1. Key Spring Connection Properties
Configure database connection parameters in `application.properties`:
*   `spring.data.mongodb.auto-index-creation`: Enables automatic index generation on startup (Default: `true`).
*   `spring.data.mongodb.uuid-representation`: Standardizes UUID binary representation type (`standard`).

### 2. Operational Diagnostic Commands
Trace database template execution:
```yaml
# Enable logging for Template operations in application.yml
logging:
  level:
    org.springframework.data.mongodb.core.MongoTemplate: DEBUG
```

### 3. Senior Engineer's Production Checklist
*   [ ] Disable `auto-index-creation` in production configurations to prevent deployment timeouts during index builds.
*   [ ] Define custom converters to handle non-standard Java classes like `ZonedDateTime`.
*   [ ] Use projections in MongoTemplate queries to select only required fields and reduce object serialization overhead.
