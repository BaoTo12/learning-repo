# 10. Relationships

In a relational database, associations are formed by correlating rows belonging to different tables. A relationship is established when a child table defines a foreign key referencing the primary key of its parent table. Every database association is built on top of foreign keys, resulting three table relationship types:

* one-to-many is the most common relationship, and it associates a row from a parent table to multiple rows in a child table.
* one-to-one requires the child table Primary Key to be associated via a Foreign Key with the parent table Primary Key column.
* many-to-many requires a link table containing two Foreign Key columns that reference the two different parent tables.

The following diagram depicts all these three table relationships:

**Figure 10.1: Table relationships**

The post table has a one-to-many relationship with the post_comment table because a post row might be referenced by multiple comments. The one-to-many relationship is established through the post_id column which has a foreign key referencing the post table primary key. Because a post_comment cannot exist without a post, the post is the parent-side while the

post_comment is the child-side.

The post table has a one-to-one relationship with the post_details. Like the one-to-many association, the one-to-one relationship involves two tables and a foreign key. The foreign key has a uniqueness constraint, so only one child row can reference a parent record.

The post and the tag are both independent tables and neither one is a child of the other. A post can feature several tag(s), while a tag can also be associated with multiple post(s). This is a typical many-to-many association, and it requires a junction table to resolve the child-side of these two parent entities. The junction table requires two foreign keys referencing the two parent tables.

The foreign key is, therefore, the most important construct in building a table relationship, and, in a relation database, the child-side controls a table relationship.

In a relational database, the foreign key is associated with the child-side only. For this reason, the parent-side has no knowledge of any associated child relationships, and, from a mapping perspective, table relationships are always unidirectional (the child foreign key references the parent primary key).

## 10.1 Relationship types

When mapping a JPA entity, besides the underlying table columns, the application developer can map entity relationships either in one direction or in a bidirectional way. This is another impedance mismatch between the object-oriented Domain Model and relational database system because, when using an ORM tool, the parent and the child-side can reference each other.

A relationship is unidirectional if only one entity side maps the table relationship and is bidirectional if the table relationship can be navigated in both directions (either from the entity parent-side or the child-side).

To properly represent both sides of an entity relationship, JPA defines four association mapping constructs:

* @ManyToOne represents the child-side (where the foreign key resides) in a database oneto-many table relationship.
* @OneToMany is associated with the parent-side of a one-to-many table relationship.
* @ElementCollection defines a one-to-many association between an entity and multiple value types (basic or embeddable).
* @OneToOne is used for both the child-side and the parent-side in a one-to-one table relationship.
* @ManyToMany mirrors a many-to-many table relationship.

Because the entity relationship choice has a considerable impact on the overall application performance, this chapter analyzes the data access operation efficiency of all these JPA associations.

Mapping collections

In a relational database, all table relationships are constructed using foreign keys and navigated through SQL queries. JPA allows mapping both the foreign key side (the child entity has a reference to its parent), as well as the parent side (the parent entity has one or more child entities).

Although @OneToMany, @ManyToMany or @ElementCollection are convenient from a data access perspective (entity state transitions can be cascaded from parent entities to children), they are definitely not free of cost. The price for reducing data access operations is paid in terms of result set fetching flexibility and performance. A JPA collection, either of entities or value types (basic or embeddables), binds a parent entity to a query that usually fetches all the associated child records. Because of this, the entity mapping becomes sensitive to the number of child entries.

If the children count is relatively small, the performance impact of always retrieving all child entities might be unnoticeable. However, if the number of child records grows too large, fetching the entire children collection may become a performance bottleneck. Unfortunately, the entity mapping is done during the early phases of a project development, and the development team might be unaware of the number of child records a production system exhibits.

Not just the mere size can be problematic, but also the number of attributes of the child entity. Because entities are usually fetched as a whole, the result set is, therefore, proportional to the number of columns the child table contains. Even if a collection is fetched lazily, Hibernate might still require to fully load each entity when the collection is accessed for the first time. Although Hibernate supports extra lazy collection fetching, this is only a workaround and does not address the root problem.

Alternatively, every collection mapping can be replaced by a data access query, which can use a SQL projection that is tailored to the data requirements of each business use case. This way, the query can take business case specific filtering criteria. Although JPA 2.1 does not support dynamic collection filtering, Hibernate offers Persistence Context-bound collection Filters.

When handling large data sets, it is good practice to limit the result set size, both for UI (to increase responsiveness) or batch processing tasks (to avoid long running transactions). Just because JPA offers supports collection mapping, it does not mean they are mandatory for every domain model mapping. Until there is a clear understanding of the number of child records (or if there is even need to fetch child entities entirely), it is better to postpone the collection mapping decision. For high-performance systems, a data access query is often a much more flexible alternative.

10.2 @ManyToOne

The @ManyToOne relationship is the most common JPA association, and it maps exactly to the one-to-many table relationship. When using a @ManyToOne association, the underlying foreign key is controlled by the child-side, no matter the association is unidirectional or bidirectional.

This section focuses on unidirectional @ManyToOne relationships only, the bidirectional case being further discussed with the @OneToMany relationship. In the following example, the Post entity represents the parent-side, while the PostComment is the child-side.

As already mentioned, the JPA entity relationship diagram matches exactly the one-to-many table relationship.

**Figure 10.2: The one-to-many table relationship**

**Figure 10.3: @ManyToOne relationship**

Instead of mapping the post_id foreign key column, the PostComment uses a @ManyToOne relationship to the parent Post entity. The PostComment can be associated with an existing Post object reference, and the PostComment can also be fetched along with the Post entity.

```java
@ManyToOne
@JoinColumn(name = "post_id")
private Post post;
```

Hibernate translates the internal state of the @ManyToOne Post object reference to the post_id foreign key column value.

If the @ManyToOne attribute is set to a valid Post entity reference:

```java
Post post = entityManager.find(Post.class, 1L);
PostComment comment = new PostComment("My review");
comment.setPost(post);
entityManager.persist(comment);
```

Hibernate will generate an insert statement populating the post_id column with the identifier of the associated Post entity.

```sql
INSERT INTO post_comment (post_id, review, id) VALUES (1, 'My review', 2)
```

If the Post attribute is later set to null:

```java
comment.setPost(null);
```

The post_id column will also be updated with a NULL value:

```sql
UPDATE post_comment SET post_id = NULL, review = 'My review' WHERE id = 2
```

Because the @ManyToOne association controls the foreign key directly, the automatically generated DML statements are very efficient.

Actually, the best-performing JPA associations always rely on the child-side to translate the JPA state to the foreign key column value.

This is one of the most important rules in JPA relationship mapping, and it will be further emphasized for @OneToMany, @OneToOne and even @ManyToMany associations.

10.3 @OneToMany

While the @ManyToOne association is the most natural mapping of the one-to-many table relationship, the @OneToMany association can also mirror this database relationship, but only when being used as a bidirectional mapping. A unidirectional @OneToMany association uses an additional junction table, which no longer fits the one-to-many table relationship semantics.

### 10.3.1 Bidirectional @OneToMany

The bidirectional @OneToMany association has a matching @ManyToOne child-side mapping that controls the underlying one-to-many table relationship. The parent-side is mapped as a collection of child entities.

**Figure 10.4: Bidirectional @OneToMany relationship**

In a bidirectional association, only one side can control the underlying table relationship. For the bidirectional @OneToMany mapping, it is the child-side @ManyToOne association in charge of keeping the foreign key column value in sync with the in-memory Persistence Context. This is the reason why the bidirectional @OneToMany relationship must define the mappedBy attribute, indicating that it only mirrors the @ManyToOne child-side mapping.

```java
@OneToMany(mappedBy = "post", cascade = CascadeType.ALL, orphanRemoval = true)
private List<PostComment> comments = new ArrayList<>();
```

Even if the child-side is in charge of synchronizing the entity state changes with the database foreign key column value, a bidirectional association must always have both the parent-side and the child-side in sync.

To synchronize both ends, it is practical to provide parent-side helper methods that add/remove child entities.

```java
public void addComment(PostComment comment) {
comments.add(comment);
comment.setPost(this);
}
public void removeComment(PostComment comment) {
comments.remove(comment);
comment.setPost(null);
}
```

One of the major advantages of using a bidirectional association is that entity state transitions can be cascaded from the parent entity to its children. In the following example, when persisting the parent Post entity, all the PostComment child entities are persisted as well.

```java
Post post = new Post("First post");
PostComment comment1 = new PostComment("My first review");
post.addComment(comment1);
PostComment comment2 = new PostComment("My second review");
post.addComment(comment2);
entityManager.persist(post);
INSERT INTO post (title, id) VALUES ('First post', 1)
INSERT INTO post_comment (post_id, review, id) VALUES (1, 'My first review', 2)
INSERT INTO post_comment (post_id, review, id) VALUES (1, 'My second review', 3)
```

When removing a comment from the parent-side collection:

```java
post.removeComment(comment1);
```

The orphan removal attribute instructs Hibernate to generate a delete DML statement on the targeted child entity:

```sql
DELETE FROM post_comment WHERE id = 2
```

Equality-based entity removal

The helper method for the child entity removal relies on the underlying child object equality for matching the collection entry that needs to be removed.

If the application developer does not choose to override the default equals and hashCode methods, the java.lang.Object identity-based equality is going to be used. The problem with this approach is that the application developer must supply a child entity object reference that is contained in the current child collection.

Sometimes child entities are loaded in one web request and saved in a HttpSession or a Stateful Enterprise Java Bean. Once the Persistence Context, which loaded the child entity is closed, the entity becomes detached. If the child entity is sent for removal into a new web request, the child entity must be reattached or merged into the current Persistence Context. This way, if the parent entity is loaded along with its child entities, the removal operation will work properly since the removing child entity is already managed and contained in the children collection.

If the entity has not changed, reattaching this child entity will be redundant and so the equals and the hashCode methods must be overridden to express equality in terms of a unique business key. In case the child entity has a @NaturalId or a unique attribute set, the equals and the hashCode methods can be implemented on top of that. Assuming the PostComment entity has the following two columns whose combination render a unique business key, the equality contract can be implemented as follows:

```java
private String createdBy;
@Temporal(TemporalType.TIMESTAMP)
private Date createdOn = new Date();
@Override
public boolean equals(Object o) {
if (this == o) return true;
if (o == null || getClass() != o.getClass()) return false;
PostComment that = (PostComment) o;
return Objects.equals(createdBy, that.createdBy) &&
Objects.equals(createdOn, that.createdOn);
}
@Override
public int hashCode() {
return Objects.hash(createdBy, createdOn);
}
```

Identifier-based equality

The java.lang.Object.equalsa method Javadoc demands the strategy be reflexive, symmetric, transitive, and consistent.

While the first three equality properties (reflexive, symmetric, transitive) are easier to achieve, especially with the java.util.Objectsb equals and hashCode utilities, consistency requires more diligence.

For a JPA or Hibernate entity, consistency means that the equality result is reflexive, symmetric and transitive across all entity state transitions (e.g. new/transient, managed, detached, removed).

If the entity has a @NaturalId attribute, then ensuring consistency is simple since the natural key is assigned even from the transient state, and this attribute never changes afterward. However, not all entities have a natural key to use for equality checks, so another table column must be used instead.

Luckily, most database tables have a primary key, which uniquely identifies each row of a particular table. The only caveat is to ensure consistency across all entity state transitions.

A naive implementation would look like this:

```java
@Entity
public class Post {
@Id @GeneratedValue
private Long id;
```

//Getters and setters omitted for brevity

```java
@Override
public boolean equals(Object o) {
if (this == o) return true;
if (!(o instanceof Post)) return false;
return Objects.equals(id, ((Post) o).getId());
}
@Override
public int hashCode() {
return Objects.hash(id);
}
}
```

ahttps://docs.oracle.com/javase/8/docs/api/java/lang/Object.html#equals-java.lang.Objectbhttps://docs.oracle.com/javase/7/docs/api/java/util/Objects.html

Now, when running the following test case:

```java
Set<Post> tuples = new HashSet<>();
tuples.add(entity);
assertTrue(tuples.contains(entity));
doInJPA(entityManager -> {
entityManager.persist(entity);
entityManager.flush();
assertTrue(tuples.contains(entity));
});
```

The final assertion will fail because the entity can no longer be found in the Set collection since the new identifier value is associated with a different Set bucket than the one where the entity got stored in.

To fix it, the equals and hashCode methods must be changed as follows:

```java
@Override
public boolean equals(Object o) {
if (this == o) return true;
if (!(o instanceof Post)) return false;
return id != null && id.equals(((Post) o).getId());
}
@Override
public int hashCode() {
return 31;
}
```

When the entity identifier is null, equality can only be guaranteed for the same object references. Otherwise, no transient object is equal to any other transient or persisted object. That’s why the equals method above skips the identifier check if the current object has a null identifier value.

Using a constant hashCode value solves the previous bucket-related problem associated with

Set(s) or Map(s) because, this time, only a single bucket is going to be used. Although in general, using a single Set bucket is not very efficient for large collection of objects, in this particular use case, this workaround is valid since managed collections should be rather small to be efficient. Otherwise, fetching a @OneToMany Set with thousands of entities is orders of magnitude more costly than the one-bucket search penalty.

When using List(s), the constant hashCode value is not an issue at all, and, for bidirectional collections, the Hibernate-internal PersistentList(s) are more efficient than PersistentSet(s).

The bidirectional @OneToMany association generates efficient DML statements because the @ManyToOne mapping is in charge of the table relationship. Because it simplifies data access operations as well, the bidirectional @OneToMany association is worth considering when the size of the child records is relatively low.

### 10.3.2 Unidirectional @OneToMany

The unidirectional @OneToMany association is very tempting because the mapping is simpler than its bidirectional counterpart. Because there is only one side to take into consideration, there is no need for helper methods and the mapping does not feature a mappedBy attribute either.

```java
@OneToMany(cascade = CascadeType.ALL, orphanRemoval = true)
private List<PostComment> comments = new ArrayList<>();
```

Unfortunately, in spite its simplicity, the unidirectional @OneToMany association is less efficient than the unidirectional @ManyToOne mapping or the bidirectional @OneToMany association.

Against any intuition, the unidirectional @OneToMany association does not map to a one-to-many table relationship. Because there is no @ManyToOne side to control this relationship, Hibernate uses a separate junction table to manage the association between a parent row and its child records.

**Figure 10.5: The @OneToMany table relationship**

The table post_post_comment has two foreign key columns, which reference both the parentside row (the Post_id column is a foreign key to the post table primary key) and the child-side entity (the comments_id references the primary key of the post_comment table).

Without going into analyzing the associated data access operations, it is obvious that joining three tables is less efficient than joining just two. Because there are two foreign keys, there need to be two indexes (instead of one), so the index memory footprint increases. However, since this is a regular table mapping for a many-to-many relationship, the extra table and the increased memory footprint are not even the biggest performance issue. The algorithm for managing the collection state is what makes any unidirectional @OneToMany association less attractive.

Considering there is a Post entity with two PostComment child records, obtained by running the following example:

```java
Post post = new Post("First post");
post.getComments().add(new PostComment("My first review"));
post.getComments().add(new PostComment("My second review"));
post.getComments().add(new PostComment("My third review"));
entityManager.persist(post);
```

While for a bidirectional @OneToMany association there were three child rows being added, the unidirectional association requires three additional inserts for the junction table records.

```sql
INSERT INTO post (title, id) VALUES ('First post', 1)
INSERT INTO post_comment (review, id) VALUES ('My first review', 2)
INSERT INTO post_comment (review, id) VALUES ('My second review', 3)
INSERT INTO post_comment (review, id) VALUES ('My third review', 4)
INSERT INTO post_post_comment (Post_id, comments_id) VALUES (1, 2)
INSERT INTO post_post_comment (Post_id, comments_id) VALUES (1, 3)
INSERT INTO post_post_comment (Post_id, comments_id) VALUES (1, 4)
```

When removing the first element of the collection:

```java
post.getComments().remove(0);
```

Hibernate generates the following DML statements:

```sql
DELETE FROM post_post_comment WHERE Post_id = 1
INSERT INTO post_post_comment (Post_id, comments_id) VALUES (1, 3)
INSERT INTO post_post_comment (Post_id, comments_id) VALUES (1, 4)
DELETE FROM post_comment WHERE id = 2
```

First, all junction table rows associated with the parent entity are deleted, and then the remaining in-memory records are added back again. The problem with this approach is that instead of a single junction table remove operation, the database has way more DML statements to execute.

Another problem is related to indexes. If there is an index on each foreign key column (which is the default for many relational databases), the database engine must delete the associated index entries only to add back the remaining ones. The more elements a collection has, the less efficient a remove operation gets.

The unidirectional @OneToMany relationship is less efficient both for reading data (three joins are required instead of two), as for adding (two tables must be written instead of one) or removing (entries are removed and added back again) child entries.

### 10.3.3 Ordered unidirectional @OneToMany

If the collection can store the index of every collection element, the unidirectional @OneToMany relationship may benefit for some element removal operations. First, an @OrderColumn annotation must be defined along the @OneToMany relationship mapping:

```java
@OneToMany(cascade = CascadeType.ALL, orphanRemoval = true)
@OrderColumn(name = "entry")
private List<PostComment> comments = new ArrayList<>();
```

At the database level, the entry column is included in the junction table.

**Figure 10.6: The unidirectional @OneToMany with an @OrderColumn**

It is better not to mistake the @OrderColumn with the @OrderBy JPA annotation. While the former allows the JPA provider to materialize the element index into a dedicated database column so that the collection is sorted using an ORDER BY clause, the latter does the sorting at runtime based on the ordering criteria provided by the @OrderBy annotation.

Considering there are three PostComment entities added for a given Post parent entity:

```java
post.getComments().add(new PostComment("My first review"));
post.getComments().add(new PostComment("My second review"));
post.getComments().add(new PostComment("My third review"));
```

The index of every collection element is going to be stored in the entry column of the junction table:

```sql
INSERT INTO post_comment (review, id) VALUES ('My first review', 2)
INSERT INTO post_comment (review, id) VALUES ('My second review', 3)
INSERT INTO post_comment (review, id) VALUES ('My third review', 4)
INSERT INTO post_post_comment (Post_id, entry, comments_id) VALUES (1, 0, 2)
INSERT INTO post_post_comment (Post_id, entry, comments_id) VALUES (1, 1, 3)
INSERT INTO post_post_comment (Post_id, entry, comments_id) VALUES (1, 2, 4)
```

When removing elements from the tail of the collection:

```java
post.getComments().remove(2);
```

Hibernate only requires a single junction table delete statement:

```sql
DELETE FROM post_post_comment WHERE Post_id = 1 AND entry = 2
DELETE FROM post_comment WHERE id = 4
```

Unfortunately, this optimization does not hold for entries that are located towards the head of the collection. So, if we remove the first element:

```java
post.getComments().remove(0);
```

Hibernate deletes the last entry associated with the parent row from the junction table, and then it updates the remaining entries to preserve the same element ordering as the inmemory collection snapshot:

```sql
DELETE FROM post_post_comment WHERE Post_id = 1 AND entry = 2
UPDATE post_post_comment SET comments_id = 4 WHERE Post_id = 1 AND entry = 1
UPDATE post_post_comment SET comments_id = 3 WHERE Post_id = 1 AND entry = 0
DELETE FROM post_comment WHERE id = 2
```

If the unidirectional @OneToMany collection is used like a stack and elements are always removed from the collection tail, the remove operations will be more efficient when using an @OrderColumn. But the closer an element is to the head of the list, the more update statements must be issued, and the additional updates have an associated performance overhead.

10.3.3.1 @ElementCollection

Although it is not an entity association type, the @ElementCollection is very similar to the unidirectional @OneToMany relationship. To represent collections of basic types (e.g. String, int,

BigDecimal) or embeddable types, the @ElementCollection must be used instead. If the previous associations involved multiple entities, this time, there is only a single Post entity with a collection of String comments.

**Figure 10.7: The @ElementCollection relationship**

The mapping for the comments collection looks as follows:

```java
@ElementCollection
private List<String> comments = new ArrayList<>();
```

Value types inherit the persistent state from their parent entities, so their lifecycle is also bound to the owner entity. Any operation against the entity collection is going to be automatically materialized into a DML statement.

When it comes to adding or removing child records, the @ElementCollection behaves like a unidirectional @OneToMany relationship, annotated with CascadeType.ALL and orphanRemoval.

From a database perspective, there is one child table holding both the foreign key column and the collection element value.

**Figure 10.8: The @ElementCollection table relationship**

To persist three comments, the data access layer only has to add them to the parent entity collection:

```java
post.getComments().add("My first review");
post.getComments().add("My second review");
post.getComments().add("My third review");
```

Hibernate issues the insert statements during Persistence Context flushing:

```sql
INSERT INTO Post_comments (Post_id, comments) VALUES (1, 'My first review')
INSERT INTO Post_comments (Post_id, comments) VALUES (1, 'My second review')
INSERT INTO Post_comments (Post_id, comments) VALUES (1, 'My third review')
```

Unfortunately, the remove operation uses the same logic as the unidirectional @OneToMany association, so when removing the first collection element:

```java
post.getComments().remove(0);
```

Hibernate deletes all the associated child-side records and re-inserts the in-memory ones back into the database table:

```sql
DELETE FROM Post_comments WHERE Post_id = 1
INSERT INTO Post_comments (Post_id, comments) VALUES (1, 'My second review')
INSERT INTO Post_comments (Post_id, comments) VALUES (1, 'My third review')
```

In spite its simplicity, the @ElementCollection is not very efficient for element removal. Just like unidirectional @OneToMany collections, the @OrderColumn can optimize the removal operation for entries located near the collection tail.

10.3.4 @OneToMany with @JoinColumn

JPA 2.0 added support for mapping the @OneToMany association with a @JoinColumn so that it can map the one-to-many table relationship. With the @JoinColumn, the @OneToMany association controls the child table foreign key, so there is no need for a junction table.

On the JPA side, the class diagram is identical to the aforementioned unidirectional @OneToMany relationship, and the only difference is the JPA mapping which takes the additional @JoinColumn:

```java
@OneToMany(cascade = CascadeType.ALL, orphanRemoval = true)
@JoinColumn(name = "post_id")
private List<PostComment> comments = new ArrayList<>();
```

When adding three PostComment entities, Hibernate generates the following SQL statements:

```sql
post.getComments().add(new PostComment("My first review"));
post.getComments().add(new PostComment("My second review"));
post.getComments().add(new PostComment("My third review"));
INSERT INTO post_comment (review, id) VALUES ('My first review', 2)
INSERT INTO post_comment (review, id) VALUES ('My second review', 3)
INSERT INTO post_comment (review, id) VALUES ('My third review', 4)
UPDATE post_comment SET post_id = 1 WHERE id = 2
UPDATE post_comment SET post_id = 1 WHERE id = 3
UPDATE post_comment SET post_id = 1 WHERE id = 4
```

Besides the regular insert statements, Hibernate issues three update statements for setting the post_id column on the newly inserted child records. The update statements are generated by the Hibernate-internal CollectionRecreateAction which tries to preserve the element order whenever the collection state changes. In this particular case, the CollectionRecreateAction should not be scheduled for execution, however, as of writing (Hibernate 5.2.3), this issue still replicates.

Although, from a performance perspective, it is an improvement over the regular

```java
@OneToMany mapping, in practice, it is still not as efficient as a regular bidirectional
@OneToMany association.
```

When deleting the last element of the collection:

```java
post.getComments().remove(2);
```

Hibernate generates the following SQL statements:

```sql
UPDATE post_comment SET post_id = null WHERE post_id = 1 AND id = 4
DELETE from post_comment WHERE id = 4
```

Again, there is an additional update statement associated with the child removal operation. When a child entity is removed from the parent-side collection, Hibernate sets the child table foreign key column to null. Afterward, the orphan removal logic kicks in, and it triggers a delete statement against the disassociated child entity.

Unlike the regular @OneToMany association, the @JoinColumn alternative is consistent in regard to the collection entry position that is being removed. So, when removing the first element of the collection:

```java
post.getComments().remove(0);
```

Hibernate still generates an additional update statement:

```sql
UPDATE post_comment SET post_id = null WHERE post_id = 1 AND id = 2
DELETE from post_comment WHERE id = 2
```

Bidirectional @OneToMany with @JoinColumn relationship

The @OneToMany with @JoinColumn association can also be turned into a bidirectional relationship, but it requires instructing the child-side to avoid any insert and update synchronization:

```java
@ManyToOne
@JoinColumn(name = "post_id", insertable = false, updatable = false)
private Post post;
```

The redundant update statements are generated for both the unidirectional and the bidirectional association, so the most efficient foreign key mapping is the @ManyToOne association.

### 10.3.5 Unidirectional @OneToMany Set

All the previous examples were using List(s), but Hibernate supports Set(s) as well. For the next exercise, the PostComment entity uses the following mapping:

```java
@Entity(name = "PostComment") @Table(name = "post_comment")
public class PostComment {
@Id @GeneratedValue
private Long id;
private String slug;
private String review;
public PostComment() {
byte[] bytes = new byte[8];
ByteBuffer.wrap(bytes).putDouble(Math.random());
slug = Base64.getEncoder().encodeToString(bytes);
}
public PostComment(String review) {
this();
this.review = review;
}
```

//Getters and setters omitted for brevity

```java
@Override
public boolean equals(Object o) {
if (this == o) return true;
if (o == null || getClass() != o.getClass()) return false;
PostComment comment = (PostComment) o;
return Objects.equals(slug, comment.getSlug());
}
@Override
public int hashCode() {
return Objects.hash(slug);
}
}
```

This time, the PostComment entity uses a slug attribute which provide a way to uniquely identify each comment belonging to a given Post entity.

Because the PostComment references are going to be stored in a java.util.Set, it is best to override the equals and hashCode Object methods according to the entity business key. In this particular example, the PostComment does not have any meaningful business key, so the

slug attribute is used for the equality checks.

The parent Post entity has a unidirectional @OneToMany association that uses a java.util.Set:

```java
@OneToMany(cascade = CascadeType.ALL, orphanRemoval = true)
private Set<PostComment> comments = new HashSet<>();
```

When adding three PostComment entities:

```java
post.getComments().add(new PostComment("My first review"));
post.getComments().add(new PostComment("My second review"));
post.getComments().add(new PostComment("My third review"));
```

Hibernate generates the following SQL statements:

```sql
INSERT INTO post_comment (review, slug, id)
VALUES ('My second review', 'P+HLCF25scI=', 2)
INSERT INTO post_comment (review, slug, id)
VALUES ('My first review', 'P9y8OGLTCyg=', 3)
INSERT INTO post_comment (review, slug, id)
VALUES ('My third review', 'P+fWF+Ck/LY=', 4)
INSERT INTO post_post_comment (Post_id, comments_id) VALUES (1, 2)
INSERT INTO post_post_comment (Post_id, comments_id) VALUES (1, 3)
INSERT INTO post_post_comment (Post_id, comments_id) VALUES (1, 4)
```

The remove operation is much more effective this time because the collection element order needs not be enforced anymore.

When removing the PostComment child entities:

```java
for(PostComment comment: new ArrayList<>(post.getComments())) {
post.getComments().remove(comment);
}
```

Hibernate generates one statement for removing the junction table entries and three delete statements for the associated post_comment records.

```sql
DELETE FROM post_post_comment WHERE Post_id = 1
DELETE FROM post_comment WHERE id = 2
DELETE FROM post_comment WHERE id = 3
DELETE FROM post_comment WHERE id = 4
```

To avoid using a secondary table, the @OneToMany mapping can use the @JoinColumn annotation.

```java
@OneToMany(cascade = CascadeType.ALL, orphanRemoval = true)
@JoinColumn(name = "post_id")
private Set<PostComment> comments = new HashSet<>();
```

Upon inserting three PostComment entities, Hibernate generates the following statements:

```sql
INSERT INTO post_comment (review, slug, id)
VALUES ('My third review', 'P8pcnLprqcQ=', 2)
INSERT INTO post_comment (review, slug, id)
VALUES ('My second review', 'P+Gau1+Hhxs=', 3)
INSERT INTO post_comment (review, slug, id)
VALUES ('My first review', 'P+kr9LOQTK0=', 4)
UPDATE post_comment SET post_id = 1 WHERE id = 2
UPDATE post_comment SET post_id = 1 WHERE id = 3
UPDATE post_comment SET post_id = 1 WHERE id = 4
```

When deleting all three PostComment entities, the generated statements look like this:

```sql
UPDATE post_comment SET post_id = null WHERE post_id = 1
DELETE FROM post_comment WHERE id = 2
DELETE FROM post_comment WHERE id = 3
DELETE FROM post_comment WHERE id = 4
```

Although it is an improvement over the unidirectional unordered or ordered List, the unidirectional Set is still less efficient than the bidirectional @OneToMany association.

10.4 @OneToOne

From a database perspective, the one-to-one association is based on a foreign key that is constrained to be unique. This way, a parent row can be referenced by at most one child record only.

In JPA, the @OneToOne relationship can be either unidirectional or bidirectional.

### 10.4.1 Unidirectional @OneToOne

In the following example, the Post entity represents the parent-side, while the PostDetails is the child-side of the one-to-one association.

As already mentioned, the JPA entity relationship diagram matches exactly the one-to-one table relationship.

**Figure 10.9: The one-to-one table relationship**

Even from the Domain Model side, the unidirectional @OneToOne relationship is strikingly similar to the unidirectional @ManyToOne association.

**Figure 10.10: The unidirectional @OneToOne relationship**

The mapping is done through the @OneToOne annotation, which, just like the @ManyToOne mapping, might also take a @JoinColumn as well.

```java
@OneToOne
@JoinColumn(name = "post_id")
private Post post;
```

The unidirectional @OneToOne association controls the associated foreign key, so, when the post attribute is set:

```java
Post post = entityManager.find(Post.class, 1L);
PostDetails details = new PostDetails("John Doe");
details.setPost(post);
entityManager.persist(details);
```

Hibernate populate the foreign key column with the associated post identifier:

```sql
INSERT INTO post_details (created_by, created_on, post_id, id)
VALUES ('John Doe', '2016-01-08 11:28:21.317', 1, 2)
```

Even if this is a unidirectional association, the Post entity is still the parent-side of this relationship. To fetch the associated PostDetails, a JPQL query is needed:

PostDetails details = entityManager.createQuery(

```sql
"select pd " +
"from PostDetails pd " +
"where pd.post = :post", PostDetails.class)
.setParameter("post", post)
.getSingleResult();
```

If the Post entity always needs its PostDetails, a separate query might not be desirable. To overcome this limitation, it is important to know the PostDetails identifier prior to loading the entity.

One workaround would be to use a @NaturalId, which might not require a database access if the entity is stored in the second-level cache. Fortunately, there is even a simpler approach which is also portable across JPA providers as well. The JPA 2.0 specification added support for derived identifiers, making possible to link the PostDetails identifier to the post table primary key.

This way, the post_details table primary key can also be a foreign key referencing the post table identifier.

The PostDetails @OneToOne mapping is changed as follows:

```java
@OneToOne
@MapsId
private Post post;
```

This time, the table relationship does not feature any additional foreign key column since the

post_details table primary key references the post table primary key:

**Figure 10.11: The shared key one-to-one**

Because PostDetails has the same identifier as the parent Post entity, it can be fetched without having to write a JPQL query.

```java
PostDetails details = entityManager.find(PostDetails.class, post.getId());
```

The shared primary key efficiency

First of all, the shared primary key approach reduces the memory footprint of the child-side table indexes since it requires a single indexed column instead of two. The more records a child table has, the better the improvement gain for reducing the number of indexed columns.

More, the child entity can now be simply retrieved from the second-level cache, therefore preventing a database hit. In the previous example, because the child entity identifier was not known, a query was inevitable. To optimize the previous use case, the query cache would be required as well, but the query cache is not without issues either.

Because of the reduced memory footprint and enabling the second-level cache direct retrieval, the JPA 2.0 derived identifier is the preferred @OneToOne mapping strategy. The shared primary key is not limited to unidirectional associations, being available for bidirectional @OneToOne relationships as well.

### 10.4.2 Bidirectional @OneToOne

A bidirectional @OneToOne association allows the parent entity to map the child-side as well:

**Figure 10.12: The bidirectional @OneToOne relationship**

The parent-side defines a mappedBy attribute because the child-side (which can still share the primary key with its parent) is still in charge of this JPA relationship:

```java
@OneToOne(mappedBy = "post", cascade = CascadeType.ALL, fetch = FetchType.LAZY)
private PostDetails details;
```

Because this is a bidirectional relationship, the Post entity must ensure that both sides of this relationship are set upon associating a PostDetails entity:

```java
public void setDetails(PostDetails details) {
if (details == null) {
if (this.details != null) this.details.setPost(null);
}
else details.setPost(this);
this.details = details;
}
```

Unlike the parent-side @OneToMany relationship where Hibernate can simply assign a proxy even if the child collection is empty, the @OneToOne relationship must decide if to assign the child reference to null or to an Object, be it the actual entity object type or a runtime Proxy.

This is an issue that affects the parent-side @OneToOne association, while the child-side, which has an associated foreign key column, knows whether the parent reference should be null or not. For this reason, the parent-side must execute a secondary query to know if there is a mirroring foreign key reference on the child-side.

Even if the association is lazy, when fetching a Post entity:

```java
Post post = entityManager.find(Post.class, 1L);
```

Hibernate fetches the child entity as well, so, instead of only one query, Hibernate requires two select statements:

```sql
SELECT p.id AS id1_0_0_, p.title AS title2_0_0_
FROM
post p
WHERE
p.id = 1
SELECT pd.post_id AS post_id3_1_0_, pd.created_by AS created_1_1_0_,
pd.created_on AS created_2_1_0_
FROM
post_details pd
WHERE
pd.post_id = 1
```

If the application developer only needs parent entities, the additional child-side secondary queries will be executed unnecessarily, and this might affect application performance. The more parent entities are needed to be retrieved, the more obvious the secondary queries performance impact gets.

Limitations

Even if the foreign key is NOT NULL and the parent-side is aware about its non-nullability through the optional attribute (e.g. @OneToOne(mappedBy = "post", fetch = FetchType.LAZY, optional

= false)), Hibernate still generates a secondary select statement.

For every managed entity, the Persistence Context requires both the entity type and the identifier, so the child identifier must be known when loading the parent entity, and the only way to find the associated post_details primary key is to execute a secondary query. Because the child identifier is known when using @MapsId, in future, HHH-10771a should address the secondary query issue.

Bytecode enhancement is the only viable workaround. However, it only works if the parent side is annotated with @LazyToOne(LazyToOneOption.NO_PROXY) and the child side is not using @MapsId. Because it’s simpler and more predictable, the unidirectional

@OneToOne relationship is often preferred.

ahttps://hibernate.atlassian.net/browse/HHH-10771

10.5 @ManyToMany

The @ManyToMany relationship is the trickiest of all JPA relationships as the remaining of this chapter demonstrates. Like the @OneToOne relationship, the @ManyToMany association can be either unidirectional or bidirectional. From a database perspective, the @ManyToMany association mirrors a many-to-many table relationship:

**Figure 10.13: The many-to-many table relationship**

### 10.5.1 Unidirectional @ManyToMany

In the following example, it makes sense to have the Post entity map the @ManyToMany relationship since there is not much need for navigating this association from the Tag relationship side (although we can still do it with a JPQL query).

**Figure 10.14: The unidirectional @ManyToMany relationship**

In the Post entity, the @ManyToMany unidirectional association is mapped as follows:

```java
@ManyToMany(cascade = { CascadeType.PERSIST, CascadeType.MERGE } )
@JoinTable(name = "post_tag",
joinColumns = @JoinColumn(name = "post_id"),
inverseJoinColumns = @JoinColumn(name = "tag_id")
)
private List<Tag> tags = new ArrayList<>();
```

When adding several entities:

```java
Post post1 = new Post("JPA with Hibernate");
Post post2 = new Post("Native Hibernate");
Tag tag1 = new Tag("Java");
Tag tag2 = new Tag("Hibernate");
post1.getTags().add(tag1);
post1.getTags().add(tag2);
post2.getTags().add(tag1);
entityManager.persist(post1);
entityManager.persist(post2);
```

Hibernate manages to persist both the Post and the Tag entities along with their junction records.

```sql
INSERT INTO post (title, id) VALUES ('JPA with Hibernate', 1)
INSERT INTO post (title, id) VALUES ('Native Hibernate', 4)
INSERT INTO tag (name, id) VALUES ('Java', 2)
INSERT INTO tag (name, id) VALUES ('Hibernate', 3)
INSERT INTO post_tag (post_id, tag_id) VALUES (1, 2)
INSERT INTO post_tag (post_id, tag_id) VALUES (1, 3)
INSERT INTO post_tag (post_id, tag_id) VALUES (4, 2)
```

Cascading

For @ManyToMany associations, CascadeType.REMOVE does not make too much sense when both sides represent independent entities. In this case, removing a Post entity should not trigger a Tag removal because the Tag can be referenced by other posts as well. The same arguments apply to orphan removal since removing an entry from the tags collection should only delete the junction record and not the target Tag entity.

For both unidirectional and bidirectional associations, it is better to avoid the

CascadeType.REMOVE mapping. Instead of CascadeType.ALL, the cascade attributes should be declared explicitly (e.g. CascadeType.PERSIST, CascadeType.MERGE).

But just like the unidirectional @OneToMany association, problems arise when it comes to removing the junction records:

```java
post1.getTags().remove(tag1);
```

Hibernate deletes all junction rows associated with the Post entity whose Tag association is being removed and inserts back the remaining ones:

```sql
DELETE FROM post_tag WHERE post_id = 1
INSERT INTO post_tag (post_id, tag_id) VALUES (1, 3)
```

### 10.5.2 Bidirectional @ManyToMany

The bidirectional @ManyToMany relationship can be navigated from both the Post and the Tag side.

**Figure 10.15: The bidirectional @ManyToMany relationship**

While in the one-to-many and many-to-one associations the child-side is the one holding the foreign key, for a many-to-many table relationship both ends are parent-sides and the junction table plays the child-side role.

Because the junction table is hidden when using the default @ManyToMany mapping, the application developer must choose an owning and a mappedBy side.

In this example, the Post retains the same mapping as shown in the unidirectional @ManyToMany section, while the Tag entity adds a mappedBy side:

```java
@ManyToMany(mappedBy = "tags")
private List<Post> posts = new ArrayList<>();
```

Like any other bidirectional associations, both sides must in sync, so the helper methods are being added here as well. For a @ManyToMany association, the helper methods must be added to the entity that is more likely to interact with. In this example, the business logic manages

Post(s) rather than Tag(s), so the helper methods are added to the Post entity:

```java
public void addTag(Tag tag) {
tags.add(tag);
tag.getPosts().add(this);
}
public void removeTag(Tag tag) {
tags.remove(tag);
tag.getPosts().remove(this);
}
```

Both Post and Tag entities have unique attributes which can simplify the entity removal operation even when mixing detached and managed entities.

While adding an entity into the @ManyToMany collection is efficient since it requires a single SQL insert into the junction table, the entity disassociation suffers from the same issue as the unidirectional @ManyToMany relationship does.

When changing the order of the elements:

```java
post1.getTags().sort(Collections.reverseOrder(Comparator.comparing(Tag::getId)));
```

Hibernate deletes all associated junction entries and reinsert them back again, as imposed by the unidirectional bag semantics:

```sql
DELETE FROM post_tag WHERE post_id = 1
INSERT INTO post_tag (post_id, tag_id) VALUES (1, 3)
INSERT INTO post_tag (post_id, tag_id) VALUES (1, 2)
```

Hibernate manages each side of a @ManyToMany relationship like a unidirectional

```sql
@OneToMany association between the parent-side (e.g. Post or the Tag) and the hidden
child-side (e.g. the post_tag table post_id or tag_id foreign keys). This is the reason why
the entity removal or changing their order resulted in deleting all junction entries and
reinserting them by mirroring the in-memory Persistence Context.
```

### 10.5.3 The @OneToMany alternative

Just like the unidirectional @OneToMany relationship can be optimized by allowing the child-side to control this association, the @ManyToMany mapping can be transformed so that the junction table is mapped to an entity.

**Figure 10.16: The @OneToMany as a many-to-many table relationship**

The PostTag entity has a composed identifier made out of the post_id and tag_id columns.

```java
@Embeddable
public class PostTagId implements Serializable {
private Long postId;
private Long tagId;
public PostTagId() {}
public PostTagId(Long postId, Long tagId) {
this.postId = postId;
this.tagId = tagId;
}
public Long getPostId() {
return postId;
}
public Long getTagId() {
return tagId;
}
@Override
public boolean equals(Object o) {
if (this == o) return true;
if (o == null || getClass() != o.getClass()) return false;
PostTagId that = (PostTagId) o;
return Objects.equals(postId, that.getPostId() &&
Objects.equals(tagId, that.getTagId());
}
@Override
public int hashCode() {
return Objects.hash(postId, tagId);
}
}
```

Using these columns, the PostTag entity can map the @ManyToOne sides as well:

```java
@Entity
@Table(name = "post_tag")
public class PostTag {
@EmbeddedId
private PostTagId id;
@ManyToOne
@MapsId("postId")
private Post post;
@ManyToOne
@MapsId("tagId")
private Tag tag;
private PostTag() {}
public PostTag(Post post, Tag tag) {
this.post = post;
this.tag = tag;
this.id = new PostTagId(post.getId(), tag.getId());
}
```

//Getters and setters omitted for brevity

```java
@Override
public boolean equals(Object o) {
if (this == o) return true;
if (o == null || getClass() != o.getClass()) return false;
PostTag that = (PostTag) o;
return Objects.equals(post, that.getPost() &&
Objects.equals(tag, that.getTag());
}
@Override
public int hashCode() {
return Objects.hash(post, tag);
}
}
```

The Post entity maps the bidirectional @OneToMany side of the post @ManyToOne association:

```java
@OneToMany(mappedBy = "post", cascade = CascadeType.ALL, orphanRemoval = true)
private List<PostTag> tags = new ArrayList<>();
```

The Tag entity maps the bidirectional @OneToMany side of the tag @ManyToOne association:

```java
@OneToMany(mappedBy = "tag", cascade = CascadeType.ALL, orphanRemoval = true)
private List<PostTag> posts = new ArrayList<>();
```

This way, the bidirectional @ManyToMany relationship is transformed in two bidirectional @One-

ToMany associations.

The removeTag helper method is much more complex because it needs to locate the PostTag associated with the current Post entity and the Tag that is being disassociated.

```java
public void removeTag(Tag tag) {
for (Iterator<PostTag> iterator = tags.iterator(); iterator.hasNext(); ) {
PostTag postTag = iterator.next();
if (postTag.getPost().equals(this) && postTag.getTag().equals(tag)) {
iterator.remove();
postTag.getTag().getPosts().remove(postTag);
postTag.setPost(null);
postTag.setTag(null);
break;
}
}
}
```

The PostTag equals and hashCode methods rely on the Post and Tag equality semantics. The Post entity uses the title as a business key, while the Tag relies on its name column uniqueness constraint.

When rerunning the entity removal example featured in the unidirectional @ManyToMany section:

```java
post1.removeTag(tag1);
```

Hibernate issues a single delete statement, therefore targeting a single PostTag junction record:

```sql
DELETE FROM post_tag WHERE post_id = 1 AND tag_id = 3
```

Changing the junction elements order has not effect this time:

post[^1].getTags().sort((postTag[^1], postTag[^2]) ->

postTag[^2].getId().getTagId().compareTo(postTag[^1].getId().getTagId()) )

This is because the @ManyToOne side only monitors the foreign key column changes and the internal collection state is not taken into consideration. To materialize the order of elements, the @OrderColumn must be used instead:

```java
@OneToMany(mappedBy = "post", cascade = CascadeType.ALL, orphanRemoval = true)
@OrderColumn(name = "entry")
private List<PostTag> tags = new ArrayList<>();
```

The post_tag junction table features an entry column storing the collection element order. When reversing the element order, Hibernate updates the entry column:

```sql
UPDATE post_tag SET entry = 0 WHERE post_id = 1 AND tag_id = 4
UPDATE post_tag SET entry = 1 WHERE post_id = 1 AND tag_id = 3
```

The most efficient JPA relationships are the ones where the foreign key side is controlled by a child-side @ManyToOne or @OneToOne association. For this reason, the many-tomany table relationship is best mapped with two bidirectional @OneToMany associations. The entity removal and the element order changes are more efficient than the default

@ManyToMany relationship and the junction entity can also map additional columns (e.g.

created_on, created_by).

## 10.6 Hypersistence Optimizer

Knowing which are the most efficient associations is of paramount importance when it comes to designing a high-performance data access layer. But choosing the right mappings is not sufficient. You also have to check the Hibernate configuration properties, as well as the queries that get executed.

For this purpose, I created the Hypersistence Optimizer[^1] tool. While you could manually investigate the JPA and Hibernate mappings and configurations, having a tool to do this task on your behalf is going to save you a lot of time.

More, Hypersistence Optimizer can validate your JPA and Hibernate usage during testing, and you could even assert the number of issues detected by the tool and trigger a build failure whenever a performance-impacting issue is detected. This way, you can ensure that future data access logic changes won’t affect the performance of your application.

Because you purchased this book, you have a 33% discount for any Hypersistence Optimizer license. All you have to do is to use the EBOOK33OFF coupon code when making the purchase. Or, you can use this link[^2] to quickly navigate to the Hypersistence Optimizer sales page with the 33% discount coupon activated.

### 10.6.1 Testimonials

“It really pays off when it comes to analyzing complex applications. For architectures that are difficult to manage, it quickly provides clues for further analysis.

This is a huge help both when setting up a new implementation and when optimizing a legacy application.”

— Kevin Peters (Software Engineer - codecentric AG)

“Let’s face it, JPA and Hibernate are very powerful but not simple tools. Even experienced developers make mistakes that may result in very heavy database queries, dramatically lowering overall application performance.

Hypersistence Optimizer feels like an additional team member - a JPA expert that is there to help and show how can you optimize your mappings and configurations before you ship them to production.”

— Maciej Walkowiak (Freelance Tech Lead)

[^1]: <https://vladmihalcea.com/hypersistence-optimizer/>

[^2]: <https://vladmihalcea.teachable.com/p/hypersistence-optimizer/?coupon_code=EBOOK33OFF>

## 10.7 Bidirectional @OneToMany Synchronization Best Practices

When implementing bidirectional `@OneToMany` associations in Hibernate, it is critical to keep both sides of the association in sync in memory to avoid state desynchronization bugs and save extra updates. 

Always map the `@OneToMany` side with the `mappedBy` attribute referencing the `@ManyToOne` side (the owning side), and provide helper synchronization methods in the parent entity:

```java
import javax.persistence.*;
import java.util.ArrayList;
import java.util.List;

@Entity
@Table(name = "post")
public class Post {

    @Id
    @GeneratedValue(strategy = GenerationType.SEQUENCE, generator = "post_seq")
    private Long id;

    private String title;

    // mappedBy marks this as the inverse side of the relationship
    @OneToMany(
        mappedBy = "post",
        cascade = CascadeType.ALL,
        orphanRemoval = true
    )
    private List<PostComment> comments = new ArrayList<>();

    // Synchronization helpers
    public void addComment(PostComment comment) {
        comments.add(comment);
        comment.setPost(this); // sync owning side
    }

    public void removeComment(PostComment comment) {
        comments.remove(comment);
        comment.setPost(null); // sync owning side
    }

    // Getters, setters, equals & hashCode omitted
}

@Entity
@Table(name = "post_comment")
public class PostComment {

    @Id
    @GeneratedValue(strategy = GenerationType.SEQUENCE, generator = "comment_seq")
    private Long id;

    private String review;

    // The owning side holds the foreign key post_id
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "post_id")
    private Post post;

    public void setPost(Post post) {
        this.post = post;
    }

    public Post getPost() {
        return post;
    }

    // Getters, setters, equals & hashCode omitted
}
```

