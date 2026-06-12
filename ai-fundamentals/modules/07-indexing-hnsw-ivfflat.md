# Module 07: Vector Indexing & Optimization — HNSW vs. IVFFlat Indices

Welcome back, class. Today we analyze **Vector Indexing & Optimization (CS-523)**.

When a database contains only a few thousand candidate resumes, pgvector calculates the similarity distance against every record sequentially. This is called a **Flat Search (Exact Nearest Neighbor)**. While it guarantees 100% accuracy, its time complexity is $O(N)$. If your candidate database grows to millions of records, sequential calculations will exhaust CPU resources, causing search queries to take seconds to complete.

To scale queries, we trade absolute mathematical precision for search speed using **Approximate Nearest Neighbor (ANN)** indices. Today, we will study the mechanics of **IVFFlat** and **HNSW** indices, write SQL indexing scripts, and tune runtime search parameters.

---

## 1. Academic Lecture: Clusters, Graphs, and Recall-Latency Trade-offs

ANN indices speed up queries by limiting the number of vector comparisons:

### 1. IVFFlat (Inverted File Flat)
IVFFlat partitions the high-dimensional vector space into $K$ distinct regions called **Clusters** (using K-Means clustering):
*   **The Ingest**: When a vector is inserted, pgvector assigns it to the nearest cluster centroid.
*   **The Search**: When a query is run, pgvector identifies the closest cluster centroids and only searches the vectors within those clusters, skipping the rest of the database.
*   **The Trade-off**: IVFFlat is fast to build and consumes very little RAM, but its search accuracy (Recall) drops if cluster centroid parameters are poorly tuned.

### 2. HNSW (Hierarchical Navigable Small World)
HNSW structures vectors as nodes in a multi-layered graph:
*   **The structure**: Similar to a Skip List. The top layers contain sparse nodes with long-distance links. The bottom layers contain dense nodes with short-distance links.
*   **The Search**: The query starts at the top layer, jumps quickly across long-distance nodes, and descends to lower layers for local nearest-neighbor checks.
*   **The Trade-off**: HNSW provides the highest recall and lowest query latency, but it is slow to build and requires significant RAM because the entire graph index must reside in memory.

### 3. Tuning Parameters
*   **`m`**: Maximum number of connection links per node in the HNSW graph (default is 16). Higher values improve recall on high-dimensional vectors but increase index size.
*   **`ef_construction`**: Size of the dynamic candidate list evaluated during index creation. Higher values build better graphs but increase build times.
*   **`hnsw.ef_search`**: Dynamic candidate list size evaluated *during search queries*. Tuning this at runtime allows you to trade speed for accuracy.

```mermaid
graph TD
    subgraph HNSW Graph Layers
        Entry[Query Start] --> L2_Node1[Layer 2: Sparse Node 1]
        L2_Node1 -->|Long Jump| L2_Node2[Layer 2: Sparse Node 2]
        L2_Node2 -->|Descend| L1_Node1[Layer 1: Medium Node 1]
        L1_Node1 -->|Medium Jump| L1_Node2[Layer 1: Medium Node 2]
        L1_Node2 -->|Descend| L0_Node1[Layer 0: Dense Node 1]
        L0_Node1 -->|Short Jump| L0_Node2[Layer 0: Target Candidate Node]
    end
```

---

## 2. Theory vs. Production Trade-offs

### IVFFlat Indexing vs. HNSW Indexing
*   **IVFFlat Indices**:
    *   *Pro*: Low RAM usage. The index only stores cluster references, keeping memory overhead to a minimum.
    *   *Con*: High build requirements. You must load all data into the table *before* building the index. If you build IVFFlat on an empty table and insert data later, the cluster centroids become unbalanced, degrading search quality unless the index is rebuilt.
*   **HNSW Indices**:
    *   *Pro*: Incremental updates. You can build the index on an empty table. Subsequent inserts automatically link themselves into the graph structure without degrading index quality. Best query latency at scale.
    *   *Con*: High RAM footprint. Because graph pointers are traversed in real-time, the index must fit entirely in RAM, increasing server costs.
*   **Production Rule**: For high-scale, low-latency text retrieval systems where VRAM/RAM is available, always use **HNSW**. For resource-constrained environments or cold datasets, use **IVFFlat**.

---

## 3. How to Use: Building Vector Indices in SQL

Let us write the SQL migration scripts to create HNSW indexes and tune query parameters.

### A. Non-Indexed Tables scans (Anti-Pattern)

Avoid querying large databases without vector indices:

```sql
-- DANGER: Querying tables without indices.
-- For a database with 5 million candidate records, this SELECT query forces
-- a sequential table scan, calculating cosine distances for all 5 million rows,
-- locking the CPU, and timing out database connection pools.
SELECT * FROM candidate_resumes 
ORDER BY embedding <=> '[0.12, -0.45, ...]' 
LIMIT 10;
```

### B. Hardened HNSW Index Configuration (Production Pattern)

Here is the production migration. We build the index specifying the optimal cosine distance metric and tune query execution parameters.

```sql
-- 1. Create HNSW index for Cosine Distance (<=>)
-- We specify vector_cosine_ops to match our <=> search operator
-- Parameters:
-- m=16 (balanced connection edges per node)
-- ef_construction=64 (build list limit)
CREATE INDEX IF NOT EXISTS candidate_resumes_hnsw_idx 
ON candidate_resumes 
USING hnsw (embedding vector_cosine_ops) 
WITH (m = 16, ef_construction = 64);
```

Next, write the Python query script that configures the runtime search list size before executing queries:

```python
from psycopg import Connection
from typing import List, Dict, Any

class IndexedSearchEngine:
    def __init__(self, db_conn: Connection):
        self.conn = db_conn

    def execute_fast_search(self, query_vector: List[float], limit: int = 5) -> List[Dict[str, Any]]:
        results = []
        with self.conn.cursor() as cur:
            # SECURE: Set HNSW search list size for the current transaction session
            # Setting ef_search=32 increases accuracy (higher recall)
            # Default is 16; higher values scan more graph paths
            cur.execute("SET LOCAL hnsw.ef_search = 32;")
            
            query = """
                SELECT id, candidate_name, 1 - (embedding <=> %s) AS similarity
                FROM candidate_resumes
                ORDER BY embedding <=> %s
                LIMIT %s;
            """
            cur.execute(query, (query_vector, query_vector, limit))
            for row in cur.fetchall():
                results.append({
                    "id": row[0],
                    "name": row[1],
                    "score": float(row[2])
                })
        return results
```

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Mismatched Index Operators
Creating an HNSW index using `vector_l2_ops` but executing queries using the `<=>` (Cosine Distance) operator.
*   **Why it fails**: PostgreSQL ignores the index entirely and falls back to a slow, sequential table scan because the index does not match the query operator.
*   **Mitigation**: Always align your index operator class with your query operators:
    *   For `<=>` (Cosine Distance), use `vector_cosine_ops`.
    *   For `<->` (L2 Distance), use `vector_l2_ops`.
    *   For `<#>` (Dot Product), use `vector_ip_ops`.

### Pitfall 2: Setting `ef_search` too low
Setting `hnsw.ef_search = 1` to maximize query speed.
*   **Why it fails**: The search terminates almost immediately, leading to high speed but extremely low recall. The query will miss the closest matches, returning irrelevant candidates.
*   **Mitigation**: Benchmark your recall at scale, keeping `ef_search` between `16` and `64` for standard searches.

---

## 5. Socratic Review Questions

### Question 1
Why does pgvector require the HNSW index to be built specifying an operator class like `vector_cosine_ops` rather than just indexing the column?

#### Answer
A column index stores ordered structures. In vector spaces, ordering depends on the distance metric. The index layout for Euclidean distance (shortest straight line) is geometrically different from Cosine distance (narrowest angle). Specifying the operator class tells pgvector how to build the index graph links.

### Question 2
What occurs if you increase the `ef_construction` parameter from `64` to `256` when building an HNSW index?

#### Answer
The index builder will evaluate more candidate nodes during graph assembly, resulting in a more accurate graph layout with higher recall. However, this increases index build time and memory consumption during the build phase.

---

## 6. Hands-on Challenge: Configuring a HNSW Migration Script

### The Challenge
In this challenge, you will write a python method to generate the SQL statements required to build an HNSW index on a custom table.

Your task:
1.  Complete the function `generate_hnsw_sql`.
2.  Input `table_name` is the table, `column_name` is the vector column, and `metric` is either `"cosine"` or `"ip"` (inner product).
3.  Choose the correct operator class: `vector_cosine_ops` for `"cosine"`, or `vector_ip_ops` for `"ip"`.
4.  Return the SQL string formatting the `CREATE INDEX` statement.

Complete the implementation below:

```python
def generate_hnsw_sql(
    table_name: str,
    column_name: str,
    metric: str,
    m: int = 16,
    ef_construction: int = 64
) -> str:
    # 1. Determine operator class
    if metric == "cosine":
        ops = "vector_cosine_ops"
    elif metric == "ip":
        ops = "vector_ip_ops"
    else:
        raise ValueError("Invalid metric")
        
    # TODO: Complete this SQL generator.
    # Return a formatted string:
    # CREATE INDEX {table_name}_{column_name}_hnsw_idx ON {table_name} USING hnsw ({column_name} {ops}) WITH (m = {m}, ef_construction = {ef_construction});
    
    return ""
```

Write the SQL formatting code. Save the completed file and verify the index parameters match the migration specs inside `modules/07-indexing-hnsw-ivfflat.md`.
