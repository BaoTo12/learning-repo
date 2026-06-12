# Module 08: Schema-First vs. Code-First — Development Methodologies and Codegen

Welcome back, students. Today we analyze the architectural choices that determine how our GraphQL codebase is structured: **Schema-First** vs. **Code-First** development.

When starting a new GraphQL project, you must decide what constitutes the "source of truth." Do you write the Schema Definition Language (SDL) files first and build code to match, or do you write annotated Java code and let the framework generate the schema dynamically? We will study the structural trade-offs of both approaches, examine **Code Generation (Codegen)** tools, and implement programmatic **Runtime Wiring** in Java.

---

## 1. Academic Lecture: The Battle of Truth

A GraphQL API is defined by its schema. How that schema is managed determines the team coordination workflow:

### Schema-First (Contract-First) Development

In Schema-First, you write `.graphqls` schema files manually. The schema is the source of truth. Frontend and backend teams collaborate to design the schema first. Once agreed, the schema is locked. Backend engineers write Java classes that match the schema types, and frontend engineers generate client queries.

```
Schema-First Workflow:
[ Write Schema (SDL) ] ---> [ Codegen Plugin ] ---> [ Generated Java DTOs ] ---> [ Implement Resolvers ]
```

*   **Pros**: Flawless collaboration contract; frontend teams can mock endpoints immediately; prevents backend-specific database leakage into the API.
*   **Cons**: Requires maintaining duplicate models (SDL types and Java DTO classes). This duplication is mitigated using codegen tools like Netflix **DGS Codegen** or `graphql-codegen` which generate Java records/classes automatically from SDL.

### Code-First Development

In Code-First, you write standard Java classes and decorate fields and methods with annotations. During application boot, the framework parses the Java bytecode reflection models and generates the GraphQL schema in memory.

```
Code-First Workflow:
[ Write Java Classes & Annotations ] ---> [ Boot Engine parses Bytecode ] ---> [ Generated SDL Schema ]
```

*   **Pros**: Zero code duplication; extremely fast iteration for backend teams; code refactoring automatically updates the schema.
*   **Cons**: Loss of strict contract control; a backend refactor (e.g., renaming a variable) can silently change the schema, breaking frontend clients; schemas can become bloated with database-specific structures.

---

## 2. Theory vs. Production Trade-offs

### Parallel Development vs. Deployment Sync
In enterprise engineering, teams are decoupled:
*   *Schema-First* is preferred for cross-team products. Because the contract is locked, the frontend team does not wait for the backend to be deployed; they mock the types in their client and build pages in parallel.
*   *Code-First* is preferred for small internal microservices or when exposing a database directly, where rapid prototyping overrides cross-team coordination.

---

## 3. How to Use: Programmatic Runtime Wiring in Java

While Spring GraphQL encourages annotation-based controllers (`@QueryMapping`), under the hood it compiles these into raw `RuntimeWiring` registers. 

To understand how the engine links schemas to Java code without relying on annotations, we can register mappings programmatically using `RuntimeWiring.Builder`.

Here is the schema we will bind programmatically:

```graphql
type Query {
  healthCheck: String!
  employee(id: ID!): Employee
}

type Employee {
  id: ID!
  fullName: String!
}
```

Let's write our Employee record representation:

```java
package com.capstone.graphql.wiring;

public record Employee(String id, String fullName) {}
```

Now let us write the programmatic wiring customizer that registers resolvers without using Spring annotation scanning:

```java
package com.capstone.graphql.wiring;

import graphql.schema.DataFetcher;
import graphql.schema.idl.RuntimeWiring;
import graphql.schema.idl.TypeRuntimeWiring;
import org.springframework.boot.autoconfigure.graphql.GraphQlSourceBuilderCustomizer;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.util.HashMap;
import java.util.Map;

/**
 * Configuration demonstrating programmatic Runtime Wiring registration in Spring GraphQL.
 * Bypasses controller scanning to define DataFetchers manually.
 */
@Configuration
public class ProgrammaticWiringConfig {

    private final Map<String, Employee> employeeDb = new HashMap<>();

    public ProgrammaticWiringConfig() {
        employeeDb.put("emp-1", new Employee("emp-1", "Sarah Connor"));
    }

    /**
     * Customizes the GraphQlSource builder by defining explicit resolver bindings.
     */
    @Bean
    public GraphQlSourceBuilderCustomizer customWiringCustomizer() {
        // Define Query.healthCheck resolver
        DataFetcher<String> healthFetcher = env -> "SYSTEM_OPERATIONAL_OK";

        // Define Query.employee resolver
        DataFetcher<Employee> employeeFetcher = env -> {
            String id = env.getArgument("id");
            return employeeDb.get(id);
        };

        // Define Employee.fullName custom resolver
        DataFetcher<String> fullNameFetcher = env -> {
            Employee emp = env.getSource();
            return emp.fullName().toUpperCase(); // Mutate display value programmatically
        };

        return builder -> builder.runtimeWiring(wiringBuilder -> wiringBuilder
                // Bind Query fields
                .type(TypeRuntimeWiring.newTypeWiring("Query")
                        .dataFetcher("healthCheck", healthFetcher)
                        .dataFetcher("employee", employeeFetcher)
                )
                // Bind Employee fields
                .type(TypeRuntimeWiring.newTypeWiring("Employee")
                        .dataFetcher("fullName", fullNameFetcher)
                )
        );
    }
}
```

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Breaking Client Contracts silently in Code-First
In Code-First, renaming a field in a Java model class (e.g., changing `userEmail` to `emailAddress` using IDE refactoring).
*   **Symptom**: The compiled GraphQL schema shifts. When the frontend attempts to execute its existing query, the validation phase throws errors and clients crash.
*   **Mitigation**: Always implement a schema versioning registry or execute compatibility validation scripts against the generated schema during CI/CD checks.

### Pitfall 2: Schema / Class Synchronization Lag in Schema-First
Updating the `.graphqls` schema file but forgetting to run compilation tasks to generate DTOs, or writing resolvers that return incorrect return types.
*   **Symptom**: ClassCastException exceptions thrown during query execution when the engine attempts to resolve fields on returned objects.
*   **Mitigation**: Bind codegen plugins directly to the Maven `compile` or Gradle `build` lifecycles to force generation on every build.

---

## 5. Socratic Review Questions

### Question 1
Explain why Code-First development is more susceptible to exposing internal database schemas to API clients than Schema-First.

#### Answer
In Code-First development, the GraphQL schema is derived directly from Java class reflection models. 

If developers decorate their database entities (e.g., JPA `@Entity` classes) directly with GraphQL annotations to save time, the generated schema will expose all database properties (such as internal foreign keys, password hashes, or version counters) automatically. 

Schema-First prevents this by forcing developers to write a separate SDL schema file. The developer must design the API contract independently from the database representation, serving as a boundary that hides implementation details.

### Question 2
What is the role of the `RuntimeWiring` builder in `graphql-java` execution?

#### Answer
The `RuntimeWiring` builder compiles the association map between the fields declared in the static SDL schema file and the executable Java code (`DataFetcher` closures) that resolves them. 

During boot startup, the schema generator merges the type registry parsed from `.graphqls` files with the `RuntimeWiring` registry to produce the executable `GraphQLSchema` instance. Without this runtime wiring, the schema is just a static interface description file with no execution capabilities.

---

## 6. Hands-on Challenge: Programmatic Runtime Wiring Builder

### The Challenge
In this challenge, you will write a programmatic wiring function. Given a `RuntimeWiring.Builder`, you must bind a custom query field named `"currentTime"` to return a static timestamp string, and bind an entity resolver for a type named `"Report"`.

Complete the binding implementation inside the class below:

```java
package com.capstone.graphql.wiring.challenge;

import graphql.schema.DataFetcher;
import graphql.schema.idl.RuntimeWiring;
import graphql.schema.idl.TypeRuntimeWiring;

public class ProgrammaticWiringBinder {

    /**
     * Registers resolvers programmatically into the runtime wiring builder.
     * 1. Query.currentTime resolves to return static string "2026-06-12".
     * 2. Report.summary resolves to convert the parent text to uppercase.
     */
    public void registerBindings(RuntimeWiring.Builder builder) {
        // TODO: Complete this implementation.
        // DataFetcher<String> timeFetcher = env -> "2026-06-12";
        // DataFetcher<String> summaryFetcher = env -> ...;
    }
}
```

Write your code and verify the wiring bindings. Save your solution notes inside `modules/08-schema-first-vs-code-first.md`.
