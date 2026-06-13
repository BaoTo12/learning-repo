# Module 03: Schema Compatibility & Evolution

Data structures inevitably change as business requirements evolve. To prevent modifications from crashing downstream consumers, Schema Registry enforces **Schema Compatibility Rules**. This module details the base compatibility modes (`BACKWARD`, `FORWARD`, `FULL`, `NONE`), their transitive variations, the exact order of upgrading producer and consumer clients, and allowed changes.

---

## 1. Schema Compatibility Matrix

Schema Registry provides four core compatibility settings. These govern which modifications (e.g., adding fields, deleting columns) are permitted when registering a new schema version under an existing subject.

| Compatibility Mode | Allowed Schema Changes | Client Upgrade Sequence | Compatibility Check |
| :--- | :--- | :--- | :--- |
| **`BACKWARD`** (Default) | • Delete fields<br>• Add optional fields (with default values) | **1. Consumers**<br>**2. Producers** | New schema version $V_x$ can read data produced by $V_{x-1}$ |
| **`FORWARD`** | • Add fields<br>• Delete optional fields | **1. Producers**<br>**2. Consumers** | Old schema version $V_{x-1}$ can read data produced by $V_x$ |
| **`FULL`** | • Add optional fields<br>• Delete optional fields | **Any order** | Bidirectional: $V_x$ reads $V_{x-1}$, and $V_{x-1}$ reads $V_x$ |
| **`NONE`** | All changes are permitted (no checks) | **Simultaneous upgrade** (or new topic) | No compatibility validations are executed |

---

## 2. Deep Dive: Compatibility Semantics and Client Upgrade Sequences

### 2.1 BACKWARD Compatibility (Consumers First)
With `BACKWARD` compatibility, a consumer using the new schema ($V_2$) is guaranteed to be able to read records produced with the previous schema ($V_1$).

```
1. Upgrade CONSUMERS to V2  ───►  Consumers read V1 records (using default values for new fields)
2. Upgrade PRODUCERS to V2  ───►  Producers write V2 records (Consumers read them normally)
```

*   **Allowed Changes**: 
    *   **Deleting fields**: The consumer simply drops the field during deserialization.
    *   **Adding optional fields**: If the new schema adds a field, it *must* have a default value. When the consumer processes older messages without that field, the deserializer populates the object field with the default.
*   **Production Risk**: If you add a field without a default value in `BACKWARD` mode, Schema Registry rejects the registration request with a compatibility check error.

### 2.2 FORWARD Compatibility (Producers First)
With `FORWARD` compatibility, a consumer using the old schema ($V_1$) is guaranteed to be able to read records written with the new schema ($V_2$).

```
1. Upgrade PRODUCERS to V2  ───►  Producers write V2 records (Old consumers ignore new fields)
2. Upgrade CONSUMERS to V2  ───►  Consumers read V2 records with full field awareness
```

*   **Allowed Changes**:
    *   **Adding fields**: The old consumer reading the new payload will ignore the new fields.
    *   **Deleting optional fields**: The field deleted in the new schema must have a default value in the old schema so that old consumers can still resolve it.

### 2.3 FULL Compatibility (Order Independent)
`FULL` compatibility combines the constraints of both `BACKWARD` and `FORWARD` compatibility.
*   **Allowed Changes**: You can add or remove fields, but **all added or removed fields must be optional** (possess default values).
*   **Upgrade Order**: It does not matter. You can deploy producers first or consumers first without breaking the stream.

---

## 3. Transitive Compatibility Modes

By default, base compatibility modes (`BACKWARD`, `FORWARD`, `FULL`) only check the new schema version against the **immediate previous version** ($V_x \leftrightarrow V_{x-1}$). 

If schemas undergo multiple revisions over time, checking only the immediate predecessor can lead to errors where older, still-running consumers crash when reading newer records. To prevent this, Schema Registry provides **Transitive** compatibility settings:

*   **`BACKWARD_TRANSITIVE`**: Enforces that the new schema version is backwards compatible with **all** previous versions ($V_x \leftrightarrow V_{x-1}, V_{x-2}, \dots, V_1$).
*   **`FORWARD_TRANSITIVE`**: Enforces that all previous schema versions can read records written using the new schema version.
*   **`FULL_TRANSITIVE`**: Enforces bidirectional compatibility across all registered schema versions.

> [!TIP]
> In production environments, **`BACKWARD_TRANSITIVE`** or **`FULL_TRANSITIVE`** are highly recommended to ensure that historical data stored in topics remains readable even after multiple iterations of schema upgrades.

---

## 4. How to Configure Subject Compatibility Levels

You can adjust compatibility levels globally or on a per-subject basis using Schema Registry's REST API.

### Set Compatibility for a Specific Subject to `FULL`
```bash
curl -X PUT -H "Content-Type: application/vnd.schemaregistry.v1+json" \
     --data '{"compatibility": "FULL"}' \
     http://localhost:8081/config/avro-avengers-value
```
*Response*:
```json
{"compatibility": "FULL"}
```
### Verify Current Compatibility of a Subject
```bash
curl -s http://localhost:8081/config/avro-avengers-value | jq
```
