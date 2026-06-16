# Module 14: Atlas, Search, and Vector Search

## 1. What Problem This Module Solves
Modern web applications require advanced search capabilities, such as fuzzy text matching, synonyms, auto-complete, and semantic vector queries. Relying on basic MongoDB regex searches (`$regex`) causes performance issues because regex queries cannot use standard indexes efficiently, resulting in costly collection scans (`COLLSCAN`) and slow response times under load.

This module addresses advanced search architectures. A senior engineer must understand Atlas Search (Lucene engine integration), index analyzers, Hierarchical Navigable Small World (HNSW) vector indexing, semantic search, and hybrid query structures. Failing to configure search indexes correctly results in slow search queries, high memory usage, and poor search relevance.

---

## 2. Why This Topic Matters
Regex searches are insufficient for modern search requirements. If a user searches for "running shoes," a regex query on "running" will miss documents containing "run" or "runs" unless complex logic is written in the application.

MongoDB Atlas integrates Apache Lucene to provide full-text search (Atlas Search) and vector search directly inside the database. This eliminates the need to deploy and sync data to an external search cluster (like Elasticsearch). This module provides the technical details required to build and query advanced search indexes.

---

## 3. Core Concepts & Internals

### 3.1 Atlas Search: Lucene Integration & Analyzers
Atlas Search integrates the **Apache Lucene** search library directly into the MongoDB process.

```
 [Application Query] ──> [mongos / mongod]
                             │
                             ▼ (Intercepts $search stage)
                     [Atlas Search Engine]
                             │
                             ▼ (Uses shared memory map)
                     [Apache Lucene Indexes] ── (Analyzers / Tokenizers)
                             │
                             ▼
                     [Data return to MongoDB]
```

#### Lucene Integration Mechanics:
*   MongoDB synchronization threads monitor collection changes in the oplog and automatically sync updates to Lucene indexes. Lucene indexes are stored as segment files on disk, separate from WiredTiger collections.
*   The search engine uses a shared memory map to query Lucene indexes, avoiding the overhead of network roundtrips.

#### Index Analyzers & Tokenizers:
*   **Analyzers**: Define how search text is processed during indexing and querying. Standard analyzers include `lucence.standard` (default), `lucene.simple`, and `lucene.whitespace`.
*   **Tokenizers**: Break text fields into individual search tokens.
*   **Token Filters**: Process tokens to prepare them for indexing:
    *   *Lower Case Filter*: Converts all tokens to lowercase.
    *   *Stemming Filter*: Reduces words to their base form (e.g. "running" and "runs" are reduced to "run").
    *   *Stopword Filter*: Removes common words (like "the," "is," "and") that do not add search relevance.

#### Dynamic vs. Static Index Mappings:
*   **Dynamic Mapping (`dynamic: true`)**: Automatically indexes all string, object, and numeric fields in documents. While convenient for prototyping, it results in large indexes and slower search performance.
*   **Static Mapping (`dynamic: false`)**: You explicitly declare which document fields are indexed, which analyzer to use, and how to tokenize values. This minimizes the search index size, reduces memory footprint, and improves search query speed.

---

### 3.2 Vector Search & HNSW Indexing
Vector Search allows applications to search for documents based on **semantic meaning** rather than exact keyword matches.

#### Embeddings & Dimensions:
*   **Embeddings**: Real-world entities (like text, images, or audio) are converted into arrays of numbers (vectors) using machine learning models (like OpenAI's text-embedding-ada-002 or HuggingFace models).
*   **Dimensions**: The length of the vector array. Dimension sizes depend on the embedding model (e.g. OpenAI's model generates 1536-dimensional vectors).

#### HNSW Vector Indexing:
*   **HNSW (Hierarchical Navigable Small World)**: A graph-based index structure that enables fast approximate nearest neighbors (ANN) searches in high-dimensional vector spaces.
*   **Distance Metrics**:
    *   *Cosine Similarity*: Measures the angle between vectors, ignoring magnitude.
    *   *Dot Product*: Measures alignment and magnitude; faster than Cosine but requires normalized vectors.
    *   *Euclidean Distance (L2)*: Measures the straight-line distance between points.
*   **HNSW Tuning Parameters**:
    *   `maxConnections`: The maximum number of connection links per node in the graph layers. Higher values improve search recall rates but increase index build times and memory size.
    *   `constructionValue`: The size of the dynamic candidate list evaluated during index builds. Higher values improve index quality at the cost of slower index build times.

---

## 4. Practical Examples

### Search Index Definition: `index-mapping.json`
```json
{
  "mappings": {
    "dynamic": false,
    "fields": {
      "name": {
        "type": "string",
        "analyzer": "lucene.standard",
        "searchAnalyzer": "lucene.standard"
      },
      "description": {
        "type": "string",
        "analyzer": "lucene.english"
      },
      "price": {
        "type": "number"
      },
      "descriptionVector": {
        "type": "knnVector",
        "dimensions": 1536,
        "similarity": "cosine"
      }
    }
  }
}
```

---

### Complete Node.js Auto-Complete Search Implementation
The following Node.js script demonstrates how to configure an auto-complete search index mapping using the edgeGram tokenizer, and query the database with fuzzy parameters.

```javascript
/**
 * Auto-Complete and Fuzzy Search Client
 * Implements Lucene autocomplete pipelines using edgeGram tokenizers.
 */
const { MongoClient } = require('mongodb');
const log = require('console');

// Search index mapping with autocomplete definition
const autocompleteIndexMapping = {
  mappings: {
    dynamic: false,
    fields: {
      name: {
        type: "autocomplete",
        analyzer: "lucene.standard",
        tokenization: "edgeGram",
        minGrams: 2,
        maxGrams: 10,
        foldDiacritics: true
      }
    }
  }
};

class AutocompleteEngine {
  constructor(uri) {
    this.client = new MongoClient(uri);
  }

  async start() {
    await this.client.connect();
    this.db = this.client.db('shop_db');
    this.products = this.db.collection('products');
    log.info("Search engine connected.");
  }

  async suggestProducts(queryText) {
    const pipeline = [
      {
        $search: {
          index: "autocomplete_idx",
          autocomplete: {
            query: queryText,
            path: "name",
            fuzzy: {
              maxEdits: 1, // Allow one character typo
              prefixLength: 1
            }
          }
        }
      },
      {
        $project: {
          _id: 0,
          name: 1,
          score: { $meta: "searchScore" }
        }
      },
      { $limit: 5 }
    ];

    try {
      const results = await this.products.aggregate(pipeline).toArray();
      return results;
    } catch (e) {
      log.error("Autocomplete search query failed:", e.message);
      return [];
    }
  }

  async close() {
    await this.client.close();
  }
}

module.exports = AutocompleteEngine;
```

---

### Complete Python Hybrid Search Script (Lucene and Vector Search)
The following Python script demonstrates how to execute fuzzy keyword searches, vector queries, and hybrid search combining both using Reciprocal Rank Fusion (RRF).

```python
#!/usr/bin/env python3
"""
Production-Ready Semantic and Hybrid Search Engine
Features Lucene full-text matching, vector similarity search, and RRF merging.
"""
import sys
import time
from pymongo import MongoClient
from pymongo.errors import PyMongoError

class ProductSearchEngine:
    def __init__(self, uri, db_name="shop_db"):
        self.client = MongoClient(uri)
        self.db = self.client[db_name]
        self.products = self.db["products"]

    def fuzzy_keyword_search(self, term):
        """Execute full-text keyword search using Lucene"""
        pipeline = [
            {
                "$search": {
                    "index": "default",
                    "text": {
                        "query": term,
                        "path": ["name", "description"],
                        "fuzzy": {"maxEdits": 2}
                    }
                }
            },
            {
                "$project": {
                    "name": 1,
                    "price": 1,
                    "score": {"$meta": "searchScore"}
                }
            },
            {"$limit": 5}
        ]
        return list(self.products.aggregate(pipeline))

    def semantic_vector_search(self, query_vector):
        """Execute vector search using HNSW indexing"""
        pipeline = [
            {
                "$vectorSearch": {
                    "index": "vector_index",
                    "path": "descriptionVector",
                    "queryVector": query_vector,
                    "numCandidates": 100,
                    "limit": 5
                }
            },
            {
                "$project": {
                    "name": 1,
                    "price": 1,
                    "score": {"$meta": "vectorSearchScore"}
                }
            }
        ]
        return list(self.products.aggregate(pipeline))

    def hybrid_search_rrf(self, term, query_vector, k=60):
        """
        Execute Hybrid Search using Reciprocal Rank Fusion (RRF).
        Merges results from keyword search and vector search.
        """
        try:
            # 1. Fetch keyword and vector search results
            keyword_results = self.fuzzy_keyword_search(term)
            vector_results = self.semantic_vector_search(query_vector)

            # 2. Apply RRF scoring: RRF_Score = sum(1 / (k + rank))
            rrf_scores = {}
            doc_map = {}

            # Score keyword results
            for rank, doc in enumerate(keyword_results, start=1):
                doc_id = doc["_id"]
                doc_map[doc_id] = doc
                rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + (1.0 / (k + rank))

            # Score vector results
            for rank, doc in enumerate(vector_results, start=1):
                doc_id = doc["_id"]
                doc_map[doc_id] = doc
                rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + (1.0 / (k + rank))

            # 3. Sort results by RRF score
            sorted_docs = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)

            hybrid_results = []
            for doc_id, score in sorted_docs[:5]:
                doc = doc_map[doc_id]
                doc["rrf_score"] = score
                hybrid_results.append(doc)

            return hybrid_results

        except PyMongoError as ex:
            print(f"Database query failed: {ex}")
            return []

if __name__ == '__main__':
    MONGO_URI = "mongodb+srv://user:pass@cluster0.mongodb.net/shop_db?retryWrites=true&w=majority"
    
    # Mock vector query (1536 dimensions initialized with zeros for demonstration)
    mock_vector = [0.0] * 1536
    mock_vector[0] = 0.42
    mock_vector[100] = 0.58

    search_engine = ProductSearchEngine(MONGO_URI)
    
    print("--- Running Keyword Search ---")
    # results = search_engine.fuzzy_keyword_search("running shoes")
    # print(results)

    print("--- Running Hybrid Search ---")
    # rrf_results = search_engine.hybrid_search_rrf("running shoes", mock_vector)
    # print(rrf_results)

---

---

## 11. Production Runbook & Deployment Guidelines

### 1. Vector Index Build Operations
Before deploying vector search indexes, check the dimension counts and similarity configurations. Changing vector properties requires dropping and rebuilding the index from scratch.

### 2. Monitoring Search Execution Latency
Check Atlas Search query times inside the console or using query logs:
```json
{ "query": { "$search": { ... } } }
```
If search query latency exceeds 200ms, configure explicit field mappings to optimize Lucene indexes.

## 12. Appendix: Advanced Troubleshooting & Operational Failure Modes

### 1. Lucene Search Index Sync Delays
*   **Failure Mode**: Updates to collection documents are not immediately reflected in search results due to replication lag or Lucene sync backlog.
*   **Resolution**: Monitor replication lag, and configure appropriate indexing query timeouts in the application layer.

### 2. HNSW Index Build Memory Spikes
*   **Failure Mode**: Building vector search indexes on large collections consumes significant memory, leading to out-of-memory crashes.
*   **Resolution**: Build vector indexes on smaller, partitioned collections, or scale database RAM resources.

### 3. Hybrid RRF Merge Failures
*   **Failure Mode**: Merging search results from Lucene and vector queries using RRF throws errors if candidate counts differ.
*   **Resolution**: Validate search candidate parameters, and use safe merging arrays in RRF scripts.

---

## 12. Enterprise Case Study: Atlas Search Sync Lag & Index Size Bloat

### 1. Scenario Description
An international e-commerce portal deployed Atlas Search for product searches and vector recommendations. During peak sales, customers complained that newly added products did not show up in searches, and query response times spiked from 50ms to 4,500ms. MongoDB Atlas consoles showed Search indexing lag metrics exceeding 20 minutes, while search node RAM usage hit 100%.

### 2. Analytical Diagnostic Investigation
The search engineering team profiled search metrics:
*   They checked search replica sync status:
    ```javascript
    db.products.aggregate([{ $searchStatus: {} }]);
    ```
*   They inspected the index mappings. The search index used "Dynamic Mapping", which instructs Lucene to index *every single field* inside all BSON documents.

**Diagnostic Findings**:
*   The dynamic search mapping generated a massive Lucene index structure, exceeding search node RAM.
*   Because Lucene ran out of memory, it began paging to disk, slowing down index update steps.
*   Since Atlas Search consumes changes from the oplog asynchronously, the slow index updates caused search results to lag behind database writes.

### 3. Step-by-Step Resolution Runbook
1.  **Define and Apply Explicit Index Mappings**:
    Disable Dynamic Mapping and define mappings only for queried fields (see config below).
2.  **Optimize Analyzer Allocations**:
    Replace heavy analyzers with specific tokenizers (like standard or edgeGram) to reduce index segment sizes.
3.  **Scale Search Node Capacity**:
    In MongoDB Atlas console, upgrade the Search Node configuration (from M30 to M40) to allocate dedicated search memory.
4.  **Implement Hybrid Query Fallbacks**:
    If search node lag metrics exceed a threshold, configure the client application to query secondary indexes as a fallback.

### 4. Code Artifact: Explicit Search Index Configuration Payload
Save this payload as `search-index-config.json` to define explicit mappings:
```json
{
  "mappings": {
    "dynamic": false,
    "fields": {
      "productName": {
        "type": "string",
        "analyzer": "lucene.standard",
        "searchAnalyzer": "lucene.standard"
      },
      "description": {
        "type": "string",
        "analyzer": "lucene.english"
      },
      "tags": {
        "type": "string"
      },
      "vectorDescription": {
        "type": "knnVector",
        "dimensions": 1536,
        "similarity": "cosine"
      }
    }
  }
}
```

### 5. Architectural Trade-offs & Lessons Learned
*   **Explicit Mappings for Search**: Never deploy dynamic mappings to production. Define search indexes explicitly to prevent Lucene index size bloat and reduce sync lag.
*   **Oplog Sync Performance**: Lucene index sync is asynchronous. If you need read-after-write consistency, do not query search nodes immediately after database writes.

---

## 13. Hands-on Lab Exercise: Evaluating Hybrid Search Query Latency

### 1. Objective and Scenario
Evaluate query latencies of hybrid search queries (vector + text query matching clauses) to compare execution speeds of combined queries.

### 2. Code Implementation: `hybrid-search.js`
Create a file named `hybrid-search.js` and paste the following code:
```javascript
const { MongoClient } = require('mongodb');

async function testSearch() {
  const client = new MongoClient("mongodb://localhost:27017");
  try {
    await client.connect();
    const db = client.db("search_db");
    
    const pipeline = [
      {
        $search: {
          compound: {
            must: [
              {
                text: {
                  query: "organic coffee",
                  path: "productName"
                }
              }
            ],
            should: [
              {
                near: {
                  origin: 5.0,
                  path: "rating",
                  pivot: 2
                }
              }
            ]
          }
        }
      },
      { $limit: 5 }
    ];
    
    const start = Date.now();
    const results = await db.collection("products").aggregate(pipeline).toArray();
    console.log(`Search execution completed in ${Date.now() - start} ms. Found ${results.length} items.`);
    
  } catch (err) {
    console.warn("Search execution failed (Atlas Search stage not supported in default standalone nodes):", err.message);
  } finally {
    await client.close();
  }
}
testSearch();
```

### 3. Lab Verification Steps
1.  Execute the search verification task:
    ```bash
    node hybrid-search.js
    ```
2.  Note how query results and execution limits are logged.

---

## 14. Search Index Mappings & Latency Tuning Reference

### 1. Key Atlas Search Mappings
Configure search properties to manage index sizes:
*   `dynamic`: Disables automatic indexing of all fields to prevent index bloat (`false`).
*   `analyzer`: The Lucene tokenizer configuration utilized for text searches (`lucene.standard`).

### 2. Operational Diagnostic Commands
Verify search status:
```javascript
// Query search status metadata for a collection
db.collection.aggregate([{ $searchStatus: {} }]);

// Inspect query performance for Lucene clauses
db.collection.aggregate([{ $searchMeta: { count: { type: "total" } } }]);
```

### 3. Senior Engineer's Production Checklist
*   [ ] Define explicit index mappings for all search properties to optimize RAM usage.
*   [ ] Set dimension parameters matching model outputs when constructing vector search indexes.
*   [ ] Monitor search lag metrics inside Atlas configurations to detect indexing bottlenecks.

---

## 15. Advanced Operational Diagnostic Playbook: Lucene Segment Merge & Disk Overhead

### 1. Lucene Segment Merge Process under the Hood
Atlas Search uses Lucene under the hood, which structures indexes into immutable segments. As database updates occur, new segments are written to disk. Periodically, Lucene runs background merge operations to combine small segments into larger ones. This process consumes significant system I/O and temporary disk space. If search nodes lack sufficient disk space, merge operations fail, segment counts spike, search query times degrade, and replication logs stall.

### 2. Operational Verification Commands
Verify search segment counts and monitor index size:
```javascript
// Query search status for index segments and sizes
db.products.aggregate([
  { $searchStatus: { showDetails: true } }
]);
```
Analyze the returned JSON payload. Pay close attention to:
*   `numSegments`: The number of search index segments. If this number is larger than 50, Lucene is falling behind on segment merge tasks.
*   `totalIndexSizeKB`: The size of the search index on disk. Ensure this value is below 60% of the allocated search node storage capacity to leave room for temporary merge operations.

### 3. Step-by-Step Resolution Runbook
1.  **Disable Dynamic Search Mappings**:
    Dynamic mapping indexes every field, creating a high volume of small, fragmented segments. Transition to explicit search mapping configurations.
2.  **Trigger Manual Segment Merges**:
    Scale search node compute tier temporarily to allocate higher I/O bandwidth, which speeds up background merge tasks.
3.  **Deploy Search Index Monitoring Alerting Rules**:
    Set up Prometheus alert thresholds for search disk utilization to trigger warnings when disk usage exceeds 75%.
