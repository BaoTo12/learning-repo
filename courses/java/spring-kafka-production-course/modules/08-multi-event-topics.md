# Module 08 — Multi Event Type Topics

In this module, we will discuss Multi Event Type Topics. We will explore how domain event architectures can leverage a shared topic to preserve message ordering across different actions. We will examine the Event Envelope pattern and detail Event Versioning. Next, we will cover how to implement polymorphic deserialization in Spring Boot using custom headers and message converters. Finally, we will study Avro RecordNameStrategy configurations, troubleshoot multi-event topics, review Socratic questions, and implement hands-on labs with complete code structures.

---

## 1. Academic Lecture: Envelope Pattern, Polymorphic Mapping & RecordNameStrategy

### Basic Level: Domain Event Architecture & Shared Topics

#### Single Event Type vs. Multi Event Type Topics
In typical Kafka setups, we define one topic per event type (e.g. `user-created-topic`, `user-updated-topic`, `user-deleted-topic`).
* **The Problem**: When events relating to the same entity are split across multiple topics, preserving absolute chronological order is impossible. A `UserUpdated` event published to one topic might be processed by consumers before the `UserCreated` event from another topic due to partition lag or network issues.
* **The Solution**: Use a **Multi Event Type Topic** (e.g. a single `user-lifecycle` topic). By publishing all lifecycle events to the same topic and using the identical partition key (e.g. `userId`), we guarantee they are stored in the exact sequence they happened in the database.

#### The Event Envelope Pattern
To handle multiple event types on a single topic, we wrap the event data inside a standard metadata **Envelope**.
* **Payload**: The specific event details (e.g., `UserCreated` attributes).
* **Metadata Envelope**: Standard headers wrapping the payload. It contains:
  * `eventId`: Unique UUID for tracking.
  * `eventType`: Identifies the schema of the inner payload (e.g., `"UserCreated"`, `"UserUpdated"`).
  * `timestamp`: When the event occurred.
  * `version`: Version of the payload schema.

---

### Intermediate Level: Polymorphic Deserialization in Spring Kafka

#### How Spring Handles Multiple Payload Types
When a consumer listens to a shared topic containing different classes, the JSON deserializer must decide which Java class to instantiate. Spring Kafka provides two main solutions:
1. **Spring Header Type Mapping**: The producer injects a type mapping header (e.g. `__TypeId__` set to the fully qualified class name or a short identifier like `"user-created"`).
2. **Polymorphic Message Converter**: We register a `RecordMessageConverter` bean (`StringJsonMessageConverter`). We configure its `DefaultJackson2JavaTypeMapper` to inspect the type identifier in the message headers and map it to a specific class on the consumer classpath.

```text
  [ Incoming Record ] ──► [ Header: __TypeId__ = "user-created" ]
                                      │
                                      ▼
                        [ RecordMessageConverter ]
                                      │
                        (Maps to UserCreated.class)
                                      │
                                      ▼
                      [ @KafkaHandler Method Signature ]
```

---

### Advanced Level: Avro RecordNameStrategy & Union Schemas

When using Avro instead of JSON for multi-event topics, we cannot rely on standard topic naming strategies.

#### RecordNameStrategy vs TopicRecordNameStrategy
* **TopicNameStrategy** (Default): Registers schemas under `<topic-name>-value`. This limits the topic to exactly one schema type.
* **RecordNameStrategy**: Registers schemas under the fully qualified class name of the Avro record (e.g., `com.springkafka.avro.UserCreated`). This allows multiple Avro schemas to share the same topic.
* **TopicRecordNameStrategy**: Registers schemas under `<topic-name>-<record-name>`. Useful if you want to reuse schemas across different topics but validate compatibility within the scope of a single topic.

#### Avro Unions for Envelope Payload
An alternative Avro approach is to use a single Avro schema that contains a **Union** of all possible events:
```json
{
  "name": "UserEnvelope",
  "type": "record",
  "fields": [
    { "name": "header", "type": "EnvelopeHeader" },
    { "name": "payload", "type": ["UserCreated", "UserUpdated", "UserDeleted"] }
  ]
}
```
* *Pros*: Simple TopicNameStrategy compatibility; the schema registry checks the wrapper schema.
* *Cons*: The schema file grows very large as new event types are added.

---

## 2. Theory & Production Best Practices

### Topic Partitioning: Single Type vs. Shared Topic

| Feature | Single Type per Topic (`user-created`) | Shared Multi-Event Topic (`user-events`) |
| :--- | :--- | :--- |
| **Strict Ordering Guarantee** | No (broken across topics) | Yes (when sharing partition keys) |
| **Consumer Typing** | Simple (single static type) | Complex (requires polymorphic routing) |
| **Metadata Consistency** | Hard to enforce | Easy (standard wrapper envelope) |
| **Schema Validation** | Simple (topic-value subject) | Harder (requires RecordNameStrategy) |

### JSON Header Mapping vs. Avro Union Schemas

| Approach | Setup Overhead | Evolution Flexibility | Serialization Speed |
| :--- | :--- | :--- | :--- |
| **JSON Header Mapping** | Low | High (decoupled classes) | Medium (text parsing) |
| **Avro Union Schemas** | Medium | Low (must update union list) | Very High (binary format) |
| **Avro RecordNameStrategy**| High | High (independent registries) | Very High (binary format) |

---

## 3. Common Errors & Troubleshooting

### 1. ClassCastException: LinkedHashMap Cannot Be Cast to Target Class
* **Symptom**: Listener throws `ClassCastException: java.util.LinkedHashMap cannot be cast to com.springkafka.course.model.UserCreated`.
* **Root Cause**: The type mapper did not find a mapping header (`__TypeId__`) in the record. As a fallback, Jackson deserializes the payload into a generic JSON map (`LinkedHashMap`) instead of your domain model.
* **Fix**: Ensure the producer's `KafkaTemplate` is configured with a type mapper that matches the consumer's configuration, and verify the header exists on the message.

### 2. Schema Registry Incompatibility Errors (422) on Shared Topic
* **Symptom**: Avro schema registration fails with `422 Unprocessable Entity` when writing a new class to a shared topic.
* **Root Cause**: The producer is using `TopicNameStrategy`, so the registry tries to validate the new schema against the previous schema registered under `topic-value` (which is a different event type).
* **Fix**: Configure `value.subject.name.strategy = io.confluent.kafka.serializers.subject.RecordNameStrategy` in the producer properties.

### 3. Out-of-Order Lifecycle Execution due to Key Mismatches
* **Symptom**: Database errors occur because a `UserUpdated` event is processed before a `UserCreated` event.
* **Root Cause**: The events were published to the shared topic, but the producer used different partition keys (e.g. using `transactionId` for updates and `userId` for creation), placing them in different partitions.
* **Fix**: Force all lifecycle events of an entity to use the identical unique identifier (`userId`) as the Kafka partition key.

---

## 4. Socratic Review Questions

### Question 1
*Why is a multi-event topic architecture preferred for domain entity lifecycles over separate topics?*
* **Answer**: Because lifecycles require strict execution order (Create -> Update -> Delete). By putting all lifecycle events on one topic and partitioning them by the entity key (e.g., `userId`), Kafka guarantees they are appended to the same partition log and read by a single consumer thread in the exact order of creation.

### Question 2
*How does `RecordNameStrategy` allow a single Kafka topic to support multiple distinct Avro schemas?*
* **Answer**: By default, confluent serializers register schemas using the topic name (`<topic>-value`). `RecordNameStrategy` overrides this behavior and registers schemas under their fully qualified Java class names (`com.example.UserCreated`). Because the subject names are independent of the topic, the Schema Registry manages compatibility checks for each schema type separately, allowing them to co-exist on the same topic.

### Question 3
*What is the purpose of the `RecordMessageConverter` bean in a Spring Kafka consumer setup?*
* **Answer**: It intercepts incoming raw `ConsumerRecord` byte arrays, extracts the type mapping headers (like `__TypeId__`), maps the class identifier to a local class type, and deserializes the payload before passing it to the `@KafkaHandler` listener method.

### Question 4
*What happens if a Spring `@KafkaListener` annotated class receives a payload type that has no matching `@KafkaHandler` method?*
* **Answer**: Spring Kafka throws a `NoSuchMethodException` or handler resolution exception. If you have not configured a fallback handler, the message will fail processing and block the partition offset. You must define a default handler using `@KafkaHandler(isDefault = true)`.

### Question 5
*How does changing a field type in `UserUpdated` affect the versioning of the envelope schema?*
* **Answer**: It does not change the version of the envelope wrapper metadata schema. It changes the schema version of the inner payload (`UserUpdated`). The envelope registry stays version 1, while `UserUpdated` schema evolves to version 2 in the registry under `RecordNameStrategy`.

---

## 5. Hands-on Labs

### Lab 8.1 — JSON Polymorphic Mapping with RecordMessageConverter

#### Scenario
We will create three event POJOs (`UserCreated`, `UserUpdated`, `UserDeleted`) and configure a Spring Boot consumer using a `RecordMessageConverter` that dynamically maps JSON string payloads to concrete classes based on type headers.

#### Domain Event Models
Create the following files under [model](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/src/main/java/com/springkafka/course/model/):

##### UserCreated.java
```java
package com.springkafka.course.model;

public class UserCreated {
    private String userId;
    private String email;
    private String fullName;

    public UserCreated() {}
    public UserCreated(String userId, String email, String fullName) {
        this.userId = userId;
        this.email = email;
        this.fullName = fullName;
    }
    public String getUserId() { return userId; }
    public String getEmail() { return email; }
    public String getFullName() { return fullName; }
}
```

##### UserUpdated.java
```java
package com.springkafka.course.model;

public class UserUpdated {
    private String userId;
    private String fullName;

    public UserUpdated() {}
    public UserUpdated(String userId, String fullName) {
        this.userId = userId;
        this.fullName = fullName;
    }
    public String getUserId() { return userId; }
    public String getFullName() { return fullName; }
}
```

##### UserDeleted.java
```java
package com.springkafka.course.model;

public class UserDeleted {
    private String userId;

    public UserDeleted() {}
    public UserDeleted(String userId) {
        this.userId = userId;
    }
    public String getUserId() { return userId; }
}
```

#### Complete Configuration Java Code
Create the file [PolymorphicConfig.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/src/main/java/com/springkafka/course/config/PolymorphicConfig.java) with the following content:

```java
package com.springkafka.course.config;

import com.springkafka.course.model.UserCreated;
import com.springkafka.course.model.UserUpdated;
import com.springkafka.course.model.UserDeleted;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.kafka.support.converter.RecordMessageConverter;
import org.springframework.kafka.support.converter.StringJsonMessageConverter;
import org.springframework.kafka.support.mapping.DefaultJackson2JavaTypeMapper;
import org.springframework.kafka.support.mapping.Jackson2JavaTypeMapper;

import java.util.HashMap;
import java.util.Map;

@Configuration
public class PolymorphicConfig {

    // 1. Configure the polymorphic record message converter
    @Bean
    public RecordMessageConverter multiTypeConverter() {
        StringJsonMessageConverter converter = new StringJsonMessageConverter();
        DefaultJackson2JavaTypeMapper typeMapper = new DefaultJackson2JavaTypeMapper();
        
        // Use mapping ID in headers rather than absolute Java class path names for decoupling
        typeMapper.setTypePrecedence(Jackson2JavaTypeMapper.TypePrecedence.TYPE_ID);
        
        Map<String, Class<?>> mappings = new HashMap<>();
        mappings.put("user.created", UserCreated.class);
        mappings.put("user.updated", UserUpdated.class);
        mappings.put("user.deleted", UserDeleted.class);
        
        typeMapper.setIdClassMapping(mappings);
        converter.setTypeMapper(typeMapper);
        return converter;
    }
}
```

---

### Lab 8.2 — Avro RecordNameStrategy Configuration

#### Scenario
We will configure a Spring Kafka Producer to publish multiple Avro schemas to a single topic by using the `RecordNameStrategy` in the Schema Registry properties.

#### Application Properties Configuration (`application.yml`)
Add these custom properties to override default subject naming behaviors:

```yaml
spring:
  kafka:
    producer:
      key-serializer: org.apache.kafka.common.serialization.StringSerializer
      value-serializer: io.confluent.connect.kafka.avro.KafkaAvroSerializer
      properties:
        schema.registry.url: http://localhost:8081
        # Configure Avro serialization subject naming strategy to use record name instead of topic
        value.subject.name.strategy: io.confluent.kafka.serializers.subject.RecordNameStrategy
```

#### Complete Producer Java Code
Create the file [MultiEventAvroProducer.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/src/main/java/com/springkafka/course/producer/MultiEventAvroProducer.java) with the following content:

```java
package com.springkafka.course.producer;

import org.apache.avro.specific.SpecificRecord;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Service;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

@Service
public class MultiEventAvroProducer {
    private static final Logger log = LoggerFactory.getLogger(MultiEventAvroProducer.class);

    // Using base interface type SpecificRecord to handle multiple Avro types
    private final KafkaTemplate<String, SpecificRecord> kafkaTemplate;

    public MultiEventAvroProducer(KafkaTemplate<String, SpecificRecord> kafkaTemplate) {
        this.kafkaTemplate = kafkaTemplate;
    }

    public void publishEvent(String userId, String topic, SpecificRecord eventPayload) {
        log.info("Routing Avro payload class: {} to shared topic: {}", eventPayload.getClass().getName(), topic);
        
        // Publish using entity ID as partition key to preserve ordering
        kafkaTemplate.send(topic, userId, eventPayload);
    }
}
```

---

### Lab 8.3 — Domain Event Router Listener

#### Scenario
We will create a multi-handler class using `@KafkaListener` and `@KafkaHandler` annotations to route incoming lifecycle events to specialized service methods.

#### Complete Listener Java Code
Create the file [UserLifecycleListener.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/src/main/java/com/springkafka/course/consumer/UserLifecycleListener.java) with the following content:

```java
package com.springkafka.course.consumer;

import com.springkafka.course.model.UserCreated;
import com.springkafka.course.model.UserUpdated;
import com.springkafka.course.model.UserDeleted;
import org.springframework.kafka.annotation.KafkaHandler;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Component;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

@Component
@KafkaListener(id = "user-lifecycle-group", topics = "user-lifecycle")
public class UserLifecycleListener {
    private static final Logger log = LoggerFactory.getLogger(UserLifecycleListener.class);

    // 1. Process User Creation
    @KafkaHandler
    public void handleUserCreated(UserCreated event) {
        log.info("EVENT ROUTED -> Created user with ID: {} | Email: {}", event.getUserId(), event.getEmail());
    }

    // 2. Process User Update
    @KafkaHandler
    public void handleUserUpdated(UserUpdated event) {
        log.info("EVENT ROUTED -> Updated user name to: {}", event.getFullName());
    }

    // 3. Process User Deletion
    @KafkaHandler
    public void handleUserDeleted(UserDeleted event) {
        log.info("EVENT ROUTED -> Deleted user ID: {}", event.getUserId());
    }

    // 4. Default Fallback Handler
    @KafkaHandler(isDefault = true)
    public void handleUnknown(Object unknownObject) {
        log.warn("CRITICAL -> Unmapped event type received. Payload representation: {}", unknownObject);
    }
}
```

---

### Step-by-Step Code Walkthrough & Parameter Configuration Tables

#### Step-by-Step Code Walkthrough

##### Lab 8.1 Walkthrough
1. **`multiTypeConverter`**: Registers Jackson deserializer with Spring container factory.
2. **`setIdClassMapping`**: Map custom type identifiers (like `"user.created"`) to classes. This decouples schemas, meaning that changing the class directory or packages will not break consumer serialization.
3. **Jackson Type Precedence**: Sets header type mappings as highest priority.

##### Lab 8.2 Walkthrough
1. **`RecordNameStrategy`**: Instructs the Avro serializer to register and lookup schemas using fully qualified class names.
2. **`SpecificRecord` template**: Configuring a generic template allowing the publisher to emit various class schemas without compile errors.

##### Lab 8.3 Walkthrough
1. **`@KafkaListener` at class level**: Configures group id and source topic.
2. **`@KafkaHandler`**: Directs the deserialized object parameters to matching signatures.
3. **`isDefault = true`**: Acts as a safety net. If a new developer adds a `UserSuspended` event, it is handled without throwing errors and stalling the partition.

---

### Configuration Parameter Tables

#### Spring Boot Polymorphic JSON & Avro Properties

| Configuration Property | Target Layer | Expected Value | Description |
| :--- | :--- | :--- | :--- |
| `value.subject.name.strategy` | Producer / Registry | `RecordNameStrategy` | Registers Avro schemas using fully qualified record names instead of the topic name. |
| `typePrecedence` | Jackson Mapper | `TypePrecedence.TYPE_ID` | Instructs the converter to resolve types using the header key mappings rather than raw class names. |
| `idClassMapping` | Jackson Mapper | Map of String to Class | Associates a header key to a Java domain class type. |
