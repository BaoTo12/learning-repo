# 16. Concurrency Control

As explained in the JDBC Transactions chapter, every SQL statement executes within the scope of a database transaction. To prevent conflicts, database engines employ row-level locks. Database physical locks can either be acquired implicitly or explicitly. Whenever a row is changed, the relational database acquires an implicit exclusive lock on the aforementioned record to prevent write-write conflicts.

Locks can also be acquired explicitly, in which case the concurrency control mechanism is called pessimistic locking. Exclusive locks can be acquired explicitly on most database systems, whereas shared locks are not universally supported.

Pessimistic locking deals with concurrency conflicts through prevention, which can impact application performance and scalability. For this reason, to increase transaction throughput while still ensuring strong consistency, many data access frameworks provide optimistic locking support as well.

## 16.1 Hibernate optimistic locking

Even if pessimistic locking has only been added in JPA 2.0, optimistic locking has been supported since version 1.0. Just like pessimistic locking, the optimistic concurrency control mechanism can be used implicitly or explicitly.

### 16.1.1 The implicit optimistic locking mechanism

To enable the implicit optimistic locking mechanism, the entity must provide a @Version attribute:

```java
@Entity @Table(name = "post")
public class Post {
@Id
private Long id;
private String title;
@Version
private int version;
//Getters and setters omitted for brevity
}
```

Logical vs. Physical clocks

Using timestamps to order events is rarely a good idea. System time is not always monotonically incremented, and it can even go backward due to network time synchronization (NTP protocol).

More, time accuracy across different database systems varies from nanoseconds (Oraclea) to 100 nanoseconds (SQL Serverb), to microseconds (PostgreSQLc and MySQL 5.6.4d and even seconds (previous versions of MySQL). In distributed systems, logical clocks (e.g. vector clocks or Lamport timestamps) are always preferred to physical timestamps (wall clocks) when it comes to ordering events.

For this reason, employing a numerical version is more appropriate than using a timestamp.

ahttp://docs.oracle.com/database/121/LNPCB/pco04dat.htm#LNPCB[^269] bhttps://msdn.microsoft.com/en-us/library/bb[^677335].aspx chttp://www.postgresql.org/docs/current/static/datatype-datetime.html dhttp://dev.mysql.com/doc/refman/5.6/en/fractional-seconds.html

To visualize the optimistic concurrency control, when executing the following test case:

```java
doInJPA(entityManager -> {
Post post = new Post();
post.setId(1L);
post.setTitle("High-Performance Java Persistence");
entityManager.persist(post);
entityManager.flush();
post.setTitle("High-Performance Hibernate");
});
```

Hibernate generates the following output:

```sql
INSERT INTO post (title, version, id)
VALUES ('High-Performance Java Persistence', 0, 1)
UPDATE post SET title = 'High-Performance Hibernate', version = 1
WHERE id = 1 AND version = 0
```

Whenever an update occurs, Hibernate is going to filter the database record according to the expected entity version. If the version has changed, the update count is going to be 0, and a

OptimisticLockException is going to be thrown.

To visualize the conflict detection mechanism, consider the following exercise:

```java
doInJPA(entityManager -> {
Post post = entityManager.find(Post.class, 1L);
executeSync(() -> {
doInJPA(_entityManager -> {
Post _post = _entityManager.find(Post.class, 1L);
_post.setTitle("High-Performance JDBC");
});
});
post.setTitle("High-Performance Hibernate");
});
```

When executing the aforementioned test case, Hibernate generates the following output:

* - Alice selects the Post entity SELECT p.id AS id1_0_0_, p.title AS title2_0_0_, p.version AS version3_0_0_ FROM post p WHERE p.id = 1
* - Bob also selects the same Post entity SELECT p.id AS id1_0_0_, p.title AS title2_0_0_, p.version AS version3_0_0_ FROM post p WHERE p.id = 1
* - Bob updates the Post entity UPDATE post SET title = 'High-Performance JDBC', version = 1 WHERE id = 1 AND version = 0
* - Alice also wants to update the Post entity UPDATE post SET title = 'High-Performance Hibernate', version = 1 WHERE id = 1 AND version = 0

```sql
--Exception thrown
javax.persistence.RollbackException: Error while committing the transaction
Caused by: javax.persistence.OptimisticLockException:
Caused by: org.hibernate.StaleStateException:
Batch update returned unexpected row count from update [0];
actual row count: 0; expected: 1
```

Because this example uses the Java Persistence API, the Hibernate internal StaleStateException is wrapped in the OptimisticLockException defined by the JPA specification.

The flow of operations can be summarized as follows:

* Alice fetches a Post entity and then her thread is suspended.
* Bob thread is resumed, he fetches the same Post entity and changes the title to High-

Performance JDBC. The entity version is set to 1.

* When Alice’s thread is resumed, she tries to update the Post entity title to High-

Performance Hibernate.

* An OptimisticLockException is thrown because the second update statement is expecting to filter the entity version with a value of 0, while the version column value is now 1.

16.1.1.1 Resolving optimistic locking conflicts

While pessimistic locking prevents conflict occurrences, optimistic locking mechanisms, just like MVCC, use conflict detection instead. So anomalies are detected and prevented from being materialized by aborting the currently running transactions, and Hibernate optimistic locking can prevent the lost update anomaly.

As explained in the application-level transactions section, when using a multi-request workflow, the database isolation level can no longer prevent lost updates. On the other hand, the optimistic locking mechanism can prevent losing updates as long as the entity state is preserved from one request to the other.

Optimistic locking discards all incoming changes that are relative to a stale entity version. However, everything has its price and optimistic locking is no different.

If two concurrent transactions are updating distinct entity attribute subsets, then there should be no risk of losing any update. However, the optimistic concurrency control mechanism takes an all-or-nothing approach even for non-overlapping changes. For this reason, two concurrent updates, both starting from the same entity version, are always going to collide. It is only the first update that is going to succeed, the second one failing with an optimistic locking exception.

This strict policy acts as if all changes are going to overlap, and, for highly concurrent write scenarios, the single version strategy can lead to a large number of transactions being rolled back.

To visualize the non-overlapping conflict, consider the following Post entity class:

**Figure 16.1: Post entity with a single global version**

In the following example, Alice modifies the Post entity title attribute, Bob increments the

likes counter, and Carol sets the views attribute to a value that was aggregated from an external batch processor.

**Figure 16.2: Optimistic locking non-overlapping conflict**

The flow of operations can be explained as follows:

* All three users are loading the same Post entity version.
* Alice modifies the title. Therefore, the Post entity version is incremented.
* Bob tries to increment the likes counter but rolls back because it expects the version to be 0, but now it has a value of 1.
* Carol’s transaction is also aborted because of the entity version mismatch.

The optimistic locking mechanism allows only monotonically increasing version updates. If changes were dependent one to another, then getting an OptimisticLockException is less of an issue than losing an update. However, if from a business logic perspective, the changing attributes are not overlapping, having a single global version is no longer sufficient.

For this reason, the single global version must be split into multiple subversions, and this can be done in two ways:

* Instead of having a single optimistic locking counter, there can be a distinct version for each individual attribute set.
* Each changing attribute can be compared against its previously known value, so lost updates are relative only to the attribute in question.

16.1.1.2 Splitting entities

The Post entity can be split into several sub-entities according to the three distinct set of attributes:

**Figure 16.3: Post entity version split**

While the title attribute remains in the Post parent entity, the likes, and the views attributes are moved to distinct entities. The PostLikes and PostViews entities are associated with the Post parent entity in a bidirectional one-to-one relationship. The PostLikes and PostViews entity identifiers are also foreign keys to the post table primary key.

Each entity has its own version attribute. Whenever the Post title is changed, it is only the

Post entity version that is checked and incremented. When the views attribute is updated, only the PostViews entity is going to be affected. The same is true for incrementing likes which are stored in the PostLikes entity.

While breaking a larger entity into several sub-entities can help address optimistic locking conflicts, this strategy has its price. This rather extreme data normalization strategy can have an impact on read operation performance because data is scattered across several tables. If the whole aggregate is needed to be fetched, the data access layer will require to join several tables or execute additional secondary select statements.

The second-level cache can mitigate the read operation performance penalty. Actually, the root entity split can improve the second-level cache performance, especially for read-through strategies (e.g. NONSTRICT_READ_WRITE). If the views attribute is modified, only the PostViews cache entry needs to be invalidated, whereas the Post and the

PostLikes remain unaffected.

When running the previous exercise, there is no longer any conflict being generated:

**Figure 16.4: Optimistic locking multiple versions**

Lost updates are prevented at the entity-level only so the three distinct attributes can be updated concurrently without generating any conflict. However, conflicts can still occur if the same attribute is getting updated by two concurrent transactions.

Designing a Domain Model must take into consideration both read and write data access patterns. Splitting entities by write responsibility can reduce optimistic locking false positives when the write ratio is relatively high.

16.1.1.3 Versionless optimistic locking

Although having a numerical version attribute is the most common optimistic concurrency control strategy, Hibernate offers a versionless optimistic locking mechanism which is not supported by JPA 2.1 specification. To switch to the versionless optimistic locking mechanism, the @OptimisticLocking annotation must be configured at the entity level.

The org.hibernate.annotations.OptimisticLocking annotation comes with a type attribute that can take the following values:

* NONE - The implicit optimistic locking mechanism is disabled.
* VERSION - The implicit optimistic locking mechanism uses a numerical or a timestamp version attribute.
* DIRTY - The implicit optimistic locking mechanism uses only the attributes that have been modified in the currently running Persistence Context.
* ALL - The implicit optimistic locking mechanism uses all entity attributes.

OptimisticLockType.ALL and OptimisticLockType.DIRTY also require the @DynamicUpdate annotation because update statements must be rewritten so that either all attributes or the ones that were modified are included in the where clause criteria. For these two optimistic lock types, the entity versioning mechanism is based on the hydrated state snapshot that was stored when the entity was first loaded in the currently running Persistence Context.

To see how the OptimisticLockType.ALL option works, consider the following Post entity mapping:

```java
@Entity @Table(name = "post") @DynamicUpdate
@OptimisticLocking(type = OptimisticLockType.ALL)
public class Post {
@Id
private Long id;
private String title;
//Getters and setters omitted for brevity
}
```

When using the aforementioned Post entity to rerun the example defined at the beginning of the Hibernate implicit optimistic locking section, Hibernate generates the following output:

```sql
INSERT INTO post (title, version, id)
VALUES ('High-Performance Java Persistence', 0, 1)
UPDATE post SET title = 'High-Performance JDBC'
WHERE id = 1 AND title = 'High-Performance Java Persistence'
```

If the Post entity had more attributes, all of them would be included in the SQL where clause.

The OptimisticLockType.ALL is useful when the underlying database table cannot be altered in order to add a numerical version column. Because it takes into consideration all entity attributes, the OptimisticLockType.ALL option behaves just like a single global version attribute, and write conflicts can occur even if two concurrent transactions are modifying non-overlapping attribute sets.

Even if the entity splitting method can address the non-overlapping attribute sets conflict, too much data normalization can affect read operation performance. The OptimisticLock-

Type.DIRTY option can deal with this issue, and so lost updates are prevented for the currently modified attributes.

To demonstrate it, the following Post entity mapping is going to be used while running the same test case employed in the resolve optimistic locking conflicts section:

```java
@Entity @Table(name = "post") @DynamicUpdate
@OptimisticLocking(type = OptimisticLockType.DIRTY)
public class Post {
@Id
private Long id;
private String title;
private long views;
private int likes;
//Getters and setters omitted for brevity
}
```

**Figure 16.5: Optimistic locking dirty attributes**

The OptimisticLockType.DIRTY option allows concurrent users to update distinct attributes without causing any conflict. However, conflicts can still occur when two concurrent transactions are updating the same attribute. Therefore, lost updates are prevented on a perattribute basis.

For heavy-write data access layers, it is not uncommon to split an entity into multiple parts, each individual subentity containing attributes that need to be updated atomically. If, from a writing perspective, attributes are independent, then the

OptimisticLockType.DIRTY mechanism is also a viable alternative.

Preventing lost updates is essential for data integrity, but the prospect of having transactions aborted due to non-overlapping attribute changes is undesirable. To cope with this issue, entities need to be carefully modeled based on both read and write data access patterns.

16.1.1.3.1 OptimisticLockType.DIRTY update caveat

In spite of being very useful for preventing optimistic locking conflicts, the OptimisticLock-

Type.DIRTY mechanism has one limitation: it does not work with the Session.update() method.

```java
Post detachedPost = doInJPA(entityManager -> {
LOGGER.info("Alice loads the Post entity");
return entityManager.find(Post.class, 1L);
});
executeSync(() -> {
doInJPA(entityManager -> {
LOGGER.info("Bob loads the Post entity and modifies it");
Post post = entityManager.find(Post.class, 1L);
post.setTitle("Hibernate");
});
});
doInJPA(entityManager -> {
LOGGER.info("Alice updates the Post entity");
detachedPost.setTitle("JPA");
entityManager.unwrap(Session.class).update(detachedPost);
});
```

When running the test case above, Hibernate generates the following statements:

* - Alice loads the Post entity SELECT p.id AS id1_0_0_, p.likes AS likes2_0_0_, p.title AS title3_0_0_, p.views AS views4_0_0_ FROM post p WHERE p.id = 1
* - Bob loads the Post entity and modifies it SELECT p.id AS id1_0_0_, p.likes AS likes2_0_0_, p.title AS title3_0_0_, p.views AS views4_0_0_ FROM post p WHERE p.id = 1

```sql
UPDATE post SET title = 'Hibernate' WHERE id = 1 AND title = 'JDBC'
```

* - Alice updates the Post entity UPDATE post SET likes=0, title='JPA', views=0 WHERE id=1

Bob’s update benefits from dirty attribute optimistic locking, just as expected. On the other hand, Alice’s update is not using any optimistic locking at all.

That is because the reattached Post entity misses the loaded state information, so the dirty checking mechanism cannot be executed in this case. For this reason, Hibernate schedules an update statement that simply copies the current entity state to the underlying database record. Unfortunately, this can lead to lost updates since Alice is not aware of Bob’s latest modification. If optimistic locking were working, Alice’s update would be prevented.

The @SelectBeforeUpdate annotation allows Hibernate to fetch the entity snapshot prior to executing the update query. This way, Hibernate can run the dirty checking mechanism and make sure that the update is really necessary.

```java
@Entity(name = "Post") @Table(name = "post")
@OptimisticLocking(type = OptimisticLockType.DIRTY)
@DynamicUpdate
@SelectBeforeUpdate
public class Post {
@Id
private Long id;
private String title;
private long views;
private int likes;
//Getters and setters omitted for brevity
}
```

Unfortunately, even when using @SelectBeforeUpdate, the optimistic locking mechanism is still circumvented, and Alice update transaction executes the following statements:

```sql
SELECT p.id AS id1_0_0_, p.likes AS likes2_0_0_, p.title AS title3_0_0_,
p.views AS views4_0_0_
FROM
post p
WHERE
p.id = 1
UPDATE post SET title='JPA' WHERE id = 1
```

The dynamic update works since the update statement contains only the modified attribute, but there is no optimistic locking filtering criteria.

If Alice uses the EntityManager.merge() operation:

```java
doInJPA(entityManager -> {
detachedPost.setTitle("JPA");
entityManager.merge(detachedPost);
});
```

Hibernate executes the following SQL statements:

```sql
SELECT p.id AS id1_0_0_, p.likes AS likes2_0_0_, p.title AS title3_0_0_,
p.views AS views4_0_0_
FROM
post p
WHERE
p.id = 1
UPDATE post SET title='JPA' WHERE id = 1 AND title = 'Hibernate'
```

The optimistic locking mechanism is used, but it is relative to the newly loaded entity state. This time, lost updates can only be detected if, while merging the detached entity, Carol would update the same Post entity title.

Statefulness to the rescue

Unfortunately, Bob’s update is still undetected by the versionless optimistic locking mechanism. The current entity state alone is no longer sufficient when merging a detached entity version because the Persistence Context cannot determine which attributes have been changed and which reference values are to be used in the where clause filtering criteria.

To fix it, the entity must store the loading-time attribute state so that the Persistence Context can use it later for the optimistic locking where clause criteria, therefore, preventing any lost update occurrence. However, this is impractical, and so the entity state must be stored either in a stateful Persistence Context, or its loading-time version value be saved separately.

Using a numerical version is practical, but it can lead to optimistic locking conflicts because all attributes are treating as a global all-or-nothing update attribute set. On the other hand, the Persistence Context does not need to be closed. Only the database connection needs to be released to allow other concurrent transactions to execute in the user think time. The Persistence Context can be kept open so that entities never become detached. This way, the entity loading-time state is never lost, and the versionless optimistic locking mechanism will work even across multiple transactions. When using Java EE, a PersistenceContextType.EXTENDED can be used inside a @Stateful EJB. Spring Webflow allows registering a Persistence Context in the HttpSession so that the EntityManager remains open throughout the whole lifecycle of the current flow.

## 16.2 The explicit locking mechanism

While the implicit locking mechanism is suitable for many application concurrency control requirements, there might be times when a finer-grained locking strategy is needed. JPA offers a concurrency control API, on top of which the application developer can implement really complex data integrity rules. The explicit locking mechanism works for both pessimistic and optimistic locking.

For pessimistic concurrency control, JPA abstracts the database-specific locking semantics, and, depending on the underlying database capabilities, the application developer can acquire exclusive or shared locks.

If the implicit optimistic locking mechanism controls the entity version automatically, and the application developer is not allowed to make changes to the underlying version attribute, the explicit optimistic lock modes allow incrementing an entity version even if the entity was not changed by the currently running transaction. This is useful when two distinct entities need to be correlated so that a child entity modification can trigger a parent entity version incrementation.

JPA offers various LockModeType(s) that can be acquired for the direct loading mechanism (e.g.

entityManager.find, entityManager.lock, entityManager.refresh) as well as for any JPQL or Criteria API query (e.g. Query.setLockMode()).

The following table lists all LockModeType(s) that can be acquired by a particular entity:

Table 16.1: LockModeType(s)

Lock Mode Type Description NONE In the absence of explicit locking, the application uses the default implicit locking mechanism.

OPTIMISTIC or READ Issues a version check upon transaction commit.

OPTIMISTIC_FORCE_INCREMENT or WRITE Increases the entity version prior to committing the current running transaction.

PESSIMISTIC_FORCE_INCREMENT An exclusive database lock is acquired, and the entity version is incremented right away.

PESSIMISTIC_READ A shared database lock is acquired to prevent any other transaction from acquiring an exclusive lock.

PESSIMISTIC_WRITE An exclusive lock is acquired to prevent any other transaction from acquiring a shared/exclusive lock.

The following sections will analyze each individual LockModeType in greater detail.

### 16.2.1 PESSIMISTIC_READ and PESSIMISTIC_WRITE

To acquire row-level locks, JPA defines two LockModeType: PESSIMISTIC_READ, for shared locks, and PESSIMISTIC_WRITE, for exclusive locks. Unfortunately, there is no standard definition for acquiring shared and exclusive locks, and each database system defines its own syntax.

Oracle

Only exclusive locks are supported for which Oracle defines the FOR UPDATEa clause. Rows that were selected with the FOR UPDATE clause cannot be locked or modified until the current transaction either commits or rolls back.

ahttps://docs.oracle.com/database/121/SQLRF/statements_10002.htm#SQLRF[^01702]

SQL Server

SQL Server does not define a FOR UPDATE select statement clause, but instead it defines several table hintsa. The WITH (HOLDLOCK, ROWLOCK) is equivalent to acquiring a shared lock until the current running transaction is ended, whereas the WITH (UPDLOCK, HOLDLOCK, ROWLOCK) hint can be used to acquire an exclusive lock.

ahttps://msdn.microsoft.com/en-us/library/ms[^187373].aspx

PostgreSQL

The select clause can take multiple locking clausesa among which FOR SHARE is used to acquire a shared lock, whereas FOR UPDATE takes an exclusive lock on each selected row.

ahttps://www.postgresql.org/docs/current/static/sql-select.html#SQL-FOR-UPDATE-SHARE

MySQL

Just like PostgreSQL, the FOR UPDATE clause can be used to acquire an exclusive lock, while LOCK IN SHARE MODEa is used for shared locks.

ahttp://dev.mysql.com/doc/refman/5.7/en/innodb-locking-reads.html

When using Hibernate, the application developer needs not to worry about the locking syntax employed by the underlying database system. To acquire an exclusive lock, the PESSIMISTIC_-

WRITE lock type must be used, and Hibernate will pick the underlying Dialect lock clause.

For instance, when running the following entity lock acquisition request on PostgreSQL:

```java
Post post = entityManager.find(Post.class, 1L, LockModeType.PESSIMISTIC_WRITE);
```

Hibernate is going to generate the following query:

```sql
SELECT p.id AS id1_0_0_, p.body AS body2_0_0_, p.title AS title3_0_0_,
p.version AS version4_0_0_
FROM
post p
WHERE
p.id = 1
FOR UPDATE
```

If the relational database offers support for acquiring shared locks explicitly, the PESSIMISTIC_-

READ lock type must be used instead. When fetching an entity directly using the PESSIMISTIC_READ lock type on PostgreSQL:

```java
Post post = entityManager.find(Post.class, 1L, LockModeType.PESSIMISTIC_READ);
```

Hibernate is going to use the FOR SHARE select clause:

```sql
SELECT p.id AS id1_0_0_, p.body AS body2_0_0_, p.title AS title3_0_0_,
p.version AS version4_0_0_
FROM
post p
WHERE
p.id = 1
FOR SHARE
```

If the underlying database does not support shared locks, when using the PESSIMISTIC_-

READ lock type, an exclusive lock is acquired instead. When running the previous

PESSIMISTIC_READ direct fetching example on Oracle, Hibernate will use a FOR UPDATE select clause.

Although it is much more convenient to lock entities at the moment they are fetched from the database, entities can also be locked even after they are loaded in the currently running Persistence context.

For this purpose, the EntityManager interface defines the lock method which takes a managed entity and a LockModeType:

```java
Post post = entityManager.find(Post.class, 1L);
entityManager.lock(post, LockModeType.PESSIMISTIC_WRITE);
```

When running the aforementioned example, Hibernate is going to execute the following statements:

```sql
SELECT p.id AS id1_0_0_, p.body AS body2_0_0_, p.title AS title3_0_0_,
p.version AS version4_0_0_
FROM
post p
WHERE
p.id = 1
SELECT id
FROM
post
WHERE
id = 1 AND version = 0
FOR UPDATE
```

Only a managed entity can be passed to the lock method when using the Java Persistence API. Otherwise, an IllegalArgumentException is being thrown indicating that the entity is not contained within the currently running Persistence Context.

On the other hand, the Hibernate native API offers entity reattachment upon locking as demonstrated by the following example:

```java
Post post = doInJPA(entityManager -> {
return entityManager.find(Post.class, 1L);
});
doInJPA(entityManager -> {
LOGGER.info("Lock and reattach");
Session session = entityManager.unwrap(Session.class);
session.buildLockRequest(
new LockOptions(LockMode.PESSIMISTIC_WRITE))
.lock(post);
post.setTitle("High-Performance Hibernate");
});
```

When running the test case above, Hibernate manages to acquire an exclusive lock on the associated database record while also propagating the entity state change to the database:

```sql
SELECT p.id AS id1_0_0_, p.body AS body2_0_0_, p.title AS title3_0_0_,
p.version AS version4_0_0_
FROM
post p
WHERE
p.id = 1
```

* - Lock and reattach SELECT id FROM post WHERE id = 1 AND version = 0 FOR UPDATE

```sql
UPDATE post
SET body = 'Chapter 17 summary', title = High-Performance Hibernate'
WHERE id = 1 AND version = 0
```

Because the detached entity becomes managed, the entity modification triggers an update statement at flush time.

16.2.1.1 Lock scope

By default, the lock scope is bound to the entity that is being locked explicitly. However, just like other entity state transitions, the lock acquisition request can be cascaded to child associations like the PostDetails and PostComment(s) entities in the next diagram.

**Figure 16.6: Post, PostDetails, and PostComment**

The easiest way to lock a whole entity graph is to apply the LockModeType at the entity query level.

When executing the following entity query:

Post post = entityManager.createQuery(

```sql
"select p " +
"from Post p " +
"join fetch p.details " +
"join fetch p.comments " +
"where p.id = :id", Post.class)
.setParameter("id", 1L)
.setLockMode(LockModeType.PESSIMISTIC_WRITE)
.getSingleResult();
```

Hibernate generates the following SQL query:

```sql
SELECT p.id AS id1_0_0_, p.body AS body2_0_0_, p.title AS title3_0_0_,
p.version AS version4_0_0_, pd.id AS id1_2_1_,
pd.created_by AS created_2_2_1_, pd.created_on AS created_3_2_1_,
pd.version AS version4_2_1_, pc.id AS id1_1_2_,
pc.post_id AS post_id4_1_2_, pc.review AS review2_1_2_,
pc.version AS version3_1_2_, pc.post_id AS post_id4_1_0__,
pc.id AS id1_1_0__
FROM
post p
INNER JOIN post_details pd ON p.id = pd.id
INNER JOIN post_comment pc ON p.id = pc.post_id
WHERE
p.id = 1
FOR UPDATE
```

The FOR UPDATE clause is applied to all records that are being selected, therefore, the whole result set is being locked. In this particular case, the lock scope depends on the query filtering criteria.

Aside from entity queries, Hibernate can also propagate a lock acquisition request from a parent entity to its children when using direct fetching. For this purpose, the child associations must be annotated with the Hibernate specific CascadeType.Lock[^1] attribute.

CascadeType.Lock can also be inherited implicitly when the child association is annotated with the CascadeType.ALL attribute.

[^1]: <https://docs.jboss.org/hibernate/orm/current/javadocs/org/hibernate/annotations/CascadeType.html#LOCK>

To demonstrate how the lock can be cascaded, the Post entity is changed so that the

CascadeType.ALL attribute is set on both comments and details child associations:

```java
@OneToMany(cascade = CascadeType.ALL, mappedBy = "post", orphanRemoval = true)
private List<PostComment> comments = new ArrayList<>();
```

@OneToOne(cascade = CascadeType.ALL, mappedBy = "post", orphanRemoval = true,

```java
fetch = FetchType.LAZY, optional = false)
private PostDetails details;
```

The implicit or explicit CascadeType.Lock is not sufficient because the LockRequest[^2] declares a

scope attribute which is disabled by default. For the lock to be cascaded, the scope attribute must be set to true as in the following example:

```java
Post post = entityManager.find(Post.class, 1L);
entityManager.unwrap(Session.class)
.buildLockRequest(
new LockOptions(LockMode.PESSIMISTIC_WRITE))
.setScope(true)
.lock(post);
```

However, when executing the test case above, Hibernate is going to lock only the Post entity:

```sql
SELECT p.id AS id1_0_0_, p.body AS body2_0_0_, p.title AS title3_0_0_,
p.version AS version4_0_0_
FROM
post p
WHERE
p.id = 1
SELECT id
FROM
post
WHERE
id = 1 AND version = 0
FOR UPDATE
```

For managed entities, Hibernate does not cascade the lock acquisition request even if the scope attribute is provided, therefore, the entity query alternative is preferred.

When locking a detached entity graph, Hibernate is going to reattach every entity that enabled cascade propagation while also propagating the lock request.

[^2]: <https://docs.jboss.org/hibernate/orm/current/javadocs/org/hibernate/Session.LockRequest.html>

```java
Post post = doInJPA(entityManager -> {
```

return entityManager.createQuery(

```sql
"select p " +
"from Post p " +
"join fetch p.details " +
"join fetch p.comments " +
"where p.id = :id", Post.class)
.setParameter("id", 1L)
.getSingleResult();
});
doInJPA(entityManager -> {
```

entityManager.unwrap(Session.class) .buildLockRequest(

```java
new LockOptions(LockMode.PESSIMISTIC_WRITE))
.setScope(true)
.lock(post);
});
```

When executing the test case above, Hibernate generates the following queries:

```sql
SELECT p.id AS id1_0_0_, pd.id AS id1_2_1_, pc.id AS id1_1_2_,
p.body AS body2_0_0_, p.title AS title3_0_0_, p.version AS version4_0_0_,
pd.created_by AS created_2_2_1_, pd.created_on AS created_3_2_1_,
pd.version AS version4_2_1_, pc.post_id AS post_id4_1_2_,
pc.review AS review2_1_2_, pc.version AS version3_1_2_,
pc.post_id AS post_id4_1_0__, pc.id AS id1_1_0__
FROM
post p
INNER JOIN post_details pd ON p.id = pd.id
INNER JOIN post_comment pc ON p.id = pc.post_id
WHERE
p.id = 1
SELECT id FROM post_comment WHERE id = 2 AND version = 0 FOR UPDATE
SELECT id FROM post_comment WHERE id = 3 AND version = 0 FOR UPDATE
SELECT id FROM post_details WHERE id = 1 AND version = 0 FOR UPDATE
SELECT id FROM post WHERE id =1 AND version =0 FOR UPDATE
```

Not only the Post entity is being locked but also the PostDetails and every PostComment child entity.

However, if the Post entity is loaded without initializing any child association:

```java
Post post = doInJPA(entityManager -> (Post) entityManager.find(Post.class, 1L));
```

When running the previous test case, Hibernate is going to execute the following statements:

```sql
SELECT p.id AS id1_2_0_, p.created_by AS created_2_2_0_,
p.created_on AS created_3_2_0_, p.version AS version4_2_0_
FROM
post_details p
WHERE
p.id = 1
SELECT id from post_details WHERE id =1 AND version = 0 FOR UPDATE
SELECT id from post WHERE id =1 AND version = 0 FOR UPDATE
```

Only the Post and PostDetails entities are locked this time. Because the PostDetails entity had not been fetched previously, the detached Post entity was using a proxy which only held the child association identifier and the child entity type. The one-to-one PostDetails association propagates all entity state transitions. Hence, the lock acquisition request is going to be applied to the PostDetails proxy as well. When being reassociated, the @OneToOne and @ManyToOne associations are fetched right away, and the lock is, therefore, propagated.

On the other hand, the PostComment child entries are not locked because Hibernate needs not to fetch @OneToMany and @ManyToMany associations upon reattaching the parent Post entity. The lock acquisition request is cascaded to child collections only if the collection is already initialized.

Locking too much data can hurt scalability because, once a row-level lock is acquired, other concurrent transactions that need to modify this record are going to be blocked until the first transaction either commits or rolls back. The lock cascading works only with detached entities and only if the @OneToMany and @ManyToMany associations have been previously fetched.

Being applicable to both managed and detached entities and giving better control over what entities are getting locked, the entity query locking mechanism is a much better alternative than entity lock event cascading.

16.2.1.2 Lock timeout

When acquiring a row-level lock, it is good practice to set a timeout value for which the current request is willing to wait before giving up. Depending on the current database Dialect, if the timeout value is greater than zero, Hibernate can use it to limit the lock acquisition request interval.

For the Hibernate native API, the timeout value can be supplied like this:

entityManager.unwrap(Session.class) .buildLockRequest(

new LockOptions(LockMode.PESSIMISTIC_WRITE)

```java
.setTimeOut((int) TimeUnit.SECONDS.toMillis(3))
)
.lock(post);
With JPA, the timeout value is given through the following hint:
```

entityManager.lock(post, LockModeType.PESSIMISTIC_WRITE,

Collections.singletonMap(

```java
"javax.persistence.lock.timeout",
TimeUnit.SECONDS.toMillis(3)
)
);
```

When running the aforementioned lock acquisition request on Oracle, Hibernate generates the following SQL query:

```sql
SELECT id
FROM
post
WHERE
id = 1 AND version = 0
FOR UPDATE WAIT 3
```

Even if the timeout value is given in milliseconds, the Hibernate Dialect converts it to the underlying database supported format (e.g. seconds for Oracle).

To avoid any waiting, Hibernate comes with a NO_WAIT lock option which simply sets the timeout value to 0.

entityManager.unwrap(Session.class) .buildLockRequest(

```java
new LockOptions(LockMode.PESSIMISTIC_WRITE)
.setTimeOut(LockOptions.NO_WAIT))
.lock(post);
```

The JPA alternative looks as follows:

entityManager.lock(post, LockModeType.PESSIMISTIC_WRITE,

```java
Collections.singletonMap("javax.persistence.lock.timeout", 0)
);
```

When running the lock acquisition request above on PostgreSQL, Hibernate is going to use the NO WAIT PostgreSQL clause:

```sql
SELECT id
FROM
post
WHERE
id = 1 AND version = 0
FOR UPDATE NOWAIT
```

The LockOptions.NO_WAIT option can only be used only if the underlying database supports such a construct (e.g. Oracle and PostgreSQL). For other database systems, this option is ignored and a regular pessimistic write lock clause is going to be used instead.

When using NO WAIT or some other timeout value greater than 0, if the row is already locked, the lock acquisition request is going to be aborted with the following exception:

ORA-00054: resource busy and acquire with NOWAIT specified or timeout expired

The exception is meant to notify the database client that the lock could not be acquired. However, getting an exception is not always desirable, especially when implementing a job queue mechanism.

For the following example, consider that Post entries need to be moderated to avoid spam messages or inappropriate content.

The Post entity is going to use a status attribute which indicates if the Post can be safely displayed or it requires manual intervention from a site administrator.

**Figure 16.7: Post with PostStatus**

The Post entities can be moderated by multiple administrators, so, in order to prevent them from approving the same entries, each administrator acquires a lock on the currently selected

Post entities.

List<Post> pendingPosts = entityManager.createQuery(

```sql
"select p " +
"from Post p " +
"where p.status = :status", Post.class)
.setParameter("status", PostStatus.PENDING)
.setFirstResult(5).setMaxResults(7)
.setLockMode(LockModeType.PESSIMISTIC_WRITE)
.setHint("javax.persistence.lock.timeout", 0)
.getResultList();
```

When Alice runs the aforementioned query on Oracle, Hibernate will generate the following statements:

```sql
SELECT * FROM (
SELECT
row_.*, rownum rownum_ FROM (
SELECT p.id AS id1_0_, p.body AS body2_0_, p.status AS status3_0_,
p.title AS title4_0_, p.version AS version5_0_
FROM
post p
WHERE
p.status = 0
) row_
WHERE
rownum <= 7
)
WHERE rownum_ > 5
SELECT id FROM post WHERE id = 5 AND version = 0 FOR UPDATE
SELECT id FROM post WHERE id = 6 AND version = 0 FOR UPDATE
```

Follow-on locking

The Oracle Dialect cannot employ the FOR UPDATE clause when the underlying query uses pagination because otherwise the database throws the following exception:

ORA-02014: cannot select FOR UPDATE from view with DISTINCT, GROUP BY, etc.

Because the original query cannot use the FOR UPDATE clause, each matching row must be locked with a secondary select statement.

After Alice has locked some Post records and started to moderate them, Bob decides to do the same thing, but, when he tries to run the same query as Alice, he will get an exception because the same rows are already locked. To address this usability issue, some database systems (e.g. Oracle 10g, PostgreSQL 9.5) define a SKIP LOCKED clause so a query can filter out row entries that are already locked. The following example is going to demonstrate how SKIP LOCKED works:

```sql
private List<Post> pendingPosts(EntityManager entityManager, int lockCount,
int maxResults, Integer maxCount) {
LOGGER.debug("Attempting to lock {} Post(s) entities", maxResults);
List<Post> posts= entityManager.createQuery(
"select p from Post p where p.status = :status", Post.class)
.setParameter("status", PostStatus.PENDING)
.setMaxResults(maxResults)
.unwrap(org.hibernate.Query.class)
.setLockOptions(new LockOptions(LockMode.UPGRADE_SKIPLOCKED))
.list();
if(posts.isEmpty()) {
if(maxCount == null) {
maxCount = pendingPostCount(entityManager);
}
if(maxResults < maxCount || maxResults == lockCount) {
maxResults += lockCount;
return pendingPosts(entityManager, lockCount, maxResults, maxCount);
}
}
LOGGER.debug("{} Post(s) entities have been locked", posts.size());
return posts;
}
```

The pendingPostCount method calculates the maximum number of Post entities that are eligible for moderation.

```java
private int pendingPostCount(EntityManager entityManager) {
```

int postCount = ((Number) entityManager.createQuery(

```sql
"select count(*) from Post where status = :status")
.setParameter("status", PostStatus.PENDING)
.getSingleResult()).intValue();
LOGGER.debug("There are {} PENDING Post(s)", postCount);
return postCount;
}
```

Because the aforementioned pendingPost is private, the following simplified overloaded method is going to be used by the service layer:

```java
public List<Post> pendingPosts(EntityManager entityManager, int lockCount) {
return pendingPosts(entityManager, lockCount, lockCount, null);
}
With this new method in place, Alice and Bob can moderate distinct Post entries without
risking any pessimistic locking conflict.
doInJPA(entityManager -> {
final int lockCount = 2;
LOGGER.debug("Alice wants to moderate {} Post(s)", lockCount);
List<Post> pendingPosts = pendingPosts(entityManager, lockCount);
List<Long> ids = pendingPosts
.stream().map(Post::getId).collect(toList());
assertTrue(ids.size() == 2 && ids.contains(0L) &&
ids.contains(1L));
executeSync(() -> {
doInJPA(_entityManager -> {
LOGGER.debug("Bob wants to moderate {} Post(s)", lockCount);
List<Post> _pendingPosts = pendingPosts(_entityManager, lockCount);
List<Long> _ids = _pendingPosts
.stream().map(Post::getId).collect(toList());
assertTrue(_ids.size() == 2 &&
_ids.contains(2L) && _ids.contains(3L));
});
});
});
```

When running the aforementioned test case, Hibernate generates the following output:

* - Alice wants to moderate 2 Post(s)
* - Attempting to lock 2 Post(s) entities SELECT * FROM (

```sql
SELECT p.id AS id1_0_, p.body AS body2_0_, p.status AS status3_0_,
p.title AS title4_0_, p.version AS version5_0_
FROM
post p
WHERE
p.status = 0
)
WHERE
rownum <= 2
FOR UPDATE SKIP LOCKED
-- 2 Post(s) entities have been locked
```

* - Bob wants to moderate 2 Post(s)
* - Attempting to lock 2 Post(s) entities SELECT * FROM (

```sql
SELECT p.id AS id1_0_, p.body AS body2_0_, p.status AS status3_0_,
p.title AS title4_0_, p.version AS version5_0_
FROM
post p
WHERE
p.status = 0
)
WHERE
rownum <= 2
FOR UPDATE SKIP LOCKED
SELECT COUNT(*) AS col_0_0_
FROM
post p
WHERE
p.status = 0
-- There are 10 PENDING Post(s)
```

* - Attempting to lock 4 Post(s) entities SELECT * FROM (

```sql
SELECT p.id AS id1_0_, p.body AS body2_0_, p.status AS status3_0_,
p.title AS title4_0_, p.version AS version5_0_
FROM
post p
WHERE
p.status = 0
)
WHERE
rownum <= 4
FOR UPDATE SKIP LOCKED
-- 2 Post(s) entities have been locked
```

The flow can be explained as follows:

* The lockCount variable dictates how many Post entities a user should be locking at once.
* Alice tries to lock 2 Post entities with a status of PENDING, and since no other user has locked any such entity, she manages to lock the first 2 Post records.
* Bob also attempts to lock 2 Post entities.
* At first, Bob’s tries to lock 2 PENDING Post(s), but the query returns no record. This happens because the SKIP LOCKED clause ignores the matching records that are already locked (by Alice).
* Bob counts the number of Post entities to know many records are eligible for moderation. Even if Alice locked two rows, because Oracle uses MVCC, the pendingPostCount query is able to count both locked and unlocked database table records.
* Knowing that there are still some records that might not be locked, he increments the

maxResults variable with the lockCount value.

* The maxResults tells the maximum number of entities that can be scanned by the current iteration.
* Because the maxResults has a value of 4, there are 4 Post records being scanned. However, since Alice has locked the first two entries (identifiers 0 and 1), Bob can only lock the next 2 records (identifiers 2 and 3).
* Because Bob has managed to lock at least one Post entity, he can continue with the moderation process.

LockMode.UPGRADE_SKIPLOCKED

Long before JPA 1.0, Hibernate defined its own LockMode(s), which have been later used as the base of the Java Persistence LockModeType(s). Although JPA 2.1 does not offer support for skipping locks, when using Hibernate, by setting the timeout value to LockOptions.SKIP_LOCKED (e.g. value of -2) the SKIP LOCKED clause is applied to the pessimistic locking clause. However, because of the follow-on locking behavior on Oracle, the SKIP LOCKED cannot by applied to the original query, so, not only the expected goal is not achieved, but this query will fail due to a stale state false positive. If a given row is already locked, the secondary follow-on locking query will not find any row, and Hibernate is going to assume that the row version has changed, or the row was deleted in the meanwhile, causing an OptimisticLockingException.

Fortunately, with Hibernate 5.1, the LockMode.UPGRADE_SKIPLOCKED bypasses the follow-on locking mechanism, as demonstrated by the previous example. Nevertheless, the locking query cannot use any ORDER BY, GROUP BY, or offset pagination. Otherwise, Oracle is going to throw an exceptiona.

ahttps://docs.oracle.com/database/121/SQLRF/statements_10002.htm#SQLRF[^55371]

Hibernate 5.2.1 follow-on locking improvements

Since Hibernate 5.2.1, the Oracle Dialect does not resort to follow-on locking on every situation. Therefore, the follow-on locking mechanism is activated if the underlying query contains one of the subsequent directives:

* DISTINCT
* GROUP BY
* UNION or UNION ALL
* Pagination with ORDER BY or with OFFSET (e.g. setFirstResult)

For this reason, on Hibernate 5.2.1, the previous example which was using UPGRADE_SKIPLOCKED

LockMode to bypass the follow-on locking mechanism can be rewritten as follows:

List<Post> posts= entityManager.createQuery(

"select p from Post p where p.status = :status", Post.class) .setParameter("status", PostStatus.PENDING) .setMaxResults(maxResults) .unwrap(org.hibernate.Query.class) .setLockOptions(new LockOptions(LockMode.PESSIMISTIC_WRITE)

```java
.setTimeOut(LockOptions.SKIP_LOCKED))
.list();
```

The aforementioned query works since it does not use any directive that would otherwise require the follow-on locking mechanism.

More, if there is any situation where the follow-on locking mechanism is being chosen although the underlying SQL query can successfully apply the row-level lock acquisition request, the LockOptions now offers the possibility of manually setting the follow-on locking strategy:

List<Post> posts= entityManager.createQuery(

"select p from Post p where p.status = :status", Post.class) .setParameter("status", PostStatus.PENDING) .setMaxResults(maxResults) .unwrap(org.hibernate.Query.class) .setLockOptions(new LockOptions(LockMode.PESSIMISTIC_WRITE)

```java
.setTimeOut(LockOptions.SKIP_LOCKED)
.setFollowOnLocking(false))
.list();
```

### 16.2.2 LockModeType.OPTIMISTIC

To understand how LockModeType.OPTIMISTIC works, the following entities are going to be used in the upcoming test cases:

**Figure 16.8: Post and PostComment entities**

Once a Post is published, users can add PostComment(s) to review and share their opinions about the content of the aforementioned Post. Even if both entities have a version attribute, lost updates can be prevented at the entity level only. However, the PostComment entity is strictly related to the state of the Post entity that was used for reviewing. If a concurrent user modified the Post entity content, the PostComment might no longer be relevant.

In the following example, Alice is going to select a Post entity, and, while she is reviewing the

Post entity, Bob is changing its content so that it now references the 17th chapter of the book. Alice, being unaware of the latest Post change, she adds a PostComment for the 16th chapter of the book.

```java
doInJPA(entityManager -> {
LOGGER.info("Alice loads the Post entity");
Post post = entityManager.find(Post.class, 1L);
executeSync(() -> {
doInJPA(_entityManager -> {
LOGGER.info("Bob loads the Post entity and modifies it");
Post _post = _entityManager.find(Post.class, 1L);
_post.setBody("Chapter 17 summary");
});
});
LOGGER.info("Alice adds a PostComment to the previous Post entity version");
PostComment comment = new PostComment();
comment.setId(1L);
comment.setReview("Chapter 16 is about Caching.");
comment.setPost(post);
entityManager.persist(comment);
});
```

When executing the test case above, Hibernate generates the following output:

* - Alice loads the Post entity SELECT p.id AS id1_0_0_, p.body AS body2_0_0_, p.title AS title3_0_0_, p.version AS version4_0_0_ FROM post p WHERE p.id = 1
* - Bob loads the Post entity and modifies it SELECT p.id AS id1_0_0_, p.body AS body2_0_0_, p.title AS title3_0_0_, p.version AS version4_0_0_ FROM post p WHERE p.id = 1

```sql
UPDATE post
SET
body = 'Chapter 17 summary' ,
title = 'High-Performance Java Persistence' ,
version = 1
WHERE
id = 1 AND version = 0
```

* - Alice adds a PostComment review to the previous Post entity version INSERT INTO post_comment (post_id, review, version, id) VALUES (1, 'Chapter 16 is about Caching.', 0, 1)

This is still a lost update that would never happen if Alice were taking a shared lock on the Post entity. Unfortunately, a shared lock would compromise application scalability because Alice reviews the Post in the user-think time. For this reason, an optimistic lock should be acquired on the Post entity to ensure that the entity state hasn’t change since it was first loaded.

```java
entityManager.lock(post, LockModeType.OPTIMISTIC);
LOGGER.info("Alice adds a PostComment to the previous Post entity version");
PostComment comment = new PostComment();
comment.setId(1L);
comment.setReview("Chapter 16 is about Caching.");
comment.setPost(post);
entityManager.persist(comment);
```

LockModeType.OPTIMISTIC does not acquire an actual lock right way, but instead it schedules a version check towards the end of the currently running transaction.

When executing the test case above while also acquiring the LockModeType.OPTIMISTIC on the

Post entity, Hibernate generates the following output:

* - Alice adds a PostComment review to the previous Post entity version INSERT INTO post_comment (post_id, review, version, id) VALUES (1, 'Chapter 16 is about Caching.', 0, 1)

```sql
SELECT version FROM post WHERE id = 1
```

javax.persistence.OptimisticLockException: Newer version [1] of entity [[Post#1]] found in database

LockModeType.OPTIMISTIC instructs Hibernate to check the Post entity version towards the end of the transaction. If the version has changed, an OptimisticLockException is thrown.

16.2.2.1 Inconsistency risk

Unfortunately, this kind of application-level check is always prone to inconsistencies due to bad timing. For example, after Hibernate executes the version check select statement, a concurrent transaction can simply update the Post entity without the first transaction noticing anything.

**Figure 16.9: LockModeType.OPTIMISTIC window of opportunity**

During that window of opportunity, another concurrent transaction might change the Post entity record before the first transaction commits its changes. To prevent such an incident, the

LockModeType.OPTIMISTIC should be accompanied by a shared lock acquisition:

```java
entityManager.lock(post, LockModeType.OPTIMISTIC);
entityManager.lock(post, LockModeType.PESSIMISTIC_READ);
```

This way, no other concurrent transaction can change the Post entity until the current transaction is ended.

### 16.2.3 LockModeType.OPTIMISTIC_FORCE_INCREMENT

LockModeType.OPTIMISTIC_FORCE_INCREMENT allows incrementing the locked entity version even if the entity hasn’t changed at all in the currently running Persistence Context.

The @Version attribute should never have a setter method because this attribute is managed automatically by Hibernate. To increment the version of a given entity, one of the two FORCE_INCREMENT lock strategies must be used instead.

To understand how the LockModeType.OPTIMISTIC_FORCE_INCREMENT strategy works, consider the following Version Control system:

**Figure 16.10: Repository, Commit, and Change**

The Repository is the root entity, and each change is represented by a Commit entry which, in turn, may contain one or more Change embeddable types.

In this particular example, the Repository version must be incremented with each new Commit being added. The Repository entity version is used to ensure that commits are applied sequentially, and a user is notified if a newer commit was added since she has updated her working copy.

The following example depicts the user flow for this particular Version Control system:

Repository repository = entityManager.find(Repository.class, 1L,

```java
LockModeType.OPTIMISTIC_FORCE_INCREMENT);
Commit commit = new Commit(repository);
commit.getChanges().add(new Change("FrontMatter.md", "0a1,5..."));
commit.getChanges().add(new Change("HibernateIntro.md", "17c17..."));
entityManager.persist(commit);
```

When Alice executes the commit command, every file that she changes is going to be represented by a Change embeddable which also holds the diff between the original and the

current file content. The Repository entity is loaded using the LockModeType.OPTIMISTIC_FORCE_IN-

CREMENT lock strategy so that its version is going to be incremented at the end of the current transaction.

Upon running the aforementioned test case, Hibernate generates the following statements:

```sql
SELECT r.id AS id1_2_0_, r.name AS name2_2_0_, r.version AS version3_2_0_
FROM
repository r WHERE
r.id = 1
INSERT INTO commit (repository_id, id) VALUES (1, 2)
INSERT INTO commit_change (commit_id, diff, path)
VALUES (2, '0a1,5...', 'FrontMatter.md')
INSERT INTO commit_change (commit_id, diff, path)
VALUES (2, '17c17...', 'HibernateIntro.md')
UPDATE repository SET version = 1 WHERE id = 1 AND version = 0
```

The Repository version is incremented before transaction completion, and, unlike LockMode-

Type.OPTIMISTIC, data integrity is guaranteed by the current transaction isolation level. If the

Repository version changed in between, the update will fail and an

OptimisticLockingException is going to trigger a transaction rollback.

In the following example, both Alice and Bob are going to issue two commits concurrently:

```java
doInJPA(entityManager -> {
```

Repository repository = entityManager.find(Repository.class, 1L,

```java
LockModeType.OPTIMISTIC_FORCE_INCREMENT);
executeSync(() -> {
doInJPA(_entityManager -> {
```

Repository _repository = _entityManager.find(Repository.class, 1L,

```java
LockModeType.OPTIMISTIC_FORCE_INCREMENT);
Commit _commit = new Commit(_repository);
_commit.getChanges().add(new Change("Intro.md", "0a1,2..."));
_entityManager.persist(_commit);
});
});
Commit commit = new Commit(repository);
commit.getChanges().add(new Change("FrontMatter.md", "0a1,5..."));
commit.getChanges().add(new Change("HibernateIntro.md", "17c17..."));
entityManager.persist(commit);
});
```

When running the aforementioned test case, Hibernate generates the following output:

* - Alice selects the Repository entity SELECT r.id AS id1_2_0_, r.name AS name2_2_0_, r.version AS version3_2_0_ FROM repository r WHERE r.id = 1
* - Bob selects the Repository entity SELECT r.id AS id1_2_0_, r.name AS name2_2_0_, r.version AS version3_2_0_ FROM repository r WHERE r.id = 1
* - Bob adds a new Commit entity INSERT INTO commit (repository_id, id) VALUES (1, 2)

```sql
INSERT INTO commit_change (commit_id, diff, path)
VALUES (2, '0a1,2...', 'Intro.md')
```

* - Bob increments the Repository version UPDATE repository SET version = 1 WHERE id = 1 AND version = 0
* - Alice adds a new Commit entity INSERT INTO commit (repository_id, id) VALUES (1, 3)

```sql
INSERT INTO commit_change (commit_id, diff, path)
VALUES (3, '0a1,5...', 'FrontMatter.md')
INSERT INTO commit_change (commit_id, diff, path)
VALUES (3, '17c17...', 'HibernateIntro.md')
```

* - Alice increments the Repository version UPDATE repository SET version = 1 WHERE id = 1 AND version = 0
* -Exception thrown javax.persistence.RollbackException: Error while committing the transaction Caused by: javax.persistence.OptimisticLockException: Caused by: org.hibernate.StaleObjectStateException: Row was updated or deleted by another transaction (or unsaved-value mapping was incorrect)

**Figure 16.11: LockModeType.OPTIMISTIC_FORCE_INCREMENT**

The flow can be explained as follows:

* Alice fetches the Repository entity and instructs Hibernate to acquire an OPTIMISTIC_FORCE_-

INCREMENT application-level lock.

* Alice’s thread is suspended by the JVM thread scheduler, so Bob gets the chance to fetch the Repository entity using the OPTIMISTIC_FORCE_INCREMENT lock strategy.
* Bob manages to add a new Commit entity, and his transaction is committed. Therefore, the

Repository entity version is also incremented.

* Alice thread is resumed, and she adds one Commit entity and initiates a transaction commit.
* The optimistic locking update fails because the Repository version has changed.

OPTIMISTIC_FORCE_INCREMENT is useful for propagating a child entity state change to the parent entity optimistic locking version. By applying an optimistic lock on a common parent entity, it is, therefore, possible to coordinate multiple child entities whose changes need to be applied sequentially so that no update is being lost.

### 16.2.4 LockModeType.PESSIMISTIC_FORCE_INCREMENT

Just like OPTIMISTIC_FORCE_INCREMENT, PESSIMISTIC_FORCE_INCREMENT can be used to increment the version of any given entity. However, if for OPTIMISTIC_FORCE_INCREMENT the entity version is incremented towards the end of the currently running transaction, the PESSIMISTIC_FORCE_IN-

CREMENT forces the version incrementation right away, as demonstrated by the test case below.

Repository repository = entityManager.find(Repository.class, 1L,

```java
LockModeType.PESSIMISTIC_FORCE_INCREMENT);
Commit commit = new Commit(repository);
commit.getChanges().add(new Change("FrontMatter.md", "0a1,5..."));
commit.getChanges().add(new Change("HibernateIntro.md", "17c17..."));
entityManager.persist(commit);
```

Hibernate generates the following statements:

```sql
SELECT r.id AS id1_2_0_, r.name AS name2_2_0_, r.version AS version3_2_0_
FROM
repository r
WHERE
r.id = 1
FOR UPDATE
UPDATE repository SET version = 1 WHERE id = 1 AND version = 0
INSERT INTO commit (repository_id, id) VALUES (1, 2)
INSERT INTO commit_change (commit_id, diff, path)
VALUES (2, '0a1,5...', 'FrontMatter.md')
INSERT INTO commit_change (commit_id, diff, path)
VALUES (2, '17c17...', 'HibernateIntro.md')
```

The Repository is locked using a FOR UPDATE SQL clause in the select statement that fetches the aforementioned entity. The Repository entity is also incremented before the entity is returned to the data access layer.

In the following example, Alice is going to lock the Repository only after she previously fetched the very same entity. However, in the meanwhile, Bob is going to increment the Repository entity version using a PESSIMISTIC_FORCE_INCREMENT lock.

```java
Repository repository = entityManager.find(Repository.class, 1L);
executeSync(() -> {
doInJPA(_entityManager -> {
```

Repository _repository = _entityManager.find(Repository.class, 1L,

```java
LockModeType.PESSIMISTIC_FORCE_INCREMENT);
Commit _commit = new Commit(_repository);
_commit.getChanges().add(new Change("Intro.md", "0a1,2..."));
_entityManager.persist(_commit);
});
});
entityManager.lock(repository, LockModeType.PESSIMISTIC_FORCE_INCREMENT);
```

When running the test case above, Hibernate generates the following output:

* - Alice selects the Repository entity SELECT r.id AS id1_2_0_, r.name AS name2_2_0_, r.version AS version3_2_0_ FROM repository r WHERE r.id = 1
* - Bob selects the Repository entity SELECT r.id AS id1_2_0_, r.name AS name2_2_0_, r.version AS version3_2_0_ FROM repository r WHERE r.id = 1 FOR UPDATE
* - Bob increments the Repository version upon fetching the Repository entity UPDATE repository SET version = 1 WHERE id = 1 AND version = 0
* - Bob adds a new Commit entity INSERT INTO commit (repository_id, id) VALUES (1, 2)

```sql
INSERT INTO commit_change (commit_id, diff, path)
VALUES (2, '0a1,2...', 'Intro.md')
```

* - Alice tries to increment the Repository entity version UPDATE repository SET version = 1 WHERE id = 1 AND version = 0
* - Exception thrown javax.persistence.OptimisticLockException: Caused by: org.hibernate.StaleObjectStateException:

**Figure 16.12: Fail fast PESSIMISTIC_FORCE_INCREMENT lock acquisition**

The flow can be explained as follows:

* Alice fetches the Repository entity without acquiring any physical or logical lock.
* Alice’s thread is suspended by the JVM thread scheduler, so Bob gets the chance to fetch the Repository entity using the PESSIMISTIC_FORCE_INCREMENT lock strategy.
* The Repository entity version is incremented right away.
* Bob manages to add a new Commit entity, and his transaction is committed.
* Alice thread is resumed, and she attempts to acquire a PESSIMISTIC_FORCE_INCREMENT on the already fetched Repository entity.
* The optimistic locking update fails because the Repository version was changed by Bob.

The instantaneous version incrementation has the following benefits:

* Because the entity is locked at the database row level, the entity version incrementation is guaranteed to succeed.
* If the entity was previously loaded without being locked and the

PESSIMISTIC_FORCE_INCREMENT version update fails, the currently running transaction can be rolled back right away.

Once a transaction acquires the PESSIMISTIC_FORCE_INCREMENT lock and increments the entity version, no other transaction can acquire a PESSIMISTIC_FORCE_INCREMENT lock because the second select statement is blocked until the first transaction releases the row-level physical lock.

The following example aims to demonstrate how two concurrent transactions can be coordinated through a common entity PESSIMISTIC_FORCE_INCREMENT lock acquisition.

```java
doInJPA(entityManager -> {
```

Repository repository = entityManager.find(Repository.class, 1L,

```java
LockModeType.PESSIMISTIC_FORCE_INCREMENT);
executeAsync(() -> doInJPA(_entityManager -> {
startLatch.countDown();
Repository _repository = _entityManager.find(Repository.class, 1L,
LockModeType.PESSIMISTIC_FORCE_INCREMENT);
Commit _commit = new Commit(_repository);
_commit.getChanges().add(new Change("Intro.md", "0a1,2..."));
_entityManager.persist(_commit);
_entityManager.flush();
endLatch.countDown();
}));
awaitOnLatch(startLatch);
LOGGER.info("Sleep for 500ms to delay the other transaction");
sleep(500);
Commit commit = new Commit(repository);
commit.getChanges().add(new Change("FrontMatter.md", "0a1,5..."));
commit.getChanges().add(new Change("HibernateIntro.md", "17c17..."));
entityManager.persist(commit);
});
endLatch.await();
```

The awaitOnLatch and sleep method utilities have the role of converting the

InterruptedException into a RuntimeException which, unlike checked exceptions, can be propagated throughout a lambda expression without having to add unnecessary try/catch clauses.

When executing the test case above, Hibernate generates the following statements:

* - Alice selects the Repository entity SELECT r.id AS id1_2_0_, r.name AS name2_2_0_, r.version AS version3_2_0_ FROM repository r WHERE r.id = 1 FOR UPDATE
* - Alice increments the Repository version upon fetching the Repository entity UPDATE repository SET version = 1 WHERE id = 1 AND version = 0
* - Bob tries to select the Repository entity, but his select is blocked SELECT r.id AS id1_2_0_, r.name AS name2_2_0_, r.version AS version3_2_0_ FROM repository r WHERE r.id = 1 FOR UPDATE
* - Alice waits 500 ms to delay Bob's lock acquisition request
* - Alice adds a new Commit entity INSERT INTO commit (repository_id, id) VALUES (1, 2)

```sql
INSERT INTO commit_change (commit_id, diff, path)
VALUES (2, '0a1,5...', 'FrontMatter.md')
INSERT INTO commit_change (commit_id, diff, path)
VALUES (2, '17c17...', 'HibernateIntro.md')
```

* - Bob's increments the Repository version upon fetching the Repository entity UPDATE repository SET version = 2 WHERE id = 1 AND version = 1
* - Bob adds a new Commit entity INSERT INTO commit (repository_id, id) VALUES (1, 3)

```sql
INSERT INTO commit_change (commit_id, diff, path)
VALUES (3, '0a1,2...', 'Intro.md')
```

**Figure 16.13: LockModeType.PESSIMISTIC_FORCE_INCREMENT**

The flow can be explained as follows:

* Alice fetches the Repository entity while also acquiring a row-level lock and incrementing the entity version.
* Alice’s thread is suspended by the JVM thread scheduler, so Bob gets the chance to fetch the Repository entity using the PESSIMISTIC_FORCE_INCREMENT lock strategy.
* Because it uses a FOR UPDATE clause, Bob Repository entity select statement is blocked by Alice’s row-level lock.
* Alice thread is resumed, and she waits for 500 ms to delay Bob’s lock acquisition request.
* Alice adds a new Commit entity, and her transaction is committed. Therefore, the Repository entity row-level lock is released.
* Bob can resume his select statement, and he acquires a row-level lock on the Repository entity.
* The Repository entity version is incremented by the PESSIMISTIC_FORCE_INCREMENT lock strategy.
* Bob manages to add his Commit entity and commits his transaction.

Once the row-level lock is acquired, the entity version update is guaranteed to succeed, therefore, reducing the likelihood of getting an OptimisticLockingException.

## 16.3 Handling OptimisticLockException with Retry Logic

In systems using optimistic locking, concurrency conflicts (which throw an `OptimisticLockException` or Hibernate's `StaleObjectStateException`) are expected behavior when two transactions attempt to update the same record version concurrently. 

To handle these conflicts robustly without failing the user request, you should implement an automatic transaction retry mechanism. Below is a clean, production-grade retry template in Java:

```java
import javax.persistence.EntityManager;
import javax.persistence.EntityManagerFactory;
import javax.persistence.EntityTransaction;
import javax.persistence.OptimisticLockException;
import org.hibernate.StaleObjectStateException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class TransactionRetryTemplate {

    private static final Logger log = LoggerFactory.getLogger(TransactionRetryTemplate.class);
    private final EntityManagerFactory emf;

    public TransactionRetryTemplate(EntityManagerFactory emf) {
        this.emf = emf;
    }

    @FunctionalInterface
    public interface TransactionCallback<T> {
        T execute(EntityManager em);
    }

    public <T> T executeWithRetry(TransactionCallback<T> callback, int maxAttempts, long backoffMillis) {
        int attempts = 0;
        while (true) {
            attempts++;
            EntityManager em = emf.createEntityManager();
            EntityTransaction tx = em.getTransaction();
            try {
                tx.begin();
                T result = callback.execute(em);
                tx.commit();
                return result;
            } catch (Exception e) {
                if (tx != null && tx.isActive()) {
                    tx.rollback();
                }
                
                // Identify if it's an optimistic locking exception
                boolean isLockException = isOptimisticLockException(e);
                
                if (isLockException && attempts < maxAttempts) {
                    log.warn("Optimistic locking conflict detected on attempt {}/{}. Retrying in {}ms...", 
                        attempts, maxAttempts, backoffMillis);
                    try {
                        Thread.sleep(backoffMillis);
                    } catch (InterruptedException ie) {
                        Thread.currentThread().interrupt();
                        throw new RuntimeException("Retry thread interrupted", ie);
                    }
                } else {
                    log.error("Transaction failed permanently after {} attempt(s): {}", attempts, e.getMessage());
                    throw e;
                }
            } finally {
                if (em != null && em.isOpen()) {
                    em.close();
                }
            }
        }
    }

    private boolean isOptimisticLockException(Throwable e) {
        Throwable cause = e;
        while (cause != null) {
            if (cause instanceof OptimisticLockException || cause instanceof StaleObjectStateException) {
                return true;
            }
            cause = cause.getCause();
        }
        return false;
    }
}
```

### 16.3.1 Usage Example

Here is how you would use the retry template to update a product price safely under optimistic locking:

```java
public void updateProductPrice(Long productId, double newPrice) {
    TransactionRetryTemplate retryTemplate = new TransactionRetryTemplate(entityManagerFactory);
    
    retryTemplate.executeWithRetry(em -> {
        // Find entity (with @Version attribute inside Product entity)
        Product product = em.find(Product.class, productId);
        product.setPrice(newPrice);
        // Will throw OptimisticLockException if version has changed on commit
        return product;
    }, 3, 100); // 3 attempts, 100ms backoff
}
```

