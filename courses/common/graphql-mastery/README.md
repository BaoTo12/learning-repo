# CS-512: GraphQL Systems Engineering & Federated Architectures

Welcome to **CS-512: GraphQL Systems Engineering & Federated Architectures**. I am Professor Antigravity. In this course, we will analyze the technical details, implementation patterns, and distributed architectural strategies of GraphQL APIs.

GraphQL is often introduced simply as a "better REST" or a client query language. However, from a systems engineering perspective, GraphQL represents a fundamental shift in how APIs are structured, executed, and scaled. Rather than exposing raw database structures over flat HTTP endpoints, GraphQL defines a strongly-typed graph schema representing your business domain. It introduces a query compilation and execution engine that runs resolvers, builds selection sets, and coordinates distributed fetches across federated networks.

In this course, we will study **query execution lifecycles, N+1 query mitigations (DataLoaders), subscription transport mechanisms, security boundaries (depth/cost limits), and Apollo Federation topologies**.

---

## Course Syllabus & Navigation

The course is divided into 10 detailed modules and a final capstone project:

| Module | Core Classification | Focus Topics |
| :--- | :--- | :--- |
| **01** | [Core GraphQL Foundations](file:///c:/Users/Admin/Desktop/projects/learning-repo/graphql-mastery/modules/01-graphql-core-foundations.md) | GraphQL SDL, Object types, scalars, unions, interfaces, queries, mutations, and REST differences. |
| **02** | [Execution Lifecycle & Resolvers](file:///c:/Users/Admin/Desktop/projects/learning-repo/graphql-mastery/modules/02-execution-lifecycle-resolvers.md) | Parse, Validate, and Execute phases, Spring `@SchemaMapping` mappings, selection sets. |
| **03** | [N+1 Problem & DataLoader](file:///c:/Users/Admin/Desktop/projects/learning-repo/graphql-mastery/modules/03-n-plus-one-dataloader.md) | Resolving N+1 query problem, batch mapping (`@BatchMapping`), DataLoader context caching. |
| **04** | [Mutations & Transactions](file:///c:/Users/Admin/Desktop/projects/learning-repo/graphql-mastery/modules/04-mutations-validation-transactions.md) | Mutation payloads, JSR-380 input validation, and database transactional boundaries in resolvers. |
| **05** | [Real-time Subscriptions](file:///c:/Users/Admin/Desktop/projects/learning-repo/graphql-mastery/modules/05-realtime-subscriptions.md) | GraphQL Subscriptions, WebSocket protocols, SSE, and Project Reactor `Flux` stream wiring. |
| **06** | [Apollo Federation](file:///c:/Users/Admin/Desktop/projects/learning-repo/graphql-mastery/modules/06-federation-schema-stitching.md) | Distributed graph architecture, `@key` entity resolution, gateway query execution plans. |
| **07** | [Securing GraphQL APIs](file:///c:/Users/Admin/Desktop/projects/learning-repo/graphql-mastery/modules/07-securing-graphql-apis.md) | Vulnerability vectors, Query Depth limits, Query Complexity costs, and field-level Security. |
| **08** | [Schema-First vs. Code-First](file:///c:/Users/Admin/Desktop/projects/learning-repo/graphql-mastery/modules/08-schema-first-vs-code-first.md) | Contract design paradigms, Dgs Codegen compilation, schema runtime wiring mapping. |
| **09** | [Client Operations & Connection Spec](file:///c:/Users/Admin/Desktop/projects/learning-repo/graphql-mastery/modules/09-client-development-operations.md) | Connections pagination, Apollo client cache normalization, variables, and `HttpGraphQlClient`. |
| **10** | [Final Capstone Project](file:///c:/Users/Admin/Desktop/projects/learning-repo/graphql-mastery/modules/10-final-capstone-collaborative-gateway.md) | Building a secure, real-time Federated Collaborative Gateway with custom depth/cost limits. |

---

## Local Development Infrastructure

To execute code challenges and verify federated query plans, you will run the local infrastructure stack. Below is the multi-container configuration containing PostgreSQL, Redis, and the Apollo Router gateway.

### Docker Compose Configuration (`docker-compose.yml`)

Create this file in your `graphql-mastery` root directory:

```yaml
version: '3.8'

services:
  # PostgreSQL (Sub-service persistence store)
  postgres_db:
    image: postgres:15-alpine
    container_name: graphql_postgres
    environment:
      POSTGRES_USER: graphuser
      POSTGRES_PASSWORD: graphpassword
      POSTGRES_DB: ecom_graph
    ports:
      - "5432:5432"
    networks:
      - graphql-network

  # Redis (Distributed query response and subscription cache)
  redis_cache:
    image: redis:7.0-alpine
    container_name: graphql_redis
    ports:
      - "6379:6379"
    networks:
      - graphql-network

  # Apollo Router (Federation Gateway routing queries)
  apollo_router:
    image: ghcr.io/apollographql/router:v1.30.0
    container_name: federation_router
    ports:
      - "4000:4000"
    volumes:
      - ./router-config.yaml:/dist/config/router.yaml
    environment:
      APOLLO_ROUTER_CONFIG_PATH: /dist/config/router.yaml
    depends_on:
      - postgres_db
    networks:
      - graphql-network

networks:
  graphql-network:
    driver: bridge
```

---

## Grading Criteria & Hands-on Success Metrics

Your performance in this course is evaluated based on the following engineering metrics:

*   **Schema Design & SDL Rigor (20%)**: Defining clean, scalable SDL schemas. Correct application of interfaces, union types, connection pagination conventions, and federated entity directives.
*   **Performance Optimization (30%)**: Efficient resolver mapping. Correct resolution of N+1 database queries using Spring `@BatchMapping` or programmatic DataLoaders, and distributed query plan optimization.
*   **Security & Gatekeeping (30%)**: Enforcing query constraints. Designing filters to intercept and block deep nested structures or high-cost queries, alongside token-based field authorization.
*   **System Real-time & Scale (20%)**: Establishing low-latency WebSocket connection streams and structuring resilient federated gateways.
