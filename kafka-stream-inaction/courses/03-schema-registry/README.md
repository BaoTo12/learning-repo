# Course 3: Schema Registry, Serialization & Schema Evolution

This course explores the architecture and design patterns of Confluent Schema Registry, mapping out schema formats (Avro, Protobuf, JSON Schema), data governance strategies, compatibility checks, and schema references in Java environments.

## Course Syllabus

*   [Module 01: Schema Registry Architecture & REST API](file:///c:/Users/Admin/Desktop/projects/learning-repo/kafka-stream-inaction/courses/03-schema-registry/01-architecture-rest-api.md)
    *   REST API communication, local schema caches, and leader/secondary node replication architecture.
    *   Compacted `_schemas` topic storage.
*   [Module 02: Subject Name Strategies](file:///c:/Users/Admin/Desktop/projects/learning-repo/kafka-stream-inaction/courses/03-schema-registry/02-subject-name-strategies.md)
    *   Deep dive into `TopicNameStrategy`, `RecordNameStrategy`, and `TopicRecordNameStrategy`.
    *   Multi-type topics vs. single-type constraints.
*   [Module 03: Schema Compatibility & Evolution](file:///c:/Users/Admin/Desktop/projects/learning-repo/kafka-stream-inaction/courses/03-schema-registry/03-schema-compatibility-evolution.md)
    *   Sane schema evolution using `BACKWARD`, `FORWARD`, `FULL`, and `NONE` modes.
    *   Transitive variations (`BACKWARD_TRANSITIVE`, `FORWARD_TRANSITIVE`, `FULL_TRANSITIVE`).
    *   Upgrade sequences: consumers first vs. producers first.
*   [Module 04: Schema References & Multi-Event Topics](file:///c:/Users/Admin/Desktop/projects/learning-repo/kafka-stream-inaction/courses/03-schema-registry/04-schema-references-multi-types.md)
    *   Reusing nested schemas via references (`$ref` and `import`).
    *   Restricting multi-event topics using union types (Avro) and `oneof` blocks (Protobuf).
    *   Configuring `auto.register.schemas=false` and `use.latest.version=true` patterns.
*   [Module 05: Raw Serdes & Custom Serializers](file:///c:/Users/Admin/Desktop/projects/learning-repo/kafka-stream-inaction/courses/03-schema-registry/05-custom-serdes-implementation.md)
    *   Implementing custom serializing tools using Jackson ObjectMapper.
    *   Configuring Java client serializers and deserializers.

---

## Build System Configuration (Gradle)

To enable code generation from schema definitions, configure the following plugins in your `build.gradle` file:

```groovy
plugins {
    id 'java'
    id 'com.github.davidmc24.gradle-avro-plugin' version '1.8.0'
    id 'com.google.protobuf' version '0.9.4'
    id 'com.github.imflog.kafka-schema-registry-gradle-plugin' version '1.11.1'
    id 'com.github.eirnym.js2p' version '1.6.0'
}

repositories {
    mavenCentral()
    maven { url "https://packages.confluent.io/maven/" }
}

dependencies {
    implementation 'org.apache.kafka:kafka-clients:3.4.0'
    
    // Confluent Serializers
    implementation 'io.confluent:kafka-avro-serializer:7.4.0'
    implementation 'io.confluent:kafka-protobuf-serializer:7.4.0'
    implementation 'io.confluent:kafka-json-schema-serializer:7.4.0'
    
    // Jackson JSON Binding
    implementation 'com.fasterxml.jackson.core:jackson-databind:2.15.2'
}

// Configuration for Schema Registry Plugin
schemaRegistry {
    url = 'http://localhost:8081'
    register {
        subject('avro-avengers-value', 'src/main/avro/avenger.avsc', 'AVRO')
    }
}

// Protobuf Compiler Integration
protobuf {
    protoc {
        artifact = 'com.google.protobuf:protoc:3.25.0'
    }
    generateProtoTasks {
        all().each { task ->
            task.builtins {
                java {}
            }
        }
    }
}

// JSON Schema Code Generation
jsonSchema2Pojo {
    source = files("${project.projectDir}/src/main/json")
    targetDirectory = file("${project.buildDir}/generated-main-json-java")
    targetPackage = 'bbejeck.chapter_3.json'
}
```
### Schema Source File Directories
*   **Avro schemas** (`.avsc`): Place in `src/main/avro/`
*   **Protobuf schemas** (`.proto`): Place in `src/main/proto/`
*   **JSON Schema files** (`.json`): Place in `src/main/json/`
*   **To compile schemas and generate Java model files**:
    ```bash
    ./gradlew generateAvroJava generateProto generateJsonSchema2Pojo
    ```
