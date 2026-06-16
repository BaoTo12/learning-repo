# 14. Fetching

While in SQL data is represented as tuples, the object-oriented Domain Model uses graphs of entities. Hibernate takes care of the object-relational impedance mismatch, allowing the data access operations to be expressed in the form of entity state transitions.

It is definitely much more convenient to operate on entity graphs and let Hibernate translate state modifications to SQL statements, but convenience has its price. All the automatically generated SQL statements need to be validated, not only for effectiveness but for ensuring their efficiency as well.

```sql
With JDBC, the application developer has full control over the underlying SQL statements, and
the select clause dictates the amount of data being fetched. Because Hibernate hides the SQL
statement generation, fetching efficiency is not as transparent as with JDBC. More, Hibernate
makes it very easy to fetch an entire entity graph with a single query, and too-much-fetching
is one of the most common JPA-related performance issues.
```

To make matters worse, many performance issues can go unnoticed during development because the testing data set might be too small, in comparison to the actual production data. For this purpose, this chapter goes through various Java Persistence fetching strategies, and it explains which ones are suitable for a high-performance data-driven application.

As explained in the JDBC ResultSet Fetching chapter, fetching too many rows or columns can greatly impact the data access layer performance, and Hibernate is no different.

Hibernate can fetch a given result set either as a projection or as a graph of entities. The former is similar to JDBC and allows transforming the ResultSet into a list of DTO (Data Transfer Objects). The latter is specific to ORM tools, and it leverages the automatic persistence mechanism.

Unfortunately too often, this distinction is being forgotten, and data projections are unnecessarily replaced by entity queries. There are multiple reasons why entity queries are not a universal solution for reading data:

1. If a graph of entities has been loaded, but only a subset of the whole graph is used during UI rendering, the unused data will become a waste of database resources, network bandwidth, and server resources (objects need to be created and then reclaimed by the Java Garbage Collector without serving any purpose). 2. Entity queries are more difficult to paginate especially if they contain child collections. 3. The automatic dirty checking and the optimistic locking mechanisms are only relevant when data is meant to be modified.

So, projections are ideal when rendering subsets of data (e.g. read-only tables, auto-scrolling selectors), while entity queries are useful when the user wants to edit the fetched entities (e.g. forms, im-place editing).

When loading a graph of entities, the application developer must pay attention to the amount of data being fetched and also the number of statements being executed.

As a rule of thumb, a transaction should fetch just as much data as required by the currently executing business logic. Fetching more data than necessary can increase response time and waste resources.

Fetching entity graphs is useful when the data access layer needs to modify the currently loading entities.

## 14.1 DTO projection

While Hibernate allows fetching projections as an Object array, it is much more convenient to materialize the ResultSet in a DTO projection. Unlike returning an Object[], the DTO projection is type-safe.

Considering the following PostCommentSummary DTO type:

```java
public class PostCommentSummary {
private Number id;
private String title;
private String review;
public PostCommentSummary(Number id, String title, String review) {
this.id = id;
this.title = title;
this.review = review;
}
public PostCommentSummary() {}
public Number getId() { return id; }
public String getTitle() { return title; }
public String getReview() { return review; }
}
```

When executing the following PostCommentSummary projection query:

List<PostCommentSummary> summaries = entityManager.createQuery(

```sql
"select new " +
"
com.vladmihalcea.book.hpjp.hibernate.fetching.PostCommentSummary( " +
"
p.id, p.title, c.review ) " +
"from PostComment c " +
"join c.post p")
.getResultList();
```

Hibernate is only selecting the columns that are needed for building a PostCommentSummary instance.

```sql
SELECT p.id AS col_0_0_, p.title AS col_1_0_, c.review AS col_2_0_
FROM
post_comment c
INNER JOIN post p ON c.post_id = p.id
```

### 14.1.1 DTO projection pagination

Selecting too much data is a common cause of performance-related issues. A UI can display as much as the screen resolution allows it, and paginating data sets allows the UI to request only the info that is needed to be displayed in the current view. Pagination is also a safety measure since it sets an upper boundary on the amount of data that is fetched at once, and this is especially relevant when the tables being scanned tend to grow with time.

Pagination is a good choice even for batch processing because it limits the transaction size, therefore avoiding long-running transactions.

As explained in the JDBC ResultSet limit clause section, the SQL:2008 ResultSet pagination syntax hast started being supported since Oracle 12c, SQL Server 2012, and PostgreSQL 8.4, and many relational database systems still use a vendor-specific SQL syntax for offset pagination.

In the SQL Performance Explaineda book, Markus Winand explains why keyset pagination scales better than the default offset pagination mechanism. Unfortunately, Hibernate 5.1 does not support it, and the Keyset pagination requires executing a native SQL query instead.

As long as the filtering criteria are highly-selective so that the scanning result set is relatively small, the offset pagination performs reasonably well.

ahttp://sql-performance-explained.com/

For the offset pagination, JPA can insulate the data access layer from database-specific syntax quirks. First, the ResultSet size can be limited by calling setMaxResults which Hibernate

translates to a Dialect-specific statement syntax. While it would have been much easier for Hibernate to use the setMaxRows method of the underlying JDBC Statement, the databasespecific query syntax is desirable since it can also influence the database execution plan.

When running the following projection query on a PostgreSQL database:

List<PostCommentSummary> summaries = entityManager.createQuery(

```sql
"select new " +
"
com.vladmihalcea.book.hpjp.hibernate.fetching.PostCommentSummary( " +
"
p.id, p.title, c.review ) " +
"from PostComment c " +
"join c.post p " +
"order by p.id")
.setFirstResult(pageStart)
.setMaxResults(pageSize)
.getResultList();
```

Hibernate generates the select statement as follows:

```sql
SELECT p.id AS col_0_0_, p.title AS col_1_0_, c.review AS col_2_0_
FROM
post_comment c
INNER JOIN post p ON c.post_id = p.id
ORDER BY p.id
LIMIT
10 OFFSET 20
```

In this particular example, the LIMIT and the OFFSET PostgreSQL directives are used to control the window of data that needs to be fetched by the currently executing query.

ORDER BY

Without the ORDER BY clause, the order of rows in a result set is not deterministic. However, in the pagination use case, the fetched record order need to be preserved whenever moving from one page to another. According to the SQL standard, only the ORDER BY clause can guarantee a deterministic result set order because records are sorted after being extracted.

In the context of pagination, the ORDER BY clause needs to be applied on a column or a set of columns that are guarded by a unique constraint.

### 14.1.2 Native query DTO projection

DTO projections can be fetched with native queries as well. When using JPA, to fetch a list of

PostCommentSummary objects with an SQL query, a @NamedNativeQuery with a @SqlResultSetMapping is required:

@NamedNativeQuery(name = "PostCommentSummary",

query =

"SELECT p.id as id, p.title as title, c.review as review " + "FROM post_comment c " + "JOIN post p ON c.post_id = p.id " + "ORDER BY p.id", resultSetMapping = "PostCommentSummary" ) @SqlResultSetMapping(name = "PostCommentSummary",

classes = @ConstructorResult(

```java
targetClass = PostCommentSummary.class,
columns = {
@ColumnResult(name = "id"),
@ColumnResult(name = "title"),
@ColumnResult(name = "review")
}
)
)
```

To execute the above SQL query, the createNamedQuery method must be used:

List<PostCommentSummary> summaries = entityManager.createNamedQuery(

```java
"PostCommentSummary")
.setFirstResult(pageStart)
.setMaxResults(pageSize)
.getResultList();
```

Hibernate generating the following paginated SQL query:

```sql
SELECT p.id as id, p.title as title, c.review as review
FROM
post_comment c
JOIN post p ON c.post_id = p.id
ORDER BY p.id
LIMIT
10 OFFSET 20
```

While JPQL might be sufficient in many situations, there might be times when a native SQL query is the only reasonable alternative because, this way, the data access layer can take advantage of the underlying database querying capabilities.

A much simpler alternative is to use the Hibernate-native API which allows transforming the

ResultSet to a DTO through Java Reflection:

List<PostCommentSummary> summaries = session.createSQLQuery(

"SELECT p.id as id, p.title as title, c.review as review " + "FROM post_comment c " + "JOIN post p ON c.post_id = p.id " + "ORDER BY p.id") .setFirstResult(pageStart) .setMaxResults(pageSize) .setResultTransformer(

```java
new AliasToBeanResultTransformer(PostCommentSummary.class))
.list();
```

Although JPA 2.1 supports Constructor Expressions for JPQL queries as previously illustrated, there is no such alternative for native SQL queries.

Fortunately, Hibernate has long been offering this feature through the

ResultTransformer mechanism which not only provides a way to return DTO projections, but it allows to customize the result set transformation, like when needing to build an hierarchical DTO structure.

To fully grasp why sometimes native queries become a necessity, the next example uses a hierarchical model that needs to be ranked across the whole tree structure. For this reason, in the following example, a post comment score ranking system is going to be implemented.

The goal of such a system is to provide the user a way to view only the most relevant comments, therefore, allowing him to ignore comments that have a low score.

The post comment score system is going to use the following database table:

**Figure 14.1:Post comment score ranking system tables**

There is a one-to-many table relationship between post and post_comment. However, because users can also reply to comments, the post_comment table has also a one-to-one self-join table relationship.

The self-join association is commonly used for representing tree-like structures in a relational database. Additionally, each post_comment has a score which indicates its relevance.

The application in question needs to display the top-ranked comment hierarchies associated with a given post. The ranking can be calculated either in the data access layer or in the database, so it is worth comparing the performance impact of each of these two solutions.

The first approach uses application-level comment ranking, and, to minimize the fetching impact, a DTO projection is used to retrieve all records that need to be aggregated hierarchically.

List<PostCommentScore> postCommentScores = entityManager.createQuery(

```sql
"select new " +
"
com.vladmihalcea.book.hpjp.hibernate.query.recursive.PostCommentScore(" +
"
pc.id, pc.parent.id, pc.review, pc.createdOn, pc.score ) " +
"from PostComment pc " +
"where pc.post.id = :postId ")
.setParameter("postId", postId)
.getResultList();
```

The associated SQL query looks as follows:

```java
SELECT
```

pc.id AS col_0_0_, pc.parent_id AS col_1_0_, pc.review AS col_2_0_, pc.created_on AS col_3_0_, pc.score AS col_4_0_ FROM post_comment pc WHERE pc.post_id = 1

The PostCommentScore DTO looks like this:

```java
public class PostCommentScore {
private Long id;
private Long parentId;
private String review;
private Date createdOn;
private long score;
private List<PostCommentScore> children = new ArrayList<>();
public PostCommentScore(Number id, Number parentId, String review,
Date createdOn, Number score) {
this.id = id.longValue();
this.parentId = parentId != null ? parentId.longValue() : null;
this.review = review;
this.createdOn = createdOn;
this.score = score.longValue();
}
public PostCommentScore() {}
```

//Getters and setters omitted for brevity

```java
public long getTotalScore() {
long total = getScore();
for(PostCommentScore child : children) {
total += child.getTotalScore();
}
return total;
}
public List<PostCommentScore> getChildren() {
List<PostCommentScore> copy = new ArrayList<>(children);
copy.sort(Comparator.comparing(PostCommentScore::getCreatedOn));
return copy;
}
public void addChild(PostCommentScore child) {
children.add(child);
}
}
```

Once the PostCommentScore list is fetched from the database, the data access layer must extract the top-ranking comment hierarchies. For this, the sorting must be done in-memory.

```java
1
List<PostCommentScore> roots = new ArrayList<>();
```

2

```java
3
Map<Long, PostCommentScore> postCommentScoreMap = new HashMap<>();
4
for(PostCommentScore postCommentScore : postCommentScores) {
5
Long id = postCommentScore.getId();
6
if (!postCommentScoreMap.containsKey(id)) {
7
postCommentScoreMap.put(id, postCommentScore);
8
}
9
}
10
for(PostCommentScore postCommentScore : postCommentScores) {
11
Long parentId = postCommentScore.getParentId();
12
if(parentId == null) {
13
roots.add(postCommentScore);
14
} else {
15
PostCommentScore parent = postCommentScoreMap.get(parentId);
16
parent.addChild(postCommentScore);
17
}
18
}
```

19 roots.sort(

20 Comparator.comparing(PostCommentScore::getTotalScore).reversed()

```java
21
);
22
if(roots.size() > rank) {
23
roots = roots.subList(0, rank);
24
}
```

The in-memory ranking process can be summarized as follows:

* Lines 4-10: Because the query does not use an ORDER BY clause, there is no ordering guarantee. Grouping PostCommentScore entries by their identifier must be done prior to reconstructing the hierarchy.
* Lines 12-20: The hierarchy is built out of the flat PostCommentScore list. The PostCommentScore map is used to locate each PostCommentScore parent entry.
* Lines 22-24: The PostCommentScore roots are sorted by their total score.
* Lines 26-28: Only the top-ranking entries are kept and handed to the business logic.

For many developers, this approach might be the first option to consider when implementing such a task. Unfortunately, this method does not scale for large ResultSet(s) because fetching too much data and sending it over the network is going to have a significant impact on application performance. If a post becomes very popular, the number of post_comment rows can easily skyrocket, and the system might start experiencing performance issues.

By moving the score ranking processing in the database, the ResultSet can be limited to a maximum size before being returned to the data access layer. Summing scores for all

comments belonging to the same post_comment root requires Recursive CTE queries and Window Functions, therefore, the following example uses PostgreSQL, and the database ranking logic looks like this:

1 List<PostCommentScore> postCommentScores = entityManager.createNativeQuery(

2 "SELECT id, parent_id, root_id, review, created_on, score " +

3 "FROM ( " +

4 " SELECT " +

5 " id, parent_id, root_id, review, created_on, score, " +

6 " dense_rank() OVER (ORDER BY total_score DESC) rank " +

7 " FROM ( " +

8 " SELECT " +

9 " id, parent_id, root_id, review, created_on, score, " +

10 " SUM(score) OVER (PARTITION BY root_id) total_score " +

11 " FROM (" +

12 " WITH RECURSIVE post_comment_score(id, root_id, post_id, " +

13 " parent_id, review, created_on, score) AS (" +

14 " SELECT " +

15 " id, id, post_id, parent_id, review, created_on, score" +

16 " FROM post_comment " +

17 " WHERE post_id = :postId AND parent_id IS NULL " +

18 " UNION ALL " +

19 " SELECT pc.id, pcs.root_id, pc.post_id, pc.parent_id, " +

20 " pc.review, pc.created_on, pc.score " +

21 " FROM post_comment pc " +

22 " INNER JOIN post_comment_score pcs ON pc.parent_id = pcs.id " +

23 " ) " +

24 " SELECT id, parent_id, root_id, review, created_on, score " +

25 " FROM post_comment_score " +

26 " ) score_by_comment " +

27 " ) score_total " +

28 " ORDER BY total_score DESC, id ASC " +

29 ") total_score_group " +

30 "WHERE rank <= :rank", "PostCommentScore")

31 .unwrap(SQLQuery.class)

32 .setParameter("postId", postId).setParameter("rank", rank)

33 .setResultTransformer(new PostCommentScoreResultTransformer())

```java
34
.list();
```

As usual, a SQL query can be better understood if starting from the inner-most query:

* Lines 14-17: This query is the first one to be executed, and it selects the post_comment roots associated with the given post identifier.
* Line 18: The UNION ALL directive combines the previously generated result set with the current Recursive CTE projection.
* Lines 19-22: These lines represent the recursive step which, in this case, it joins the current post_comment rows with the previously scanned parents.
* Lines 12-13 and 24-25: The Recursive CTE is only a construct that needs to be explicitly called by a query. For this example, the post_comment hierarchy has a root_id which identifies all records belonging to the same comment root.
* Lines 8-11 and 26: This outer query is used to sum all scores for a given post_comment hierarchy. Unlike a regular GROUP BY clause, the Window Function allows aggregating the score without affecting the selected result set.
* Lines 4-7 and 27-28: This outer query is used to order the post_comment hierarchies by their overall score, and each hierarchy is given a top rank (e.g. 1, 2, 3).
* Lines 2-3 and 29-30: The outer-most query is only selecting the post_comment hierarchies that have a top rank higher than a given threshold.
* Line 31: The JPA Query is dereferenced to the underlying Hibernate-specific SQLQuery object.
* Line 33: Because the query was cast to an SQLQuery instance, the result can be transformed using the ResultTransformer utility.

Without using a ResultTransformer, Hibernate would return a List of PostCommentScore objects that need to be manually transformed into a tree structure, exactly like it was the case with the first DTO projection that was fetching all PostCommentScore records.

In the Recursive CTE use case, the result set is already ordered by the database so that the hierarchical structure can be constructed in a single iteration. This can also be done for the first example, but adding an ORDER BY directive is going to slow down the query execution significantly. When ORDER BY was added, the SQL query was 20 times slower even if the ordering was done by the entity identifier which was indexed by default.

For this reason, the first example did not feature a SQL ORDER BY clause, and the result set was, therefore, iterated twice. Compared to a SQL query, in-memory processing is blazing fast. For instance, processing around 35 000 PostCommentScore records takes around 2.5 milliseconds. On the other hand, fetching just 100 PostCommentScore(s) takes more than 3 milliseconds.

In PostgreSQL, CTE is treated as an optimization fencea, so caution is advised.

ahttp://blog.2ndquadrant.com/postgresql-ctes-are-optimization-fences/

The PostCommentScoreResultTransformer looks as follows:

```java
public class PostCommentScoreResultTransformer implements ResultTransformer {
private Map<Long, PostCommentScore> postCommentScoreMap = new HashMap<>();
private List<PostCommentScore> roots = new ArrayList<>();
@Override
public Object transformTuple(Object[] tuple, String[] aliases) {
PostCommentScore commentScore = (PostCommentScore) tuple[0];
Long parentId = commentScore.getParentId();
if (parentId == null) {
roots.add(commentScore);
} else {
PostCommentScore parent = postCommentScoreMap.get(parentId);
if (parent != null) {
parent.addChild(commentScore);
}
}
postCommentScoreMap.putIfAbsent(commentScore.getId(), commentScore);
return commentScore;
}
@Override
public List transformList(List collection) {
return roots;
}
}
```

Having two options for the same data access logic requires a test to prove which one performs better. Considering that n is the number of root-level post_comment records, the following test creates comments on three levels, each upper level having twice as much entries as the immediate lower level, and the total number of post_comment entries is given by the following formula:

N = n + n × n

2 + n × n

2 × n

4

To understand how each of these two options scales, the number of root-level post_comment entries varies from 4 to 8, 16, 24, 32, 48, and 64 records. By applying the mathematical formula above, the total number of post_comment records contained within one hierarchy can vary from 20 to 104, 656, 2040, 4640, 15024, and 34880 rows. Increasing the ResultSet size, the impact of fetching too much data becomes more and more apparent. On the other hand, even if it still needs to scan a lot of records, the database-level processing can avoid the fetching penalty.

The following graph captures the results when running these two score ranking data processing alternatives:

**Figure 14.2: Fetching all records vs Recursive CTE**

If the number of post_comment entries is low, the application-level processing will perform very well, even better than the Recursive CTE query. However, the larger the ResultSet, the more advantageous the database-processing alternative becomes. This graph is a good reminder that moving processing logic closer to the data set is a performance optimization that is worth considering.

Stored procedures

While SQL queries are ideal for fetching data projections, stored procedures and database functions can be very useful for processing data. Some complex database processing tasks can only be expressed through a procedure language (e.g. PL/SQL, T-SQL, PL/pgSQL) if the task requires mixing loops, conditional statements, arrays, or temporary tables.

Unlike SQL queries which are executed in the scope of the currently running transaction, stored procedure can also manipulate transaction boundaries. This can be very handy when trying to break an otherwise long-running transaction into smaller batches which can better fit the undo log memory buffers.

## 14.2 Query fetch size

When using JPA, the JDBC ResultSet is fully traversed and materialized into the expected query result. For this reason, the fetch size can only influence the number of database roundtrips required for fetching the entire ResultSet.

As explained in the JDBC Fetching Size section, when using PostgreSQL or MySQL, the

ResultSet is fetched in a single database roundtrip. For these two relational database systems, as well as for SQL Server, which uses adaptive buffering, the default fetch size setting is often the right choice when executing a JPA query.

On the other hand, Oracle uses a default fetch size of only 10 records. Considering the previous pagination query, the page size being also 10, the default fetch size does not influence the number of database roundtrips. However, if the page size is 50, then Hibernate will require 5 roundtrips to fetch the entire ResultSet.

Luckily, Hibernate can control the fetch size either on a query basis or at the EntityManager-

Factory level.

At the query level, the fetch size can be configured using the org.hibernate.fetchSize hint:

List<PostCommentSummary> summaries = entityManager.createQuery(

```sql
"select new " +
"
com.vladmihalcea.book.hpjp.hibernate.fetching.PostCommentSummary( " +
"
p.id, p.title, c.review ) " +
"from PostComment c " +
"join c.post p")
.setFirstResult(pageStart)
.setMaxResults(pageSize)
.setHint(QueryHints.HINT_FETCH_SIZE, pageSize)
.getResultList();
```

The default fetch size can also be configured as a configuration property:

<property name="hibernate.jdbc.fetch_size" value="50"/>

However, setting the default fetch size requires diligence because it affects every executing SQL query. Like with any other performance tuning setting, measuring the gain is the only way to determine if a settings makes sense or not.

## 14.3 Fetching entities

DTO projections are suitable for loading read-only data sets because they minimize the number of columns being fetched, and native queries can take advantage of the underlying database advanced querying capabilities. However, most enterprise applications need also modify data, and that is where DTO projections are no longer suitable for this task.

As explained at the beginning of this chapter, object-oriented queries predate entity state modifications. Hibernate supports the standard Java Persistence Query Language (JPQL) and the type-safe Criteria API. More, the Hibernate Query Language (HQL) extends JPQL, therefore offering more features that are not supported by the standard specification.

When an entity is loaded, it becomes managed by the currently running Persistence Context, and Hibernate can automatically detect changes and propagate them as SQL statements.

### 14.3.1 Direct fetching

The easiest way to load an entity is to call the find method of the Java Persistence EntityManager interface.

```java
Post post = entityManager.find(Post.class, 1L);
```

The same can be achieved with the Hibernate native API:

```java
Session session = entityManager.unwrap(Session.class);
Post post = session.get(Post.class, 1L);
```

When running either the find or the get method, Hibernate fires a LoadEvent. Without customizing event listeners, the LoadEvent is handled by the DefaultLoadEventListener class which tries to locate the entity as follows:

* First, Hibernate tries to find the entity in the currently running Persistence Context (the first-level cache). Once an entity is loaded, Hibernate always returns the same object instance on any successive fetching requests, no matter if it is a query or a direct fetching call. This mechanism guarantees application-level repeatable reads.
* If the entity is not found in the first-level cache and the second-level cache is enabled, Hibernate will try to fetch the entity from the second-level cache.
* If the second-level cache is disabled or the entity is not found in the cache, Hibernate will execute a SQL query to fetch the requested entity.

Not only the data access layer is much easier to implement this way, but Hibernate also offers strong data consistency guarantees. Backed by the application-level repeatable reads offered by the first-level cache, the built-in optimistic concurrency control mechanism can prevent lost updates, even across successive web requests.

While a SQL projection requires a database roundtrip to fetch the required data, entities can also be loaded from the second-level caching storage. By avoiding database calls, the entity caching mechanism can improve response time, while the database load can decrease as well.

14.3.1.1 Fetching a Proxy reference

Alternatively, direct fetching can also be done lazily. For this purpose, the EntityManager must return a Proxy which delays the SQL query execution until the entity is accessed for the first time.

This can be demonstrated with the following example:

```java
Post post = entityManager.getReference(Post.class, 1L);
LOGGER.info("Loaded post entity");
LOGGER.info("The post title is '{}'", post.getTitle());
```

Hibernate generates the following logging sequence:

INFO - Loaded post entity

```sql
SELECT p.id AS id1_0_0_, p.title AS title2_0_0_
FROM
post p
WHERE
p.id = 1
```

INFO - The post title is 'Post nr. 1'

The getReference method call does not execute the SQL statement right away, so the Loaded

post entity message is the first to be logged. When the Post entity is accessed by calling the

getTitle method, Hibernate executes the select query and, therefore, loads the entity prior to returning the title attribute.

The same effect can be achieved with the Hibernate native API which offers two alternatives for fetching an entity Proxy:

```java
Session session = entityManager.unwrap(Session.class);
Post post = session.byId(Post.class).getReference(1L);
Session session = entityManager.unwrap(Session.class);
Post post = session.load(Post.class, 1L);
```

Populating a child-side parent association

The child table row must set the foreign key column according to the parent record primary key value. However, the child entity mapping contains a reference to a parent object, and, if the parent entity is fetched with the find method, Hibernate is going to issue a select statement just for the sake of populating the underlying foreign key column value.

If the current Persistence Context does not require to load the parent entity, the aforementioned select statement will be a waste of resources. For this purpose, the getReference method allows populating the parent attribute with a Proxy which Hibernate can use to set the underlying foreign key value even if the Proxy is uninitialized.

In the following example, a PostComment entity must be persisted with a reference to its parent

Post entity.

```java
Post post = entityManager.getReference(Post.class, 1L);
PostComment postComment = new PostComment("Excellent reading!");
postComment.setPost(post);
entityManager.persist(postComment);
```

Executing the above test case, Hibernate generates a single insert statement without fetching the Post entity:

```sql
INSERT INTO post_comment (post_id, review, id)
VALUES (1, 'Excellent reading!', 2)
```

14.3.1.2 Natural identifier fetching

Hibernate offers the possibility of loading an entity by its natural identifier (business key). The natural id can be either a single column or a combination of multiple columns that uniquely identifies a given database table row.

In the following example, the Post entity defines a slug attribute which serves as a natural identifier.

```java
@Entity
@Table(name = "post")
public class Post {
@Id
@GeneratedValue
private Long id;
private String title;
@NaturalId
@Column(nullable = false, unique = true)
private String slug;
//Getters and setters omitted for brevity
}
```

Fetching an entity by its natural key is done as follows:

```java
Session session = entityManager.unwrap(Session.class);
Post post = session.bySimpleNaturalId(Post.class).load(slug);
```

Behind the scenes, Hibernate executes the following SQL statements:

```sql
SELECT p.id AS id1_0_
FROM
post p
WHERE
p.slug = 'high-performance-java-persistence'
SELECT p.id AS id1_0_0_, p.slug AS slug2_0_0_, p.title AS title3_0_0_
FROM
post p
WHERE
p.id = 1
```

The natural identifier direct fetching mechanism defines a getReference method which, just like its JPA Proxy loading counterpart, returns an entity Proxy.

```java
Post post = session.bySimpleNaturalId(Post.class).getReference(slug);
```

Caching

If the second-level cache is enabled, Hibernate can avoid executing the second query by loading the entity directly from the cache. Hibernate can also cache the natural identifier (e.g. @NaturalIdCache) associated with a given entity identifier, therefore preventing the first query as well.

### 14.3.2 Query fetching

```sql
With a simple API and having support for bypassing the database entirely by loading entities
from the second-level cache, the direct fetching mechanism is a very convenient entity
loading mechanism.
```

On the downside, direct fetching is limited to loading a single entity and only by its identifier or natural key. If the data access layer wants to load multiple entities satisfying a more complex filtering criteria, an entity query will become mandatory.

In the following example, a JPQL query is used to load all Post entities that have a non-nullable

slug attribute.

List<Post> posts = entityManager.createQuery(

```sql
"select p " +
"from Post p " +
"where p.slug is not null", Post.class)
.getResultList();
```

Executing the JPQL query above, Hibernate generates the following SQL query:

```sql
SELECT p.id AS id1_0_, p.slug AS slug2_0_, p.title AS title3_0_
FROM
post p
WHERE
p.slug IS NOT NULL
```

Loading by the entity natural key can be done through an entity query as well:

Post post = entityManager.createQuery(

```sql
"select p from Post p where p.slug = :slug", Post.class)
.setParameter("slug", slug)
.getSingleResult();
```

And, as opposed to direct fetching API, the entity query alternative requires a single SQL statement:

```sql
SELECT p.id AS id1_0_, p.slug AS slug2_0_, p.title AS title3_0_
FROM
post p
WHERE
p.slug = 'high-performance-java-persistence'
```

Not only that it can take more filtering criteria, but the query can be constructed programmatically and in a type-safe manner as well. For this purpose, the following example is going to filter Post entities by their title attribute using an incoming titlePattern argument.

If the titlePattern is null, the underlying SQL statement will contain an IS NULL directive. Otherwise, the query must use a LIKE filtering criteria.

```java
CriteriaBuilder builder = entityManager.getCriteriaBuilder();
CriteriaQuery<Post> criteria = builder.createQuery(Post.class);
Root<Post> fromPost = criteria.from(Post.class);
```

Predicate titlePredicate = titlePattern == null ?

```java
builder.isNull(fromPost.get(Post_.title)) :
builder.like(fromPost.get(Post_.title), titlePattern);
criteria.where(titlePredicate);
List<Post> posts = entityManager.createQuery(criteria).getResultList();
```

Metamodel API

In the previous example, the title attribute is accessed through the Post entity Metamodel (e.g. Post_.title). The Post_ class is auto-generated during build-time by the

org.hibernate.jpamodelgen.JPAMetaModelEntityProcessor Hibernate utility, and it provides a typesafe alternative to locating entity attributes.

Unlike using String attribute identifiers, the Metamodel API can generate a compilation error if an attribute name is changed without updating all Criteria API queries as well. When using an IDE, the Metamodel API allows entity attributes to be auto-discovered, therefore simplifying Criteria API query development.

Although Hibernate features a native Criteria query implementation, it is better to use the Java Persistence Criteria API which supports the Metamodel API as well.

### 14.3.3 Fetching associations

All the previous entity queries were rather simple since only one entity type was resulting from the query execution. However, Java Persistence allows fetching associations as well, and this feature is a double-edged sword because it makes it very easy to select more data than a business case might require.

In the database, relationships are represented using foreign keys. To fetch a child association, the database could either join the parent and the child table in the same query, or the parent and the child can be extracted with distinct select statements.

In the object-oriented Domain Model, associations are either object references (e.g. @Many-

ToOne, @OneToOne) or collections (e.g. @OneToMany, @ManyToMany). From a fetching perspective, an association can either be loaded eagerly or lazily.

An eager association is bound to its declaring entity so, when the entity is fetched, the association must be fetched prior to returning the result back to the data access layer. The association can be loaded either through table joining or by issuing a secondary select statement.

A lazy relationship is fetched only when being accessed for the first time, so the association is initialized using a secondary select statement.

By default, @ManyToOne and @OneToOne associations are fetched eagerly, while the @OneToMany and

@ManyToMany relationships are loaded lazily. During entity mapping, it is possible to overrule the implicit fetching strategies through the fetch association attribute, and, combining the implicit fetching strategies with the explicitly declared ones, the default entity graph is formed.

While executing a direct fetching call or an entity query, Hibernate inspects the default entity graph to know what other entity associations must be fetched additionally.

JPA 2.1 added support for custom entity graphs which, according to the specification, can be used to override the default entity graph on a per-query basis. However, lazy fetching is only a hint, and the underlying persistence provider might choose to simply ignore it.

Entity graphs

These default fetching strategies are a consequence of conforming to the Java Persistence specification. Prior to JPA, Hibernate would fetch every association lazily (@ManyToOne and the

@OneToOne relationships used to be loaded lazily too).

Just because the JPA 1.0 specification says that @ManyToOne and the @OneToOne must be fetched eagerly, it does not mean that this is the right thing to do, especially in a high-performance data access layer. Even if JPA 2.1 defines the javax.persistence.fetchgraph hint which can override a FetchType.EAGER strategy at the query level, in reality, Hibernate ignores it and fetches the eager association anyway.

While a lazy association can be fetched eagerly during a query execution, eager associations cannot be overruled on a query basis. For this reason, FetchType.LAZY associations are much more flexible to deal with than FetchType.EAGER ones.

14.3.3.1 FetchType.EAGER

Assuming that the PostComment entity has a post attribute which is mapped as follows:

```java
@ManyToOne
private Post post;
```

By omitting the fetch attribute, the @ManyToOne association is going to inherit the default

FetchType.EAGER strategy so the post association is going to be initialized whenever a PostComment entity is being loaded in the currently running Persistence Context. This way, when fetching a PostComment entity:

```java
PostComment comment = entityManager.find(PostComment.class, 1L);
```

Hibernate generates a select statement that joins the post_comment and post tables so that the

PostComment entity has its post attribute fully initialized.

```sql
SELECT pc.id AS id1_1_0_, pc.post_id AS post_id3_1_0_,
pc.review AS review2_1_0_, p.id AS id1_0_1_, p.title AS title2_0_1_
FROM
post_comment pc
LEFT OUTER JOIN post p ON pc.post_id = p.id
WHERE
pc.id = 1
```

When fetching the PostComment entity using the following JPQL query:

PostComment comment = entityManager.createQuery(

```sql
"select pc " +
"from PostComment pc " +
"where pc.id = :id", PostComment.class)
.setParameter("id", commentId)
.getSingleResult();
```

Hibernate generates two queries: one for loading the PostComment entity and another one for initializing the post association.

```sql
SELECT pc.id AS id1_1_, pc.post_id AS post_id3_1_, pc.review AS review2_1_
FROM
post_comment pc
WHERE
pc.id = 1
SELECT p.id AS id1_0_0_, p.title AS title2_0_0_
FROM
post p
WHERE
p.id = 1
```

While the PostComment entity is fetched explicitly as specified in the select clause, the post attribute is fetched implicitly according to the default entity graph.

Every time an entity is fetched via an entity query (JPQL or Criteria API) without explicitly fetching all the FetchType.EAGER associations, Hibernate generates additional SQL queries to initialize those relationships as well.

To execute a single SQL query that joins the post_comment and the post table, the JPQL query must use the fetch directive on the post attribute join clause:

PostComment comment = entityManager.createQuery(

```sql
"select pc " +
"from PostComment pc " +
"left join fetch pc.post p " +
"where pc.id = :id", PostComment.class)
.setParameter("id", commentId)
.getSingleResult();
```

The SQL query is similar to the one generated by the direct fetching mechanism:

```sql
SELECT pc.id AS id1_1_0_, p.id AS id1_0_1_, pc.post_id AS post_id3_1_0_,
pc.review AS review2_1_0_, p.title AS title2_0_1_
FROM
post_comment pc
LEFT OUTER JOIN post p ON pc.post_id = p.id
WHERE
pc.id = 1
```

Although collections can also be fetched eagerly, most often, this is a very bad idea. Because the eager fetching strategy cannot be overridden, every parent entity direct fetching call or entity query is going to load the FetchType.EAGER collection as well.

However, if these collections are not needed by every business case, the eagerly fetched associations will be just a waste of resources and a major cause of performance issues.

To prove it, the following example features a Post entity with two FetchType.EAGER collections:

```java
@OneToMany(mappedBy = "post", fetch = FetchType.EAGER)
private Set<PostComment> comments = new HashSet<>();
```

@ManyToMany(fetch = FetchType.EAGER) @JoinTable(name = "post_tag",

```java
joinColumns = @JoinColumn(name = "post_id"),
inverseJoinColumns = @JoinColumn(name = "tag_id")
)
private Set<Tag> tags = new HashSet<>();
```

When loading multiple Post entities while eager fetching the comments and tags collections:

List<Post> posts = entityManager.createQuery(

```sql
"select p " +
"from Post p " +
"left join fetch p.comments " +
"left join fetch p.tags", Post.class)
.getResultList();
```

Hibernate generates a Cartesian Product between the post_comment and the post_tag tables.

```sql
SELECT p.id AS id1_0_0_, p.title AS title2_0_0_,
pc.post_id AS post_id3_1_1_, pc.id AS id1_1_1_, pc.id AS id1_1_2_,
pc.post_id AS post_id3_1_2_, pc.review AS review2_1_2_,
pt.post_id AS post_id1_2_3_,
t.id AS tag_id2_2_3_, t.id AS id1_3_4_, t.name AS name2_3_4_
FROM
post p
LEFT OUTER JOIN post_comment pc ON p.id = pc.post_id
LEFT OUTER JOIN post_tag pt ON p.id = pt.post_id
LEFT OUTER JOIN tag t ON pt.tag_id = t.id
```

Even if there is a single Post entity with 20 PostComment(s) and 10 Tag(s), this SQL query will fetch 200 entries. For 100 Post(s), the associated ResultSet will contain 20 000 entries. That’s why the Cartesian Product is undesirable from a performance perspective.

The aforementioned example uses Set(s) because fetching multiple List(s) ends up with a MultipleBagFetchException. On the other hand, Set(s) and ordered List(s) are allowed to be fetched concomitantly with other collections.

If the previous entity query omits the JPQL fetch directive, then, instead of a Cartesian Product, two additional queries are going to be executed. so that the tags and comments collections are initialized, as required by the FetchType.EAGER strategy.

```sql
SELECT p.id AS id1_0_, p.title AS title2_0_
FROM
post p
WHERE
p.id = 1
SELECT pt.post_id AS post_id1_2_0_, pt.tag_id AS tag_id2_2_0_,
t.id AS id1_3_1_, t.name AS name2_3_1_
FROM
post_tag pt
INNER JOIN tag t ON pt.tag_id = t.id
WHERE
pt.post_id = 1
SELECT pc.post_id AS post_id3_1_0_, pc.id AS id1_1_0_, pc.id AS id1_1_1_,
pc.post_id AS post_id3_1_1_, pc.review AS review2_1_1_
FROM
post_comment pc
WHERE
pc.post_id = 1
```

The more associations are fetched eagerly, the slower the entity fetching will get because it either involves many table joins or a large number of secondary queries. If there are 1000 posts, each post with 50 comments and 5 tags, the Cartesian Product query is going to fetch 1000 × 50 × ×5 = 2500000 rows. On the other hand, if the collections are not fetched during the query execution, there are going to be 2000 additional queries (1000 for fetching comments and another 1000 queries to fetch the tags of every individual Post entity).

For this purpose, it is better to avoid the FetchType.EAGER strategy, especially for

```java
@OneToMany and @ManyToMany associations.
```

14.3.3.2 FetchType.LAZY

By now, it is obvious that marking associations as FetchType.LAZY is a much better alternative for a high-performance application. The fetching strategy is driven by the business use case data access requirements, so the entity graph should be constructed on a per-query basis. Just because a relationship was annotated as FetchType.LAZY, it does not mean it cannot be fetched eagerly as well.

Considering that the PostComment entity has a post attribute that is annotated with the

FetchType.LAZY attribute:

```java
@ManyToOne(fetch = FetchType.LAZY)
private Post post;
```

When the PostComment entity is fetched either through direct fetching or a JPQL query, Hibernate is going to generate a single post_comment select statement. The post attribute is referencing a Proxy which is only initialized when the attribute is being accessed for the first time.

To visualize the lazy fetching strategy, the following example is going to select a PostComment entity, and then log the title of it its associated Post parent entity:

```java
PostComment comment = entityManager.find(PostComment.class, 1L);
LOGGER.info("Loaded comment entity");
LOGGER.info("The post title is '{}'", comment.getPost().getTitle());
```

When the post attribute is being navigated, Hibernate executes a select statement to fetch the uninitialised Post entity Proxy:

```sql
SELECT pc.id AS id1_1_0_, pc.post_id AS post_id3_1_0_, pc.review AS review2_1_0_
FROM
post_comment pc
WHERE
pc.id = 1
```

INFO - Loaded comment entity

```sql
SELECT p.id AS id1_0_0_, p.title AS title2_0_0_
FROM
post p
WHERE
p.id = 1
```

INFO - The post title is 'Post nr. 1'

For @OneToMany and @ManyToMany associations, Hibernate uses its own collection Proxy implementations (e.g. PersistentBag, PersistentList, PersistentSet, PersistentMap) which can execute the lazy loading SQL statement on demand.

Navigating the lazy association is just one way to initialize the underlying Proxy or collection. The lazy association can also be fetched eagerly using a custom entity graph.

EntityGraph<PostComment> postEntityGraph = entityManager.createEntityGraph(

```java
PostComment.class);
postEntityGraph.addAttributeNodes(PostComment_.post);
```

PostComment comment = entityManager.find(PostComment.class, 1L,

```java
Collections.singletonMap("javax.persistence.fetchgraph", postEntityGraph)
);
```

When running the example above, Hibernate generates the following SQL statement:

```sql
SELECT pc.id AS id1_1_0_, pc.post_id AS post_id3_1_0_,
pc.review AS review2_1_0_, p.id AS id1_0_1_, p.title AS title2_0_1_
FROM
post_comment pc
LEFT OUTER JOIN post p ON pc.post_id = p.id
WHERE
pc.id = 1
```

In the example above, the EntityGraph specifies that it needs to fetch the post attribute which is identified by the type-safe Metamodel Attribute (e.g. PostComment_.post). This way, the default entity graph is substituted for the duration of the currently executing query.

The same effect can be obtained with an entity query using a fetch directive on the join clause.

PostComment comment = entityManager.createQuery(

```sql
"select pc " +
"from PostComment pc " +
"join fetch pc.post p " +
"where pc.id = :id", PostComment.class)
.setParameter("id", 1L)
.getSingleResult();
```

14.3.3.2.1 The N+1 query problem

Unfortunately, the lazy associations are not without problems, and the most common issue is called the N+1 query problem. This situation can be observed in the following example:

List<PostComment> comments = entityManager.createQuery(

```sql
"select pc " +
"from PostComment pc " +
"where pc.review = :review", PostComment.class)
.setParameter("review", review)
.getResultList();
LOGGER.info("Loaded {} comments", comments.size());
for(PostComment comment : comments) {
LOGGER.info("The post title is '{}'", comment.getPost().getTitle());
}
```

Which generates the following SQL statements:

```sql
SELECT pc.id AS id1_1_, pc.post_id AS post_id3_1_, pc.review AS review2_1_
FROM
post_comment pc
WHERE
pc.review = 'Excellent!'
```

INFO - Loaded 3 comments

```sql
SELECT pc.id AS id1_0_0_, pc.title AS title2_0_0_
FROM
post pc
WHERE
pc.id = 1
```

INFO - The post title is 'Post nr. 1'

```sql
SELECT pc.id AS id1_0_0_, pc.title AS title2_0_0_
FROM
post pc
WHERE
pc.id = 2
```

INFO - The post title is 'Post nr. 2'

```sql
SELECT pc.id AS id1_0_0_, pc.title AS title2_0_0_
FROM
post pc
WHERE
pc.id = 3
```

INFO - The post title is 'Post nr. 3'

First, Hibernate executes the JPQL query, and a list of PostComment entities is fetched. Then, for each PostComment, the associated post attribute is used to generate a log message containing the Post title. Because the post association is not initialized, Hibernate must fetch the Post entity with a secondary query, and for N PostComment entities, N more queries are going to be executed (hence the N+1 query problem).

The more queries are executed, the bigger the impact of the N+1 query problem. Although it is commonly associated with the FetchType.LAZY associations, the N+1 query problem can manifest even when using FetchType.EAGER. When executing a JPQL query, if the eager associations are not explicitly fetched as well, Hibernate is going to initialize every eager association with a secondary select query, therefore causing a N+1 query problem.

To fix the N+1 query problem, the Post(s) must be fetched along their PostComment child entities:

List<PostComment> comments = entityManager.createQuery(

```sql
"select pc " +
"from PostComment pc " +
"join fetch pc.post p " +
"where pc.review = :review", PostComment.class)
.setParameter("review", review)
.getResultList();
```

This time, Hibernate generates a single SQL statement and the N+1 query problem is gone:

```sql
SELECT pc.id AS id1_1_0_, p.id AS id1_0_1_, pc.post_id AS post_id3_1_0_,
pc.review AS review2_1_0_, p.title AS title2_0_1_
FROM
post_comment pc
INNER JOIN post p ON pc.post_id = p.id
WHERE
pc.review = 'Excellent!'
```

INFO - Loaded 3 comments

INFO - The post title is 'Post nr. 1' INFO - The post title is 'Post nr. 2' INFO - The post title is 'Post nr. 3'

14.3.3.2.2 How to catch N+1 query problems during testing

When an application feature is implemented, the development team must assert the number of statements generated, therefore making sure that the number of statements is the expected one. However, a change in the entity fetch strategy can ripple in the data access layer causing N+1 query problems. For this reason, it is better to automate the statement count validation, and this responsibility should be carried by integration tests.

The datasource-proxy statement logging framework provides various listeners to customize the statement interception mechanism. Additionally, the framework ships with a built-in

DataSourceQueryCountListener, which counts all statements executed by a given DataSource.

```java
ChainListener listener = new ChainListener();
listener.addListener(new SLF4JQueryLoggingListener());
listener.addListener(new DataSourceQueryCountListener());
```

DataSource dataSourceProxy = ProxyDataSourceBuilder.create(dataSource)

```java
.name(dataSourceProxyName())
.listener(listener)
.build();
```

First, an SQLStatementCountMismatchException can be defined to capture the expected and the

recorded count values. Because the query counters are stored in the QueryCountHolder utility, it is desirable to isolate integration tests from the underlying datasource-proxy specific API, therefore the SQLStatementCountValidator is an adapter for the datasource-proxy utilities.

```java
public class SQLStatementCountMismatchException extends RuntimeException {
private final int expected;
private final int recorded;
public SQLStatementCountMismatchException(int expected, int recorded) {
```

super(String.format("Expected %d statement(s) but recorded %d instead!",

```java
expected, recorded)
);
this.expected = expected;
this.recorded = recorded;
}
public int getExpected() { return expected; }
public int getRecorded() { return recorded; }
}
public final class SQLStatementCountValidator {
public static void reset() {
QueryCountHolder.clear();
}
public static void assertSelectCount(int expectedSelectCount) {
QueryCount queryCount = QueryCountHolder.getGrandTotal();
int recordedSelectCount = queryCount.getSelect();
if (expectedSelectCount != recordedSelectCount) {
```

throw new SQLStatementCountMismatchException(expectedSelectCount,

```java
recordedSelectCount);
}
}
public static void assertInsertCount(int expectedInsertCount) {
QueryCount queryCount = QueryCountHolder.getGrandTotal();
int recordedInsertCount = queryCount.getInsert();
if (expectedInsertCount != recordedInsertCount) {
```

throw new SQLStatementCountMismatchException(expectedInsertCount,

```java
recordedSelectCount);
}
}
public static void assertUpdateCount(int expectedUpdateCount) {
QueryCount queryCount = QueryCountHolder.getGrandTotal();
int recordedUpdateCount = queryCount.getUpdate();
if (expectedUpdateCount != recordedUpdateCount) {
```

throw new SQLStatementCountMismatchException(expectedUpdateCount,

```java
recordedUpdateCount);
}
}
public static void assertDeleteCount(int expectedDeleteCount) {
QueryCount queryCount = QueryCountHolder.getGrandTotal();
int recordedDeleteCount = queryCount.getDelete();
if (expectedDeleteCount != recordedDeleteCount) {
```

throw new SQLStatementCountMismatchException(expectedDeleteCount,

```java
recordedDeleteCount);
}
}
}
```

The N+1 query detection integration test looks like this:

```sql
SQLStatementCountValidator.reset();
List<PostComment> comments = entityManager.createQuery(
"select pc " +
"from PostComment pc " +
"where pc.review = :review", PostComment.class)
.setParameter("review", review)
.getResultList();
SQLStatementCountValidator.assertSelectCount(1);
```

If the PostComment entity post attribute is changed to FetchType.EAGER, this test is going to throw a

SQLStatementCountMismatchException because Hibernate executes an additional query statement to initialize the post attribute.

In case there were N PostComment entities being selected, Hibernate would generate N+1 queries according to the FetchType.EAGER contract.

```sql
SELECT pc.id AS id1_1_, pc.post_id AS post_id3_1_, pc.review AS review2_1_
FROM
post_comment pc
WHERE
pc.review = 'Excellent!'
SELECT p.id AS id1_0_0_, p.title AS title2_0_0_
FROM
post p
WHERE
p.id = 1
```

com.vladmihalcea.book.hpjp.hibernate.logging.SQLStatementCountMismatchException: Expected 1 statement(s) but recorded 2 instead!

Whenever statements are generated automatically, it is mandatory to validate their number using an integration test assertion mechanism, and Hibernate makes no exception. Having such tests ensures the number of generated statements does not change, as the tests would fail otherwise.

The datasource-proxy statement count validator supports other DML statements too, and it can be used to validate that insert, update, and delete statements are batched properly.

14.3.3.2.3 LazyInitializationException

Another common issue associated with lazy fetching is the infamous LazyInitializationExcep-

tion. As previously explained, @ManyToOne and @OneToOne associations are replaced with Proxies, while collections are substituted with Hibernate internal Proxy Collection implementations. As long as the Persistence Context is open, Hibernate can initialize such Proxies lazily. When the underlying Session is closed, attempting to navigate an uninitialized Proxy is going to end with a LazyInitializationException.

Assuming that the PostComment entity has a FetchType.LAZY post attribute, when executing the following example:

```java
PostComment comment = null;
EntityManager entityManager = null;
EntityTransaction transaction = null;
try {
entityManager = entityManagerFactory().createEntityManager();
transaction = entityManager.getTransaction();
transaction.begin();
comment = entityManager.find(PostComment.class, 1L);
transaction.commit();
} catch (Throwable e) {
```

if ( transaction != null && transaction.isActive())

```java
transaction.rollback();
throw e;
} finally {
if (entityManager != null) {
entityManager.close();
}
}
LOGGER.info("The post title is '{}'", comment.getPost().getTitle());
```

Hibernate throws a LazyInitializationException because the comment.getPost() Proxy is disconnected from the original Session:

org.hibernate.LazyInitializationException: could not initialize proxy -no Session at org.hibernate.proxy.AbstractLazyInitializer.initialize at org.hibernate.proxy.AbstractLazyInitializer.getImplementation at org.hibernate.proxy.pojo.javassist.JavassistLazyInitializer.invoke at com.vladmihalcea.book.hpjp.hibernate.forum.Post_$$_jvst15e_0.getTitle

The best way yo deal with the LazyInitializationException is to fetch all the required associations as long as the Persistence Context is open. Using the fetch JPQL directive, a custom entity graph, or the initialize method of the org.hibernate.Hibernate utility, the lazy

associations that are needed further up the stack (in the service or the view layer) must be loaded before the Hibernate Session is closed.

Unfortunately, there are bad ways to deal with the LazyInitializationException too. One quick fix would be to change the association in question to FetchType.EAGER. While this would work for the current business use case, the FetchType.EAGER is going to affect all other queries where the root entity of this association is fetched.

The fetching strategy is a query time responsibility, and each query should only fetch just as much data that is needed by the current business use case. On the other hand,

FetchType.EAGER is a mapping time decision that is taken outside the business logic context where the association is meant to be used.

There is also the Open Session in View anti-pattern that is sometimes proposed as a solution for the LazyInitializationException.

14.3.3.2.4 The Open Session in View Anti-Pattern

Open Session in View is an architectural pattern that proposes to hold the Persistence Context open throughout the whole web request. This way, if the service layer fetched an entity without fully initializing all its associations further needed by the UI, then the view layer could silently trigger a Proxy initialization on demand.

Spring framework comes with a javax.servlet.Filter[^1] implementation of the Open Session in View pattern. The OpenSessionInViewFilter gets a Session from the underlying SessionFactory and registers it in a ThreadLocal storage where the HibernateTransactionManager can also locate it. This service layer is still responsible for managing the actual JDBC or JTA transaction, but the Session is no longer closed by the HibernateTransactionManager[^2].

[^1]: <https://docs.spring.io/spring/docs/current/javadoc-api/org/springframework/orm/hibernate5/support/>

OpenSessionInViewFilter.html

[^2]: <https://docs.spring.io/spring/docs/current/javadoc-api/org/springframework/orm/hibernate5/>

HibernateTransactionManager.html

To visualize the whole process, consider the following sequence diagram:

**Figure 14.3: Open Session in View lifecycle**

* The OpenSessionInViewFilter calls the openSession method of the underlying SessionFactory and obtains a new Session.
* The Session is bound to the TransactionSynchronizationManager[^3].
* The OpenSessionInViewFilter calls the doFilter of the javax.servlet.FilterChain object reference and the request is further processed
* The DispatcherServlet[^4] is called, and it routes the HTTP request to the underlying

PostController.

* The PostController calls the PostService to get a list of Post entities.
* The PostService opens a new transaction, and the HibernateTransactionManager reuses the same Session that was opened by the OpenSessionInViewFilter.
* The PostDAO fetches the list of Post entities without initializing any lazy association.
* The PostService commits the underlying transaction, but the Session is not closed because it was opened externally.
* The DispatcherServlet starts rendering the UI, which, in turn, navigates the lazy associations and triggers their initialization.
* The OpenSessionInViewFilter can close the Session, and the underlying database connection is released as well.

At a first glance, this might not look like a terrible thing to do, but, once you view it from a database perspective, a series of flaws start to become more obvious.

[^3]: <http://docs.spring.io/spring/docs/current/javadoc-api/org/springframework/transaction/support/>

TransactionSynchronizationManager.html

[^4]: <http://docs.spring.io/spring/docs/current/javadoc-api/org/springframework/web/servlet/DispatcherServlet.html>

The service layer opens and closes a database transaction, but afterward, there is no explicit transaction going on. For this reason, every additional statement issued from the UI rendering phase is executed in auto-commit mode. Auto-commit puts pressure on the database server because each statement must flush the transaction log to disk, therefore causing a lot of I/O traffic on the database side. One optimization would be to mark the Connection as read-only which would allow the database server to avoid writing to the transaction log.

There is no separation of concerns anymore because statements are generated both by the service layer and by the UI rendering process. Writing integration tests that assert the number of statements being generated requires going through all layers (web, service, DAO), while having the application deployed on a web container. Even when using an in-memory database (e.g. HSQLDB) and a lightweight web server (e.g. Jetty), these integration tests are going to be slower to execute than if layers were separated and the back-end integration tests used the database, while the front-end integration tests were mocking the service layer altogether.

The UI layer is limited to navigating associations which can, in turn, trigger N+1 query problems, as previously explained. Although Hibernate offers @BatchSize[^5] for fetching associations in batches, and FetchMode.SUBSELECT[^6] to cope with this scenario, the annotations are affecting the default fetch plan, so they get applied to every business use case. For this reason, a data access layer query is much more suitable because it can be tailored for the current use case data fetch requirements.

Last but not least, the database connection is held throughout the UI rendering phase which increases connection lease time and limits the overall transaction throughput due to congestion on the database connection pool. The more the connection is held, the more other concurrent requests are going to wait to get a connection from the pool.

The Open Session in View is a solution to a problem that should not exist in the first place, and the most likely root cause is relying exclusively on entity fetching.

If the UI layer only needs a view of the underlying data, then the data access layer is going to perform much better with a DTO projection. A DTO projection forces the application developer to fetch just the required data set and is not susceptible to

LazyInitializationException(s).

This way, the separation of concerns is no longer compromised, and performance optimizations can be applied at the data access layer since all statements are confined to the boundaries of the currently executing transaction.

[^5]: <https://docs.jboss.org/hibernate/orm/current/javadocs/org/hibernate/annotations/BatchSize.html>

[^6]: <https://docs.jboss.org/hibernate/orm/current/javadocs/org/hibernate/annotations/FetchMode.html#SUBSELECT>

14.3.3.2.5 Temporary Session Lazy Loading Anti-Pattern

Analogous to the Open Session in View, Hibernate offers the hibernate.enable_lazy_load_-

no_trans configuration property which allows an uninitialized lazy association to be loaded outside of the context of its original Persistence Context.

<property name="hibernate.enable_lazy_load_no_trans" value="true"/>

```java
With this configuration property in place, the following code snippets can be executed
without throwing any LazyInitializationException:
List<PostComment> comments = null;
EntityManager entityManager = null;
EntityTransaction transaction = null;
try {
entityManager = entityManagerFactory().createEntityManager();
transaction = entityManager.getTransaction();
transaction.begin();
```

comments = entityManager.createQuery(

```sql
"select pc " +
"from PostComment pc " +
"where pc.review = :review", PostComment.class)
.setParameter("review", review)
.getResultList();
transaction.commit();
} catch (Throwable e) {
```

if ( transaction != null && transaction.isActive())

```java
transaction.rollback();
throw e;
} finally {
if (entityManager != null) {
entityManager.close();
}
}
for(PostComment comment : comments) {
LOGGER.info("The post title is '{}'", comment.getPost().getTitle());
}
```

Behind the scenes, a temporary Session is opened just for initializing every post association. Every temporary Session implies acquiring a new database connection, as well as a new database transaction.

The more associations being loaded lazily, the more additional connections are going to be requested which puts pressure on the underlying connection pool. Each association being loaded in a new transaction, the transaction log is forced to flush after each association initialization.

Just like Open Session in View, the hibernate.enable_lazy_load_no_trans configuration property is an anti-pattern as well because it only treats the symptoms and does not solve the actual cause of the LazyInitializationException.

By properly initializing all lazy associations prior to closing the initial Persistence Context, and switching to DTO projections where entities are not even necessary, the LazyInitializationException is prevented in a much more efficient way.

14.3.3.3 Associations and pagination

As previously explained, paginating result sets has many benefits, from lowering the response time to ensuring that the application works with the ever increasing data sets. Also, fetching a collection with the join fetch JPQL directive can prevent N+1 query problems and LazyIni-

tializationException(s) as well. Unfortunately, mixing collection fetching and pagination does not work very well together.

Collections must always be fetched fully because otherwise the collection size might not be consistent with the number of child entries associated with a given parent. On the other hand, SQL pagination can truncate the collection before returning all child records, therefore breaking the aforementioned consistency guarantee.

To visualize this process, the following entity query is going to load a list of Post entities, filtered by their title, and also, fetch all comments associated with a given Post record.

When specifying a maxResults restriction:

List<Post> posts = entityManager.createQuery(

```sql
"select p " +
"from Post p " +
"left join fetch p.comments " +
"where p.title like :title " +
"order by p.id", Post.class)
.setParameter("title", titlePattern)
.setMaxResults(50)
.getResultList();
```

Hibernate issues a warning message saying that pagination is done in memory, and the SQL query shows no sign of limiting the result set:

```sql
WARN - firstResult/maxResults specified with collection fetch;
applying in memory!
SELECT p.id AS id1_0_0_, pc.id AS id1_1_1_, p.title AS title2_0_0_,
pc.post_id AS post_id3_1_1_, pc.review AS review2_1_1_,
pc.post_id AS post_id3_1_0__, pc.id AS id1_1_0__
FROM
post p
LEFT OUTER JOIN post_comment pc ON p.id = pc.post_id
WHERE
p.title LIKE 'high-performance%'
ORDER BY p.id
```

So, Hibernate fetches the whole result set, and then it limits the number of root entities according to the maxResults query attribute value.

Compared to SQL-level pagination, entity query result set size restriction is not very efficient, causing the database to fetch the whole result set.

Entity queries vs DTO projections

By now, it is obvious that entity queries, although useful in certain scenarios, are not a universal solution to fetching data from a relational database. It can be detrimental to application performance to rely only on entity queries exclusively. As a rule of thumb, entity queries should be used when there is a need to modify the currently selected entities.

For read-only views, DTO projections can be more efficient because there are fewer columns being selected, and the queries can be paginated at the SQL-level. While the entity query language (JPQL and HQL) offers a wide range of filtering criteria, a native SQL query can take advantage of the underlying relational database querying capabilities.

JPQL/HQL and SQL queries are complementary solutions, both having a place in an enterprise system developer’s toolkit.

### 14.3.4 Attribute lazy fetching

When fetching an entity, all attributes are going to be loaded as well. This is because every entity attribute is implicitly marked with the @Basic[^7] annotation whose default fetch policy is

FetchType.EAGER.

However, the attribute fetch strategy can be set to FetchType.LAZY, in which case the entity attribute is loaded with a secondary select statement upon being accessed for the first time.

@Basic(fetch = FetchType.LAZY)

This configuration alone is not sufficient because Hibernate requires bytecode instrumentation to intercept the attribute access request and issue the secondary select statement on demand.

When using the Maven bytecode enhancement plugin, the enableLazyInitialization configuration property must be set to true as illustrated in the following example:

<plugin>

```java
<groupId>org.hibernate.orm.tooling</groupId>
<artifactId>hibernate-enhance-maven-plugin</artifactId>
<version>${hibernate.version}</version>
<executions>
```

<execution>

<configuration>

<failOnError>true</failOnError> <enableLazyInitialization>true</enableLazyInitialization> </configuration> <goals>

<goal>enhance</goal> </goals> </execution> </executions> </plugin>

```sql
With this configuration in place, all JPA entity classes are going to be instrumented with
lazy attribute fetching. This process takes place at build time, right after entity classes are
compiled from their associated source files.
```

The attribute lazy fetching mechanism is very useful when dealing with column types that store large amounts of data (e.g. BLOB, CLOB, VARBINARY). This way, the entity can be fetched without automatically loading data from the underlying large column types, therefore improving performance.

To demonstrate how attribute lazy fetching works, the following example is going to use an

Attachment entity which can store any media type (e.g. PNG, PDF, MPEG).

[^7]: <http://docs.oracle.com/javaee/7/api/javax/persistence/Basic.html#fetch-->

```java
@Entity @Table(name = "attachment")
public class Attachment {
@Id
@GeneratedValue
private Long id;
private String name;
@Enumerated
@Column(name = "media_type")
private MediaType mediaType;
@Lob
@Basic(fetch = FetchType.LAZY)
private byte[] content;
//Getters and setters omitted for brevity
}
```

Attributes such as the entity identifier, the name or the media type are to be fetched eagerly on every entity load. On the other hand, the media file content should be fetched lazily, only when being accessed by the application code.

After the Attachment entity is instrumented, the class bytecode is changed as follows:

```java
@Transient
private transient PersistentAttributeInterceptor
$$_hibernate_attributeInterceptor;
public byte[] getContent() {
return $$_hibernate_read_content();
}
public byte[] $$_hibernate_read_content() {
if ($$_hibernate_attributeInterceptor != null) {
```

this.content = ((byte[]) $$_hibernate_attributeInterceptor

```java
.readObject(this, "content", this.content));
}
return this.content;
}
```

The content attribute fetching is done by the PersistentAttributeInterceptor object reference, therefore providing a way to load the underlying BLOB column only when the getter is called for the first time.

**Figure 14.4: The attachment database table**

When executing the following test case:

```java
Attachment book = entityManager.find(Attachment.class, bookId);
LOGGER.debug("Fetched book: {}", book.getName());
assertArrayEquals(Files.readAllBytes(bookFilePath), book.getContent());
```

Hibernate generates the following SQL queries:

```sql
SELECT a.id AS id1_0_0_,
a.media_type AS media_ty3_0_0_,
a.name AS name4_0_0_
FROM
attachment a
WHERE
a.id = 1
```

* - Fetched book: High-Performance Java Persistence

```sql
SELECT a.content AS content2_0_
FROM
attachment a
WHERE
a.id = 1
```

Because it is marked with the FetchType.LAZY annotation and lazy fetching bytecode enhancement is enabled, the content column is not fetched along with all the other columns that initialize the Attachment entity. Only when the data access layer tries to access the content attribute, Hibernate issues a secondary select to load this attribute as well.

Just like FetchType.LAZY associations, this technique is prone to N+1 query problems, so caution is advised. One slight disadvantage of the bytecode enhancement mechanism is that all entity attributes, not just the ones marked with the FetchType.LAZY annotation, are going to be transformed, as previously illustrated.

### 14.3.5 Fetching subentities

Another approach to avoid loading table columns that are rather large is to map multiple subentities to the same database table.

**Figure 14.5: Attachment and AttachmentSummary entities**

Both the Attachment entity and the AttachmentSummary subentity inherit all common attributes from a BaseAttachment superclass.

```java
@MappedSuperclass
public class BaseAttachment {
@Id
@GeneratedValue
private Long id;
private String name;
@Enumerated
@Column(name = "media_type")
private MediaType mediaType;
//Getters and setters omitted for brevity
}
```

While AttachmentSummary extends BaseAttachment without declaring any new attribute:

```java
@Entity @Table(name = "attachment")
public class AttachmentSummary extends BaseAttachment {}
```

The Attachment entity inherits all the base attributes from the BaseAttachment superclass and maps the content column as well.

```java
@Entity @Table(name = "attachment")
public class Attachment extends BaseAttachment {
@Lob
private byte[] content;
//Getters and setters omitted for brevity
}
```

When fetching the AttachmentSummary subentity:

AttachmentSummary bookSummary = entityManager.find(

```java
AttachmentSummary.class, bookId);
```

The generated SQL statement is not going to fetch the content column:

```sql
SELECT a.id as id1_0_0_, a.media_type as media_ty2_0_0_, a.name as name3_0_0_
FROM attachment a
WHERE
a.id = 1
```

However, when fetching the Attachment entity:

```java
Attachment book = entityManager.find(Attachment.class, bookId);
```

Hibernate is going to fetch all columns from the underlying database table:

```sql
SELECT a.id as id1_0_0_, a.media_type as media_ty2_0_0_,
a.name as name3_0_0_, a.content as content4_0_0_
FROM attachment a
WHERE
a.id = 1
```

When it comes to reading data, subentities are very similar to DTO projections. However, unlike DTO projections, subentities can track state changes and propagate them to the database.

## 14.4 Entity reference deduplication

Considering that the Post comment has a bidirectional @OneToMany association with a PostComment entity, and the database contains the following entities:

```java
Post post = new Post();
post.setId(1L);
post.setTitle("High-Performance Java Persistence");
post.addComment(new PostComment("Excellent!"));
post.addComment(new PostComment("Great!"));
entityManager.persist(post);
```

When fetching a Post entity along with all its PostComment child entries:

List<Post> posts = entityManager.createQuery(

```sql
"select p " +
"from Post p " +
"left join fetch p.comments " +
"where p.title = :title", Post.class)
.setParameter("title", "High-Performance Java Persistence")
.getResultList();
LOGGER.info("Fetched {} post entities: {}", posts.size(), posts);
```

Hibernate generates the following output:

```sql
SELECT p.id AS id1_0_0_ , pc.id AS id1_1_1_ , p.title AS title2_0_0_ ,
pc.post_id AS post_id3_1_1_, pc.review AS review2_1_1_
FROM
post p
LEFT OUTER JOIN post_comment pc ON p.id = pc.post_id
WHERE
p.title = 'High-Performance Java Persistence'
```

* - Fetched 2 post entities: [

```java
Post{id=1, title='High-Performance Java Persistence'},
Post{id=1, title='High-Performance Java Persistence'}]
```

Because the underlying SQL query result set size is given by the number of post_comment rows, and the post data is duplicated for each associated post_comment entry, Hibernate is going to return 2 Post entity references.

Because the Persistence Context guarantees application-level repeatable reads, the posts list contains two references to the same Post entity object. To enable entity reference deduplication, JPA and Hibernate provide the distinct keyword.

Therefore, when adding distinct to the previous entity query:

List<Post> posts = entityManager.createQuery(

```sql
"select distinct p " +
"from Post p " +
"left join fetch p.comments " +
"where p.title = :title", Post.class)
.setParameter("title", "High-Performance Java Persistence")
.getResultList();
```

Hibernate generates the following output:

```sql
SELECT DISTINCT
```

p.id AS id1_0_0_ , pc.id AS id1_1_1_ , p.title AS title2_0_0_ , pc.post_id AS post_id3_1_1_, pc.review AS review2_1_1_ FROM post p LEFT OUTER JOIN post_comment pc ON p.id = pc.post_id WHERE p.title = 'High-Performance Java Persistence'

* - Fetched 1 post entities: [

```java
Post{id=1, title='High-Performance Java Persistence'}]
```

So, the duplicated entries have been removed from the result set, but the DISTINCT keyword was passed to the underlying SQL query. While this would be beneficial for scalar queries, for entity queries, this can affect the query execution plan.

When executing the query above that with the DISTINCT keyword on PostgreSQL, the following execution plan is obtained:

HashAggregate

Group Key: p.id, pc.id, p.title, pc.post_id, pc.review

* > Hash Right Join

Hash Cond: (pc.post_id = p.id)

* > Seq Scan on post_comment pc
* > Hash
* > Seq Scan on post p Filter: (title = 'High-Performance Java Persistence')

The HashAggregate is going to execute a sort the result set so that duplicate entries can be removed much faster. In this particular use case, this extra sorting phase is completely redundant because there are no duplicate entries to be removed. Therefore, the overall response time is going to be increased unnecessarily.

For this reason, Hibernate 5.2.2 adds an optimization via the DISTINCT_PASS_THROUGH query hint. When providing this query hint, and rerunning the previous entity query:

List<Post> posts = entityManager.createQuery(

```sql
"select distinct p " +
"from Post p " +
"left join fetch p.comments " +
"where p.title = :title", Post.class)
.setParameter("title", "High-Performance Java Persistence")
.setHint(QueryHints.HINT_PASS_DISTINCT_THROUGH, false)
.getResultList();
```

Hibernate is going to generate the following output:

```sql
SELECT p.id AS id1_0_0_ , pc.id AS id1_1_1_ , p.title AS title2_0_0_ ,
pc.post_id AS post_id3_1_1_, pc.review AS review2_1_1_
FROM
post p
LEFT OUTER JOIN post_comment pc ON p.id = pc.post_id
WHERE
p.title = 'High-Performance Java Persistence'
```

* - Fetched 1 post entities: [

```java
Post{id=1, title='High-Performance Java Persistence'}]
```

So, the entity references have been deduplicated while the distinct JPA keyword was not passed through the underlying SQL statement. This time, the PostgreSQL execution plan looks as follows:

Hash Right Join

Hash Cond: (pc.post_id = p.id)

* > Seq Scan on post_comment pc
* > Hash
* > Seq Scan on post p Filter: (title = 'High-Performance Java Persistence')

As illustrated by the execution plan above, there is no HashAggregate step this time. Therefore, the unnecessary sorting phase is skipped, and the query execution is going to be faster.

## 14.5 Query plan cache

There are two types of entity queries: dynamic and named queries. For dynamic queries, the EntityManager offers the createQuery method, while for named queries, there is the creat-

eNamedQuery alternative. There is no obvious performance gain for using named queries over dynamic ones because, behind the scenes, a named query is able to cache only its definition (e.g. NamedQueryDefinition), and the actual query plan cache is available for both dynamic and named queries.

Every query must be compiled prior to being executed, and, because this process might be resource intensive, Hibernate provides a QueryPlanCache for this purpose. For entity queries, the query String representation is parsed into an Abstract Syntax Tree. For native queries, the phase extracts information about the named parameters and query return type.

The query plan cache is shared by entity and native queries, and its size is controlled by the following configuration property:

<property name="hibernate.query.plan_cache_max_size" value="2048"/>

By default, the QueryPlanCache stores 2048 plans which is sufficient for many small and medium-sized enterprise applications.

For native queries, the QueryPlanCache stores also the ParameterMetadata which holds info about parameter name, position, and associated Hibernate type. The ParameterMetadata cache is controlled via the following configuration property:

<property name="hibernate.query.plan_parameter_metadata_max_size" value="128"/>

If the application executes more queries than the QueryPlanCache can hold, there is going to be a performance penalty due to query compilation.

Next, we are going to run a test which executes only two queries while varying the QueryPlan-

Cache and the ParameterMetadata cache size from 1 to 100.

```java
for (int i = 0; i < 2500; i++) {
long startNanos = System.nanoTime();
query1.apply(entityManager);
timer.update(System.nanoTime() - startNanos, TimeUnit.NANOSECONDS);
startNanos = System.nanoTime();
query2.apply(entityManager);
timer.update(System.nanoTime() - startNanos, TimeUnit.NANOSECONDS);
}
```

When executing our test case using two JPQL queries, we get the following results based on the underlying plan cache size:

**Figure 14.6: Entity query plan cache performance gain**

When the plan cache size is 100, both entity queries will be compiled just once since any successive query execution will fetch the previously compiled plan from the cache, therefore speeding up the Query object creation.

On the other hand, when the query plan cache size is 1, the entity queries are compiled on every execution, hence the Query‘ object creation will take way longer this time.

Only for entity queries, the plan cache can really make a difference in terms of performance. For native queries, the gain is less significant.

For entity queries (JPQL and Criteria API), it is important to set the

hibernate.query.plan_cache_max_size property so that it can accommodate all queries being executed. Otherwise, some entity queries might have to be recompiled, therefore increasing the transaction response time.

For native SQL queries, the ParameterMetadata cache can also provide a performance improvement, although not as significant as for entity queries:

**Figure 14.7: Native SQL query plan cache performance gain**

## 14.6 Resolving N+1 Query Problems in Practice

Below are practical code templates demonstrating how the N+1 query problem occurs and how to resolve it using JPQL `JOIN FETCH` or JPA `EntityGraph`.

### 14.6.1 The N+1 Fetching Problem

If you execute a query to load `PostComment` entities and then iterate over them to get their parent `Post` entity names, Hibernate executes 1 query to fetch the comments and N queries to fetch the post details:

```java
// Anti-Pattern: Triggers N+1 SELECT queries
List<PostComment> comments = entityManager.createQuery(
    "select pc from PostComment pc", PostComment.class)
    .getResultList();

for (PostComment comment : comments) {
    // Navigating the lazy relationship triggers an additional SELECT query per post
    String title = comment.getPost().getTitle(); 
    System.out.println("Comment Review: " + comment.getReview() + " on Post: " + title);
}
```

### 14.6.2 Solution 1: JPQL JOIN FETCH Query

The most common way to resolve the N+1 query problem is to use a `JOIN FETCH` directive in your JPQL/HQL query. This forces Hibernate to retrieve the parent and child entities in a single database roundtrip:

```java
// Solution 1: Single SELECT query with JOIN FETCH
List<PostComment> comments = entityManager.createQuery(
    "select pc from PostComment pc join fetch pc.post p", PostComment.class)
    .getResultList();

for (PostComment comment : comments) {
    // No extra query is generated because the Post entity is already initialized
    String title = comment.getPost().getTitle();
    System.out.println("Comment Review: " + comment.getReview() + " on Post: " + title);
}
```

### 14.6.3 Solution 2: JPA Entity Graphs

JPA Entity Graphs provide a type-safe way to define a fetching plan at runtime. This allows you to keep the association as `FetchType.LAZY` in the mapping, but fetch it eagerly on a query-by-query basis:

```java
import javax.persistence.EntityGraph;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

// Create a dynamic entity graph for PostComment
EntityGraph<PostComment> entityGraph = entityManager.createEntityGraph(PostComment.class);
entityGraph.addAttributeNodes("post"); // Specify the association to fetch eagerly

// Pass the entity graph as a hint to the query
Map<String, Object> hints = new HashMap<>();
hints.put("javax.persistence.fetchgraph", entityGraph);

List<PostComment> comments = entityManager.createQuery(
    "select pc from PostComment pc", PostComment.class)
    .setHint("javax.persistence.fetchgraph", entityGraph)
    .getResultList();

for (PostComment comment : comments) {
    // No extra queries generated
    String title = comment.getPost().getTitle();
    System.out.println("Comment Review: " + comment.getReview() + " on Post: " + title);
}
```

