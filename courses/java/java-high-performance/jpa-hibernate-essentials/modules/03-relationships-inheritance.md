# Module 03: Relationships Mapping & Inheritance

## 1. What Problem This Module Solves
Designing object relationships in ORM frameworks incorrectly can introduce severe performance overhead:
*   **The Unidirectional Collection Cascade**: Configuring a unidirectional `@OneToMany` collection forces Hibernate to execute secondary `UPDATE` statements to set foreign keys after inserting child rows.
*   **Collection Delete-All Bottleneck**: Modifying an ordered unidirectional `List` collection can cause Hibernate to delete all existing association records in the join table and insert them again.
*   **Polymorphic Query Degradation**: Using table-per-class inheritance mapping forces the database optimizer to execute slow `UNION` queries when querying parent records.

This module details association types, how to map relationships efficiently, and JPA inheritance strategies.

---

## 2. Relationships Sizing and Optimization

### 2.1 Unidirectional vs Bidirectional `@OneToMany`

```
[ Unidirectional @OneToMany (Parent has List<Child>) ]
1. Insert Child (foreign key is initially set to NULL).
2. Update Child (sets foreign key pointing to Parent).
* Double execution steps. Wastes execution resources.

[ Bidirectional @OneToMany (Child has @ManyToOne mappedBy) ]
1. Insert Child (foreign key is set immediately during insert).
* Single execution step. Efficient.
```

In a bidirectional mapping, the child entity acts as the owner of the relationship (mapped using `@ManyToOne`). To prevent update statements, define helpers in the parent class to keep both sides of the association synchronized:

```java
package com.example.jpa.relations;

import jakarta.persistence.*;
import java.util.ArrayList;
import java.util.List;

@Entity
public class Parent {
    @Id
    @GeneratedValue(strategy = GenerationType.SEQUENCE)
    private Long id;

    // mappedBy points to the parent field name in the Child entity
    @OneToMany(mappedBy = "parent", cascade = CascadeType.ALL, orphanRemoval = true)
    private List<Child> children = new ArrayList<>();

    public void addChild(Child child) {
        children.add(child);
        child.setParent(this); // Synchronize bidirectional context
    }

    public void removeChild(Child child) {
        children.remove(child);
        child.setParent(null);
    }
}
```

```java
package com.example.jpa.relations;

import jakarta.persistence.*;

@Entity
public class Child {
    @Id
    @GeneratedValue(strategy = GenerationType.SEQUENCE)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY) // Always use LAZY fetch type
    @JoinColumn(name = "parent_id")
    private Parent parent;

    public void setParent(Parent parent) {
        this.parent = parent;
    }
}
```

---

## 3. Relationships Configurations

### 3.1 `@ManyToMany` (Always use `Set`, never `List`)
If you map a `@ManyToMany` association using a Java `List`, Hibernate will delete all rows from the join table and re-insert them every time you add or remove an element. Using a `Set` allows Hibernate to execute a single `DELETE` or `INSERT` statement targeting only the modified record.

### 3.2 `@ElementCollection` (Avoid for Large Collections)
`@ElementCollection` maps basic value types (like lists of strings) to a secondary table. Since the child table does not have an entity lifecycle or identifier, Hibernate must delete all existing rows and re-insert them on updates, making it unsuitable for large collections. Use a bidirectional `@OneToMany` entity mapping instead.

---

## 4. JPA Inheritance Models Compared

JPA supports four inheritance strategies, each with distinct database layouts and execution costs:

| Inheritance Strategy | Database Schema Layout | Query Performance | Data Integrity Constraints |
| :--- | :--- | :--- | :--- |
| **Single Table** | One single database table containing all columns from all subclasses, plus a discriminator column. | **Fastest**. Requires no database joins. | Weak. Subclass columns cannot be configured with `NOT NULL` constraints. |
| **Joined Table** | Separate database tables for each class. Subclass tables contain only their specific columns and map to the parent using foreign keys. | Slow. Requires executing `LEFT JOIN` queries across multiple tables. | Strong. Supports configuring `NOT NULL` constraints on subclass columns. |
| **Table per Class** | Separate database tables for each concrete subclass containing all columns. | Very Slow. Querying parent records requires running `UNION` queries across all tables. | Strong. |
| **Mapped Superclass** | Parent class is not an entity table. Subclass tables contain all inherited columns. | Fast. Cannot execute polymorphic queries targeting the parent directly. | Strong. |

---

## 5. Common Mistakes and Anti-Patterns
*   **Using `FetchType.EAGER` on Collections**: Marking collections with eager fetching. This forces Hibernate to fetch child records automatically, generating unnecessary queries (N+1 problem) and consuming database resources. Always configure associations to use `FetchType.LAZY`.
*   **Orphan Records via Unidirectional Mappings**: Deleting a child from a unidirectional list and expecting the row to be deleted from the database. Hibernate will set the foreign key column to `NULL` instead of deleting the row, creating orphan records in the database.

---

## 6. Interview Questions

### Q1: Why does updating a `@ManyToMany` list collection execute a `DELETE ALL` statement on the join table before re-inserting elements? How do you fix it?
**Answer**: 
*   **The Cause**: A Java `List` allows duplicate elements. Since the join table has no primary key or unique index, Hibernate cannot determine which duplicate list item was updated or removed. To guarantee consistency, Hibernate deletes all rows in the join table matching the parent ID and re-inserts the active elements.
*   **The Fix**: Use a `java.util.Set` instead of a `List`. A `Set` enforces uniqueness, allowing Hibernate to identify the modified element and execute a single targeted `DELETE` or `INSERT` statement.

### Q2: What are the performance and schema trade-offs between Single Table and Joined Table inheritance strategies in Hibernate?
**Answer**: 
*   **Single Table**:
    *   *Performance*: Highly optimized. Querying subclasses requires no joins, executing fast index lookups.
    *   *Schema*: Poor. Because all fields are stored in a single table, subclass-specific columns cannot enforce database-level `NOT NULL` constraints.
*   **Joined Table**:
    *   *Performance*: Poor. Fetching polymorphic entities requires executing `LEFT JOIN` statements across all subclass tables, consuming significant database CPU.
    *   *Schema*: Clean. Normalizes the data layout, allowing subclass columns to enforce `NOT NULL` constraints and foreign keys.
