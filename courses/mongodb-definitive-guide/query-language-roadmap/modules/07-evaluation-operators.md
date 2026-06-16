# Module 07: Evaluation Operators (Pattern Matching & Text Search)

In this module, we will explore evaluation operators in the MongoDB Query Language (MQL), specifically focusing on `$regex` and `$text`. These operators analyze string content using pattern matching and tokenized text search. We will cover their syntax, execution mechanics, index interactions, relevance scoring, and performance trade-offs.

---

## 1. Operator Reference

Evaluation operators evaluate fields containing strings against patterns or search criteria.

### A. `$regex` (Pattern Matching)
#### Description
Matches documents where a string field matches a specified regular expression pattern.

#### Syntax
MongoDB supports two syntax styles for regular expressions:
1.  **BSON Regex Literals (Shorthand)**:
    ```javascript
    { "<field>": /pattern/options }
    ```
2.  **Operator Syntax (Required inside `$in` or for dynamic values)**:
    ```json
    { "<field>": { "$regex": "pattern", "$options": "options" } }
    ```

#### Flags/Options Reference:
*   `i`: Case-insensitivity (matches both uppercase and lowercase characters).
*   `m`: Multiline matching (enables caret `^` and dollar sign `$` anchors to match start and end of individual lines, not just the entire string).
*   `x`: Ignore whitespace characters in the pattern.
*   `s`: Matches any character including the newline character (`\n`).

#### Behavior & Index Interactions
*   **Anchored Prefix Scan (Optimal)**: If the regex pattern starts with a caret anchor (`^`) and does not use the case-insensitivity option `i` (e.g. `/^John/`), MongoDB performs an index range scan (`IXSCAN`). This is because the characters after the anchor define a prefix boundary that the B-Tree index can scan sequentially.
*   **Substring Search (Expensive)**: If the pattern does not use a prefix anchor (e.g. contains a leading wildcard like `.*john` or simply `/john/`), MongoDB cannot use the index to narrow down bounds. It must perform a full scan of all keys in the index tree or all documents on disk, causing high CPU load.
*   **Case-Insensitivity (`i`) Performance Trap**: Case-insensitivity (`i`) prevents standard index range scans because B-Tree indexes are case-sensitive. A query like `/^john/i` forces a full index scan.
    *   *Optimization*: To execute case-insensitive prefix searches efficiently, configure a **Case-Insensitive Collation** on the collection/index:
        Configure a **Case-Insensitive Collation** when creating the index visually under the Compass **Indexes** tab (under **Options**, specify `{ "locale": "en", "strength": 2 }` in the Collation document input).

#### Examples
Find users whose email address ends with `@gmail.com` (case-insensitive):
*   **MongoDB Compass Filter**:
    ```json
    { "email": { "$regex": "@gmail\\.com$", "$options": "i" } }
    ```

Find users whose username starts with `"admin"` (case-sensitive, anchored start):
*   **MongoDB Compass Filter**:
    ```json
    { "username": { "$regex": "^admin" } }
    ```

---

### B. `$text` (Full-Text Search)
#### Description
Performs full-text search on string fields indexed with a **Text Index**. It tokenizes text, removes language-specific stop-words (e.g. "the", "and", "a"), and performs **stemming** (e.g. matching "runs", "running", and "ran" to the stem "run").

#### Syntax
```json
{ "$text": { "$search": "<searchString>", "$language": "<languageCode>" } }
```

#### Behavior & Index Rules
*   **Single Index Limit**: A collection can have **at most one** text index. However, a single text index can cover multiple fields (a compound text index):
Define it in MongoDB Compass under the **Indexes** tab: Set the type of `title` and `body` fields to `"text"`.
*   **Search Types**:
    *   *Logical OR*: Space-separated words match documents containing any of the terms (e.g. `"coffee cake"` matches coffee OR cake).
    *   *Exact Phrase Match*: Wrap words in double quotes to search for exact strings: `"\"coffee cake\""`.
    *   *Negations*: Prefix a word with a minus sign (`-`) to exclude documents containing it: `"coffee -cake"`.
*   **Relevance Scoring (`textScore`)**: MongoDB computes a relevance score (`textScore`) for each matching document. You can project this metadata score using the `$meta` operator and sort the results to return the most relevant documents first:
    *   **MongoDB Compass Inputs**:
        *   *Filter Box*: `{ "$text": { "$search": "coffee" } }`
        *   *Project Box*: `{ "score": { "$meta": "textScore" } }`
        *   *Sort Box*: `{ "score": { "$meta": "textScore" } }`
*   **Performance Overhead**: Text indexes are large and slow down insert and update operations because strings must be tokenized and indexed. Use them selectively.

#### Examples
Find articles containing either `"coffee"` or `"tea"`:
*   **MongoDB Compass Filter**:
    ```json
    { "$text": { "$search": "coffee tea" } }
    ```

Find articles containing the exact phrase `"green tea"`, but excluding any article that mentions `"sugar"`:
*   **MongoDB Compass Filter**:
    ```json
    { "$text": { "$search": "\"green tea\" -sugar" } }
    ```

---

## 2. Comparing `$regex` vs. `$text` Search

| Dimension | `$regex` Pattern Match | `$text` Full-Text Search |
| :--- | :--- | :--- |
| **Search Mechanism** | Character-by-character pattern matching. | Tokenization, stemming, and stop-word filtering. |
| **Index Overhead** | Low. Uses standard B-Tree indexes. | **High**. Text indexes are larger and slow down write operations. |
| **Performance** | Fast only for prefix scans (`/^abc/`). Slow for wildcard substrings. | **Very Fast** even for large datasets. |
| **Relevance Scoring** | No. Matches are binary (yes/no). | Yes. Calculates `textScore` for ranking. |
| **Language Support** | Basic. | Advanced (ignores language-specific stop-words like "the", "and"). |
