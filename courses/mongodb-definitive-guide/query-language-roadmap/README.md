# MongoDB Query Language (MQL) Learning Roadmap
## Sub-Course: Production Query Engineering

Welcome to the **MongoDB Query Language (MQL) Learning Roadmap**. This is an advanced, practical sub-course focused on writing, tuning, and understanding raw MongoDB queries. 

Unlike traditional courses that focus exclusively on syntax, this roadmap teaches the systems-level reasoning behind query patterns, their index utilization, and real-world database client integration.

---

## 🎮 Practice Sandbox (Docker Setup & Sample Data)

To support hands-on learning, this course includes a containerized **Practice Sandbox** pre-seeded with **470 documents** representing products, users, orders, inventory, and employee reporting relationships.

*   **Setup & Seeding Guide**: [sandbox/README.md](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/mongodb-definitive-guide/query-language-roadmap/sandbox/README.md)
*   **Docker Configuration**: [sandbox/docker-compose.yml](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/mongodb-definitive-guide/query-language-roadmap/sandbox/docker-compose.yml)
*   **Seeding Script**: [sandbox/init-db.js](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/mongodb-definitive-guide/query-language-roadmap/sandbox/init-db.js)

Navigate to the [sandbox folder](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/mongodb-definitive-guide/query-language-roadmap/sandbox/) to spin up the database and begin practicing raw query commands.

---

## 🗺️ Sub-Course Curriculum Outline

This sub-course is divided into 19 sequential modules:

*   **[Module 01: MongoDB Fundamentals & Environment Setup](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/mongodb-definitive-guide/query-language-roadmap/modules/01-mongodb-fundamentals.md)**: Explore document vs relational database models, BSON storage types, replica primary/secondary node roles, sharding concepts, Docker sandbox config, and Compass/DBeaver GUI setups.
*   **[Module 02: Query Language Fundamentals](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/mongodb-definitive-guide/query-language-roadmap/modules/02-query-language-fundamentals.md)**: Master the core read commands (`find()`, `findOne()`), equality searches across nested schemas/arrays, and comparison filters (`$eq`, `$gt`, `$in`, etc.).
*   **[Module 03: Logical Operators](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/mongodb-definitive-guide/query-language-roadmap/modules/03-logical-operators.md)**: Build advanced search criteria using logical operators (`$and`, `$or`, `$not`, `$nor`) to support complex nested logic in real systems.
*   **[Module 04: Element Operators](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/mongodb-definitive-guide/query-language-roadmap/modules/04-element-operators.md)**: Query based on dynamic field availability (`$exists`) and enforce structural checks on data schemas using type filters (`$type`).
*   **[Module 05: Array Query Operations](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/mongodb-definitive-guide/query-language-roadmap/modules/05-array-query-operations.md)**: Query arrays, exact array matches, element existence, array operators (`$all`, `$elemMatch`, `$size`), and nested arrays of subdocuments.
*   **[Module 06: Embedded Document Queries](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/mongodb-definitive-guide/query-language-roadmap/modules/06-embedded-document-queries.md)**: Navigate subdocuments via dot notation, query deeply nested objects, and evaluate embedding vs. referencing trade-offs.
*   **[Module 07: Evaluation Operators](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/mongodb-definitive-guide/query-language-roadmap/modules/07-evaluation-operators.md)**: Match patterns using `$regex` anchored range indexes, query text contents with text indexes, score text relevance, and compare regex vs. text searches.
*   **[Module 08: Projection](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/mongodb-definitive-guide/query-language-roadmap/modules/08-projection.md)**: Limit returned attributes using inclusions/exclusions, extract deeply nested paths, perform array slicing/positional selectors, and optimize Covered Queries.
*   **[Module 09: Sorting and Pagination](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/mongodb-definitive-guide/query-language-roadmap/modules/09-sorting-and-pagination.md)**: Sort records in ascending/descending order, align compound sorting keys with indexes to bypass the 32MB limit, and compare Offset vs. Keyset (Cursor) pagination designs.
*   **[Module 10: Update Query Language](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/mongodb-definitive-guide/query-language-roadmap/modules/10-update-query-language.md)**: Mutate fields in-place via updateOne/Many, use field updates (`$set`, `$unset`, `$rename`, `$inc`, `$min`, `$max`), and structure Upsert pipelines.
*   **[Module 11: Array Updates](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/mongodb-definitive-guide/query-language-roadmap/modules/11-array-updates.md)**: Learn push, pull, pop, and addToSet array operations, positional index matching, and conditional array item updates using `arrayFilters`.
*   **[Module 12: Delete Operations](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/mongodb-definitive-guide/query-language-roadmap/modules/12-delete-operations.md)**: Explore single and multi-document deletes, indexing requirements to prevent table-scan locks, safety checklists, and the Soft Delete design pattern.
*   **[Module 13: Aggregation Framework Fundamentals](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/mongodb-definitive-guide/query-language-roadmap/modules/13-aggregation-fundamentals.md)**: Explore why aggregation exists, the pipeline concept, execution model limitations (100MB RAM check, disk use), and database vs. application data processing.
*   **[Module 14: Aggregation Stages](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/mongodb-definitive-guide/query-language-roadmap/modules/14-aggregation-stages.md)**: Study Core Stages (`$match`, `$project`, `$group`, `$sort`, `$limit`, `$skip`, `$count`), Intermediate Transformations (`$addFields`, `$set`, `$unset`), and Data Reshaping (`$replaceRoot`, `$replaceWith`).
*   **[Module 15: Advanced Aggregation](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/mongodb-definitive-guide/query-language-roadmap/modules/15-advanced-aggregation.md)**: Deep dive into array unwinding (`$unwind`), multi-collection lookups (`$lookup`), recursive queries (`$graphLookup`), parallel processing (`$facet`), and execution plan optimization.
*   **[Module 16: Aggregation Expressions](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/mongodb-definitive-guide/query-language-roadmap/modules/16-aggregation-expressions.md)**: Perform computations using Arithmetic, String, Date, Conditional (`$cond`, `$switch`), Array, Object, and Type Conversion (`$convert`, `$toString`, `$toInt`, `$toDate`) expressions.
*   **[Module 17: Index-Aware Query Design](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/mongodb-definitive-guide/query-language-roadmap/modules/17-index-aware-query-design.md)**: Analyze index range scans (`IXSCAN`), compound index alignment (the ESR rule), multikey, text, sparse, partial, and TTL indexes, and query optimizations.
*   **[Module 18: Query Performance Analysis](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/mongodb-definitive-guide/query-language-roadmap/modules/18-query-performance-analysis.md)**: Audit query planner outputs using `explain()`, parse keys/docs scan statistics, configure Database Profiler tracing levels, and optimize slow execution paths.
*   **[Module 19: Transactions and Consistency](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/mongodb-definitive-guide/query-language-roadmap/modules/19-transactions-and-consistency.md)**: Execute multi-document transactions using sessions, configure read concerns (`local`, `majority`, `snapshot`), write concerns (`w:majority`, `j:true`), and analyze rollback mechanics.

---

## 🎯 Learning Objectives

By the end of this sub-course, you will be able to:
1. Spin up clean, containerized database instances locally.
2. Connect professional graphical user interface clients to inspect collections.
3. Write clean, optimal MQL search documents.
4. Reason about comparison and logical evaluations on indexes and memory.
