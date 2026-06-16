# CS-519: Domain-Driven Design (DDD) in Java/Spring

Welcome to **CS-519: Domain-Driven Design (DDD) in Java/Spring**. I am Professor Antigravity. In this course, we will transition from building basic, database-centric CRUD applications to creating highly scalable, decoupled, domain-centric enterprise architectures.

Many developers make the mistake of jumping directly into writing database tables and JPA schemas. This creates tight coupling between the database structure and the business logic, leading to "anemic domain models," fragile codebases, and systems that are impossible to refactor. Domain-Driven Design solves this by putting the business domain at the center of the architecture, mapping out clear consistency boundaries, and defining clean interfaces between different parts of the system.

In this course, we will study **Strategic Design (Bounded Contexts, Context Mapping, Subdomains)**, **Tactical Design (Value Objects, Entities, Aggregates, Domain Services, Domain Events)**, and modern architectural patterns like **Hexagonal Architecture (Ports & Adapters)** and **CQRS / Event Sourcing** using **Java 21** and **Spring Boot 3.x**.

---

## Course Syllabus & Navigation

The course is divided into 11 detailed modules and a final application engineering capstone project:

| Module | Core Classification | Focus Topics |
| :--- | :--- | :--- |
| **01** | [Strategic DDD Foundations](file:///c:/Users/Admin/Desktop/projects/learning-repo/ddd-java-spring/modules/01-introduction-strategic-design.md) | Ubiquitous Language, Core vs. Supporting vs. Generic subdomains, domain-centric isolation. |
| **02** | [Bounded Contexts & Context Mapping](file:///c:/Users/Admin/Desktop/projects/learning-repo/ddd-java-spring/modules/02-bounded-contexts-context-mapping.md) | Bounded Context boundaries, Upstream/Downstream relations, Shared Kernel, Anticorruption Layer (ACL). |
| **03** | [Value Objects & Immutability](file:///c:/Users/Admin/Desktop/projects/learning-repo/ddd-java-spring/modules/03-value-objects.md) | Designing immutable value objects, structural equality, self-validation using Java 21 `records`. |
| **04** | [Entities & Identity Lifecycles](file:///c:/Users/Admin/Desktop/projects/learning-repo/ddd-java-spring/modules/04-entities-identity.md) | Mutable domain states, business identity generation, Rich Domain Models vs. Anemic Data Models. |
| **05** | [Aggregates & Aggregate Roots](file:///c:/Users/Admin/Desktop/projects/learning-repo/ddd-java-spring/modules/05-aggregates-aggregate-roots.md) | Aggregate boundaries, invariants, transactional consistency boundaries, referencing by ID. |
| **06** | [Domain Services](file:///c:/Users/Admin/Desktop/projects/learning-repo/ddd-java-spring/modules/06-domain-services.md) | Isolating stateless business operations, separating domain services from application services. |
| **07** | [Domain Events & Decoupling](file:///c:/Users/Admin/Desktop/projects/learning-repo/ddd-java-spring/modules/07-domain-events.md) | Event-driven modeling, Spring `ApplicationEventPublisher`, eventual consistency, outbox pattern. |
| **08** | [Repositories & Persistence Mapping](file:///c:/Users/Admin/Desktop/projects/learning-repo/ddd-java-spring/modules/08-repositories-persistence-mapping.md) | Abstracating database access, separating domain state from database schemas, Data Mappers. |
| **09** | [Hexagonal Architecture](file:///c:/Users/Admin/Desktop/projects/learning-repo/ddd-java-spring/modules/09-hexagonal-architecture.md) | Ports & Adapters design, Onion/Clean architecture, strict domain isolation rules. |
| **10** | [CQRS & Event Sourcing](file:///c:/Users/Admin/Desktop/projects/learning-repo/ddd-java-spring/modules/10-cqrs-event-sourcing.md) | Command/Query segregation, custom event store, dynamic read-model projections. |
| **11** | [Final Capstone Project](file:///c:/Users/Admin/Desktop/projects/learning-repo/ddd-java-spring/modules/11-final-capstone-checkout-service.md) | Building a complete, secure E-Commerce checkout microservice utilizing Hexagonal Architecture. |

---

## Strategic Hexagonal Architecture Project Layout

In our tactical implementations, we will enforce strict directory boundaries to separate our core domain logic from framework dependencies. We configure our projects using the **Hexagonal Architecture** layout:

```
ddd-java-spring/
├── domain/
│   ├── model/         <-- Aggregate Roots, Entities, Value Objects (Zero external deps)
│   ├── event/         <-- Domain Events representing state changes
│   └── service/       <-- Stateless Domain Services representing multi-object logic
├── ports/
│   ├── inbound/       <-- Use Cases (interfaces called by controllers/external inputs)
│   └── outbound/      <-- Repository and External Service interfaces implemented by infra
├── application/       <-- Command Handlers and Use Case implementations
└── infrastructure/
    ├── adapters/
    │   ├── inbound/   <-- REST Controllers, CLI runners, Webhook listeners
    │   └── outbound/  <-- Spring Data JPA repositories, Postgres entities, Email adapters
    └── config/        <-- Spring Bean declarations, Security, and configurations
```

---

## Grading Criteria & Defensive Success Metrics

Your progress in this course is evaluated based on the following architectural metrics:

*   **Domain Isolation and Purity (30%)**: Keeping the `domain/` directory 100% free of external library annotations (e.g. no JPA `@Entity`, `@Column`, no Jackson `@JsonProperty`, no Spring `@Component`).
*   **Aggregate Invariant Enforcement (30%)**: Ensuring that Aggregate Roots encapsulate their child entities, enforce strict data invariants, and prevent client code from making invalid modifications.
*   **Decoupled Integration & Events (20%)**: Correctly publishing and consuming asynchronous `DomainEvents` using Transactional Outbox patterns for eventual consistency.
*   **Hexagonal Boundaries Compliance (20%)**: Restricting dependency paths so that the database and web framework layers depend on the domain, but the domain never depends on them.
