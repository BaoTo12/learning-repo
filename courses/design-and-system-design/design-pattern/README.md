# Software Design Patterns & Enterprise Architectures Masterclass

Welcome to **CS-504: Advanced Software Design Patterns & Enterprise Architectures**. I am your instructor, Professor Antigravity. Over my 20+ years of building large-scale systems and teaching computer science, I've learned that code syntax is easy, but **system design is hard**. 

Many developers learn design patterns as rigid, academic recipes. This course takes a different approach. Here, you will learn to look at design patterns not as templates to copy, but as **reusable solutions to recurring object-oriented and distributed systems design problems**. We will examine the forces that drive these designs, the trade-offs they introduce, and how to write clean, idiomatic Java 21 code to implement them.

---

## Course Syllabus & Navigation

The course is divided into 11 modules, moving from local object-oriented patterns to distributed cloud-native architectures:

| Module | Classification | Covered Patterns |
| :--- | :--- | :--- |
| **01** | [Creational Patterns](file:///c:/Users/Admin/Desktop/projects/learning-repo/design-pattern/modules/01-creational-patterns.md) | Singleton, Factory Method, Abstract Factory, Builder, Prototype |
| **02** | [Structural Patterns (Part 1)](file:///c:/Users/Admin/Desktop/projects/learning-repo/design-pattern/modules/02-structural-patterns-part1.md) | Adapter, Decorator, Facade, Proxy |
| **03** | [Structural Patterns (Part 2)](file:///c:/Users/Admin/Desktop/projects/learning-repo/design-pattern/modules/03-structural-patterns-part2.md) | Composite, Bridge, Flyweight |
| **04** | [Behavioral Patterns (Part 1)](file:///c:/Users/Admin/Desktop/projects/learning-repo/design-pattern/modules/04-behavioral-patterns-part1.md) | Strategy, Observer, Command, Template Method |
| **05** | [Behavioral Patterns (Part 2)](file:///c:/Users/Admin/Desktop/projects/learning-repo/design-pattern/modules/05-behavioral-patterns-part2.md) | Chain of Responsibility, State, Iterator |
| **06** | [Behavioral Patterns (Part 3)](file:///c:/Users/Admin/Desktop/projects/learning-repo/design-pattern/modules/06-behavioral-patterns-part3.md) | Mediator, Visitor, Memento |
| **07** | [Enterprise Data Patterns](file:///c:/Users/Admin/Desktop/projects/learning-repo/design-pattern/modules/07-enterprise-data-patterns.md) | Repository, Unit of Work, Data Mapper, Active Record, DAO |
| **08** | [Enterprise Structural Patterns](file:///c:/Users/Admin/Desktop/projects/learning-repo/design-pattern/modules/08-enterprise-structural-patterns.md) | Service Layer, DTO, Dependency Injection |
| **09** | [Distributed Consistency & Events](file:///c:/Users/Admin/Desktop/projects/learning-repo/design-pattern/modules/09-distributed-consistency-and-events.md) | CQRS, Event Sourcing, Outbox Pattern |
| **10** | [Distributed Reliability & Resilience](file:///c:/Users/Admin/Desktop/projects/learning-repo/design-pattern/modules/10-distributed-reliability-and-resilience.md) | Saga, Circuit Breaker, Retry, Bulkhead |
| **11** | [Cloud Integration & Gateways](file:///c:/Users/Admin/Desktop/projects/learning-repo/design-pattern/modules/11-cloud-infrastructure-integration.md) | Rate Limiter, API Gateway, Strangler Fig |

---

## Grading Criteria & Course Success Metrics

This is a rigorous, implementation-heavy course. To pass, you must demonstrate both conceptual understanding and clean coding practices. Your work will be evaluated based on the following criteria:

*   **Software Design Principles (35%)**: How well your code applies SOLID principles. Are you programming to interfaces? Are you avoiding tight coupling?
*   **Implementation Correctness (35%)**: Your Java code must compile, run, and be thread-safe where required (e.g. Singleton, Registry pools, Outbox pollers).
*   **Trade-off Analysis (20%)**: Your ability to justify why you chose a pattern and explain the trade-offs it introduces (e.g., memory overhead, latency, cognitive complexity).
*   **Idiomatic Modern Java (10%)**: Proper use of Java 21 features (Records, Pattern Matching, Sealed Classes, Sequenced Collections) to keep implementations clean.

---

## Course Prerequisites
1.  **JDK 21**: We will use modern Java features to implement patterns cleanly.
2.  **Basic OOP Foundations**: Familiarity with inheritance, polymorphism, encapsulation, and interfaces.
3.  **Docker Desktop** (For Modules 9-11): Required to run local brokers, databases, and sidecars (e.g., Kafka, PostgreSQL, Redis) during distributed systems exercises.

---

## Professor's Advice for Success

1.  **Do not memorize the patterns**: Memorizing code structures is useless. Focus on understanding the **problem forces**—the design constraints that make a pattern necessary.
2.  **Run the demo code**: Every pattern has a complete, compile-ready Java example. Clone the files, run them locally, and experiment with changes to see what breaks.
3.  **Complete the exercises**: The mini-challenges at the end of each module are designed to test your understanding. Do not skip them!
