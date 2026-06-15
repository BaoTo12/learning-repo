# Module 13: Spring Data MongoDB Comparison

Welcome, student. Today we study data mapping frameworks and abstractions in **Spring Data MongoDB vs Native Java Driver (CS-529)**. We will analyze how Spring wraps the native Java sync driver to simplify development, examine core APIs, compare mapping annotations, and establish production guidelines for choosing the right tool.

---

## 1. What problem does this solve?

While the native MongoDB Java Driver is highly performant and flexible, it operates at a relatively low level:
1. **Verbose Boilerplate**: Standard database modifications, transaction declarations, session configurations, and exception catching blocks require significant repetitive code.
2. **Manual Mapping Management**: Developers must configure custom codec registries and handle nested collections translation routines.
3. **No Auditing or Lifecycle Events**: Tracking creation/modification dates or user IDs requires manual hooks during each write pipeline.

**Spring Data MongoDB** solves these problems by providing declarative abstraction layers (`MongoRepository` and `MongoTemplate`) that integrate directly with the Spring Framework ecosystem, managing transactions, mapping entities, and automating common operations.

---

## 2. Why does Spring/MongoDB provide this feature?

Spring Data MongoDB is an open-source framework developed to:
*   **Decouple Boilerplate from Domain Logic**: Interface-driven repository proxies allow developers to execute complex read/write operations without writing queries.
*   **Enforce Enterprise Patterns**: Standardize transaction handling using familiar Spring `@Transactional` paradigms, while translating low-level driver failures directly into Spring's unified `DataAccessException` hierarchy.
*   **Accelerate Integration**: Wire up connection pooling, cluster routing, authentication, and entity metadata settings seamlessly via standard `application.properties` configurations.

---

## 3. How does it work internally or conceptually?

### The Architecture: Spring Template vs Native Driver
Spring Data MongoDB does not replace the native driver; it acts as a decorator wrapping the native Java Sync Driver client.

```text
[ Application Logic ] ──> MongoRepository (Proxy Interface)
                               │ (Dynamic Query Generation)
                               ▼
                          MongoTemplate (Core Operation Manager)
                               │ (Mapping Mongo Converter)
                               ▼
                          Native Sync Driver (BSON & Connections)
                               │ (Binary Wire Protocol)
                               ▼
                         [ MongoDB Server ]
```

*   **MongoTemplate**: The core execution engine. It handles connection lifecycles, database selection, exception translation, and executes queries mapped through the BSON parser.
*   **MongoRepository**: Dynamic proxies generated at application startup. Dynamic query methods are parsed using reflection and converted into Spring `Query` and `Criteria` representations under the hood.

### Core Annotations
*   `@Document(collection = "users")`: Identifies Java classes as database entities. Allows specifying custom target collection names.
*   `@Id`: Designates the primary identifier. The framework maps this field to the MongoDB `_id` BSON field on disk, transforming standard Java `String`, `Long`, or `ObjectId` values automatically.
*   `@Field("db_field_name")`: Explicitly overrides property keys written to BSON documents.
*   `@Indexed`: Automates index creation on collection startups. Supports options like `unique = true`, `sparse = true`, and index direction.
*   `@CompoundIndex`: Declares multi-field indexes at the class level. E.g., `@CompoundIndex(def = "{'username': 1, 'status': -1}")`.
*   `@Query("{ 'status': ?0 }")`: Allows writing raw MongoDB JSON queries inside repository interfaces. The index placeholder `?0` represents the first method argument.
*   `@Version`: Enables **Optimistic Locking**. The framework tracks an integer version field; modifications assert that the version matches the record in the database, throwing an `OptimisticLockingFailureException` on concurrent writes.

### Entity Auditing
Spring Data MongoDB includes built-in auditing hooks to automatically populate creation and modification audit trails:
*   `@CreatedDate`: Automatically records database write timestamps.
*   `@LastModifiedDate`: Records the last time the document was updated.
*   `@CreatedBy` / `@LastModifiedBy`: Tracks the security context principal who initiated the write. Requires registering an `AuditorAware` bean.

### Dynamic Mapping and the `_class` Property
By default, Spring Data MongoDB's `MappingMongoConverter` writes a field called `_class` containing the fully-qualified package and class name of the Java entity into every document.
*   *Purpose*: Resolves concrete class instances when mapping polymorphic hierarchies (e.g. deserializing a list of abstract `Payment` classes into `CreditCard` or `PayPal` objects).
*   *Drawback*: Adds significant metadata storage overhead to every document. In massive collections, this can cause gigabytes of wasted storage and cache memory.
*   *Fix*: Configure a custom `MongoTypeMapper` that disables writing this attribute if polymorphism is not required.

### Query, Criteria, and Update builders
Programmatic queries in `MongoTemplate` are built using three main abstract syntax builders:
1.  **Criteria**: Binds keys to filters. E.g., `Criteria.where("price").gt(50).and("status").is("AVAILABLE")`.
2.  **Query**: Orchestrates `Criteria` filters, sorting configurations, pagination bounds, and fields projections. E.g., `new Query(criteria).limit(10).with(Sort.by(Direction.DESC, "price"))`.
3.  **Update**: Declares modification instructions. E.g., `new Update().set("status", "ARCHIVED").inc("loginCount", 1)`.

---

## 4. How do we use it in Java?

Here is a typical Spring Boot configuration class enabling auditing and disabling the `_class` type mapper:

```java
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.data.mongodb.config.EnableMongoAuditing;
import org.springframework.data.mongodb.core.MongoTemplate;
import org.springframework.data.mongodb.core.SimpleMongoClientDatabaseFactory;
import org.springframework.data.mongodb.core.convert.DbRefResolver;
import org.springframework.data.mongodb.core.convert.DefaultDbRefResolver;
import org.springframework.data.mongodb.core.convert.DefaultMongoTypeMapper;
import org.springframework.data.mongodb.core.convert.MappingMongoConverter;
import org.springframework.data.mongodb.core.mapping.MongoMappingContext;

@Configuration
@EnableMongoAuditing // Enable @CreatedDate and @LastModifiedDate features
public class SpringMongoConfig {

    private final SimpleMongoClientDatabaseFactory mongoDbFactory;

    public SpringMongoConfig(SimpleMongoClientDatabaseFactory mongoDbFactory) {
        this.mongoDbFactory = mongoDbFactory;
    }

    @Bean
    public MappingMongoConverter mappingMongoConverter(MongoMappingContext context) {
        DbRefResolver dbRefResolver = new DefaultDbRefResolver(mongoDbFactory);
        MappingMongoConverter converter = new MappingMongoConverter(dbRefResolver, context);
        
        // Disable the _class attribute insertion
        converter.setTypeMapper(new DefaultMongoTypeMapper(null));
        return converter;
    }
}
```

---

## 5. What are the trade-offs?

### Pros and Cons of Spring Data MongoDB
*   **Pros**:
    *   Declarative database operations speed up development time.
    *   Standard auditing features (`@CreatedDate`, `@Version`) protect data integrity.
    *   Integrates seamlessly with Spring Boot's transaction management abstraction (`@Transactional`).
    *   Exception translation standardizes error handling.
*   **Cons**:
    *   Introduces mapping abstraction overhead compared to the raw Java driver.
    *   Dynamic reflection mapping causes higher initial startup latency.
    *   Deep nesting mapping issues are hard to debug when runtime converter mappings fail.
    *   Couples database operations to the Spring framework container context.

### Selecting the Right Approach: Matrix Comparison
Use this guide to choose the appropriate MongoDB interaction layer:

| Dimension | Spring Data `MongoRepository` | Spring Data `MongoTemplate` | Native Java Driver |
| :--- | :--- | :--- | :--- |
| **Primary Use Case** | Standard CRUD and simple query methods. | Complex dynamic queries, bulk writes, updates. | High-throughput systems, custom drivers, non-Spring apps. |
| **Query Complexity** | Low to Medium. | High (programmatic Java API). | Unlimited (raw BSON constructs). |
| **Boilerplate** | Minimum (declarative interfaces). | Medium (requires builder classes). | High (manual BSON query parsing). |
| **Performance** | Dynamic proxy mapping overhead. | Clean conversion, but minor reflection. | Fastest throughput, zero abstraction overhead. |
| **Polymorphism** | Easily handled via `_class` meta-keys. | Supported natively in conversion maps. | Requires manual `@BsonDiscriminator` codecs. |

---

## 6. Common Mistakes

1. **Production Boot Bottlenecks via `auto-index-creation=true`**
   Leaving auto-indexing enabled in production is highly dangerous. On application startup, Spring scans all `@Document` classes and issues `createIndex` operations. If a collection contains millions of records, this blocks Spring startup and can lock the database server.
   *Fix*: Set `spring.data.mongodb.auto-index-creation=false` in production. Construct indexes out-of-band using migration scripts.

2. **Bypassing `@Version` Concurrency Controls in Template Updates**
   If an entity declares a `@Version` field, Spring repositories verify and increment it automatically on `save()`. However, calling direct update methods on `MongoTemplate` (e.g., `MongoTemplate.updateFirst()`) bypasses these mapping lifecycle events.
   *Fix*: Manually fetch, update, and save the entity to preserve optimistic locking version checks, or append dynamic version checks to the update criteria.

3. **Disk Bloat due to `_class` Field Storage**
   Failing to disable the default class type mapper writes full package names to every document, bloating storage and indexes.
   *Fix*: Configure the `MappingMongoConverter` with a null type mapper as illustrated in Section 4.

4. **Missing Transaction Manager Registrations**
   Adding `@Transactional` annotations on Spring services does nothing unless a `MongoTransactionManager` is explicitly registered as a Spring bean.
   *Fix*: Register a `MongoTransactionManager` in the application configuration.

---

## 7. When should we use it?
*   Use Spring Data MongoDB when building standard Spring Boot REST microservices, enterprise applications, or platforms requiring auditing logs and transaction controls.
*   Use `MongoRepository` for simple lookup queries and typical CRUD patterns. Use `MongoTemplate` for dynamic filters or complex updates.

---

## 8. When should we avoid it?
*   Avoid when building high-performance, non-Spring applications, massive stream consumers, or applications where JVM startup times must be minimized (such as AWS Lambda serverless functions).
*   Avoid when writing low-level shard key routing engines, replica controllers, or migration tools.

---

## 9. Code Examples

### 9.1 Custom Repository Fragment (Decoupled Architecture)
To combine dynamic template query features with type-safe Spring Data repositories, we build custom repository fragments.

**1. The Custom Fragment Interface:**
```java
package com.mongodb.systems;

import java.util.List;

public interface CustomProductRepository {
    long bulkUpdateDiscountByCategory(String category, double discountPercentage);
    List<ProductDoc> findMatchingDynamicProducts(String category, Double maxPrice);
}
```

**2. The Custom Fragment Implementation:**
```java
package com.mongodb.systems;

import org.springframework.data.mongodb.core.MongoTemplate;
import org.springframework.data.mongodb.core.query.Criteria;
import org.springframework.data.mongodb.core.query.Query;
import org.springframework.data.mongodb.core.query.Update;
import com.mongodb.client.result.UpdateResult;
import java.util.List;

public class CustomProductRepositoryImpl implements CustomProductRepository {

    private final MongoTemplate mongoTemplate;

    // MongoTemplate is injected automatically by Spring
    public CustomProductRepositoryImpl(MongoTemplate mongoTemplate) {
        this.mongoTemplate = mongoTemplate;
    }

    @Override
    public long bulkUpdateDiscountByCategory(String category, double discountPercentage) {
        Query query = new Query(Criteria.where("category").is(category));
        Update update = new Update().set("discount", discountPercentage);
        
        UpdateResult result = mongoTemplate.updateMany(query, update, ProductDoc.class);
        return result.getModifiedCount();
    }

    @Override
    public List<ProductDoc> findMatchingDynamicProducts(String category, Double maxPrice) {
        Criteria criteria = Criteria.where("category").is(category);
        if (maxPrice != null) {
            criteria.and("price").lte(maxPrice);
        }
        return mongoTemplate.find(new Query(criteria), ProductDoc.class);
    }
}
```

**3. The Primary Spring Data Interface:**
```java
package com.mongodb.systems;

import org.springframework.data.mongodb.repository.MongoRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface ProductRepository extends MongoRepository<ProductDoc, String>, CustomProductRepository {
    // Declarative query method
    List<ProductDoc> findByCategory(String category);
}
```

---

### 9.2 Spring Data MongoDB Declarative Aggregation
Performing multi-stage aggregations using Spring's type-safe aggregation pipelines:

```java
package com.mongodb.systems;

import org.springframework.data.domain.Sort;
import org.springframework.data.mongodb.core.MongoTemplate;
import org.springframework.data.mongodb.core.aggregation.Aggregation;
import org.springframework.data.mongodb.core.aggregation.AggregationResults;
import org.springframework.data.mongodb.core.query.Criteria;
import java.util.List;

public class SalesReportService {

    private final MongoTemplate mongoTemplate;

    public SalesReportService(MongoTemplate mongoTemplate) {
        this.mongoTemplate = mongoTemplate;
    }

    public List<SalesSummary> getCategorySalesReport(String region) {
        // Build the aggregation stages programmatically
        Aggregation aggregation = Aggregation.newAggregation(
            Aggregation.match(Criteria.where("region").is(region)),
            Aggregation.group("category")
                .sum("price").as("totalSales")
                .avg("price").as("avgPrice"),
            Aggregation.sort(Sort.Direction.DESC, "totalSales")
        );

        AggregationResults<SalesSummary> results = mongoTemplate.aggregate(
            aggregation, "orders", SalesSummary.class
        );

        return results.getMappedResults();
    }

    public static class SalesSummary {
        private String id; // Represents the grouped field (category)
        private double totalSales;
        private double avgPrice;

        public SalesSummary() {}

        public String getId() { return id; }
        public void setId(String id) { this.id = id; }
        public double getTotalSales() { return totalSales; }
        public void setTotalSales(double totalSales) { this.totalSales = totalSales; }
        public double getAvgPrice() { return avgPrice; }
        public void setAvgPrice(double avgPrice) { this.avgPrice = avgPrice; }
    }
}
```

---

## 10. Hands-on Exercises

### Exercise 1: Custom Repository Fragment
Implement a custom repository interface fragment using Spring's `MongoTemplate`. The method must search for user records matching a specific `role` and update their account status to `status` using `Criteria` and `Update` builders.

#### Implementation Stub
Complete the repository fragment implementation:

```java
package com.mongodb.systems;

import org.springframework.data.mongodb.core.MongoTemplate;
import org.springframework.data.mongodb.core.query.Criteria;
import org.springframework.data.mongodb.core.query.Query;
import org.springframework.data.mongodb.core.query.Update;
import com.mongodb.client.result.UpdateResult;

public class CustomAccountRepositoryImpl implements CustomAccountRepository {

    private final MongoTemplate mongoTemplate;

    public CustomAccountRepositoryImpl(MongoTemplate mongoTemplate) {
        this.mongoTemplate = mongoTemplate;
    }

    @Override
    public long updateAccountStatuses(String role, String newStatus) {
        // TODO: Build the query criteria matching role, and apply status update
        Query query = new Query(Criteria.where("role").is(role));
        Update update = new Update().set("status", newStatus);
        
        UpdateResult result = mongoTemplate.updateMany(query, update, AccountDoc.class);
        return result.getModifiedCount();
    }
}
```

Support classes:

```java
package com.mongodb.systems;

public interface CustomAccountRepository {
    long updateAccountStatuses(String role, String newStatus);
}
```

```java
package com.mongodb.systems;

import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.mapping.Document;

@Document(collection = "accounts")
public class AccountDoc {
    @Id
    private String id;
    private String role;
    private String status;

    public AccountDoc() {}
    public AccountDoc(String id, String role, String status) {
        this.id = id;
        this.role = role;
        this.status = status;
    }

    public String getId() { return id; }
    public void setId(String id) { this.id = id; }
    public String getRole() { return role; }
    public void setRole(String role) { this.role = role; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
}
```

#### Verification Test
Ensure your custom repository passes this JUnit 5 test mock wrapper:

```java
package com.mongodb.systems;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

import com.mongodb.client.result.UpdateResult;
import org.junit.jupiter.api.Test;
import org.springframework.data.mongodb.core.MongoTemplate;
import org.springframework.data.mongodb.core.query.Query;
import org.springframework.data.mongodb.core.query.Update;

class CustomAccountRepositoryTest {

    @Test
    void testUpdateAccountStatusesUpdatesProperly() {
        MongoTemplate mockTemplate = mock(MongoTemplate.class);
        UpdateResult mockResult = mock(UpdateResult.class);
        when(mockResult.getModifiedCount()).thenReturn(15L);

        // Stub template execution
        when(mockTemplate.updateMany(any(Query.class), any(Update.class), eq(AccountDoc.class)))
                .thenReturn(mockResult);

        CustomAccountRepository repository = new CustomAccountRepositoryImpl(mockTemplate);
        long modified = repository.updateAccountStatuses("ADMIN", "SUSPENDED");

        assertEquals(15L, modified);
        verify(mockTemplate).updateMany(any(Query.class), any(Update.class), eq(AccountDoc.class));
    }
}
```

---

### Exercise 2: Entity Auditing and Optimistic Locking
Create a spring-compliant audited document mapping class. The class must feature optimistic locking, auto-generated auditing fields for creation dates, and track update versions.

#### Implementation Stub
Complete the mappings on the entity below:

```java
package com.mongodb.systems;

import org.springframework.data.annotation.CreatedDate;
import org.springframework.data.annotation.Id;
import org.springframework.data.annotation.LastModifiedDate;
import org.springframework.data.annotation.Version;
import org.springframework.data.mongodb.core.mapping.Document;
import org.springframework.data.mongodb.core.mapping.Field;
import java.time.Instant;

// TODO: Add document collection binding mapping to "audited_orders"
@Document(collection = "audited_orders")
public class AuditedOrder {

    // TODO: Add Id annotation
    @Id
    private String orderId;

    // TODO: Map to custom field "order_amount"
    @Field("order_amount")
    private double amount;

    // TODO: Configure Optimistic Locking version mapping
    @Version
    private Long version;

    // TODO: Add created date audit mapping
    @CreatedDate
    private Instant createdTime;

    // TODO: Add last modified date audit mapping
    @LastModifiedDate
    private Instant modifiedTime;

    public AuditedOrder() {}
    public AuditedOrder(String orderId, double amount) {
        this.orderId = orderId;
        this.amount = amount;
    }

    public String getOrderId() { return orderId; }
    public void setOrderId(String id) { this.orderId = id; }

    public double getAmount() { return amount; }
    public void setAmount(double amount) { this.amount = amount; }

    public Long getVersion() { return version; }
    public void setVersion(Long version) { this.version = version; }

    public Instant getCreatedTime() { return createdTime; }
    public void setCreatedTime(Instant createdTime) { this.createdTime = createdTime; }

    public Instant getModifiedTime() { return modifiedTime; }
    public void setModifiedTime(Instant modifiedTime) { this.modifiedTime = modifiedTime; }
}
```

#### Verification Test
Verify annotations are configured correctly using this reflection test:

```java
package com.mongodb.systems;

import static org.junit.jupiter.api.Assertions.*;

import org.junit.jupiter.api.Test;
import org.springframework.data.annotation.CreatedDate;
import org.springframework.data.annotation.Id;
import org.springframework.data.annotation.LastModifiedDate;
import org.springframework.data.annotation.Version;
import org.springframework.data.mongodb.core.mapping.Document;
import org.springframework.data.mongodb.core.mapping.Field;
import java.lang.reflect.Field;

class AuditedOrderTest {

    @Test
    void testMappingAnnotationsPresence() throws Exception {
        // Class level binding assertion
        assertTrue(AuditedOrder.class.isAnnotationPresent(Document.class));
        assertEquals("audited_orders", AuditedOrder.class.getAnnotation(Document.class).collection());

        // Assert primary key is annotated
        java.lang.reflect.Field idField = AuditedOrder.class.getDeclaredField("orderId");
        assertTrue(idField.isAnnotationPresent(Id.class));

        // Assert Field Mapping
        java.lang.reflect.Field amountField = AuditedOrder.class.getDeclaredField("amount");
        assertTrue(amountField.isAnnotationPresent(Field.class));
        assertEquals("order_amount", amountField.getAnnotation(Field.class).value());

        // Assert Optimistic locking version configuration
        java.lang.reflect.Field versionField = AuditedOrder.class.getDeclaredField("version");
        assertTrue(versionField.isAnnotationPresent(Version.class));

        // Assert Auditing fields
        java.lang.reflect.Field createdField = AuditedOrder.class.getDeclaredField("createdTime");
        java.lang.reflect.Field modifiedField = AuditedOrder.class.getDeclaredField("modifiedTime");
        assertTrue(createdField.isAnnotationPresent(CreatedDate.class));
        assertTrue(modifiedField.isAnnotationPresent(LastModifiedDate.class));
    }
}
```

---

### Exercise 3: Aggregation API Construction
Build a dynamic Spring aggregation pipeline method that groups records by `category`, sums the field `sales`, and filters out records where category is null.

#### Implementation Stub
Complete the aggregation builder logic below:

```java
package com.mongodb.systems;

import org.springframework.data.mongodb.core.aggregation.Aggregation;
import org.springframework.data.mongodb.core.aggregation.GroupOperation;
import org.springframework.data.mongodb.core.aggregation.MatchOperation;
import org.springframework.data.mongodb.core.query.Criteria;

public class SpringAggregationFactory {

    /**
     * Builds and returns a Spring Data Aggregation pipeline.
     */
    public static Aggregation buildCategorySalesAggregation() {
        // TODO: Build match stage and group stage
        MatchOperation match = Aggregation.match(Criteria.where("category").ne(null));
        GroupOperation group = Aggregation.group("category").sum("sales").as("totalSales");
        
        return Aggregation.newAggregation(match, group);
    }
}
```

#### Verification Test
Run the JUnit 5 test class to verify settings correctness:

```java
package com.mongodb.systems;

import static org.junit.jupiter.api.Assertions.*;

import org.junit.jupiter.api.Test;
import org.springframework.data.mongodb.core.aggregation.Aggregation;
import org.springframework.data.mongodb.core.query.Criteria;
import org.bson.Document;

class SpringAggregationFactoryTest {

    @Test
    void testAggregationStages() {
        Aggregation agg = SpringAggregationFactory.buildCategorySalesAggregation();
        assertNotNull(agg);

        var context = Aggregation.DEFAULT_CONTEXT;
        Document doc = agg.toDocument("sales", context);
        assertNotNull(doc);

        // Verify structure has pipeline stages
        assertTrue(doc.containsKey("pipeline"));
        var pipeline = doc.get("pipeline", java.util.List.class);
        assertEquals(2, pipeline.size());
    }
}
```
