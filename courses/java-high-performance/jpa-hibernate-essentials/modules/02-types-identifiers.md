# Module 02: Mapping Types and Identifier Optimizers

## 1. What Problem This Module Solves
Primary key allocation and mapping choices can introduce performance bottlenecks:
*   **The Database Sequence Bottleneck**: Querying the database sequence for every single insert statement generates excessive network round-trips.
*   **Table Generator Locking**: Using table-based identifier generation (`GenerationType.TABLE`) creates a physical table lock, blocking concurrent transactions.
*   **Non-Standard Type Serialization**: Serializing custom Java structures (like JSON properties or encryption vectors) using standard JPA mappings requires writing custom converters to avoid performance degradation.

This module details custom types mapping, identifier generation strategies, and sequence optimizers like `pooled` and `pooled-lo`.

---

## 2. Custom Type Mapping in Hibernate

Hibernate provides the `UserType` interface to map custom Java objects to database columns (e.g. encrypting strings, mapping JSON payloads).

### 2.1 Implementing a Custom UserType in Hibernate 6
Here is an example mapping a custom Java class `Money` (composed of value and currency string) to a single database VARCHAR column:

```java
package com.example.jpa.types;

import org.hibernate.engine.spi.SharedSessionContractImplementor;
import org.hibernate.usertype.UserType;
import java.io.Serializable;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Types;
import java.util.Objects;

public class MoneyUserType implements UserType<MoneyUserType.Money> {

    public static class Money implements Serializable {
        public double amount;
        public String currency;
        public Money(double amount, String currency) {
            this.amount = amount;
            this.currency = currency;
        }
    }

    @Override
    public int getSqlType() {
        return Types.VARCHAR;
    }

    @Override
    public Class<Money> returnedClass() {
        return Money.class;
    }

    @Override
    public boolean equals(Money x, Money y) {
        if (x == y) return true;
        if (x == null || y == null) return false;
        return x.amount == y.amount && x.currency.equals(y.currency);
    }

    @Override
    public int hashCode(Money x) {
        return Objects.hash(x.amount, x.currency);
    }

    @Override
    public Money nullSafeGet(ResultSet rs, int position, SharedSessionContractImplementor session, Object owner) 
            throws SQLException {
        String cell = rs.getString(position);
        if (cell == null) return null;
        String[] parts = cell.split(" ");
        return new Money(Double.parseDouble(parts[0]), parts[1]);
    }

    @Override
    public void nullSafeSet(PreparedStatement st, Money value, int index, SharedSessionContractImplementor session) 
            throws SQLException {
        if (value == null) {
            st.setNull(index, Types.VARCHAR);
        } else {
            st.setString(index, value.amount + " " + value.currency);
        }
    }

    @Override public Money deepCopy(Money value) { return value == null ? null : new Money(value.amount, value.currency); }
    @Override public boolean isMutable() { return true; }
    @Override public Serializable disassemble(Money value) { return value; }
    @Override public Money assemble(Serializable cached, Object owner) { return (Money) cached; }
    @Override public Money replace(Money original, Money target, Object owner) { return original; }
}
```

Register and use this type on entity properties:
```java
@Type(MoneyUserType.class)
private Money price;
```

---

## 3. Identifier Generation Strategies

Selecting the right primary key generation strategy determines whether statement batching is possible:

1.  **Identity Generator (`GenerationType.AUTO` / `IDENTITY`)**:
    *   *Mechanics*: Relies on auto-increment database columns.
    *   *Trade-off*: Disables statement batching. The JDBC driver must execute each insert statement immediately to retrieve the generated ID.
2.  **Sequence Generator (`GenerationType.SEQUENCE`)**:
    *   *Mechanics*: Queries a database sequence.
    *   *Trade-off*: Enables statement batching. We use sequence optimizers to minimize network round-trips.
3.  **Table Generator (`GenerationType.TABLE`)**:
    *   *Mechanics*: Uses a database table to store identifier sequences.
    *   *Trade-off*: **Extreme Anti-Pattern**. Uses write locks on the generator table, causing thread blockages under load.

---

## 4. Sequence Optimizers: Pooled and Pooled-Lo

To avoid querying the database sequence for every single insert statement, Hibernate uses sequence optimizers:

### 4.1 Pooled Optimizer
*   **How it works**: The generator queries the sequence to fetch the maximum value of the allocation block ($V$). The allocation block range is $[V - \text{incrementSize} + 1, V]$.
*   **Formula**: The database sequence is configured to increment by $N$ (e.g. 50).

### 4.2 Pooled-Lo Optimizer (Recommended)
*   **How it works**: Similar to the pooled optimizer, but the sequence value queries return the **lowest value** of the allocation block ($V$). The allocation range is $[V, V + \text{incrementSize} - 1]$.
*   **Benefit**: The values in the database match the values generated in the application, which simplifies debugging.

```
Individual sequence calls (allocationSize = 1):
INSERT 1 ──► Select nextval('seq') ──► INSERT
INSERT 2 ──► Select nextval('seq') ──► INSERT (Double the network traffic)

Pooled-Lo optimizer (allocationSize = 50):
INSERT 1 ──► Select nextval('seq') (Returns 100, application gets range 100-149 in memory)
INSERT 2 ──► Application assigns ID 101 (NO database sequence query)
INSERT 3 ──► Application assigns ID 102 (NO database sequence query)
```

### Configuring Pooled-Lo in Hibernate:
```java
@Id
@GeneratedValue(strategy = GenerationType.SEQUENCE, generator = "pooled_lo_generator")
@SequenceGenerator(
    name = "pooled_lo_generator",
    sequenceName = "order_sequence",
    allocationSize = 50 // Increment block size
)
private Long id;
```

---

## 5. Common Mistakes and Anti-Patterns
*   **Using `@GeneratedValue(strategy = GenerationType.TABLE)`**: This configuration is slow under concurrent write loads because it relies on transaction locks on a shared row in the generator table.
*   **Mismatching `allocationSize` and Sequence Increments**: Setting `allocationSize = 50` in Hibernate while the database sequence is configured with `INCREMENT BY 1`. This will cause primary key conflict exceptions because Hibernate will attempt to assign IDs that the database sequence will generate.

---

## 6. Interview Questions

### Q1: Why is the `pooled-lo` optimizer preferred over the legacy `hi/lo` sequence optimizer in Hibernate?
**Answer**: 
*   **hi/lo**: Maps sequence values using custom calculations:
    $$\text{ID} = (\text{hi} \times \text{incrementSize}) + \text{lo}$$
    This generates IDs that do not match the raw database sequence values, making it hard to debug database records. Additionally, other client applications (like Python or Go services) sharing the database cannot easily replicate this identifier logic.
*   **pooled-lo**: Returns the **lowest value** of the allocation block directly from the sequence query (e.g. returning `100` for a block size of 50). The database sequence is configured with `INCREMENT BY 50`. The generated values match the database sequence values, which simplifies debugging and supports integrations with other client applications.

### Q2: What is the performance impact of using `@GeneratedValue(strategy = GenerationType.IDENTITY)` under high-throughput batch insert workloads?
**Answer**: 
Using `GenerationType.IDENTITY` disables statement batching. The JDBC driver must execute each `INSERT` statement immediately to retrieve the database-generated ID and update the entity context. 
This forces the application to make separate network round-trips for every insert statement, increasing latency and reducing throughput. To enable batching, you must use `GenerationType.SEQUENCE` combined with a sequence optimizer.
