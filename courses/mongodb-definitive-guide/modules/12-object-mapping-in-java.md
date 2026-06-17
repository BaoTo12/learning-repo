# Module 12: Object Mapping in Java

Welcome, student. Today we study data translation in **MongoDB Object Mapping (CS-529)**. We will analyze how Java applications translate strongly-typed object structures into MongoDB's native BSON format, examining driver-level mapping mechanics, architectural layers, and framework comparisons.

---

## 1. What problem does this solve?

Working directly with raw MongoDB `Document` instances is highly flexible but leads to significant drawbacks in production-grade systems:
1. **Lack of Type Safety**: Reading keys using string literals (`doc.getInteger("price")` or `doc.getString("title")`) relies on developer memory. Simple typing mistakes lead to runtime `ClassCastException` bugs.
2. **Boilerplate Code**: Converting custom domain objects (e.g., `Order`, `Customer`) to and from `Document` maps requires verbose getter/setter conversion loops.
3. **No Validation in IDEs**: Modern refactoring tools cannot track database attributes renamed within double quotes.

**Object Mapping** resolves these issues by automatically binding Java class fields directly to BSON fields, enabling compile-time type checking and reducing serialization boilerplate.

---

## 2. Why does MongoDB provide this feature?

The official MongoDB Java Driver includes native object mapping facilities (`Codec` and `CodecRegistry`) to:
*   **Decouple App Logic from BSON Details**: Developers write standard Java Beans (POJOs) with plain data types, while the driver translates them to binary BSON under the hood.
*   **Provide High Performance Serialization**: The native codec system compiles translation routines or utilizes highly optimized reflection, yielding significantly higher throughput and lower memory allocation compared to standard JSON parser libraries.
*   **Support Flexible Customization**: By defining custom codecs, developers can control exactly how complex Java types (e.g., Joda-Time, custom currency classes, encryption envelopes) write to BSON format.

---

## 3. How does it work internally or conceptually?

### The Codec and CodecRegistry System
At the heart of BSON translation are three main interfaces:
*   `Codec<T>`: Responsible for encoding a Java instance of type `T` into BSON bytes, and decoding BSON bytes back into an instance of `T`.
*   `CodecProvider`: A factory interface that creates a `Codec<T>` for a given Java class.
*   `CodecRegistry`: A centralized registry of codecs. When the driver needs to read or write a class type, it queries the `CodecRegistry` for a matching `Codec`.

### PojoCodecProvider
The `PojoCodecProvider` scans standard Java classes to create mappings.
*   By default, it uses Java reflection to discover property descriptors (fields with standard getter and setter methods).
*   Configuring the provider with `automatic(true)` instructs it to dynamically create codecs for any POJO class it encounters at runtime.
*   It requires a public or protected no-argument constructor to instantiate objects before setting property values.

### BSON Annotations
You can customize mapping behaviors using standard BSON annotations:
*   `@BsonId`: Marks a Java field to be used as the MongoDB primary key `_id` field.
*   `@BsonProperty("db_field_name")`: Overrides the default property-to-field naming logic.
*   `@BsonIgnore`: Instructs the serializer to skip this Java property during writes and reads.
*   `@BsonDiscriminator`: Enables polymorphic serialization. It writes a special discriminator field (typically `_t`) to BSON so the correct Java subclass is instantiated during read queries.

### Handling ObjectId and UUIDs
*   **ObjectId**: Java representations of `ObjectId` are converted to 12-byte binary BSON ObjectIds. If a class uses a `String` representing an hexadecimal ID, developers can use annotations or custom codecs to automatically transform strings to database `ObjectId` values.
*   **UUID**: Storing UUID fields requires configuring a client's `UuidRepresentation`. The standard modern layout is `UuidRepresentation.STANDARD` (BSON subtype `0x04`), which is cross-platform compatible. Legacy Java applications sometimes default to `UuidRepresentation.JAVA_LEGACY` (BSON subtype `0x03`), which uses Java-specific byte ordering.

### Architectural Patterns: DTO vs Entity vs Document Model
To maintain clean code in enterprise systems, you should separate data structures into distinct layers:

```text
[ REST API / Clients ] ──> DTO Model (Data Transfer Object)
                               │ (Mapping Layer)
                               ▼
[ Application Core ]   ──> Entity Model (POJO, annotated for MongoDB)
                               │ (CodecRegistry serialization)
                               ▼
[ Database Storage ]   ──> Document Model (BSON structure on disk)
```

1. **Document Model**: The physical schema stored in MongoDB. Highly denormalized, structured for query performance, and validated via database-level JSON Schema validators.
2. **Entity Model (POJO)**: The Java mapping representation containing BSON mappings, indexes, and primary keys. Couples the domain representation directly to the database library.
3. **DTO Model**: Completely decoupled from persistence structures. Contains validation annotations (`@NotNull`, etc.) and contains only the attributes exposed through APIs, protecting the internal database schema from client-facing API changes.

### Manual vs Automatic Mapping
Here is a side-by-side comparison of manual mapping (using raw `Document` models) versus automatic mapping (using POJO codecs):

| Dimension | Manual Mapping (Document) | Automatic Mapping (POJOs) |
| :--- | :--- | :--- |
| **Boilerplate** | Extremely high (manual `getString()`, `put()` calls). | Low (uses simple declarations and annotations). |
| **Type Safety** | Low (runtime casting errors). | High (compile-time checking). |
| **Performance** | Fastest (direct conversion, no reflection). | Highly optimized, but minor overhead during initial class parsing. |
| **Flexibility** | Perfect for highly dynamic, unstructured schemas. | Rigid (requires pre-defined class blueprints). |
| **Refactoring** | Prone to failure when database field names change. | Safe (field renames are tracked through IDE references). |

### Comparison with Spring Data MongoDB Mapping
Many Java projects use Spring Data MongoDB rather than the native driver. Understanding the translation differences is critical:

*   **Annotations**: 
    - Native Driver: uses `@BsonId` and `@BsonProperty`.
    - Spring Data: uses `@Id` and `@Field`.
*   **Polymorphic Metadata**: 
    - Spring Data automatically inserts a `_class` field in all documents to store the fully-qualified Java class name. This allows instant deserialization of interfaces but adds significant storage overhead to every document.
    - Native Driver only writes subclass metadata when `@BsonDiscriminator` is explicitly configured.
*   **Conversion Infrastructure**:
    - Spring Data routes mapping through `MongoConverter` and `MappingMongoConverter`, converting entities to custom Spring mapping contexts.
    - Native Driver relies on low-level binary `Codec` classes registered in `MongoClientSettings`, which bypasses Spring application context overhead.

---

## 4. How do we use it in Java?

To configure automatic POJO mapping with standard UUID representations in the Java Sync Driver:

### 4.1 Visual Dataset & Codec Mapping Path Trace

#### JVM Object State to Serialize:
```java
new User("Alice", "alice@gmail.com")
```

#### Step-by-Step Serialization Execution Path:

1. **Driver Receives Object**:
   * Application invokes `collection.insertOne(user)`.
2. **Codec Registry Lookup**:
   * Driver queries `pojoCodecRegistry` to find a codec for `User.class`.
   * It scans `MongoClientSettings.getDefaultCodecRegistry()` -> no matching codec found.
   * It queries `fromProviders(pojoProvider)` -> `PojoCodecProvider` matches class type and returns a dynamically constructed `PojoCodec<User>`.
3. **Property Extraction**:
   * The `PojoCodec` uses reflection to extract values by calling getters (`getName()` and `getEmail()`).
4. **Binary BSON Write**:
   * Driver translates values into binary key-value tuples and writes them to the database output stream.
   * *Output BSON bytes schema*: `\x02name\x00\x06\x00\x00\x00Alice\x00\x02email\x00\x0f\x00\x00\x00alice@gmail.com\x00`

```java
import static org.bson.codecs.configuration.CodecRegistries.fromProviders;
import static org.bson.codecs.configuration.CodecRegistries.fromRegistries;

import com.mongodb.ConnectionString;
import com.mongodb.MongoClientSettings;
import com.mongodb.client.MongoClient;
import com.mongodb.client.MongoClients;
import org.bson.UuidRepresentation;
import org.bson.codecs.configuration.CodecRegistry;
import org.bson.codecs.pojo.PojoCodecProvider;

public class MongoPojoBootstrap {

    public static MongoClient createClient(String connectionString) {
        // 1. Build the POJO Codec Provider configured for automatic class mapping.
        // automatic(true) enables dynamic creation of codecs for any Java Bean (POJO) encountered.
        PojoCodecProvider pojoProvider = PojoCodecProvider.builder()
                .automatic(true)
                .build();

        // 2. Combine default driver codecs (String, Double, Integer, etc.) with the POJO codec registry.
        // fromRegistries executes lookups in the order registries are passed.
        CodecRegistry pojoCodecRegistry = fromRegistries(
                MongoClientSettings.getDefaultCodecRegistry(),
                fromProviders(pojoProvider)
        );

        // 3. Build Client Settings configuring the custom registry and standard UUID bytes storage representation.
        MongoClientSettings settings = MongoClientSettings.builder()
                .applyConnectionString(new ConnectionString(connectionString))
                .codecRegistry(pojoCodecRegistry)
                .uuidRepresentation(UuidRepresentation.STANDARD) // Store UUIDs as standard cross-platform subtype 0x04
                .build();

        // 4. Create and return client
        return MongoClients.create(settings);
    }
}
```

#### Detailed Operations & Syntax Explanation:
- **`PojoCodecProvider.builder().automatic(true)`**: Tells the driver to automatically generate codecs for standard Java classes using reflection, eliminating the need to register every POJO class explicitly.
- **`CodecRegistries.fromRegistries`**: Combines multiple registries. The lookup processes left-to-right; therefore, standard driver types are matched first before evaluating user class shapes.
- **`uuidRepresentation(UuidRepresentation.STANDARD)`**: Enforces standard cross-language BSON UUID representations (BSON subtype `0x04`) instead of language-specific byte orders.

---

## 5. What are the trade-offs?

### Working with Document Directly
*   **Pros**: Complete control over read/write representations; ideal for telemetry feeds or unstructured JSON logs; zero reflection overhead.
*   **Cons**: Error-prone key typing; verbose converter classes; high maintenance cost.

### Automatic POJO Mapping
*   **Pros**: Rapid developer onboarding; type-safe filters; seamless nested object hierarchies serialization.
*   **Cons**: Couples Java domain classes to BSON annotation namespaces; requires no-argument constructors which might compromise encapsulation; polymorphic class mapping is rigid.

---

## 6. Common Mistakes

1. **Missing a Nullary (No-Arg) Constructor**
   The POJO codec system instantiates target objects via reflection. If a class defines a parameterized constructor but lacks an empty constructor, the driver throws a runtime exception during deserialization.
   *Fix*: Always declare a `public` or `protected` default constructor inside mapping entities.

2. **Query ID Type Mismatches**
   If the database document store stores primary keys as BSON `ObjectId`, but the Java entity maps the ID field as a plain `String` (without converting), queries matching on a string representation (e.g. `Filters.eq("_id", "507f191e810c19729de860ea")`) fail to return results because the database performs strict type checking.
   *Fix*: Declare fields as `ObjectId`, or use a custom converter class during operations.

3. **Subclasses Missing in Codec Registries**
   When using inheritance (e.g., `BillingDetails` class sub-typed by `CreditCard` and `PayPal`), BSON reader will fail to deserialize polymorphic documents if the subclasses are not registered with the provider.
   *Fix*: Register subclasses explicitly or ensure they are discoverable under package scanning.

---

## 7. When should we use it?
*   Use automatic POJO mapping for primary domain objects (users, orders, catalogs) where the database schema maps closely to classic JVM representations.
*   Use standard UUID configuration properties (`UuidRepresentation.STANDARD`) to avoid driver incompatibilities when exchanging data with other backend languages.

---

## 8. When should we avoid it?
*   Avoid automatic mapping when writing migration tools that process highly variable and legacy schemas containing dynamic field keys; raw `Document` objects are a much safer choice here.
*   Avoid standard automatic reflection codecs in specialized low-latency setups where runtime reflection overhead must be completely eliminated; write custom, hand-coded `Codec` instances instead.

---

## 9. Code Examples

### 9.1 Raw Document Mapping (Manual approach)
Below is an example of manual data transformation to highlight the boilerplate required compared to POJO codecs:

##### Manual Document Mapping Trace:

###### Input Domain Entity:
```java
new UserDomain("507f191e810c19729de860ea", "bob@gmail.com", 5)
```

###### Output Database BSON (Document):
```json
{
  "_id": { "$oid": "507f191e810c19729de860ea" },
  "user_email": "bob@gmail.com",
  "login_count": 5
}
```

```java
import org.bson.Document;
import org.bson.types.ObjectId;

public class ManualUserMapper {

    public static class UserDomain {
        private String id;
        private String email;
        private int loginCount;

        public UserDomain(String id, String email, int loginCount) {
            this.id = id;
            this.email = email;
            this.loginCount = loginCount;
        }

        public String getId() { return id; }
        public String getEmail() { return email; }
        public int getLoginCount() { return loginCount; }
    }

    // Convert domain POJO to raw BSON Document
    public static Document toDocument(UserDomain user) {
        Document doc = new Document();
        if (user.getId() != null) {
            // Converts standard 24-character hexadecimal String into database binary ObjectId
            doc.put("_id", new ObjectId(user.getId()));
        }
        doc.put("user_email", user.getEmail());
        doc.put("login_count", user.getLoginCount());
        return doc;
    }

    // Convert raw BSON Document to domain POJO
    public static UserDomain fromDocument(Document doc) {
        ObjectId oid = doc.getObjectId("_id");
        // Converts binary ObjectId back to 24-character hex String for APIs
        String idString = oid != null ? oid.toHexString() : null;
        String email = doc.getString("user_email");
        // Uses getInteger with default value fallback to avoid NullPointerException on null fields
        int count = doc.getInteger("login_count", 0);
        return new UserDomain(idString, email, count);
    }
}
```

#### Detailed Operations & Syntax Explanation:
- **`new ObjectId(String hexString)`**: Constructs a BSON `ObjectId` from a 24-character hexadecimal string, performing syntax validation.
- **`doc.getObjectId("_id")`**: Extracts the binary BSON `_id` field as a Java `ObjectId` type.
- **`doc.getInteger("fieldName", defaultValue)`**: Safe getter method that extracts integer values and returns a fallback value if the key does not exist or has a null value.

### 9.2 Complete POJO Mapping with Nested Objects and Lists
The following entity class maps a complex schema including arrays and embedded child structures using standard BSON mappings:

##### Nested Array BSON Dataset Layout:

###### Output BSON/JSON Database State:
```json
{
  "_id": { "$oid": "507f191e810c19729de860ea" },
  "customer_name": "Alice Developer",
  "items": [
    { "productSku": "SKU-99", "price": 49.99 }
  ]
}
```

```java
import org.bson.codecs.pojo.annotations.BsonId;
import org.bson.codecs.pojo.annotations.BsonProperty;
import org.bson.types.ObjectId;
import java.util.ArrayList;
import java.util.List;

public class OrderEntity {

    // @BsonId maps this field to the unique primary key "_id" in MongoDB
    @BsonId
    private ObjectId id;

    // @BsonProperty customizes the key name written to the database document
    @BsonProperty("customer_name")
    private String customerName;

    // Collections lists are automatically converted to BSON array wrappers
    private List<OrderItem> items = new ArrayList<>();

    public OrderEntity() {} // Required nullaryDefault constructor for reflection

    public OrderEntity(ObjectId id, String customerName, List<OrderItem> items) {
        this.id = id;
        this.customerName = customerName;
        this.items = items;
    }

    public ObjectId getId() { return id; }
    public void setId(ObjectId id) { this.id = id; }

    public String getCustomerName() { return customerName; }
    public void setCustomerName(String customerName) { this.customerName = customerName; }

    public List<OrderItem> getItems() { return items; }
    public void setItems(List<OrderItem> items) { this.items = items; }

    // Nested Class represents subdocuments embedded in the parent document array
    public static class OrderItem {
        private String productSku;
        private double price;

        public OrderItem() {} // Default nullary constructor required for nested class serialization

        public OrderItem(String productSku, double price) {
            this.productSku = productSku;
            this.price = price;
        }

        public String getProductSku() { return productSku; }
        public void setProductSku(String productSku) { this.productSku = productSku; }

        public double getPrice() { return price; }
        public void setPrice(double price) { this.price = price; }
    }
}
```

#### Detailed Operations & Syntax Explanation:
- **`@BsonId`**: Directs the serialization process to treat this field as the unique identifier.
- **`@BsonProperty("customer_name")`**: Maps the camelCase Java property name to a snake_case database field key.
- **`public static class OrderItem`**: Nested static subclasses are automatically mapped as subdocuments inside the parent BSON document.

### 9.3 Polymorphic Inheritance mapping with `@BsonDiscriminator`
We use annotations to instruct the database how to map subclass types to the same collection:

##### Polymorphic BSON Dataset Layout & Discriminator Trace:

###### Output BSON/JSON Document for CreditCardPayment:
```json
{
  "_id": { "$oid": "507f191e810c19729de860ea" },
  "_t": "CREDIT_CARD",
  "amount": 250.0,
  "cardHolder": "Alice Developer",
  "cardNumber": "1111-2222-3333-4444"
}
```

###### Deserialization Resolution Path:
1. Driver queries document from database.
2. It encounters `_t` key matching the discriminator configured for `PaymentMethod`.
3. The value `"CREDIT_CARD"` maps to the `CreditCardPayment` class definition.
4. Driver instantiates a `CreditCardPayment` object, maps standard fields, and returns it cast as the abstract class `PaymentMethod`.

```java
import org.bson.codecs.pojo.annotations.BsonDiscriminator;
import org.bson.codecs.pojo.annotations.BsonId;
import org.bson.types.ObjectId;

// @BsonDiscriminator configures the discriminator key and value used during polymorphism
@BsonDiscriminator(key = "_t", value = "PAYMENT")
public abstract class PaymentMethod {
    @BsonId
    private ObjectId id;
    private double amount;

    public PaymentMethod() {} // Nullary default constructor required
    public PaymentMethod(double amount) { this.amount = amount; }

    public ObjectId getId() { return id; }
    public void setId(ObjectId id) { this.id = id; }
    public double getAmount() { return amount; }
    public void setAmount(double amount) { this.amount = amount; }
}

// Subclasses must also be annotated with @BsonDiscriminator defining their unique type value
@BsonDiscriminator(key = "_t", value = "CREDIT_CARD")
class CreditCardPayment extends PaymentMethod {
    private String cardHolder;
    private String cardNumber;

    public CreditCardPayment() {}
    public CreditCardPayment(double amount, String cardHolder, String cardNumber) {
        super(amount);
        this.cardHolder = cardHolder;
        this.cardNumber = cardNumber;
    }

    public String getCardHolder() { return cardHolder; }
    public void setCardHolder(String cardHolder) { this.cardHolder = cardHolder; }
    public String getCardNumber() { return cardNumber; }
    public void setCardNumber(String cardNumber) { this.cardNumber = cardNumber; }
}
```

#### Detailed Operations & Syntax Explanation:
- **`@BsonDiscriminator(key = "_t", value = "CREDIT_CARD")`**: Instructs the codec registry to append a field named `_t` storing the class type value during write serialization, and uses this field to resolve subclasses during queries.

---

## 10. Hands-on Exercises

### Exercise 1: Polymorphic Entity Mapping
Define a polymorphic class hierarchy for vehicles. The base class must be abstract, use a discriminator key of `_t`, and declare sub-classes `Car` and `Truck`. Register these elements inside the provider context to enable seamless type-safe database queries.

##### Dataset and execution Trace:

###### Input dataset shape for Car entity:
```json
{
  "_id": { "$oid": "507f191e810c19729de860ea" },
  "_t": "CAR",
  "modelName": "Model S",
  "passengerCapacity": 5
}
```

###### Deserialization processing flow:
1. `registry.get(Car.class)` parses BSON properties.
2. Checks class annotations -> finds `@BsonDiscriminator(key = "_t", value = "CAR")`.
3. Instantiates `Car` class through nullary Default constructor, mapping `modelName` and `passengerCapacity` values.

Complete the implementation stub:

```java
package com.mongodb.systems;

import org.bson.codecs.pojo.annotations.BsonDiscriminator;
import org.bson.codecs.pojo.annotations.BsonId;
import org.bson.codecs.pojo.annotations.BsonProperty;
import org.bson.types.ObjectId;

// Configures base vehicle discriminator key
@BsonDiscriminator(key = "_t", value = "VEHICLE")
public abstract class Vehicle {
    @BsonId
    private ObjectId id;
    private String modelName;

    public Vehicle() {} // Required nullary constructor
    public Vehicle(String modelName) {
        this.modelName = modelName;
    }

    public ObjectId getId() { return id; }
    public void setId(ObjectId id) { this.id = id; }

    public String getModelName() { return modelName; }
    public void setModelName(String modelName) { this.modelName = modelName; }
}

// Configures Car discriminator value
@BsonDiscriminator(key = "_t", value = "CAR")
public class Car extends Vehicle {
    private int passengerCapacity;

    public Car() {}
    public Car(String modelName, int passengerCapacity) {
        super(modelName);
        this.passengerCapacity = passengerCapacity;
    }

    public int getPassengerCapacity() { return passengerCapacity; }
    public void setPassengerCapacity(int capacity) { this.passengerCapacity = capacity; }
}

// Configures Truck discriminator value
@BsonDiscriminator(key = "_t", value = "TRUCK")
public class Truck extends Vehicle {
    private double payloadCapacity;

    public Truck() {}
    public Truck(String modelName, double payloadCapacity) {
        super(modelName);
        this.payloadCapacity = payloadCapacity;
    }

    public double getPayloadCapacity() { return payloadCapacity; }
    public void setPayloadCapacity(double payload) { this.payloadCapacity = payload; }
}
```

#### Detailed Operations & Syntax Explanation:
- **`@BsonDiscriminator(key = "_t", value = "VEHICLE")`**: Tells the POJO provider that the field `_t` stores class metadata for subclass resolution during operations.

---

### Exercise 2: Hex ID & UUID Mapping Service
Implement an internal mapper that sits between a database `ProductEntity` (mapped using native BSON ObjectIds and binary UUID keys) and a network `ProductDto` (exposing only clean string values). Ensure proper validation checks are executed.

##### Dataset mapping Trace:

###### Database ProductEntity State:
```json
{
  "_id": { "$oid": "507f191e810c19729de860ea" },
  "productUuid": { "$binary": { "base64": "A4...", "subType": "04" } },
  "name": "Server Rack"
}
```

###### ProductDto representation:
```json
{
  "hexId": "507f191e810c19729de860ea",
  "stringUuid": "4e7a83d3-1383-4a11-a8cf-3c32e1850125",
  "name": "Server Rack"
}
```

Complete the implementation stub:

```java
package com.mongodb.systems;

import org.bson.types.ObjectId;
import java.util.UUID;

public class ProductMapper {

    // Database Entity
    public static class ProductEntity {
        private ObjectId id;
        private UUID productUuid;
        private String name;

        public ProductEntity() {}
        public ProductEntity(ObjectId id, UUID productUuid, String name) {
            this.id = id;
            this.productUuid = productUuid;
            this.name = name;
        }

        public ObjectId getId() { return id; }
        public void setId(ObjectId id) { this.id = id; }
        public UUID getProductUuid() { return productUuid; }
        public void setProductUuid(UUID uuid) { this.productUuid = uuid; }
        public String getName() { return name; }
        public void setName(String name) { this.name = name; }
    }

    // Client-facing DTO
    public static class ProductDto {
        private String hexId;
        private String stringUuid;
        private String name;

        public ProductDto() {}
        public ProductDto(String hexId, String stringUuid, String name) {
            this.hexId = hexId;
            this.stringUuid = stringUuid;
            this.name = name;
        }

        public String getHexId() { return hexId; }
        public void setHexId(String hexId) { this.hexId = hexId; }
        public String getStringUuid() { return stringUuid; }
        public void setStringUuid(String stringUuid) { this.stringUuid = stringUuid; }
        public String getName() { return name; }
        public void setName(String name) { this.name = name; }
    }

    // Map ProductEntity to ProductDto representation
    public static ProductDto toDto(ProductEntity entity) {
        if (entity == null) return null;
        String hexId = entity.getId() != null ? entity.getId().toHexString() : null;
        String strUuid = entity.getProductUuid() != null ? entity.getProductUuid().toString() : null;
        return new ProductDto(hexId, strUuid, entity.getName());
    }

    // Map ProductDto to ProductEntity representation with syntax validations
    public static ProductEntity toEntity(ProductDto dto) {
        if (dto == null) return null;
        
        ObjectId oid = null;
        if (dto.getHexId() != null && !dto.getHexId().isEmpty()) {
            // Validate that string is a valid 24-character hexadecimal ObjectId
            if (!ObjectId.isValid(dto.getHexId())) {
                throw new IllegalArgumentException("Invalid Hex ID representation");
            }
            oid = new ObjectId(dto.getHexId());
        }

        UUID uuid = null;
        if (dto.getStringUuid() != null && !dto.getStringUuid().isEmpty()) {
            // Parses standard String UUID format into binary UUID representation
            uuid = UUID.fromString(dto.getStringUuid());
        }

        return new ProductEntity(oid, uuid, dto.getName());
    }
}
```

#### Detailed Operations & Syntax Explanation:
- **`ObjectId.isValid(String hexString)`**: Validates if the string can be parsed into a 12-byte binary BSON ObjectId.
- **`UUID.fromString(String uuidString)`**: Parses standard 36-character hyphenated UUID strings.

---

### Exercise 3: CodecRegistry Customizer
Write a configuration utility that configures standard codec registries. The registry should enforce standard UUID representations, include the default codecs, and automatically build codecs for mapped entities.

##### Registry Resolution Trace:
1. Application queries `registry.get(SimplePojo.class)`.
2. First registry `getDefaultCodecRegistry` returns no match.
3. Second registry `fromProviders` queries `PojoCodecProvider`.
4. `PojoCodecProvider` scans `SimplePojo` getters/setters and constructs a dynamic Codec mapper, returning success.

Complete the implementation stub:

```java
package com.mongodb.systems;

import static org.bson.codecs.configuration.CodecRegistries.fromProviders;
import static org.bson.codecs.configuration.CodecRegistries.fromRegistries;

import com.mongodb.MongoClientSettings;
import org.bson.codecs.configuration.CodecRegistry;
import org.bson.codecs.pojo.PojoCodecProvider;

public class CustomRegistryFactory {

    /**
     * Builds a CodecRegistry configured with the default codecs and
     * an automatic PojoCodecProvider.
     */
    public static CodecRegistry buildCustomRegistry() {
        // Construct and return combined codec registries mapping POJOs automatically
        return fromRegistries(
            MongoClientSettings.getDefaultCodecRegistry(),
            fromProviders(PojoCodecProvider.builder().automatic(true).build())
        );
    }
}
```

---

### Verification Tests

Below is the JUnit 5 verification test suite. It runs tests on polymorphism mappings, UUID formatting conversions, and custom codec registries.

#### Detailed Testing & Verification Explanation:
*   **`Vehicle.class.isAnnotationPresent(BsonDiscriminator.class)`**: Asserts the class layout includes polymorphic metadata.
*   **`registry.get(SimplePojo.class)`**: Verifies that the POJO provider constructs codecs at runtime.

```java
package com.mongodb.systems;

import static org.junit.jupiter.api.Assertions.*;

import org.bson.codecs.configuration.CodecRegistries;
import org.bson.codecs.configuration.CodecRegistry;
import org.bson.codecs.pojo.PojoCodecProvider;
import org.bson.codecs.pojo.annotations.BsonDiscriminator;
import org.junit.jupiter.api.Test;
import java.util.UUID;
import org.bson.types.ObjectId;

class VehiclePolymorphismTest {

    @Test
    void testDiscriminatorAnnotations() {
        // Assert base class is annotated
        assertTrue(Vehicle.class.isAnnotationPresent(BsonDiscriminator.class), "Vehicle must have BsonDiscriminator");
        BsonDiscriminator baseAnn = Vehicle.class.getAnnotation(BsonDiscriminator.class);
        assertEquals("_t", baseAnn.key());

        // Assert sub-classes are annotated
        assertTrue(Car.class.isAnnotationPresent(BsonDiscriminator.class));
        assertEquals("CAR", Car.class.getAnnotation(BsonDiscriminator.class).value());

        assertTrue(Truck.class.isAnnotationPresent(BsonDiscriminator.class));
        assertEquals("TRUCK", Truck.class.getAnnotation(BsonDiscriminator.class).value());
    }

    @Test
    void testRegistryResolution() {
        // Verify we can compile and register these POJOs inside the standard providers
        PojoCodecProvider provider = PojoCodecProvider.builder()
                .register(Vehicle.class, Car.class, Truck.class)
                .build();
        
        CodecRegistry registry = CodecRegistries.fromRegistries(
                MongoClientSettings.getDefaultCodecRegistry(),
                CodecRegistries.fromProviders(provider)
        );

        assertNotNull(registry.get(Car.class));
        assertNotNull(registry.get(Truck.class));
    }
}

class ProductMapperTest {

    @Test
    void testEntityToDtoConversion() {
        ObjectId oid = new ObjectId();
        UUID uuid = UUID.randomUUID();
        ProductMapper.ProductEntity entity = new ProductMapper.ProductEntity(oid, uuid, "Enterprise Router");

        ProductMapper.ProductDto dto = ProductMapper.toDto(entity);
        assertNotNull(dto);
        assertEquals(oid.toHexString(), dto.getHexId());
        assertEquals(uuid.toString(), dto.getStringUuid());
        assertEquals("Enterprise Router", dto.getName());
    }

    @Test
    void testDtoToEntityConversion() {
        String hexId = new ObjectId().toHexString();
        String uuidStr = UUID.randomUUID().toString();
        ProductMapper.ProductDto dto = new ProductMapper.ProductDto(hexId, uuidStr, "DB Server");

        ProductMapper.ProductEntity entity = ProductMapper.toEntity(dto);
        assertNotNull(entity);
        assertEquals(hexId, entity.getId().toHexString());
        assertEquals(uuidStr, entity.getProductUuid().toString());
        assertEquals("DB Server", entity.getName());
    }

    @Test
    void testInvalidHexIdThrowsException() {
        ProductMapper.ProductDto dto = new ProductMapper.ProductDto("invalid-hex-id", UUID.randomUUID().toString(), "Broken Product");
        assertThrows(IllegalArgumentException.class, () -> ProductMapper.toEntity(dto));
    }
}

class CustomRegistryFactoryTest {

    @Test
    void testCombinedRegistryConfiguration() {
        CodecRegistry registry = CustomRegistryFactory.buildCustomRegistry();
        assertNotNull(registry);

        // Verify it contains base codecs
        assertNotNull(registry.get(String.class));
        assertNotNull(registry.get(org.bson.types.ObjectId.class));

        // Verify it dynamically resolves a simple POJO
        assertNotNull(registry.get(SimplePojo.class));
    }

    public static class SimplePojo {
        private String value;
        public SimplePojo() {}
        public String getValue() { return value; }
        public void setValue(String val) { this.value = val; }
    }
}
```
