# 13. Batching

As explained in the JDBC Batch Updates chapter, grouping multiple statements can reduce the number of database roundtrips, therefore, lowering transaction response time.

When it comes to translating entity state transitions, Hibernate uses only PreparedStatement(s) for the automatically generated insert, update, and delete DML operations. This way, the application is protected against SQL injection attacks, and the data access layer can better take advantage of JDBC batching and statement caching.

```java
With plain JDBC, batch updates require programmatic configuration because, instead of
calling executeUpdate, the application developer must use the addBatch and executeBatch meth-
ods. Unfortunately, performance tuning is sometimes done only after the application is
deployed into production, and switching to batching JDBC statements requires significant
code changes.
```

By default, Hibernate doesn’t use JDBC batch updates, so when inserting 3 Post entities:

```java
for (int i = 0; i < 3; i++) {
entityManager.persist(new Post(String.format("Post no. %d", i + 1)));
}
```

Hibernate executes 3 insert statements, each one in a separate database roundtrip:

```sql
INSERT INTO post (title, id) VALUES (Post no. 1, 1)
INSERT INTO post (title, id) VALUES (Post no. 2, 2)
INSERT INTO post (title, id) VALUES (Post no. 3, 3)
```

Unlike JDBC, Hibernate can switch to batched PreparedStatement(s) with just one configuration property, and no code change is required:

<property name="hibernate.jdbc.batch_size" value="5"/>

The hibernate.jdbc.batch_size configuration is applied globally for all Session(s).

Session-level JDBC batching

Hibernate 5.2 adds support for Session-level JDBC batching. Prior to this release, there was no way to customize the JDBC batch size on a per-business use case basis. However, this feature is really useful since not all business use cases have the same data persistence requirements.

The JDBC batch size can be set programmatically on a Hibernate Session as follows:

```java
doInJPA(entityManager -> {
entityManager.unwrap(Session.class).setJdbcBatchSize(10);
for ( long i = 0; i < entityCount; ++i ) {
Post post = new Post();
post.setTitle(String.format("Post nr %d", i));
entityManager.persist(post);
}
});
```

If the EntityManager uses a PersistenceContextType.EXTENDED scope, it is good practice to reset the custom JDBC batch size before existing the current business method:

```java
@PersistenceContext(type = PersistenceContextType.EXTENDED)
private EntityManager entityManager;
@TransactionAttribute(value=REQUIRED)
public void savePosts() {
entityManager.unwrap(Session.class).setJdbcBatchSize(10);
try {
for ( long i = 0; i < entityCount; ++i ) {
Post post = new Post();
post.setTitle(String.format("Post nr %d", i));
entityManager.persist(post);
}
entityManager.flush();
} finally {
entityManager.unwrap(Session.class).setJdbcBatchSize(null);
}
}
```

By setting the Session-level JDBC batch size to null, Hibernate is going to use the SessionFactory configuration (e.g. hibernate.jdbc.batch_size) the next time the EXTENDED EntityManager gets reused.

## 13.1 Batching insert statements

After setting the batch size property, when rerunning the previous test case, Hibernate generates a single insert statement:

Query: ["INSERT INTO post (title, id) VALUES (?, ?)"], Params: [('Post no. 1', 1), ('Post no. 2', 2), ('Post no. 3', 3)]

Identity columns and JDBC batching

If the Post identifier used an identity column, Hibernate would disable batched inserts.

```sql
INSERT INTO post (id, title) VALUES (default, 'Post no. 1')
INSERT INTO post (id, title) VALUES (default, 'Post no. 2')
INSERT INTO post (id, title) VALUES (default, 'Post no. 3')
```

Once an entity becomes managed, the Persistence Context needs to know the entity identifier to construct the first-level cache entry key, and, for identity columns, the only way to find the primary key value is to execute the insert statement.

This restriction does not apply to update and delete statements which can still benefit from JDBC batching even if the entity uses the identity strategy.

Assuming the Post entity has a @OneToMany association with the PostComment entity, and the persist event is cascaded from the Post entity to its PostComment children:

```java
@OneToMany(cascade = CascadeType.ALL, mappedBy = "post", orphanRemoval = true)
private List<PostComment> comments = new ArrayList<>();
```

When persisting three Post(s) along with their PostComment child entities:

```java
for (int i = 0; i < 3; i++) {
Post post = new Post(String.format("Post no. %d", i));
post.addComment(new PostComment("Good"));
entityManager.persist(post);
}
```

Hibernate executes one insert statement for each persisted entity:

```sql
INSERT INTO post (title, id) VALUES ('Post no. 0', 1)
INSERT INTO post_comment (post_id, review, id) VALUES (1, 'Good', 2)
INSERT INTO post (title, id) VALUES ('Post no. 1', 3)
INSERT INTO post_comment (post_id, review, id) VALUES (3, 'Good', 4)
INSERT INTO post (title, id) VALUES ('Post no. 2', 5)
INSERT INTO post_comment (post_id, review, id) VALUES (5, 'Good', 6)
```

Even if the JDBC batching is enabled, Hibernate still executes each statement separately. This is because JDBC batching requires executing the same PreparedStatement, and, since the parent and the child entity persist operations are interleaved, the batch must be flushed prior to proceeding with an entity of different type.

To fix this, the inserts must be ordered while still maintaining the parent-child referential integrity rules. For this purpose, Hibernate offers the following configuration property:

<property name="hibernate.order_inserts" value="true"/>

```sql
With this setting in place, Hibernate can benefit from JDBC batching once more:
INSERT INTO post (title, id)
VALUES (Post no. 0, 1), (Post no. 1, 3), (Post no. 2, 5)
INSERT INTO post_comment (post_id, review, id)
VALUES (1, Good, 2), (3, Good, 4), (5, Good, 6)
```

## 13.2 Batching update statements

Once the hibernate.jdbc.batch_size configuration property is set up, JDBC batching applies to SQL update statements too. Running the following test case:

List<Post> posts = entityManager.createQuery(

```sql
"select p from Post p ", Post.class)
.getResultList();
posts.forEach(post -> post.setTitle(post.getTitle().replaceAll("no", "nr")));
```

Hibernate generates only one SQL update statement:

Query: ["UPDATE post SET title = ? WHERE id = ?"], Params: [('Post nr. 1', 1), ('Post nr. 2', 2), ('Post nr. 3', 3)]

Just like it was the case for batching insert statements, when updating entities of different types:

List<PostComment> comments = entityManager.createQuery(

```sql
"select c " +
"from PostComment c " +
"join fetch c.post ", PostComment.class)
.getResultList();
comments.forEach(comment -> {
comment.setReview(comment.getReview().replaceAll("Good", "Very good"));
Post post = comment.getPost();
post.setTitle(post.getTitle().replaceAll("no", "nr"));
});
```

Hibernate flushes the batched PreparedStatement before switching to an entity of a different type:

Query: ["UPDATE post_comment SET post_id = ?, review = ? WHERE id = ?"], Params: [(1, 'Very good', 2)]

Query: ["UPDATE post SET title = ? WHERE id = ?"], Params: [('Post nr. 0', 1)]

Query: ["UPDATE post_comment SET post_id = ?, review = ? WHERE id = ?"], Params: [(3, 'Very good', 4)]

Query: ["UPDATE post SET title = ? WHERE id = ?"], Params: [('Post nr. 1', 3)]

Query: ["UPDATE post_comment SET post_id = ?, review = ? WHERE id = ?"], Params: [(5, 'Very good', 6)]

Query: ["UPDATE post SET title = ? WHERE id = ?"], Params: [('Post nr. 2', 5)]

Analogous to ordering inserts, Hibernate offers the possibility of reordering batch updates as well:

<property name="hibernate.order_updates" value="true"/>

```sql
With this configuration in place, when rerunning the previous example, Hibernate generates
only two update statements:
```

Query: ["UPDATE post SET title = ? WHERE id = ?"], Params: [('Post nr. 0', 1), ('Post nr. 1', 3), ('Post nr. 2', 5)]

Query: ["UPDATE post_comment SET post_id = ?, review = ? WHERE id = ?"], Params: [(1, 'Very good', 2), (3, 'Very good', 4), (5, 'Very good', 6)]

Batching versioned data

An entity is versioned if the @Version annotation is associated with a numerical or a timestamp attribute. The presence of the @Version attribute activates the implicit optimistic locking mechanism for update and delete statements. When the entity is updated or deleted, Hibernate includes the entity version in the where clause of the currently executing SQL statement. If the entity was modified by a concurrent transaction, the version of the underlying table row would not match the one supplied by the current running statement. The update count returned by an update or a delete statement reports the numbers of rows affected by the statement in question, and, if the count value is zero (or even less), a StaleObjectStateException is thrown.

Prior to Hibernate 5, JDBC batching was disabled for versioned entities during update and delete operations. This limitation was due to some JDBC drivers inability of correctly returning the update count of the affected table rows when enabling JDBC batching.

Validating the underlying JDBC driver support is fairly simple. Once the hibernate.jdbc.batch_-

versioned_data property is activated, if there is no optimistic locking exception being mistakenly thrown during a non-concurrent batch update, then the driver supports versioned JDBC batching.

Since Hibernate 5, the hibernate.jdbc.batch_versioned_data configuration property is enabled by default, and it is disabled when using a pre-12c Oracle dialect (e.g. Oracle 8i, Oracle 9i, Oracle 10g). Because the Oracle 12c JDBC driver manages to return the actual update count even when using batching, the Oracle12cDialect sets the hibernate.jdbc.batch_versioned_data property to true.

For Hibernate 3 and 4, the hibernate.jdbc.batch_versioned_data should be enabled if the JDBC driver supports this feature.

## 13.3 Batching delete statements

Considering that the hibernate.jdbc.batch_size configuration property is set, when running the following test case:

List<Post> posts = entityManager.createQuery(

```sql
"select p " +
"from Post p ", Post.class)
.getResultList();
posts.forEach(entityManager::remove);
```

Hibernate will generate a single PreparedStatement:

Query: ["DELETE FROM post WHERE id = ?"], Params: [(1), (2), (3)]

If the Post entity has a @OneToMany PostComment association, and since CascadeType.REMOVE is inherited from the CascadeType.ALL attribute, when the Post entity is removed, the associated

PostComment child entities will be removed as well.

List<Post> posts = entityManager.createQuery(

```sql
"select p " +
"from Post p " +
"join fetch p.comments ", Post.class)
.getResultList();
posts.forEach(entityManager::remove);
```

Even if the JDBC batching setting is enabled, Hibernate still issues each delete statement separately.

```sql
DELETE FROM post_comment WHERE id = 2
DELETE FROM post WHERE id = 1
DELETE FROM post_comment WHERE id = 4
DELETE FROM post WHERE id = 3
DELETE FROM post_comment WHERE id = 6
DELETE FROM post WHERE id = 5
```

Once the HHH-10483a is resolved, Hibernate will support delete statement ordering.

The hibernate.jdbc.batch_versioned_data property applies to batched deletes just like for update statements.

ahttps://hibernate.atlassian.net/browse/HHH-10483

Fortunately, there are multiple workarounds to this issue. Instead of relying on Cascade-

Type.REMOVE, the child entities can be manually removed before deleting the parent entities.

```java
for (Post post : posts) {
for (Iterator<PostComment> commentIterator = post.getComments().iterator();
commentIterator.hasNext(); ) {
PostComment comment = commentIterator.next();
comment.setPost(null);
commentIterator.remove();
}
}
entityManager.flush();
posts.forEach(entityManager::remove);
```

Prior to deleting the Post entities, the Persistence Context is flushed to force the PostComment delete statements to be executed. This way, the Persistence Context does not interleave the SQL delete statements of the removing Post and PostComment entities.

Query: ["DELETE FROM post_comment WHERE id = ?"], Params: [(2), (4), (6)

Query: ["DELETE FROM post WHERE id = ?"], Params: [(1), (3), (5)]

A more efficient alternative is to execute a bulk HQL delete statement instead. First, the

PostComment collection mapping must be modified to remove the orphanRemoval, as well as the

CascadeType.REMOVE setting.

```java
@OneToMany(cascade = {CascadeType.PERSIST, CascadeType.MERGE}, mappedBy = "post")
private List<PostComment> comments = new ArrayList<>();
```

Without removing the orphanRemoval and the CascadeType.REMOVE setting, Hibernate will issue a select statement for every child entity that gets removed. Not only the SQL statements are more effective (due to batching), but the flushing is also faster since the Persistence Context doesn’t have to propagate the remove action.

```java
With this new mapping in place, the remove operation can be constructed as follows:
```

List<Post> posts = entityManager.createQuery(

```sql
"select p " +
"from Post p ", Post.class)
.getResultList();
```

entityManager.createQuery(

```sql
"delete " +
"from PostComment c " +
"where c.post in :posts")
.setParameter("posts", posts)
.executeUpdate();
posts.forEach(entityManager::remove);
```

This time, Hibernate generates only two statements. The child entities are deleted using a single bulk delete statement, while the parent entities are removed using a batched

PreparedStatement.

Query: ["DELETE FROM post_comment WHERE post_id in (? , ? , ?)"], Params: [(1, 3, 5)]

Query: ["DELETE FROM post WHERE id = ?"], Params: [(1), (3), (5)]

The most efficient approach is to rely on database-level cascading. For this purpose, the

post_comment table should be modified so that the post_id foreign key defines a DELETE CASCADE directive.

```sql
ALTER TABLE post_comment ADD CONSTRAINT fk_post_comment_post
FOREIGN KEY (post_id) REFERENCES post ON DELETE CASCADE
```

This way, the deletion operation can be reduced to simply removing the Post entities:

List<Post> posts = entityManager.createQuery(

```sql
"select p " +
"from Post p ", Post.class)
.getResultList();
posts.forEach(entityManager::remove);
```

Running the Post removal operation generates only one batched PreparedStatement:

Query: ["DELETE FROM post WHERE id = ?"], Params: [(1), (3), (5)]

Because the Hibernate Session is unaware of the table rows being deleted on the database side, it is good practice to avoid fetching the associations that will be removed by the database.

List<Post> posts = entityManager.createQuery(

```sql
"select p " +
"from Post p ", Post.class)
.getResultList();
```

List<PostComment> comments = entityManager.createQuery(

```sql
"select c " +
"from PostComment c " +
"where c.post in :posts", PostComment.class)
.setParameter("posts", posts)
.getResultList();
posts.forEach(entityManager::remove);
comments.forEach(comment -> comment.setReview("Excellent"));
```

When running the test case above, Hibernate generates the following SQL statements:

Query: ["UPDATE post_comment SET post_id=?, review=? WHERE id=?"], Params: [(1, 'Excellent', 2), (3, 'Excellent', 4), (5, 'Excellent', 6)]

Query: ["DELETE FROM post WHERE id=?"], Params: [(1), (3), (5)]

Luckily, the EntityDeleteAction is the last action being executed during flushing, so, even if the

PostComment(s) are changed, the update statement is executed before the parent deletion.

But if the Persistence Context is flushed before changing the PostComment entities:

List<Post> posts = entityManager.createQuery(

```sql
"select p " +
"from Post p ", Post.class)
.getResultList();
```

List<PostComment> comments = entityManager.createQuery(

```sql
"select c " +
"from PostComment c " +
"where c.post in :posts", PostComment.class)
.setParameter("posts", posts)
.getResultList();
posts.forEach(entityManager::remove);
entityManager.flush();
comments.forEach(comment -> comment.setReview("Excellent"));
```

An OptimisticLockException will be thrown because the associated table rows cannot be found anymore.

Query: ["DELETE FROM post WHERE id=?"], Params: [(1), (3), (5)]

Query: ["UPDATE post_comment SET post_id=?, review=? WHERE id=?"], Params: [(1, 'Excellent', 2), (3, 'Excellent', 4), (5, 'Excellent', 6)]

```sql
o.h.e.j.b.i.BatchingBatch - HHH000315: Exception executing batch
[Batch update returned unexpected row count from update [0];
actual row count: 0; expected: 1]
```

Because the row count value is zero, Hibernate assumes that the records were modified by some other concurrent transaction and it throws the exception to notify the upper layers of the data consistency violation.
