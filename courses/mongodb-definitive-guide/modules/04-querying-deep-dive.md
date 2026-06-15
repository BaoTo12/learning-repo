# Module 04: Querying Deep Dive

Welcome, student. Today we study every aspect of **Querying Deep Dive (CS-529)** using the official MongoDB Java Sync Driver.

---

## 1. What problem does this solve?
When collections scale to millions of records, applications need precise, expressive, and high-performance querying capabilities. 
In relational databases, this is solved via SQL query strings containing complex JOIN and WHERE syntax. However, SQL strings must be parsed at runtime, and mapping flat relations back to nested structures is complex.

MongoDB solves this by expressing queries directly as BSON documents. Query filters match native document shapes, including nested sub-documents and arrays, without parsing SQL text or performing slow relational joins.

---

## 2. Why does MongoDB provide this feature?
MongoDB provides complex querying builders and operators to:
*   **Leverage Rich Datatypes**: Filter on elements within arrays, evaluate sub-document properties, and perform regular expression lookups.
*   **Optimize Search Efficiency**: Enable server-side evaluation of comparison and logical filters using B-Tree indexes, sending only the final matching documents over the wire.
*   **Provide Advanced Search Modalities**: Support full-text indexes, geospatial distance queries, and type evaluation at the database layer.

---

## 3. How does it work internally or conceptually?
*   **The Query Optimizer**: When a query is received, the query optimizer parses the filter document and evaluates potential index paths. It creates multiple candidate execution plans and runs them concurrently for a brief trial period. The plan that returns results fastest is saved as the "winning plan" in the cache.
*   **Dot Notation Routing**: For nested queries (e.g. `"profile.address.zip"`), MongoDB traverses the document hierarchy byte-by-byte in BSON format, matching nested keys without deserializing the entire document into memory.
*   **Collation Engines**: Case-insensitive and localized sorting are handled by the collation engine. Collation defines language-specific rules for string comparison, including strength levels (e.g., matching character casing or accent marks).
*   **Text Search Inverted Indexes**: Text search uses an inverted index mapping words to document locations. It applies stemming rules (e.g., matching "fishing" and "fishes" to "fish") and calculates matching weights to return a text score.

---

## 4. How do we use it in Java?
We construct query criteria using static utility builders from the `com.mongodb.client.model.Filters` class, passing them to the collection's `.find()` method.

```java
import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.Filters;
import org.bson.Document;
import org.bson.conversions.Bson;

public class BasicQueryDemo {
    public void execute(MongoCollection<Document> collection) {
        Bson filter = Filters.and(
            Filters.eq("status", "ACTIVE"),
            Filters.gt("rating", 4.5)
        );
        collection.find(filter).forEach(doc -> System.out.println(doc.toJson()));
    }
}
```

---

## 5. What are the trade-offs?
*   **Pros**:
    *   **Nested Query Expressiveness**: Match nested fields and array components directly.
    *   **Dynamic Parsing**: Query builders construct safe BSON filters at compile time, eliminating SQL injection vulnerabilities.
    *   **Flexible Execution**: Collation and projection are configured per-query.
*   **Cons**:
    *   **No Joins (Standard)**: Querying across multiple collections requires either multiple round-trips or aggregate pipelines (`$lookup`), which can be slow.
    *   **Memory Cost of Bad Regex**: Unanchored regex queries run as full table scans (`COLLSCAN`), spiking CPU and memory.
    *   **Text Index Write Penalty**: Text indexes are large and slow down insert/update throughput.

---

## 6. Common Mistakes
*   **Unanchored regular expressions**: Writing `Filters.regex("sku", "102")` instead of `Filters.regex("sku", "^102")`. Without the leading caret (`^`), MongoDB cannot perform index range scans and must read every document in the collection.
*   **Confusing Null vs. Missing fields**: Searching for a field equal to `null` (`Filters.eq("deletedAt", null)`) also matches documents where the field `deletedAt` does not exist at all.
*   **Offset Pagination memory leak**: Using `.skip(100000).limit(20)` for deep pagination. The database engine must load and sort 100,020 documents in memory, only to discard the first 100,000.

---

## 7. When should we use it?
*   Use comparison and logical filters for primary search screens.
*   Use `$elemMatch` when searching array properties where multiple constraints must be met by the *same* array element.
*   Use keyset (cursor-based) pagination for all unbounded user-facing feeds.

---

## 8. When should we avoid it?
*   Do not use `$regex` for complex text searches (e.g. search bars with stemming and auto-correct). Instead, use a `$text` index or integrate with dedicated search engines like Elasticsearch.
*   Do not query columns without verifying they are backed by proper indexes using the `.explain()` API.

---

## 9. Code Examples

### A. QUERY BUILDERS (`Filters`)

#### 1. Comparison & Logical Operators
Standard filter operations to query values and link criteria.

```java
import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.Filters;
import org.bson.Document;
import org.bson.conversions.Bson;
import java.util.ArrayList;
import java.util.List;

public class BasicFiltersDemo {
    public void run(MongoCollection<Document> collection) {
        // Comparison Filters
        Bson eqFilter = Filters.eq("department", "CS");                    // Equality
        Bson neFilter = Filters.ne("status", "ARCHIVED");                 // Not equal
        Bson gtFilter = Filters.gt("age", 21);                            // Greater than
        Bson gteFilter = Filters.gte("gpa", 3.5);                         // Greater than or equal
        Bson ltFilter = Filters.lt("price", 10.00);                       // Less than
        Bson lteFilter = Filters.lte("price", 10.00);                     // Less than or equal
        Bson inFilter = Filters.in("roles", "USER", "ADMIN");             // Value in list
        Bson ninFilter = Filters.nin("status", "DELETED", "INACTIVE");    // Value not in list

        // Logical Filters
        Bson logicalAnd = Filters.and(eqFilter, gteFilter);               // AND logic
        Bson logicalOr = Filters.or(Filters.eq("role", "SUPER"), gtFilter); // OR logic
        Bson logicalNot = Filters.not(Filters.eq("status", "LOCKED"));    // NOT logic

        List<Document> students = collection.find(logicalAnd).into(new ArrayList<>());
    }
}
```

#### 2. Element & Evaluation Operators
Checking structure type and computing query math.
*   `Filters.exists`: Checks if a field key is present or missing.
*   `Filters.type`: Checks field datatypes (e.g., Double vs. String).
*   `Filters.expr`: Enables comparing two fields within the same document.
*   `Filters.mod`: Matches values matching a modulo math operation.

```java
import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.Filters;
import org.bson.Document;
import org.bson.conversions.Bson;
import java.util.ArrayList;
import java.util.List;

public class ElementEvaluationDemo {
    public void run(MongoCollection<Document> collection) {
        // Element: Find documents where graduationDate is present
        Bson exists = Filters.exists("graduationDate", true);

        // Type: Find documents where 'age' is stored as an Integer (BSON Type 16)
        Bson typeCheck = Filters.type("age", "int");

        // Evaluation: Compare two fields inside the same document
        // Find documents where spentBudget exceeds allocatedBudget
        Bson expr = Filters.expr(new Document("$gt", List.of("$spentBudget", "$allocatedBudget")));

        // Modulo: Find documents where 'idNum' modulo 2 equals 0 (even IDs)
        Bson mod = Filters.mod("idNum", 2, 0);

        List<Document> results = collection.find(Filters.and(exists, expr)).into(new ArrayList<>());
    }
}
```

#### 3. Array Query Operators
Matching elements inside arrays.
*   `Filters.all`: Matches if the array contains all specified values.
*   `Filters.size`: Matches if the array has an exact length.
*   `Filters.elemMatch`: Matches if at least one subdocument in the array meets all conditions.

```java
import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.Filters;
import org.bson.Document;
import org.bson.conversions.Bson;
import java.util.ArrayList;
import java.util.List;

public class ArrayQueryDemo {
    public void run(MongoCollection<Document> collection) {
        // Matches tag arrays containing both "java" and "nosql"
        Bson all = Filters.all("tags", "java", "nosql");

        // Matches tag arrays with exactly 3 elements
        Bson size = Filters.size("tags", 3);

        // elemMatch: Matches arrays of subdocuments
        // Matches if a student has an enrollment with course "CS" AND score >= 90
        Bson elemMatch = Filters.elemMatch("enrollments", Filters.and(
            Filters.eq("course", "CS"),
            Filters.gte("score", 90.0)
        ));

        List<Document> matchedDocs = collection.find(elemMatch).into(new ArrayList<>());
    }
}
```

---

### B. ADVANCED SCENARIOS

#### 1. Dot Notation & Embedded Document Searches
Querying subdocument fields.

```java
import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.Filters;
import org.bson.Document;
import java.util.ArrayList;
import java.util.List;

public class NestedQueriesDemo {
    public void run(MongoCollection<Document> collection) {
        // Querying subdocuments via dot notation
        var filter = Filters.eq("profile.contact.address.city", "Austin");

        List<Document> austinProfiles = collection.find(filter).into(new ArrayList<>());
    }
}
```

#### 2. Null Values vs. Missing Fields
*   `Filters.eq("field", null)` matches **both** documents where the field is explicitly `null` and documents where the field does not exist at all.
*   To match **only** explicit nulls: combine `exists(true)` with `type("null")` or `eq(null)`.
*   To match **only** missing fields: use `exists(false)`.

```java
import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.Filters;
import org.bson.Document;
import org.bson.conversions.Bson;
import java.util.ArrayList;
import java.util.List;

public class NullMissingQueries {
    public void run(MongoCollection<Document> collection) {
        // 1. Matches null OR missing fields
        Bson nullOrMissing = Filters.eq("archivedAt", null);

        // 2. Matches ONLY documents with an explicit BSON null value
        Bson explicitNullOnly = Filters.and(
            Filters.exists("archivedAt", true),
            Filters.type("archivedAt", "null")
        );

        // 3. Matches ONLY documents where the field is missing completely
        Bson missingOnly = Filters.exists("archivedAt", false);

        List<Document> explicitNullDocs = collection.find(explicitNullOnly).into(new ArrayList<>());
    }
}
```

#### 3. Querying by `ObjectId`
To query documents by their database identifier, you must convert the incoming string representation to an `org.bson.types.ObjectId`. Passing a raw String to a query matching an ObjectId column will return zero results.

```java
import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.Filters;
import org.bson.Document;
import org.bson.types.ObjectId;

public class ObjectIdQueryDemo {
    public Document findById(MongoCollection<Document> collection, String hexStringId) {
        // Validate hex string length prior to instantiation
        if (hexStringId == null || hexStringId.length() != 24) {
            throw new IllegalArgumentException("Invalid Hexadecimal ObjectId");
        }

        ObjectId objectId = new ObjectId(hexStringId);
        return collection.find(Filters.eq("_id", objectId)).first();
    }
}
```

#### 4. Regex & Full-Text Search
*   **Regex Search**: Uses patterns. Anchored regular expressions (starting with `^`) can utilize indexes efficiently. Unanchored matches force collection scans.
*   **Full-Text Search**: Requires a text index on the target fields. It parses terms, removes stop words, stems keywords, and returns relevance scores.

```java
import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.Filters;
import com.mongodb.client.model.Projections;
import com.mongodb.client.model.Sorts;
import org.bson.Document;
import org.bson.conversions.Bson;
import java.util.ArrayList;
import java.util.List;

public class SearchOperationsDemo {
    public void run(MongoCollection<Document> collection) {
        // 1. Regex Match (Case-Insensitive & Anchored)
        // Highly efficient - uses prefix index scan
        Bson prefixRegex = Filters.regex("sku", "^PROD-", "i");
        List<Document> matchingSkus = collection.find(prefixRegex).into(new ArrayList<>());

        // 2. Full-Text Search
        // Matches "database" or "learning". Requires a text index.
        Bson textSearch = Filters.text("database learning");

        // Retrieve results sorted by text score relevance
        Bson projection = Projections.metaTextScore("score");
        Bson sort = Sorts.metaTextScore("score");

        List<Document> matchedText = collection.find(textSearch)
                                               .projection(projection)
                                               .sort(sort)
                                               .into(new ArrayList<>());
    }
}
```

#### 5. Case-Insensitive Search: RegEx vs. Collation
*   **RegEx Case Insensitivity (`i` flag)**: Simple to write, but prevents efficient index usage for queries that do not start with a prefix anchor.
*   **Collation (Case Insensitive Indexing)**: Set collation properties on the query and index. By using a strength of 2 (compare base characters only, ignore case and accents), queries are executed as fast index scans.

```java
import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.Collation;
import com.mongodb.client.model.CollationStrength;
import com.mongodb.client.model.Filters;
import org.bson.Document;
import java.util.ArrayList;
import java.util.List;

public class CollationDemo {
    public List<Document> queryCaseInsensitive(MongoCollection<Document> collection, String name) {
        // Set Collation configuration: strength 2 ignores case and diacritics
        Collation collation = Collation.builder()
                                       .locale("en")
                                       .collationStrength(CollationStrength.SECONDARY)
                                       .build();

        return collection.find(Filters.eq("name", name))
                         .collation(collation)
                         .into(new ArrayList<>());
    }
}
```

---

### C. PAGINATION STRATEGIES

#### 1. Offset Pagination (Skip + Limit)
Offset pagination relies on `.skip(n).limit(size)`.
*   **Internal Cost**: MongoDB fetches `n + size` documents, parses their keys, and discards the first `n` items. 
*   **Query Performance**: $O(N)$ query complexity. Performance degrades severely on deep pages.

```java
import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.Sorts;
import org.bson.Document;
import java.util.ArrayList;
import java.util.List;

public class OffsetPagination {
    public List<Document> getPage(MongoCollection<Document> collection, int pageIndex, int pageSize) {
        return collection.find()
                         .sort(Sorts.descending("createdAt"))
                         .skip(pageIndex * pageSize)
                         .limit(pageSize)
                         .into(new ArrayList<>());
    }
}
```

#### 2. Keyset / Cursor Pagination (Indexed)
Keyset pagination tracks the unique boundary value (like `_id` or `createdAt` + `_id`) of the last document on the current page to filter the next set.
*   **Internal Cost**: Executes an index range scan starting directly at the boundary. No documents are discarded.
*   **Query Performance**: $O(1)$ constant query complexity. Performance is identical on page 1 and page 10,000.

```java
import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.Filters;
import com.mongodb.client.model.Sorts;
import org.bson.Document;
import org.bson.types.ObjectId;
import java.util.ArrayList;
import java.util.List;

public class KeysetPagination {
    public List<Document> getPage(MongoCollection<Document> collection, ObjectId lastSeenId, int pageSize) {
        var filter = (lastSeenId == null) ? new Document() : Filters.gt("_id", lastSeenId);
        
        return collection.find(filter)
                         .sort(Sorts.ascending("_id"))
                         .limit(pageSize)
                         .into(new ArrayList<>());
    }
}
```

---

### D. QUERY PERFORMANCE CONCERNS

To write production-grade queries, keep these execution patterns in mind:
*   **COLLSCAN vs. IXSCAN**: A query without a backing index executes a collection scan (`COLLSCAN`), reading every byte of the collection from disk. Indexed queries perform an index scan (`IXSCAN`), quickly fetching pointers to matching documents.
*   **Index Selectivity**: An index should be highly selective. For example, indexing gender (male/female) is not selective, as queries still scan 50% of the collection. Indexing fields with high cardinality (like email, SKU, or user ID) is highly selective.
*   **Covered Queries**: If a query's filters, sorting, and projection properties all reference fields covered by a single compound index, and the `_id` field is excluded from projection, MongoDB returns results directly from the index in memory. It bypasses reading the actual documents from disk (`FETCH` stage), achieving maximum performance.

---

## 10. Hands-on Exercises

### Challenge 1: Advanced Student Filter
Implement a service method that queries an active student collection. You must retrieve all students matching these criteria:
*   `status` is `"ACTIVE"`
*   `graduationYear` is not missing (field exists)
*   Contains a nested enrollment in the `grades` array matching `courseCode = "CS-101"` AND a grade `score >= 85.0`.

Complete the implementation stub:

```java
package com.mongodb.systems;

import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.Filters;
import org.bson.Document;
import org.bson.conversions.Bson;
import java.util.ArrayList;
import java.util.List;

public class HonorRollQueryService {

    public List<Document> queryHonorStudents(MongoCollection<Document> collection) {
        // TODO: Build and return the query using Filters helper
        Bson filter = Filters.and(
            Filters.eq("status", "ACTIVE"),
            Filters.exists("graduationYear", true),
            Filters.elemMatch("grades", Filters.and(
                Filters.eq("courseCode", "CS-101"),
                Filters.gte("score", 85.0)
            ))
        );
        return collection.find(filter).into(new ArrayList<>());
    }
}
```

### Challenge 2: Keyset Pagination with Tie-Breaker
Implement a keyset pagination query. Documents are sorted primarily by `score` in descending order, and secondarily by `_id` in ascending order (tie-breaker).
*   For the first page: parameters `lastSeenScore` will be `null` and `lastSeenId` will be `null`.
*   For subsequent pages: you must build a composite range filter: `(score < lastSeenScore) OR (score == lastSeenScore AND _id > lastSeenId)`.

Complete the implementation stub:

```java
package com.mongodb.systems;

import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.Filters;
import com.mongodb.client.model.Sorts;
import org.bson.Document;
import org.bson.types.ObjectId;
import org.bson.conversions.Bson;
import java.util.ArrayList;
import java.util.List;

public class HighScorePaginationService {

    public List<Document> fetchScoresPage(MongoCollection<Document> collection, Double lastSeenScore, String lastSeenId, int pageSize) {
        // TODO: Build compound keyset pagination filters
        Bson filter;
        if (lastSeenScore == null || lastSeenId == null) {
            filter = new Document();
        } else {
            ObjectId boundaryId = new ObjectId(lastSeenId);
            filter = Filters.or(
                Filters.lt("score", lastSeenScore),
                Filters.and(
                    Filters.eq("score", lastSeenScore),
                    Filters.gt("_id", boundaryId)
                )
            );
        }

        Bson sort = Sorts.compoundSort(
            Sorts.descending("score"),
            Sorts.ascending("_id")
        );

        return collection.find(filter)
                         .sort(sort)
                         .limit(pageSize)
                         .into(new ArrayList<>());
    }
}
```

### Challenge 3: Full-Text Search relevance score sorting
Implement a full text query search. Retrieve documents matching a text query string, project their search relevance metadata score, sort by relevance score in descending order, and project only `title` and `score` (excluding the `_id`).

Complete the implementation stub:

```java
package com.mongodb.systems;

import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.Filters;
import com.mongodb.client.model.Projections;
import com.mongodb.client.model.Sorts;
import org.bson.Document;
import org.bson.conversions.Bson;
import java.util.ArrayList;
import java.util.List;

public class TextSearchService {

    public List<Document> searchCatalog(MongoCollection<Document> collection, String queryText) {
        // TODO: Perform full text search, project meta score, sort, and execute query
        Bson filter = Filters.text(queryText);
        Bson projection = Projections.fields(
            Projections.metaTextScore("score"),
            Projections.include("title"),
            Projections.excludeId()
        );
        Bson sort = Sorts.metaTextScore("score");

        return collection.find(filter)
                         .projection(projection)
                         .sort(sort)
                         .into(new ArrayList<>());
    }
}
```

### Verification Tests
Verify all three query challenges using this JUnit 5 verification test suite:

```java
package com.mongodb.systems;

import com.mongodb.client.MongoCollection;
import com.mongodb.client.FindIterable;
import org.bson.Document;
import org.bson.conversions.Bson;
import org.junit.jupiter.api.Test;
import java.util.List;
import static org.mockito.Mockito.*;
import static org.junit.jupiter.api.Assertions.*;

class QueryDeepDiveTest {

    @SuppressWarnings("unchecked")
    @Test
    void testQueryHonorStudents() {
        MongoCollection<Document> mockCol = mock(MongoCollection.class);
        FindIterable<Document> mockFind = mock(FindIterable.class);
        
        when(mockCol.find(any(Bson.class))).thenReturn(mockFind);
        when(mockFind.into(any())).thenReturn(List.of(new Document("name", "Alice")));

        HonorRollQueryService service = new HonorRollQueryService();
        List<Document> result = service.queryHonorStudents(mockCol);

        assertNotNull(result);
        assertEquals(1, result.size());
        verify(mockCol, times(1)).find(any(Bson.class));
    }

    @SuppressWarnings("unchecked")
    @Test
    void testFetchScoresPageFirstPage() {
        MongoCollection<Document> mockCol = mock(MongoCollection.class);
        FindIterable<Document> mockFind = mock(FindIterable.class);

        when(mockCol.find(any(Bson.class))).thenReturn(mockFind);
        when(mockFind.sort(any())).thenReturn(mockFind);
        when(mockFind.limit(anyInt())).thenReturn(mockFind);
        when(mockFind.into(any())).thenReturn(List.of(new Document("name", "Bob")));

        HighScorePaginationService service = new HighScorePaginationService();
        List<Document> result = service.fetchScoresPage(mockCol, null, null, 5);

        assertNotNull(result);
        assertEquals(1, result.size());
    }

    @SuppressWarnings("unchecked")
    @Test
    void testSearchCatalog() {
        MongoCollection<Document> mockCol = mock(MongoCollection.class);
        FindIterable<Document> mockFind = mock(FindIterable.class);

        when(mockCol.find(any(Bson.class))).thenReturn(mockFind);
        when(mockFind.projection(any())).thenReturn(mockFind);
        when(mockFind.sort(any())).thenReturn(mockFind);
        when(mockFind.into(any())).thenReturn(List.of(new Document("title", "Learn MongoDB").append("score", 1.1)));

        TextSearchService service = new TextSearchService();
        List<Document> result = service.searchCatalog(mockCol, "MongoDB");

        assertNotNull(result);
        assertEquals(1, result.size());
        assertEquals("Learn MongoDB", result.get(0).get("title"));
    }
}
```
