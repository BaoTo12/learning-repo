# 15. Caching

## 15.1 Caching flavors

Caching is everywhere. For instance, the CPU has several caching layers to decrease the latency associated with accessing data from the main memory. Being close to the processing unit, the CPU cache is very fast. However, compared to the main memory, the CPU cache is very small and can only store frequently-accessed data.

To speed up reading and writing to the underlying disk drive, the operating system uses caching as well. Data is read in pages that are cached into main memory, so frequentlyaccessed data is served from OS buffers rather than the disk drive. Disk cache improves the write operations as well because modifications can be buffered and flushed at once, therefore improving write throughput.

Since indexes and data blocks are better off served from memory, most relational database systems employ an internal caching layer.

So even without explicitly setting up a caching solution, an enterprise application already uses several caching layers. Nevertheless, enterprise caching is most often a necessity, and there are several solutions that can be used for this purpose.

**Figure 15.1: Enterprise caching layers**

As illustrated in the diagram above, caching entails a trade-off. On one hand, bypassing the underlying data access layer can speed up reads and writes. However, the farther the caching solution is situated, the more difficult it is for it to maintain consistency with the underlying database system.

For it guarantees ACID transactions, the database cache is highly consistent, so, from a data integrity perspective, it entails no risk of reading stale data. However, the database engine can only spare disk access, and so it cannot alleviate the networking overhead. More, if the data access layer needs to fetch an aggregate that spans over multiple database tables, the result set would either contain many joins, or it will require multiple secondary queries. The more complex the data access pattern, the more work a database server has to do, and, for this reason, it is common to use an application-level cache as well.

Most often, application-level caches are key-value stores. Once an aggregate is fetched from the database, it can be stored in the application cache so that any successive request can bypass the database entirely. The application-level cache can outperform the database engine because it can bypass the networking overhead associated with fetching result sets.

Another very important reason for using an application-level caching solution is that it can provide a safety hook for when the database has to be taken down for maintenance.

If the front-end cache stores a sufficient amount of data, it can serve as a temporary replacement for the database system, allowing read-only operations to be served from the cache. Even if write operations are prevented while the database system is unavailable, the read-only mode increases the overall system availability.

However, application-level caches come at a price, and ensuring consistent reads is no longer a trivial thing to do. Because of its tight integration with Hibernate, the second-level cache can avoid many consistency-related issues associated with application-level caches.

The Hibernate second-level cache is a data access caching solution that aims to reduce database load when it comes to fetching entities. Along with it collection cache component, the second-level cache allows retrieving an entire entity graph without a single access to the database.

As explained in the previous chapter, fetching entities is usually associated with propagating entity state transitions. Therefore, the second-level cache can improve response time for read-write transactions without compromising data consistency.

Application-level caches are useful for read scenarios, while the second-level cache consistency guarantee is better suited for offloading write traffic.

## 15.2 Cache synchronization strategies

In database nomenclature, the system of record represents the source of truth when information is scattered among various data providers. Duplicating data, so that it resides closer to application layers, can improve response time at the price of making it more difficult to synchronize the two data copies. To avoid inconsistent reads and data integrity issues, whenever a change occurs in the system, it is very important to synchronize both the database and the cache.

There are various ways to keep the cache and the underlying database in sync, and this section is going to present some of the most common cache synchronization strategies.

### 15.2.1 Cache-aside

The application code manually manages both the database system and the caching layer.

**Figure 15.2: Cache-aside synchronization strategy**

Before hitting the database, the application logic inspects the cache to see if the requested entity was previously loaded. Whenever an entity changes, the application must update both the database and the cache store.

Mixing application logic with caching management semantics breaks the Single Responsibility Principle. For this reason, it is good practice to move the caching logic into an AOP (aspectoriented programming) interceptor, therefore decoupling the cache management logic from the business logic code.

### 15.2.2 Read-through

```java
Instead of managing both the database and the cache, the application layer interacts only
with the cache system; the database management logic being hidden behind the caching API.
Compared to the cache-aside use case, the data access logic is simplified since there is only
one data source to communicate with.
```

**Figure 15.3: Read-through synchronization strategy**

When fetching an entity, the cache checks if the requested entity is already contained in the cache store, and, upon a cache miss, the entity is loaded from the database.

### 15.2.3 Write-invalidate

If the entity is modified, the cache propagates the change to the underlying database and removes the associated entry from the cache. The next time this entity is requested, the cache system is going to load the latest version from the database.

**Figure 15.4: Write-invalidate synchronization strategy**

### 15.2.4 Write-through

If the entity is modified, the changed is propagated to the underlying database and the cache as well.

**Figure 15.5: Write-through synchronization strategy**

If the caching layer supports JTA transactions, the cache and the database can be committed at once. Although XA transactions can simplify development, the two-phase commit protocol incurs a significant performance overhead.

An alternative is to use soft locks on the cache side to hide the cache entry modification until the database transaction is committed, so that, until the lock is released, other concurrent transactions must load the entity from the database.

### 15.2.5 Write-behind

If strong consistency is not mandated, the change requests can be enqueued and flushed at once to the database.

**Figure 15.6: Write-behind synchronization strategy**

This strategy is employed by the JPA Persistence Context, all entity state transitions being flushed towards the end of the currently running transaction or prior to executing a query.

## 15.3 Database caching

As explained at the beginning of this chapter, most database engines make use of internal caching mechanisms to speed up read and write operations. The most common database cache component is the in-memory buffers, but there might be other components as well such as the execution plan cache or query result buffer. Even without a database cache, the underlying operating system may offer caching for data pages.

Unlike application-level caches, the database cache does not compromise data consistency. Being both read-through and write-through, the database cache is transparent to the data access layer. Even with the advent of SSD (solid-state drive), disks still have a much higher latency than RAM. For this purpose, it makes much sense to load frequently-accessed data from memory, rather than going to disk.

Oracle

Oracle has multiple mechanisms for caching, such as:

* Buffer pool - storing blocks of data that are loaded from the underlying disk drive.
* Shared pool - storing parsed SQL statements, schema object metadata, sequence numbers.
* Large pool - stores results for parallel queries, large I/O buffers that are used for recovery management and backup or restore procedures.
* Result cache - stores results for SQL queries (when using the RESULT_CACHE query hint) and PL/SQL functions (when using the RESULT_CACHE directive).

On Unix systems, all I/O goes through the OS page cache. However, the same data is going to be cached in the Buffer pool, therefore data blocks are cached twice. For this reason, direct I/Oa is desirable because it can bypass the file system cache, and the OS page cache can be used for other system processes.

There are also use cases when Oracle does not use the Buffer pool for caching data blocks (e.g. TEMP tablespace operations, LOB columns using the NOCACHE storing option), in which case the operating system cache may be suitable for speeding up read and write operations.

Although each caching structure can be configured manually, it is often a good idea to leave this responsibility to the automatic memory managementb mechanism, which is enabled by default.

ahttp://docs.oracle.com/database/121/TGDBA/pfgrf_os.htm#TGDBA[^94410] bhttps://docs.oracle.com/database/121/TGDBA/memory.htm#TGDBA[^505]

SQL Server

To provide very low transaction response times, SQL Server strives for reducing I/O operations (which are a source of performance-related issues in many database systems). For this reason, the database engine tries to use as much system memory as possible so that frequently-accessed data and index disk pages are served from RAM rather than the disk drive.

Upon startup, SQL Server allocates a portion of the system memory and uses it as a buffer pool. The buffer pool is divided into multiple pages of 8KB. Both data and index pages are read from disk into buffer pages, and, when the in-memory pages are modified, they are written back to disk.

SQL Server 2014 supports buffer pool extensionsa, which allow it to use SSD drives to increase the buffer cache size beyond the capabilities of the current system available memory.

ahttps://msdn.microsoft.com/en-us/library/dn[^133176].aspx

PostgreSQL

For improving read and write operation performance, PostgreSQL relies heavily on the underlying operating system caching capabilities. However, most operating systems use a LRU (least recently used) page replacement policy which is unaware of the data access patterns or other database-related considerations.

For this reason, PostgreSQL defines a shared buffers structure which stores disk pages into 8KB in-memory page cache entries. The shared buffer size is controlled via the shared_buffers configuration property. Unlike the OS cache, the shared buffers use a LFU (least frequently used) algorithm called clock sweep which counts the number of times a disk page is used. The more often a disk page is being used, the longer it is going to linger in the shared buffer database internal cache.

That being said, the shared buffer structure is more useful for storing frequently-accessed data blocks, while the operating system cache can be used for everything else. The shared buffer cache should not be set too high because the database engine requires memory for other operations as well (sorting, hashing, building indexes, vacuuming).

Although the shared buffers structure is very important for speeding up reads and writes, it is good practice to limit the shared buffer sizea to the size of the current working set, therefore leaving enough memory for other database-related tasks.

ahttp://www.postgresql.org/docs/current/static/runtime-config-resource.html

MySQL

MySQL uses its internal buffer pool to cache data and indexes. The buffer pool is implemented as a linked list of memory pages. If the buffer pool size is smaller than the overall InnoDB tablespace size, a LRU-based algorithm is going to be used to deallocate older page entries.

The pool size is given by the innodb_buffer_pool_size configuration property which, ideally, should be adjusted so that it can hold all data and indexes in memory. Care must be taken to allow enough memory for the OS, as well for other MySQL structures and processes (e.g. threads allocated for each individual connection, sort buffers, query cache).

On Linux, to avoid double buffering caused by the operating system caching mechanism, the

innodb_flush_methoda configuration property should be set to O_DIRECT.

Nevertheless, the OS cache is useful for storing the InnoDB transaction log (used for ensuring ACID transactions), the binary log (used for database replication), and other MySQL structures that are not covered by the InnoDB buffer pool.

ahttp://dev.mysql.com/doc/refman/5.7/en/innodb-parameters.html#sysvar_innodb_flush_method

Essential, but not sufficient

Database caching is very important for a high-performance enterprise application. However, database caching only applies to a single node, and, if the database size is bigger than the capacity of a single node, then this solution alone is no longer sufficient. One workaround is to use database sharding, but that is not without challenges.

Even if database caching improves performance considerably, the networking overhead still plays a significant role in the overall transaction response time. If the application operates on graphs of entities, fetching an entire graph might require lots of joins or many secondary select statements. For this reason, it makes sense to cache the whole entity aggregate and have it closer to the application layer.

If the enterprise system relies only on the database system alone to serve read requests, the database becomes a single point of failure. This availability can be increased by using database replication. However, if all database nodes are collocated (to reduce the synchronization overhead caused by networking latency), the database system can still become unavailable if the data center is facing a sudden power outage.

For all these reasons, it is good practice to use an application-layer caching solution to address database caching limitations.

## 15.4 Application-level caching

Application caches are a necessity for high-performance enterprise applications, and this section is going to explore this topic in greater detail. No matter how well tuned a database engine is, the statement response time is highly dependent on the incoming database load. A traffic spike incurs a high contention of database system resources, which can lead to higher response times.

For instance, most internet applications expose a sitemap which is used by Search Engine bots to index the content of the site in question and make it available for searches. From a business perspective, having a high page rank is highly desirable because it can translate to more revenue. However, the Search Engine bot can generate a sudden traffic spike, which, in turn, can lead to a spike in transaction response time. Unfortunately, high response times can affect the site page rank. That being said, the translation response time must be relatively low even during high traffic loads.

The application-level cache can, therefore, level up traffic spikes because the cache fetching complexity is O(1). More, if the application-level cache holds a significant portion of the entire data set, the application can still work (even if in a read-only mode) when the database is shut down for maintenance or due to a catastrophic event.

### 15.4.1 Entity aggregates

In a relation database, data is normalized, and, for a complex enterprise application, it is usually spread across multiple tables. On the other hand, the business logic might operate on entity graphs which assemble information from various database tables.

To better visualize the entity aggregate, consider the following diagram depicting all entities associated with a single Post in a particular forum.

**Figure 15.7: Entity aggregates**

The Post entity is the root since all other entities relate to it, either directly or indirectly. A

Post belongs to a Board entity, and it can have several Tag(s). The PageViews entity summarizes statistics about how popular a given Post might be. There is also a SocialMediaCounters entity to hold the number of shares for social media platforms. Users can add Comment(s) to a Post, and they can also cast a vote on both the Post or the Comment entity.

The sitemap contains the list of all Post(s) so that Search Engines can index all questions and answers. When a Post is requested, the whole entity aggregate is required to render the display. Without application-level caching, the data access layer would have to either join all the associated entities or use secondary select statements.

To avoid a Cartesian Product, the Post entity should be joined to its Tag(s), as well as with other many-to-one relationships (e.g. Board, PageViews, SocialMediaCounters). A secondary query is used to fetch the UserVote(s) associated with the current Post. The Comment(s) can be fetched with a secondary select, and this is desirable since there might be many Comment(s), and the secondary query can better use pagination. The Comment query could also join the UserVote(s) so that these two entities are fetched with a single query as well.

### 15.4.2 Distributed key-value stores

While the underlying data resides in the relational database, the entity aggregate can also be saved in a distributed cache, such as Redis or Memcached. Key-value stores are optimized for storing data structures in memory, and the lookup complexity is O(1). This is ideal for high-performance enterprise applications since response time can stay low even during unforeseen traffic spikes.

**Figure 15.8: Application-level cache integration**

The relational database is still the system of record, while the key-value caching solution is used as an alternate data provider.

### 15.4.3 Cache synchronization patterns

Unfortunately, duplicating data among two data sources is not without issues. Ideally, both the relational database and the application-level cache should be in sync, every update being applied synchronously to both data stores. In reality, not all business use cases have strict consistency requirements.

For instance, the PageViews and the SocialMediaCounters can be updated periodically by a batch processor which can aggregate the database counters and update the cache entry with the latest aggregated values. On the other hand, some actions need a more strict consistency guarantees. For Comment entries, read-your-writes consistency is needed because otherwise users might miss their own changes.

Caching is always about trade-offs, and not all business use cases are equal in terms of consistency guarantees. For strict consistency, some transactions might need to bypass the cache entirely and read from the database.

Once a user or a batch process makes a change to the underlying database records, the cache needs to be updated as well. As explained in the cache concurrency strategies section, there are several ways to implement the synchronization logic.

### 15.4.4 Synchronous updates

If cache-aside is being used, the business logic must update both the database and all associated cache entries in the same transaction. Because most key-value stores do not use XA transactions, the cache entries can be either invalidated (in which case there is no risk of reading stale data), or they can be updated after the database transaction has been committed (in which case there is a slight time interval when a concurrent transaction can read a stale entry from the cache).

For the previous Domain Model, Comment entities should be processed synchronously. Adding or modifying a UserVote entry can also be done synchronously, or at least for the comments that are associated with the currently logged user.

### 15.4.5 Asynchronous updates

If eventual consistency is tolerated, then asynchronous updates are also a viable solution, and the application logic can be simplified since the caching logic is decoupled from business logic. This is also necessary when there are multiple data stores that need to be updated according to the latest changes that happened in the database. For instance, the enterprise

application might need to propagate changes to a cache, an in-memory data processing framework (e.g. Spark) which might monitor the forum for spam messages, or to a data warehouse. In this case, the changes must be captured from the database and propagated to all other subsystems that are interested in being notified about these updates.

15.4.5.1 Change data capture

In database terminology, change data capture (CDC) is an assembly of patterns that are responsible for recording database changes.

One solution is to record the timestamp version of every row that is either inserted, updated, or deleted. This pattern only works if records are not actually physically removed, but instead, they are simply marked as deleted (soft deleting), and hidden away from any database query.

Another implementation would be to capture changes using database triggers so that an event is recorded whenever a row is inserted, updated, or deleted. Unfortunately, triggers might slow down write operations which is undesirable especially if there is only one database Master node because the longer the write transactions take, the less throughput the Master node will accommodate.

A more efficient approach is to use a framework that can parse the database transaction log. Unlike database triggers, this approach does not incur any additional performance penalty for write operations since the transaction log is being parsed asynchronously. The only drawback is that not all database support this natively, and the transaction log entries can change from one database version to the other.

Oracle

Oracle GoldenGatea is a change data capture tool that can be used either for database replication or as an ETL (extract, transform, and load) process in order to feed a data warehouse. Another approach is to use Databusb, which is an open-source framework developed by Linkedin for log mining.

ahttp://www.oracle.com/us/products/middleware/data-integration/goldengate/overview/index.html bhttps://github.com/linkedin/databus

SQL Server

Since version 2008, SQL Server offers a Change Data Capturea solution that can be configured at the database, table, or even column level.

ahttps://msdn.microsoft.com/en-us/library/cc[^627369].aspx

PostgreSQL

Even if there is no native CDC solution, PostgreSQL 9.4 has introduced logical decodinga

which can be used for extracting row-level modifications.

ahttp://www.postgresql.org/docs/current/static/logicaldecoding.html

MySQL

There are multiple solutions that are able to parse the MySQL binary log, and the most notable is Databus which supports both Oracle and MySQL.

Denormalization ripple effect

In the previous Domain Model, storing the Board and the list of Tag(s) associated with every particular Post entity graph is appropriate only if the Board and the Tag are practically immutable. Otherwise, changing the Board entity could ripple throughout the cache, causing a large number of entries to be updated as well. This problem is even more acute if cache entry invalidation is being used. For Tag(s), the Post aggregate should store only a list of Tag identifiers, the actual Tag names being resolved upon fetching the Post entity aggregate from the cache.

On the other hand, Comment(s) and UserVote(s) are more related to a single Post entry, so they are more suitable for being stored in the Post entity aggregate. To avoid the ripple effect, the UserVote entity should only contain virtually immutable user-related columns (e.g. user identifier).

The higher the data denormalization degree associated with entity aggregates, the bigger the data change ripple. Therefore, it is good practice to avoid storing associations that might be shared among many entity graphs cache entries.

## 15.5 Second-level caching

While the Persistence Context has long been referred to as the first-level cache, in reality, it is meant to provide application-level repeatable reads rather than lowering fetch execution time. The first-level cache is not thread-safe, and, once the Hibernate Session is closed, the cached entities are no longer accessible.

On the other hand, the second-level cache is bound to a SessionFactory, it is thread-safe, and it provides a solution for optimizing entity aggregate loading time. Hibernate only defines the contract for the second-level cache API and does not provide a reference implementation for this specification. The second-level cache API is implemented by third-party caching providers, such as Infinispan[^1], Ehcache[^2], or Hazelcast[^3].

Being tightly integrated with Hibernate, the second-level cache does not require any data access layer code change. While application-level caches operate in a cache-aside synchronization mode, the second-level cache offers read-through and write-through cache update strategies.

Unlike an application-level caching solution, the second-level does not store entity aggregates. Instead, entities are saved in a row-level data format which is closer to the associated database row values. Although it features a collection-level cache component, behind the scenes, it only saves the entity identifiers contained in a particular collection instance. The same is true for the entity query caching, whose cache entries contain only the entity identifiers that satisfy a given query filtering criteria.

For all the aforementioned reasons, the second-level cache is not a replacement or a substitute for application-level caches. The biggest gain for using the Hibernate secondlevel cache is that, in a Master-Slave database replication scheme, it can optimize readwrite transactions. While read-only queries can be executed on many Slave nodes, read-write transactions can only be executed by the Master node.

Being capable of working in read-through and write-through mode, the second-level cache can help reduce read-write transactions response time by reducing the amount of work the Master node is required to do.

[^1]: <http://infinispan.org/>

[^2]: <http://www.ehcache.org/>

[^3]: <http://hazelcast.org/>

### 15.5.1 Enabling the second-level cache

By default, the hibernate.cache.use_second_level_cache configuration is set to true. However, this is not sufficient because Hibernate requires a CachingRegionFactory implementation as well, and, without specifying any third-party implementation, Hibernate defaults to using the NoCachingRegionFactory implementation, meaning that nothing is actually being cached.

For this reason, it is mandatory to supply the hibernate.cache.region.factory_class configuration property, which takes the fully-qualified class name of the CacheRegionFactory third-party implementation.

<property name="hibernate.cache.region.factory_class"

value="org.hibernate.cache.ehcache.EhCacheRegionFactory"/>

After enabling the second-level cache, the application developer must instruct Hibernate which entities should be cached. Although JPA 2.0 defined the @Cacheable annotation, Hibernate also requires a cache concurrency strategy.

For this reason, the org.hibernate.annotations.Cache annotation should be provided as well.

```java
@Entity
@Cache(usage = CacheConcurrencyStrategy.READ_WRITE)
public class Post {
//Fields, getters, and setters omitted for brevity
}
```

Hibernate defines the hibernate.cache.default_cache_concurrency_strategy configuration property which applies the same synchronization strategy to all cacheable entities. When this configuration property is set, the @Cache annotation is no longer mandatory, and the @Cacheable annotation can be used instead. By supplying a @Cache annotation, the default cache concurrency strategy can be overridden on a per-entity basis.

### 15.5.2 Entity cache loading flow

Once the second-level cache is activated for a particular entity, it participates automatically in the entity loading mechanism.

**Figure 15.9: Entity loading control flow**

When loading an entity, Hibernate always checks the Persistence Context first. This behavior guarantees application-level repeatable reads. Once an entity becomes managed, Hibernate will use the same entity instance when loading it directly or including it in an entity query.

If the entity is not found in the currently running Persistence Context and the second-level cache is configured properly, Hibernate checks the second-level cache. Only if the secondlevel cache does not contain the entity in question, Hibernate will fetch the entity from the underlying database.

### 15.5.3 Entity cache entry

Internally, every entity is stored as a CacheEntry. As previously explained, Hibernate does not store aggregates, and the second-level cache entry is close to the underlying table row representation.

Hydrated and disassembled state

In Hibernate nomenclature, hydration represents the process of transforming a JDBC ResultSet into an array of raw values.

The hydrated state is saved in the currently running Persistence Context as an EntityEntry object which encapsulated the loading time entity snapshot. The hydrated state is then used by the default dirty checking mechanism which compares the current entity data against the loading time snapshot.

The second-level cache entry values contain the hydrated state of a particular entity. However, for the second-level cache the hydrated state is called disassembled state.

To visualize the disassembled entity state, consider the following entity model:

```java
@Entity @Cache(usage = CacheConcurrencyStrategy.READ_WRITE)
public class Post {
@Id
private Long id;
private String title;
@Version
private int version;
//Getters and setters omitted for brevity
}
@Entity @Cache(usage = CacheConcurrencyStrategy.READ_WRITE)
public class PostDetails {
@Id
private Long id;
private Date createdOn;
private String createdBy;
@OneToOne
@MapsId
private Post post;
//Getters and setters omitted for brevity
}
@Entity @Cache(usage = CacheConcurrencyStrategy.READ_WRITE)
public class PostComment {
@Id
private Long id;
@ManyToOne
private Post post;
private String review;
//Getters and setters omitted for brevity
}
```

Upon saving and fetching the following Post entity:

```java
Post post = new Post();
post.setId(1L);
post.setTitle("High-Performance Java Persistence");
entityManager.persist(post);
```

Hibernate stores the following second-level cache entry:

```java
item = {org.hibernate.cache.ehcache.internal.strategy.AbstractReadWriteEhcacheAccess\
Strategy$Item}
value = {org.hibernate.cache.spi.entry.StandardCacheEntryImpl}
disassembledState = {java.io.Serializable[1]}
```

0 = "High-Performance Java Persistence" subclass = "com.vladmihalcea.book.hpjp.hibernate.cache.Post" version = 0 timestamp = 5990528746983424

The disassembledState is an Object[] array which, in this case, contains a single entry that represents the Post title. The version attribute is stored separately, outside of the disassembledState array. The entity identifier is stored in the cache entry key which looks as follows:

```java
key = {org.hibernate.cache.internal.OldCacheKeyImplementation}
id = {java.lang.Long} "1"
type = {org.hibernate.type.LongType}
entityOrRoleName = "com.vladmihalcea.book.hpjp.hibernate.cache.Post"
tenantId = null
hashCode = 31
```

The cache entry key contains the entity type (e.g. entityOrRoleName), the identifier (e.g. id), and the identifier type (e.g. type). When multitenancy is being used, the tenant identifier (e.g.

tenantId) is stored as well.

When storing a PostDetails entity:

```java
PostDetails details = new PostDetails();
details.setCreatedBy("Vlad Mihalcea");
details.setCreatedOn(new Date());
details.setPost(post);
entityManager.persist(details);
```

The second-level cache entry looks like this:

```java
item = {org.hibernate.cache.ehcache.internal.strategy.AbstractReadWriteEhcacheAccess\
Strategy$Item}
value = {org.hibernate.cache.spi.entry.StandardCacheEntryImpl}
disassembledState = {java.io.Serializable[3]}
0 = "Vlad Mihalcea"
1 = {java.util.Date} "Fri May 06 15:45:10 EEST 2016"
subclass = "com.vladmihalcea.book.hpjp.hibernate.cache.PostDetails"
version = null
timestamp = 5990558557458432
```

The version attribute is null because the PostDetails entity does not feature a @Version attribute. The disassembledState array has a length of 3, although just the createdBy and the createdOn attributes are visible. The @OneToOne association information is stored as null in the disassem-

bledState array because Hibernate knows that the entity identifier is sufficient to locate the associated parent relationship.

When persisting a PostComment entity:

```java
PostComment comment1 = new PostComment();
comment1.setId(1L);
comment1.setReview("JDBC part review");
comment1.setPost(post);
entityManager.persist(comment1);
```

The disassembled state will contain the review attribute and the foreign key value that is used for identifying the @ManyToOne association:

```java
item = {org.hibernate.cache.ehcache.internal.strategy.AbstractReadWriteEhcacheAccess\
Strategy$Item}
value = {org.hibernate.cache.spi.entry.StandardCacheEntryImpl}
disassembledState = {java.io.Serializable[2]}
0 = {java.lang.Long} "1"
1 = "JDBC part review"
subclass = "com.vladmihalcea.book.hpjp.hibernate.cache.PostComment"
version = null
timestamp = 5990563491569665
```

15.5.3.1 Entity reference cache store

Hibernate can also store entity references directly in the second-level cache, therefore avoiding the performance penalty of reconstructing an entity from its disassembled state. However, not all entity types are allowed to benefit from this optimization.

For an entity to be cached as a reference, it must obey the following rules:

* The entity must be immutable, meaning that it must be marked with the

@org.hibernate.annotations.Immutable annotation.

* It might not feature any entity association (@ManyToOne, @OneToOne, @OneToMany, @ManyToMany, or @ElementCollection).
* The hibernate.cache.use_reference_entries configuration property must be enabled.

Among the previously Domain Model entities, only the Post entity could be stored as an entity reference because PostDetails has a @OneToOne Post association, while PostComment has a @ManyToOne Post relationship. Therefore, the Post entity only needs to be marked with the

@Immutable annotation:

```java
@Entity @Immutable
@Cache(usage = CacheConcurrencyStrategy.READ_ONLY)
public class Post implements Serializable {
@Id
private Long id;
private String title;
@Version
private int version;
//Getters and setters omitted for brevity
}
```

It is good practice to make the entity Serializable because the cache provider might need to persist the entity reference on disk. Because entities are immutable, the READ_-

ONLY is the most obvious CacheConcurrencyStrategy to use in this case.

When storing the same Post entity instance that was used for the disassembled state use case, the cache entry value is going to look as follows:

```java
value = {org.hibernate.cache.spi.entry.ReferenceCacheEntryImpl}
reference = {com.vladmihalcea.book.hpjp.hibernate.cache.Post}
id = {java.lang.Long} "0"
title = "High-Performance Java Persistence"
version = 0
subclassPersister = {org.hibernate.persister.entity.SingleTableEntityPersister}
```

To understand the performance gain for storing and retrieving entity references, the following test case is going to measure how much time it takes to fetch 100, 500, 1000, 5000, and 10 000 entities from the second-level cache when using the default entity disassembled state mechanism or the entity reference cache store.

**Figure 15.10: Disassembled state vs Entity references**

Fetching entity references is much more efficient since new objects are not required to be instantiated and populated with the entity disassembled state. The more entities are fetched from the cache, the more apparent the time gap between the default entity cache store and its entity reference alternative.

Although the hibernate.cache.use_reference_entries configuration allows reducing the cache fetching time, it’s not a general purpose second-level cache optimization technique because it’s only applicable to entities that do not have any association mapping.

### 15.5.4 Collection cache entry

The collection cache allows storing the entity identifiers that are contained within a given collection instance. Because it only stores identifiers, it is mandatory that the contained entities are cached as well.

The collection cache is activated by the hibernate.cache.use_second_level_cache configuration property, just like the regular entity caching mechanism.

The Post entity has a bidirectional one-to-many PostComment association that is mapped as follows:

```java
@OneToMany(cascade = CascadeType.ALL, mappedBy = "post", orphanRemoval = true)
@Cache(usage = CacheConcurrencyStrategy.READ_WRITE)
private List<PostComment> comments = new ArrayList<>();
```

For the next example, two PostComment child entities are going to be associated with a managed

Post entity:

```java
Post post = entityManager.find(Post.class, 1L);
PostComment comment1 = new PostComment();
comment1.setId(1L);
comment1.setReview("JDBC part review");
post.addComment(comment1);
PostComment comment2 = new PostComment();
comment2.setId(2L);
comment2.setReview("Hibernate part review");
post.addComment(comment2);
```

Because the collection is marked with the @Cache annotation, upon accessing the collection for the first time, Hibernate is going to cache its content using the following cache entry key:

```java
key = {org.hibernate.cache.internal.OldCacheKeyImplementation}
id = {java.lang.Long} "1"
type = {org.hibernate.type.LongType}
entityOrRoleName = "com.vladmihalcea.book.hpjp.hibernate.cache.Post.comments"
tenantId = null
hashCode = 31
```

The collection cache entry key is almost identical with the entity cache one, the only difference being the cache region name, which is constructed by appending the collection attribute name to the fully-qualified entity class name.

As previously explained, the associated cache entry value contains PostComment entity identifiers that are contained within the currently used Post entity comment collection:

```java
item = {org.hibernate.cache.spi.entry.CollectionCacheEntry}
state = {java.io.Serializable[2]}
0 = {java.lang.Long} "1"
1 = {java.lang.Long} "2"
```

Along with the entity cache, the collection cache allows retrieving an entity aggregate without having to hit the database even once. Although fetching an entire entity graph requires multiple cache calls, the major advantage of storing entities and collections separately is that invalidation or updates affect a single cache entry.

### 15.5.5 Query cache entry

Just like the collection cache, the query cache is strictly related to entities, and it draws an association between a search criteria and the entities satisfying the given filtering condition. The query cache is disabled by default, and, to activate it, the following configuration property needs to be supplied:

<property name="hibernate.cache.use_query_cache" value="true"/>

Even if the query cache is enabled, queries must be explicitly marked as cacheable. When using the Hibernate native API, the setCacheable method must be used:

List<Post> posts = (List<Post>) session.createQuery(

```sql
"select p from Post p " +
"where p.title like :token")
.setParameter("token", "High-Performance%")
.setCacheable(true)
.list();
```

For the Java Persistence API, the org.hibernate.cacheable query hint must be provided, so when executing the following query:

List<Post> posts = entityManager.createQuery(

```sql
"select p from Post p " +
"where p.title like :token", Post.class)
.setParameter("token", "High-Performance%")
.setHint("org.hibernate.cacheable", true)
.getResultList();
```

Hibernate stores it using the following cache entry key:

```java
key = {QueryKey}
```

sqlQueryString = "select p0_.id as id1_0_, p0_.title as title2_0_, p0_.version as \ version3_0_ from Post p0_ where p0_.title like ?"

```java
positionalParameterTypes = {org.hibernate.type.Type[0]}
positionalParameterValues = {java.lang.Object[0]}
namedParameters = {java.util.HashMap}
size = 1
0 = {java.util.HashMap$Node} "token" -> "High-Performance%"
firstRow = null
maxRows = null
tenantIdentifier = null
filterKeys = null
customTransformer = {org.hibernate.transform.CacheableResultTransformer}
hashCode = -221304300
```

The cache entry value associated with the query above looks like this:

```java
element = {net.sf.ehcache.Element}
key = {org.hibernate.cache.spi.QueryKey}
value = {java.util.ArrayList}
size = 2
0 = {java.lang.Long} "5990928755007489"
1 = {java.lang.Long} "1"
2 = {java.lang.Long} "2"
version = 1
hitCount = 1
timeToLive = 120
timeToIdle = 120
creationTime = 1462629167305
lastAccessTime = 1462629171227
lastUpdateTime = 1462629167305
cacheDefaultLifespan = true
id = 0
```

The first entry represents the timestamp of the Session that stored the given query cache result. When the query cache entry is read, Hibernate checks if the query timestamp is greater than the associated tablespace update timestamps, and it only returns the cached element if there was no update since the cached result was stored.

The second and the third value entries represent the entity identifiers that satisfied these query filtering criteria.

Just like the collection cache, because the query cache only stores entity identifiers, it is mandatory that the associated entities are cached as well.

### 15.5.6 Cache concurrency strategies

The usage property of the @Cache annotation specifies the CacheConcurrencyStrategy in use for a particular entity or collection. There are four distinct strategies to choose from (READ_ONLY,

NONSTRICT_READ_WRITE, READ_WRITE, TRANSACTIONAL), each one defining a distinct behavior when it comes to inserting, updating, or deleting entities:

Before starting explaining each particular cache concurrency strategy, it is better to provide some guidelines related to visualizing the cache content. Hibernate can gather statistics about the second-level cache usage, and, as explained in the Hibernate statistics section, the

hibernate.generate_statistics configuration property must be set to true.

Once statistics are enabled, it is very easy to inspect the second-level cache regions using the following utility method:

```java
protected void printCacheRegionStatistics(String region) {
```

SecondLevelCacheStatistics statistics =

```java
sessionFactory().getStatistics().getSecondLevelCacheStatistics(region);
LOGGER.debug("\nRegion: {},\nStatistics: {},\nEntries: {}",
region, statistics, statistics.getEntries());
}
```

As previously explained, enterprise caching requires diligence because data is duplicated between the database, which is also the system of record, and the caching layer. To make sure that the two separate sources of data do not drift apart, Hibernate must synchronize the second-level cache entry whenever the associated entity state is changed. Because it has a great impact on data integrity, as well as on application performance, the following sections will discuss in greater detail each of those cache concurrency strategies.

15.5.6.1 READ_ONLY

If the cached data is immutable, there is no risk of data inconsistencies, so read-only data is always a good candidate for caching.

15.5.6.1.1 Inserting READ_ONLY cache entries

Considering that the previous Post entity is using the READ_ONLY cache concurrency strategy, when persisting a new entity instance:

```java
doInJPA(entityManager -> {
Post post = new Post();
post.setId(1L);
post.setTitle("High-Performance Java Persistence");
entityManager.persist(post);
});
printCacheRegionStatistics(Post.class.getName());
```

Hibernate generates the following output:

```sql
INSERT INTO post (title, version, id)
VALUES ('High-Performance Java Persistence', 0, 1)
Region: com.vladmihalcea.book.hpjp.hibernate.cache.Post,
Statistics: SecondLevelCacheStatistics[hitCount=0,missCount=0,putCount=1],
Entries: {1=CacheEntry(Post)[1,High-Performance Java Persistence,0]}
```

The putCount value is 1, so the entity is cached on insert, meaning that READ_ONLY is a writethrough strategy. Afterward, when issuing a direct load operation, Hibernate generates the following cache statistics:

```java
doInJPA(entityManager -> {
Post post = entityManager.find(Post.class, 1L);
printCacheRegionStatistics(post.getClass().getName());
});
Region: com.vladmihalcea.book.hpjp.hibernate.cache.Post,
Statistics: SecondLevelCacheStatistics[hitCount=1,missCount=0,putCount=1],
Entries: {1=CacheEntry(Post)[1,High-Performance Java Persistence,0]}
```

The hitCount value is 1 because the entity was loaded from the cache, therefore bypassing the database.

For generated identifiers, the write-through entity caching works only for sequences and table generator, so when inserting a Post entity that uses the GenerationType.SEQUENCE strategy:

```java
doInJPA(entityManager -> {
Post post = new Post();
post.setTitle("High-Performance Java Persistence");
entityManager.persist(post);
});
printCacheRegionStatistics(Post.class.getName());
```

Hibernate is going to generate the following output:

```sql
INSERT INTO post (title, version, id)
VALUES ('High-Performance Java Persistence', 0, 1)
Region: com.vladmihalcea.book.hpjp.hibernate.cache.Post,
Statistics: SecondLevelCacheStatistics[hitCount=0,missCount=0,putCount=1],
Entries: {1=CacheEntry(Post)[1,High-Performance Java Persistence,0]}
```

Unfortunately, for identity columns, READ_ONLY uses a read-through cache strategy instead. If the Post entity uses the GenerationType.IDENTITY strategy, upon inserting the same Post entity instance, the second-level cache is not going to store the newly persisted entity:

```java
Region: com.vladmihalcea.book.hpjp.hibernate.cache.Post,
Statistics: SecondLevelCacheStatistics[hitCount=0,missCount=0,putCount=0],
Entries: {}
```

On the other hand, when the entity is fetched for the first time:

```java
doInJPA(entityManager -> {
Post post = entityManager.find(Post.class, 1L);
printCacheRegionStatistics(post.getClass().getName());
});
```

Hibernate is going to store the entity into the second-level cache:

```sql
SELECT p.id AS id1_0_0_, p.title AS title2_0_0_, p.version AS version3_0_0_
FROM
post p
WHERE
p.id = 1
Region: com.vladmihalcea.book.hpjp.hibernate.cache.readonly.Post,
Statistics: SecondLevelCacheStatistics[hitCount=0,missCount=1,putCount=1],
Entries: {1=CacheEntry(Post)[High-Performance Java Persistence,0]}
```

Considering that the Post entity has a bidirectional @OneToMany PostComment association, and the collection is cached using the READ_ONLY strategy, when adding two comments:

```java
doInJPA(entityManager -> {
Post post = entityManager.find(Post.class, 1L);
PostComment comment1 = new PostComment();
comment1.setId(1L);
comment1.setReview("JDBC part review");
post.addComment(comment1);
PostComment comment2 = new PostComment();
comment2.setId(2L);
comment2.setReview("Hibernate part review");
post.addComment(comment2);
});
printCacheRegionStatistics(Post.class.getName() + ".comments");
```

Hibernate inserts the two comments in the database, while the collection cache region is not updated:

```sql
INSERT INTO post_comment (post_id, review, id)
VALUES (1, 'JDBC part review', 1)
INSERT INTO post_comment (post_id, review, id)
VALUES (1, 'Hibernate part review', 2)
Region: com.vladmihalcea.book.hpjp.hibernate.cache.Post.comments,
Statistics: SecondLevelCacheStatistics[hitCount=0,missCount=0,putCount=0],
Entries: {}
```

However, upon requesting the collection for the first time:

```java
Post post = entityManager.find(Post.class, 1L);
assertEquals(2, post.getComments().size());
printCacheRegionStatistics(Post.class.getName() + ".comments");
```

Hibernate executes the SQL query and updates the cache as well:

```sql
SELECT pc.post_id AS post_id3_1_0_, pc.id AS id1_1_0_, pc.review AS review2_1_1_
FROM
post_comment pc
WHERE
pc.post_id = 1
Region: com.vladmihalcea.book.hpjp.hibernate.cache.Post.comments,
Statistics: SecondLevelCacheStatistics[hitCount=0,missCount=1,putCount=1],
Entries: {1=CollectionCacheEntry[1,2]}
```

Once the collection is cached, any further collection fetch request is going to be served from the cache, therefore bypassing the database.

As opposed to the READ_ONLY entity cache, the READ_ONLY collection cache is not write-through. Instead, it uses a read-through caching strategy.

15.5.6.1.2 Updating READ_ONLY cache entries

The READ_ONLY strategy disallows updates, so when trying to modify a Post entity, Hibernate throws the following exception:

java.lang.UnsupportedOperationException: Can't write to a readonly object

As of writing (Hibernate 5.1.0), Hibernate allows removing elements from a READ_ONLY cached collection. However, it does not invalidate the collection cache entry.

This way, when removing a PostComment from the Post entity comments collection:

```java
doInJPA(entityManager -> {
Post post = entityManager.find(Post.class, 1L);
PostComment comment = post.getComments().remove(0);
comment.setPost(null);
});
printCacheRegionStatistics(Post.class.getName());
printCacheRegionStatistics(PostComment.class.getName());
doInJPA(entityManager -> {
Post post = entityManager.find(Post.class, 1L);
});
```

Hibernate generates the following output:

```sql
DELETE FROM post_comment WHERE id = 1
Region: com.vladmihalcea.book.hpjp.hibernate.cache.Post.comments,
Statistics: SecondLevelCacheStatistics[hitCount=0,missCount=1,putCount=1],
Entries: {1=CollectionCacheEntry[1,2]}
Region: com.vladmihalcea.book.hpjp.hibernate.cache.PostComment,
Statistics: SecondLevelCacheStatistics[hitCount=0,missCount=0,putCount=2],
Entries: {2=CacheEntry(PostComment)[1,Hibernate part review]}
```

javax.persistence.EntityNotFoundException: Unable to find com.vladmihalcea.book.hpjp.hibernate.cache.PostComment with id 1

In reality, every READ_ONLY entity and collection should be marked with the @Immutable annotation:

```java
@Entity @Immutable @Cache(usage = CacheConcurrencyStrategy.READ_ONLY)
public class Post {
@OneToMany(cascade = CascadeType.PERSIST, mappedBy = "post")
@Immutable @Cache(usage = CacheConcurrencyStrategy.READ_ONLY)
private List<PostComment> comments = new ArrayList<>();
//Code omitted for brevity
}
```

This way, when trying to update a PostComment collection, Hibernate is going to throw the following exception:

org.hibernate.HibernateException: changed an immutable collection instance: [com.vladmihalcea.book.hpjp.hibernate.cache.Post.comments#1]

15.5.6.1.3 Deleting READ_ONLY cache entries

While updates should never occur for READ_ONLY entities (which signals a data access logic issue), deletes are permitted.

When deleting a Post entity that happens to be stored in the second-level cache:

```java
printCacheRegionStatistics(Post.class.getName());
printCacheRegionStatistics(PostComment.class.getName());
doInJPA(entityManager -> {
Post post = entityManager.find(Post.class, 1L);
entityManager.remove(post);
});
printCacheRegionStatistics(Post.class.getName());
printCacheRegionStatistics(PostComment.class.getName());
```

Hibernate generates the following output:

```sql
Region: com.vladmihalcea.book.hpjp.hibernate.cache.Post,
Statistics: SecondLevelCacheStatistics[hitCount=2,missCount=0,putCount=1],
Entries: {1=CacheEntry(Post)[1,High-Performance Java Persistence,0]}
Region: com.vladmihalcea.book.hpjp.hibernate.cache.PostComment,
Statistics: SecondLevelCacheStatistics[hitCount=0,missCount=0,putCount=2],
Entries: {1=CacheEntry(PostComment)[1,JDBC part review],
2=CacheEntry(PostComment)[1,Hibernate part review]}
DELETE FROM post_comment WHERE id = 1
DELETE FROM post_comment WHERE id = 2
DELETE FROM post WHERE id = 1 AND version = 0
Region: com.vladmihalcea.book.hpjp.hibernate.cache.Post,
Statistics: SecondLevelCacheStatistics[hitCount=3,missCount=0,putCount=1],
Entries: {}
Region: com.vladmihalcea.book.hpjp.hibernate.cache.PostComment,
Statistics: SecondLevelCacheStatistics[hitCount=2,missCount=0,putCount=2],
Entries: {}
```

The Post and PostComment entities are successfully removed form the database and the secondlevel cache as well.

15.5.6.2 NONSTRICT_READ_WRITE

The NONSTRICT_READ_WRITE concurrency strategy is designed for entities that are updated infrequently, and when strict consistency is not a mandatory requirement. The following examples are going to reuse the same entities that were previously employed, the only thing being different is that the Post and PostComment entities, as well as the comments collections, are using the @Cache(usage = CacheConcurrencyStrategy.NONSTRICT_READ_WRITE) annotation.

15.5.6.2.1 Inserting NONSTRICT_READ_WRITE cache entries

First of all, unlike other strategies, NONSTRICT_READ_WRITE is not write-through. Therefore, when persisting a Post entity, the second-level cache is not going to store the newly inserted object. Instead, NONSTRICT_READ_WRITE is a read-through cache concurrency strategy.

```java
doInJPA(entityManager -> {
Post post = new Post();
post.setId(1L);
post.setTitle("High-Performance Java Persistence");
PostComment comment1 = new PostComment();
comment1.setId(1L);
comment1.setReview("JDBC part review");
post.addComment(comment1);
PostComment comment2 = new PostComment();
comment2.setId(2L);
comment2.setReview("Hibernate part review");
post.addComment(comment2);
entityManager.persist(post);
});
printCacheRegionStatistics(Post.class.getName());
printCacheRegionStatistics(Post.class.getName() + ".comments");
LOGGER.info("Load Post entity and comments collection");
doInJPA(entityManager -> {
Post post = entityManager.find(Post.class, 1L);
assertEquals(2, post.getComments().size());
printCacheRegionStatistics(post.getClass().getName());
printCacheRegionStatistics(Post.class.getName() + ".comments");
});
```

When executing the test case above, the Post entity and PostComment collections are going to be cached upon being fetched for the first time.

```sql
INSERT INTO post (title, version, id)
VALUES ('High-Performance Java Persistence', 0, 1)
INSERT INTO post_comment (post_id, review, id) VALUES (1, 'JDBC part review', 1)
INSERT INTO post_comment (post_id, review, id)
VALUES (1, 'Hibernate part review', 2)
Region: com.vladmihalcea.book.hpjp.hibernate.cache.Post,
Statistics: SecondLevelCacheStatistics[hitCount=0,missCount=0,putCount=0],
Entries: {}
Region: com.vladmihalcea.book.hpjp.hibernate.cache.Post.comments,
Statistics: SecondLevelCacheStatistics[hitCount=0,missCount=0,putCount=0],
Entries: {}
```

* -Load Post entity and comments collection SELECT p.id AS id1_0_0_, p.title AS title2_0_0_, p.version AS version3_0_0_ FROM post p WHERE p.id = 1

```sql
SELECT pc.post_id AS post_id3_1_0_, pc.id AS id1_1_0_, pc.review AS review2_1_1_
FROM
post_comment pc
WHERE
pc.post_id = 1
Region: com.vladmihalcea.book.hpjp.hibernate.cache.Post,
Statistics: SecondLevelCacheStatistics[hitCount=0,missCount=1,putCount=1],
Entries: {1=CacheEntry(Post)[1,High-Performance Java Persistence,0]}
Region: com.vladmihalcea.book.hpjp.hibernate.cache.Post.comments,
Statistics: SecondLevelCacheStatistics[hitCount=0,missCount=1,putCount=1],
Entries: {1=CollectionCacheEntry[1,2]}
```

For it removes cache entries, NONSTRICT_READ_WRITE is only appropriate when entities are rarely changed. Otherwise, if the cache miss rate is too high, the cache renders inefficient.

15.5.6.2.2 Updating NONSTRICT_READ_WRITE cache entries

Unlike the READ_ONLY cache concurrency strategy, NONSTRICT_READ_WRITE supports entity and collection modifications.

```java
doInJPA(entityManager -> {
Post post = entityManager.find(Post.class, 1L);
post.setTitle("High-Performance Hibernate");
PostComment comment = post.getComments().remove(0);
comment.setPost(null);
});
printCacheRegionStatistics(Post.class.getName());
printCacheRegionStatistics(Post.class.getName() + ".comments");
printCacheRegionStatistics(PostComment.class.getName());
```

When executing the test case above, Hibernate generates the following output:

```sql
UPDATE post
SET title = 'High-Performance Hibernate', version = 1
WHERE id = 1 AND version = 0
DELETE FROM post_comment WHERE id = 1
Region: com.vladmihalcea.book.hpjp.hibernate.cache.Post,
Statistics: SecondLevelCacheStatistics[hitCount=1,missCount=1,putCount=1],
Entries: {}
Region: com.vladmihalcea.book.hpjp.hibernate.cache.Post.comments,
Statistics: SecondLevelCacheStatistics[hitCount=1,missCount=1,putCount=1],
Entries: {}
Region: com.vladmihalcea.book.hpjp.hibernate.cache.PostComment,
Statistics: SecondLevelCacheStatistics[hitCount=2,missCount=0,putCount=2],
Entries: {2=CacheEntry(PostComment)[1,Hibernate part review]}
```

15.5.6.2.3 Risk of inconsistencies

NONSTRICT_READ_WRITE does not offer strict consistency because it takes no locks on the cache entries that get modified. For this reason, on very tiny time interval, it is possible that the database and the cache might render different results.

During an entity update, the flow of operations goes like this:

# 1. The current Hibernate transaction (e.g. JdbcTransaction or JtaTransaction) is flushed.

ActionQueue. 3. The EntityUpdateAction calls the update method of the EntityRegionAccessStrategy. 4. The NonStrictReadWriteEhcacheCollectionRegionAccessStrategy removes the cache entry from the underlying ‘EhcacheEntityRegion.

After the database transaction is committed, the cache entry is removed once again:

1. The after transaction completion callback is called. 2. The current Session propagates this event to its internal ActionQueue. 3. The EntityUpdateAction calls the afterUpdate method on the EntityRegionAccessStrategy. 4. The NonStrictReadWriteEhcacheCollectionRegionAccessStrategy calls the remove method on the underlying EhcacheEntityRegion.

**Figure 15.11: NONSTRICT_READ_WRITE update flow**

The cache invalidation is not synchronized with the current database transaction. Even if the associated cache region entry gets invalidated twice (before and after transaction completion), there is still a tiny time window when the cache and the database might drift apart.

15.5.6.2.4 Deleting NONSTRICT_READ_WRITE cache entries

When deleting a Post entity that cascades the remove event to the PostComment collection:

```java
printCacheRegionStatistics(Post.class.getName());
printCacheRegionStatistics(Post.class.getName() + ".comments");
printCacheRegionStatistics(PostComment.class.getName());
doInJPA(entityManager -> {
Post post = entityManager.find(Post.class, 1L);
entityManager.remove(post);
});
printCacheRegionStatistics(Post.class.getName());
printCacheRegionStatistics(Post.class.getName() + ".comments");
printCacheRegionStatistics(PostComment.class.getName());
```

Hibernate is going to remove all associated cache regions:

```sql
Region: com.vladmihalcea.book.hpjp.hibernate.cache.Post,
Statistics: SecondLevelCacheStatistics[hitCount=0,missCount=1,putCount=1],
Entries: {1=CacheEntry(Post)[1,High-Performance Java Persistence,0]}
Region: com.vladmihalcea.book.hpjp.hibernate.cache.Post.comments,
Statistics: SecondLevelCacheStatistics[hitCount=0,missCount=1,putCount=1],
Entries: {1=CollectionCacheEntry[1,2]}
Region: com.vladmihalcea.book.hpjp.hibernate.cache.PostComment,
Statistics: SecondLevelCacheStatistics[hitCount=0,missCount=0,putCount=2],
Entries: {1=CacheEntry(PostComment)[1,JDBC part review],
2=CacheEntry(PostComment)[1,Hibernate part review]}
DELETE FROM post_comment WHERE id = 1
DELETE FROM post_comment WHERE id = 2
DELETE FROM post WHERE id = 1 AND version = 0
Region: com.vladmihalcea.book.hpjp.hibernate.cache.Post,
Statistics: SecondLevelCacheStatistics[hitCount=1,missCount=1,putCount=1],
Entries: {}
Region: com.vladmihalcea.book.hpjp.hibernate.cache.Post.comments,
Statistics: SecondLevelCacheStatistics[hitCount=1,missCount=1,putCount=1],
Entries: {}
Region: com.vladmihalcea.book.hpjp.hibernate.cache.PostComment,
Statistics: SecondLevelCacheStatistics[hitCount=2,missCount=0,putCount=2],
Entries: {}
```

Just like with update, the cache entry removal is called twice (the first time during flush and the second time after the transaction is committed).

15.5.6.3 READ_WRITE

To avoid any inconsistency risk while still using a write-through second-level cache, Hibernate offers the READ_WRITE cache concurrency strategy. A write-through cache strategy is a much better choice for write-intensive applications since cache entries can be updated rather than being simply removed.

Because the database is the system of record and database operations are wrapped inside one single physical transaction, the cache can either be updated synchronously which requires JTA transactions or asynchronously, right after the database transaction gets committed.

READ_WRITE is an asynchronous cache concurrency strategy, and, to prevent data integrity issues like stale cache entries, it employs a soft locking mechanism that provides the guarantees of a logical transaction isolation.

The following examples are going to reuse the same entities that were previously employed, and the only thing that differs is that the Post and PostComment entities, as well as the comments collections, are using the @Cache(usage = CacheConcurrencyStrategy.READ_WRITE) annotation.

15.5.6.3.1 Inserting READ_WRITE cache entries

Only the entity cache region can work in write-through mode, and, just like with any other cache concurrency strategy, the collection cache is read-through.

When running the same example used for inserting NONSTRICT_READ_WRITE cache entries, Hibernate generates the following output:

```sql
INSERT INTO post (title, version, id)
VALUES ('High-Performance Java Persistence', 0, 1)
INSERT INTO post_comment (post_id, review, id)
VALUES (1, 'JDBC part review', 1)
INSERT INTO post_comment (post_id, review, id)
VALUES (1, 'Hibernate part review', 2)
Region: com.vladmihalcea.book.hpjp.hibernate.cache.Post,
Statistics: SecondLevelCacheStatistics[hitCount=0,missCount=0,putCount=1],
Entries: {1=[ value = CacheEntry(Post)[1,High-Performance Java Persistence,0],
version=0, timestamp=5991931785445376 ]}
Region: com.vladmihalcea.book.hpjp.hibernate.cache.Post.comments,
Statistics: SecondLevelCacheStatistics[hitCount=0,missCount=0,putCount=0],
Entries: {1=Lock Source-UUID:7d059ff0-0ec8-490f-b316-e77efad0b15f Lock-ID:0}
```

* -Load Post entity and comments collection

```sql
SELECT pc.post_id AS post_id3_1_0_, pc.id AS id1_1_0_, pc.review AS review2_1_1_
FROM
post_comment pc
WHERE
pc.post_id = 1
Region: com.vladmihalcea.book.hpjp.hibernate.cache.Post,
Statistics: SecondLevelCacheStatistics[hitCount=1,missCount=0,putCount=1],
Entries: {1=[ value = CacheEntry(Post)[1,High-Performance Java Persistence,0],
version=0, timestamp=5991931785445376 ]}
Region: com.vladmihalcea.book.hpjp.hibernate.cache.Post.comments,
Statistics: SecondLevelCacheStatistics[hitCount=0,missCount=1,putCount=1],
Entries: {1=[ value = CollectionCacheEntry[1,2],
version=null, timestamp=5991931785895936 ]}
```

Unfortunately, this write-through caching does not work for the identity columns, and if the

Post entity is using the IDENTITY generator:

```java
@Id @GeneratedValue(strategy = GenerationType.IDENTITY)
private Long id;
```

When inserting a Post entity:

```java
doInJPA(entityManager -> {
Post post = new Post();
post.setTitle("High-Performance Java Persistence");
entityManager.persist(post);
});
printCacheRegionStatistics(Post.class.getName());
```

Hibernate is going to generate the following output:

```java
Region: com.vladmihalcea.book.hpjp.hibernate.cache.Post,
Statistics: SecondLevelCacheStatistics[hitCount=0,missCount=0,putCount=0],
Entries: {}
```

Because it supports write-through READ_WRITE entity caching, the sequence generator is preferred over identity columns. The behavior might change in future, so it is better to check the HHH-7964a JIRA issue status.

ahttps://hibernate.atlassian.net/browse/HHH-7964

15.5.6.3.2 Updating READ_WRITE cache entries

As already mentioned, the READ_WRITE cache concurrency strategy employs a soft locking mechanism to ensure data integrity.

1. The Hibernate transaction commit procedure triggers a Session flush. 2. The EntityUpdateAction replaces the current cache entry with a Lock object. 3. The update method is used for synchronous strategies. Therefore, it is a no-op in this case. 4. The after transaction callbacks are called, and the EntityUpdateAction executes the af-

terUpdate method of the EntityRegionAccessStrategy. 5. The ReadWriteEhcacheEntityRegionAccessStrategy replaces the Lock entry with an actual Item, encapsulating the entity disassembled state.

**Figure 15.12: READ_WRITE update flow**

Just like with database transactions, changes are applied directly, and locks are used to prevent other concurrent transactions from reading uncommitted data. When reading a Lock object from the cache, Hibernate knows that the associated entry is being modified by an uncommitted transaction. Therefore, it reads the entity from the database.

To visualize the whole process, when running the following test case:

```java
doInJPA(entityManager -> {
Post post = entityManager.find(Post.class, 1L);
post.setTitle("High-Performance Hibernate");
PostComment comment = post.getComments().remove(0);
comment.setPost(null);
entityManager.flush();
printCacheRegionStatistics(Post.class.getName());
printCacheRegionStatistics(Post.class.getName() + ".comments");
printCacheRegionStatistics(PostComment.class.getName());
LOGGER.debug("Commit after flush");
});
printCacheRegionStatistics(Post.class.getName());
printCacheRegionStatistics(Post.class.getName() + ".comments");
printCacheRegionStatistics(PostComment.class.getName());
```

Hibernate generates the following output:

```sql
UPDATE post
SET title = 'High-Performance Hibernate', version = 1
WHERE id = 1 AND version = 0
DELETE FROM post_comment WHERE id = 1
Region: com.vladmihalcea.book.hpjp.hibernate.cache.Post,
Statistics: SecondLevelCacheStatistics[hitCount=1,missCount=0,putCount=1],
Entries: {1=Lock Source-UUID:69c2fd51-11a3-43c1-9db2-91f30624ac74 Lock-ID:0}
Region: com.vladmihalcea.book.hpjp.hibernate.cache.Post.comments,
Statistics: SecondLevelCacheStatistics[hitCount=0,missCount=1,putCount=1],
Entries: {1=Lock Source-UUID:e75094c1-6bc2-43f3-87e3-1dcdf6bee083 Lock-ID:1}
Region: com.vladmihalcea.book.hpjp.hibernate.cache.PostComment,
Statistics: SecondLevelCacheStatistics[hitCount=0,missCount=0,putCount=2],
Entries: {1=Lock Source-UUID:99aafdef-7816-43ee-909d-5f10ab759c60 Lock-ID:0,
```

2=[ value = CacheEntry(PostComment)[1,Hibernate part review],

```java
version=null, timestamp=5992022222598145 ]}
```

* -Commit after flush

```java
Region: com.vladmihalcea.book.hpjp.hibernate.cache.Post,
Statistics: SecondLevelCacheStatistics[hitCount=1,missCount=0,putCount=2],
Entries: {1=[ value = CacheEntry(Post)[1,High-Performance Hibernate,1],
version=1, timestamp=5992019884548096 ]}
Region: com.vladmihalcea.book.hpjp.hibernate.cache.Post.comments,
Statistics: SecondLevelCacheStatistics[hitCount=0,missCount=1,putCount=1],
Entries: {1=Lock Source-UUID:db769a0a-d65a-4911-952e-1d0bb851ed8d Lock-ID:1}
Region: com.vladmihalcea.book.hpjp.hibernate.cache.PostComment,
Statistics: SecondLevelCacheStatistics[hitCount=0,missCount=0,putCount=2],
Entries: {1=Lock Source-UUID:f357da6a-665e-40d1-84c0-760e450df421 Lock-ID:0,
```

2=[ value = CacheEntry(PostComment)[1,Hibernate part review],

```java
version=null, timestamp=5992019884109825 ]}
```

Right after the Persistence Context is flushed, Hibernate executes the associated SQL statements and adds Lock objects into the cache entries associated with the currently modifying

Post entity and comments collection, as well as for the deleting PostComment entity.

After the transaction is committed, the Post entity cache entry is replaced with an Item object containing the updated disassembled state. Since READ_WRITE collections are not writethrough, the comments collection cache entry is still a Lock object even after commit. Since the

PostComment entity has been deleted, its cache entry is represented by a Lock entry.

15.5.6.3.3 Deleting READ_WRITE cache entries

Deleting entities is similar to the update process, as we can see from the following sequence diagram:

**Figure 15.13: READ_WRITE delete flow**

1. The Hibernate transaction commit procedure triggers a Session flush. 2. The EntityDeleteAction replaces the current cache entry with a Lock object 3. The remove method call doesn’t do anything since READ_WRITE is an asynchronous cache concurrency strategy. 4. The after transaction callbacks are called, and the EntityDeleteAction executes the unlock-

Item method of the EntityRegionAccessStrategy. 5. The ReadWriteEhcacheEntityRegionAccessStrategy replaces the Lock entry with another Lock object whose timeout period is further increased.

After an entity is deleted, its associated second-level cache entry will be replaced by a Lock object, so that any subsequent request is redirected to reading from the database instead of using the second-level cache entry.

When running the same example used for deleting NONSTRICT_READ_WRITE cache entries, Hibernate generates the following output:

```java
Region: com.vladmihalcea.book.hpjp.hibernate.cache.Post,
Statistics: SecondLevelCacheStatistics[hitCount=1,missCount=0,putCount=1],
Entries: {1=[ value = CacheEntry(Post)[1,High-Performance Java Persistence,0],
version=0, timestamp=5992355751620608 ]}
Region: com.vladmihalcea.book.hpjp.hibernate.cache.Post.comments,
Statistics: SecondLevelCacheStatistics[hitCount=0,missCount=1,putCount=1],
Entries: {1=[ value = CollectionCacheEntry[1,2],
version=null, timestamp=5992355752042496 ]}
Region: com.vladmihalcea.book.hpjp.hibernate.cache.PostComment,
Statistics: SecondLevelCacheStatistics[hitCount=0,missCount=0,putCount=2],
Entries: {1=[ value = CacheEntry(PostComment)[1,JDBC part review],
```

version=null, timestamp=5992355751624704 ], 2=[ value = CacheEntry(PostComment)[1,Hibernate part review],

```sql
version=null, timestamp=5992355751624705 ]}
DELETE FROM post_comment WHERE id = 1
DELETE FROM post_comment WHERE id = 2
DELETE FROM post WHERE id = 1 AND version = 0
Region: com.vladmihalcea.book.hpjp.hibernate.cache.Post,
Statistics: SecondLevelCacheStatistics[hitCount=2,missCount=0,putCount=1],
Entries: {1=Lock Source-UUID:b042192a-9ac6-4877-8663-018f898f1cdb Lock-ID:0}
Region: com.vladmihalcea.book.hpjp.hibernate.cache.Post.comments,
Statistics: SecondLevelCacheStatistics[hitCount=1,missCount=1,putCount=1],
Entries: {1=Lock Source-UUID:e75f034a-0346-4696-88fd-1b5100658a6f Lock-ID:1}
Region: com.vladmihalcea.book.hpjp.hibernate.cache.PostComment,
Statistics: SecondLevelCacheStatistics[hitCount=2,missCount=0,putCount=2],
Entries: {1=Lock Source-UUID:1d13b830-e96d-40f5-aa2b-6a402fa6135d Lock-ID:0,
2=Lock Source-UUID:1d13b830-e96d-40f5-aa2b-6a402fa6135d Lock-ID:1}
```

The delete operation does not remove entries from the second-level cache, but instead it replaces the previous Item entries with Lock objects. The next time a deleted cache entry is being read, Hibernate is going to redirect the request to the database, therefore guaranteeing strong consistency.

15.5.6.3.4 Soft locking concurrency control

Because the database is the system of record, strong consistency implies that uncommitted cache changes should not be read by other concurrent transactions. The READ_WRITE can store either an Item or a Lock.

The Item holds the entity disassembled state, as well as the entity version and a timestamp. The version and the timestamp are used for concurrency control as follows:

* An Item is readable only from a Session that has been started after the cache entry creation timestamp.
* An Item entry can be written only if the incoming version is greater than the current one held in the cache entry.

When an entity or a collection is either updated or deleted, Hibernate replaces the cached

Item entry with a Lock, whose concurrency control mechanism works as follows:

* Since it overwrites an Item cache entry, the Lock object instructs a concurrent Session to read the entity or the collection from the database.
* If at least one Session has managed to lock this entry, any write operation is forbidden.
* A Lock entry is writable only if the incoming entity state has a version which is newer than the one contained in the Lock object, or if the current Session creation timestamp is greater than the Lock timeout threshold.

If the database transaction is rolled back, the current cache entry holds a Lock instance which cannot be undone to the previous Item state. For this reason, the Lock must time out to allow the cache entry to be replaced by an actual Item cache entry.

For Ehcache, the default Lock timeout is 120 seconds, and it can be customized via the

net.sf.ehcache.hibernate.cache_lock_timeout configuration property.

The READ_WRITE concurrency strategy offers a write-through caching mechanism without requiring JTA transactions.

However, for heavy write contention scenarios, when there is a chance of rolling back transactions, the soft locking concurrency control can lead to having other concurrent transactions hitting the database for the whole duration of the lock timeout period. For this kind of situations, the TRANSACTIONAL concurrency strategy might be more suitable.

15.5.6.4 TRANSACTIONAL

While READ_WRITE is an asynchronous write-through cache concurrency strategy, TRANSACTIONAL uses a synchronous caching mechanism.

To enlist two data sources (the database and the second-level cache) in the same global transaction, a JTA transaction manager is needed. When using Java EE, the application server provides JTA transactions by default. For stand-alone enterprise applications, there are multiple transaction managers to choose from (e.g. Bitronix, Atomikos, Narayana).

For JTA transactions, Ehcache offers two failure recovery options: xa_strict and xa.

15.5.6.4.1 XA_Strict mode

In this mode, the second-level cache exposes a XAResource interface so that it can participate in the two-phase commit (2PC) protocol.

**Figure 15.14: TRANSACTIONAL XA_Strict flow**

The entity state is modified both in the database and in the cache, but these changes are isolated from other concurrent transactions, and they become visible once the current XA transaction gets committed.

The database and the cache remain consistent even in the case of an application crash.

15.5.6.4.2 XA mode

If only one DataSource participates in a global transaction, the transaction manager can apply the one-phase commit optimization. The second-level cache is managed through a

javax.transaction.Synchronization transaction callback. The Synchronization does not actively participate in deciding the transaction outcome, therefore following the current database transaction outcome:

**Figure 15.15: TRANSACTIONAL XA flow**

This mode trades durability for a lower response time, and in the case of a server crash (happening in between the database transaction commit and the second-level cache transaction callback), the two data sources will drift apart. This issue can be mitigated if entities employ an optimistic concurrency control mechanism, so, even if the application reads stale data, it will not lose updates upon writing it back.

The following examples are going to reuse the same entities that were previously employed, and the only thing that differs is that the Post and PostComment entities, as well as the comments collections, are using the @Cache(usage = CacheConcurrencyStrategy.TRANSACTIONAL) annotation. The transaction boundaries are managed by Spring framework, and the actual JTA transaction logic is coordinated by Bitronix Transaction Manager.

15.5.6.4.3 Inserting TRANSACTIONAL cache entries

When running the same example used for inserting NONSTRICT_READ_WRITE cache entries, Hibernate generates the following output:

```sql
INSERT INTO post (title, version, id)
VALUES ('High-Performance Java Persistence', 0, 1)
INSERT INTO post_comment (post_id, review, id)
VALUES (1, 'JDBC part review', 1)
INSERT INTO post_comment (post_id, review, id)
VALUES (1, 'Hibernate part review', 2)
Region: com.vladmihalcea.book.hpjp.hibernate.cache.Post,
Statistics: SecondLevelCacheStatistics[hitCount=0,missCount=0,putCount=1],
Entries: {1=CacheEntry(Post)[1,High-Performance Java Persistence,0]}
Region: com.vladmihalcea.book.hpjp.hibernate.cache.Post.comments,
Statistics: SecondLevelCacheStatistics[hitCount=0,missCount=0,putCount=00],
Entries: {}
```

* -Load Post entity and comments collection

```sql
SELECT pc.post_id AS post_id3_1_0_, pc.id AS id1_1_0_, pc.review AS review2_1_1_
FROM
post_comment pc
WHERE
pc.post_id = 1
Region: com.vladmihalcea.book.hpjp.hibernate.cache.Post,
Statistics: SecondLevelCacheStatistics[hitCount=1,missCount=0,putCount=1],
Entries: {1=CacheEntry(Post)[1,High-Performance Java Persistence,0]}
Region: com.vladmihalcea.book.hpjp.hibernate.cache.Post.comments,
Statistics: SecondLevelCacheStatistics[hitCount=0,missCount=1,putCount=1],
Entries: {1=CollectionCacheEntry[1,2]}
```

Just like READ_WRITE, the TRANSACTIONAL cache concurrency strategy is write-through for entities (unless using the identity generator in which case it is read-through), and read-though for collections.

15.5.6.4.4 Updating TRANSACTIONAL cache entries

Because the TRANSACTIONAL cache is synchronous, all changes are applied directly to cache, as illustrated by the following example:

```java
doInJPA(entityManager -> {
printCacheRegionStatistics(Post.class.getName());
printCacheRegionStatistics(Post.class.getName() + ".comments");
printCacheRegionStatistics(PostComment.class.getName());
Post post = entityManager.find(Post.class, 1L);
post.setTitle("High-Performance Hibernate");
PostComment comment = post.getComments().remove(0);
comment.setPost(null);
entityManager.flush();
printCacheRegionStatistics(Post.class.getName());
printCacheRegionStatistics(Post.class.getName() + ".comments");
printCacheRegionStatistics(PostComment.class.getName());
LOGGER.debug("Commit after flush");
});
printCacheRegionStatistics(Post.class.getName());
printCacheRegionStatistics(Post.class.getName() + ".comments");
printCacheRegionStatistics(PostComment.class.getName());
```

For which Hibernate generates the following output:

```sql
Region: com.vladmihalcea.book.hpjp.hibernate.cache.Post,
Statistics: SecondLevelCacheStatistics[hitCount=1,missCount=0,putCount=1],
Entries: {1=CacheEntry(Post)[1,High-Performance Java Persistence,0]}
Region: com.vladmihalcea.book.hpjp.hibernate.cache.Post.comments,
Statistics: SecondLevelCacheStatistics[hitCount=0,missCount=1,putCount=1],
Entries: {1=CollectionCacheEntry[1,2]}
Region: com.vladmihalcea.book.hpjp.hibernate.cache.PostComment,
Statistics: SecondLevelCacheStatistics[hitCount=0,missCount=0,putCount=2],
Entries: {1=CacheEntry(PostComment)[1,JDBC part review],
2=CacheEntry(PostComment)[1,Hibernate part review]}
UPDATE post
SET title = 'High-Performance Hibernate', version = 1
WHERE id = 1 AND version = 0
DELETE FROM post_comment WHERE id = 1
Region: com.vladmihalcea.book.hpjp.hibernate.cache.Post,
Statistics: SecondLevelCacheStatistics[hitCount=2,missCount=0,putCount=2],
Entries: {1=CacheEntry(Post)[1,High-Performance Hibernate,1]}
Region: com.vladmihalcea.book.hpjp.hibernate.cache.Post.comments,
Statistics: SecondLevelCacheStatistics[hitCount=1,missCount=1,putCount=1],
Entries: {}
Region: com.vladmihalcea.book.hpjp.hibernate.cache.PostComment,
Statistics: SecondLevelCacheStatistics[hitCount=2,missCount=0,putCount=2],
Entries: {2=CacheEntry(PostComment)[1,Hibernate part review]}
```

* -Commit after flush

```java
Region: com.vladmihalcea.book.hpjp.hibernate.cache.Post,
Statistics: SecondLevelCacheStatistics[hitCount=2,missCount=0,putCount=2],
Entries: {1=CacheEntry(Post)[1,High-Performance Hibernate,1]}
Region: com.vladmihalcea.book.hpjp.hibernate.cache.Post.comments,
Statistics: SecondLevelCacheStatistics[hitCount=1,missCount=1,putCount=1],
Entries: {}
Region: com.vladmihalcea.book.hpjp.hibernate.cache.PostComment,
Statistics: SecondLevelCacheStatistics[hitCount=2,missCount=0,putCount=2],
Entries: {2=CacheEntry(PostComment)[1,Hibernate part review]}
```

Unlike the READ_WRITE cache concurrency strategy, TRANSACTIONAL does not use Lock cache entries, but instead it offers transaction isolation through the second-level cache provider internal locking mechanisms. After the Post entity and the comments collections are modified, Hibernate applies all the changes synchronously.

The Post entity modification is immediately visible in the cache, but only for the currently running transaction. Other transactions will not see any pending modifications until the current transaction is committed.

The PostComment entity that was deleted from the database is going to be removed from the entity cache region as well.

The Post.comments collection cache region is invalidated, and all its content is being removed.

From the current running transaction perspective, the TRANSACTIONAL cache concurrency strategy offers read-your-own-writes consistency guarantees. Once the transaction is com-

mitted, all pending database and cache changes are becoming visible to other concurrent transactions as well.

15.5.6.4.5 Deleting TRANSACTIONAL cache entries

When running the same example used for deleting NONSTRICT_READ_WRITE cache entries, Hibernate generates the following output:

```sql
Region: com.vladmihalcea.book.hpjp.hibernate.cache.Post,
Statistics: SecondLevelCacheStatistics[hitCount=1,missCount=0,putCount=1],
Entries: {1=CacheEntry(Post)[1,High-Performance Java Persistence,0]}
Region: com.vladmihalcea.book.hpjp.hibernate.cache.Post.comments,
Statistics: SecondLevelCacheStatistics[hitCount=0,missCount=1,putCount=1],
Entries: {1=CollectionCacheEntry[1,2]}
Region: com.vladmihalcea.book.hpjp.hibernate.cache.PostComment,
Statistics: SecondLevelCacheStatistics[hitCount=0,missCount=0,putCount=2],
Entries: {1=CacheEntry(PostComment)[1,JDBC part review],
2=CacheEntry(PostComment)[1,Hibernate part review]}
DELETE FROM post_comment WHERE id = 1
DELETE FROM post_comment WHERE id = 2
DELETE FROM post WHERE id = 1 AND version = 0
Region: com.vladmihalcea.book.hpjp.hibernate.cache.Post,
Statistics: SecondLevelCacheStatistics[hitCount=2,missCount=0,putCount=1],
Entries: {}
Region: com.vladmihalcea.book.hpjp.hibernate.cache.Post.comments,
Statistics: SecondLevelCacheStatistics[hitCount=1,missCount=1,putCount=1],
Entries: {}
Region: com.vladmihalcea.book.hpjp.hibernate.cache.PostComment,
Statistics: SecondLevelCacheStatistics[hitCount=2,missCount=0,putCount=2],
Entries: {}
```

Unlike the READ_WRITE cache concurrency strategy which replaces the deleted Item cache entry with a Lock object, TRANSACTIONAL removes all the previously stored cache entries.

Choosing the right cache concurrency strategy

The concurrency strategy choice is based on the underlying data access patterns, as well as on the current application consistency requirements. By analyzing the second-level cache statistics, the application developer can tell how effective a cache concurrency strategy

renders. A high hitCount number indicates that the data access layer benefits from using the current cache concurrency strategy, while a high missCount value tells the opposite.

Although analyzing statistics is the best way to make sure that a strategy is a right choice, there are still some general guidelines that can be used to narrow the choice list.

For immutable data, the READ_ONLY strategy makes much sense because it even disallows updating cache entries.

If entities are changed infrequently and reading a stale entry is not really an issue, then the

NONSTRICT_READ_WRITE concurrency might be a good candidate.

For strong consistency, the data access layer can either use READ_WRITE or TRANSACTIONAL.

READ_WRITE is a good choice when the volume of write operations, as well as the chance of rolling back transaction, are rather low.

If the read and write ratio is balanced, TRANSACTIONAL might be a good alternative because updates are applied synchronously. If the roll back ratio is high (e.g. due to optimistic locking exceptions), the TRANSACTIONAL strategy is a much better choice because it allows rolling back cache entries, unlike READ_WRITE cache mode which maintains a Lock entry until it times out. Depending on the caching provider, even the TRANSACTIONAL cache concurrency strategy might offer different consistency modes (e.g. xa, xa_strict) so that the application developer can balance strong consistency with throughput. To overcome the overhead of the two-phase commit protocol, the Ehcache XA mode can leverage the one-phase commit optimization.

The concurrency strategy choice might be affected by the second-level cache topology as well. If the volume of data is high, a single node might not be sufficient, so data needs to be distributed across multiple nodes. A distributed cache increases cache availability because, if one node crashes, the cached data still lives on other machines. However, most distributed second-level cache providers do not support the TRANSACTIONAL cache concurrency strategy, leaving the application developer to choose either NONSTRICT_READ_WRITE or READ_WRITE.

### 15.5.7 Query cache strategy

The query cache does not take into consideration the cache concurrency strategy of the associated cached entities, so it has its own rules when it comes to ensuring data consistency. Just like the collection cache, the query cache uses a read-through approach, so queries are cached upon being executed for the first time.

org.hibernate.cache.internal.StandardQueryCache is the second-level cache region where query results are being stored.

To visualize how the read-through query cache works, consider the following query:

```java
public List<PostComment> getLatestPostComments(EntityManager entityManager) {
```

return entityManager.createQuery(

```sql
"select pc " +
"from PostComment pc " +
"order by pc.post.id desc", PostComment.class)
.setMaxResults(10)
.setHint(QueryHints.HINT_CACHEABLE, true)
.getResultList();
}
```

The QueryHints.HINT_CACHEABLE constant can be used to supply the JPA query hint that enables the second-level query cache.

If the current database contains the following entities:

```java
Post post = new Post();
post.setId(1L);
post.setTitle("High-Performance Java Persistence");
PostComment comment = new PostComment();
comment.setId(1L);
comment.setReview("JDBC part review");
post.addComment(comment);
entityManager.persist(post);
```

When running the aforementioned query and printing the associated query cache region statistics:

```java
doInJPA(entityManager -> {
printCacheRegionStatistics(StandardQueryCache.class.getName());
assertEquals(1, getLatestPostComments(entityManager).size());
printCacheRegionStatistics(StandardQueryCache.class.getName());
});
```

Hibernate generates the following output:

```sql
Region: org.hibernate.cache.internal.StandardQueryCache,
Statistics: SecondLevelCacheStatistics[hitCount=0,missCount=0,putCount=0],
Entries: {}
SELECT pc.id AS id1_1_, pc.post_id AS post_id3_1_, pc.review AS review2_1_
FROM
post_comment pc ORDER BY pc.post_id DESC LIMIT 10
Region: org.hibernate.cache.internal.StandardQueryCache,
Statistics: SecondLevelCacheStatistics[hitCount=0,missCount=1,putCount=1],
Entries: {sql: ; named parameters: {}; max rows: 10; = [5992563495481345, 1]}
```

For brevity, the query cache entry was shortened. As expected, once the query is being executed, the matching entity identifiers are stored in the query cache entry.

15.5.7.1 Tablespace query cache invalidation

To understand query cache invalidation, considering the following exercise:

```java
doInJPA(entityManager -> {
assertEquals(1, getLatestPostComments(entityManager).size());
printCacheRegionStatistics(StandardQueryCache.class.getName());
LOGGER.info("Insert a new PostComment");
PostComment newComment = new PostComment();
newComment.setId(2L);
newComment.setReview("JDBC part review");
Post post = entityManager.find(Post.class, 1L);
post.addComment(newComment);
entityManager.flush();
assertEquals(2, getLatestPostComments(entityManager).size());
printCacheRegionStatistics(StandardQueryCache.class.getName());
});
LOGGER.info("After transaction commit");
printCacheRegionStatistics(StandardQueryCache.class.getName());
doInJPA(entityManager -> {
LOGGER.info("Check query cache");
assertEquals(2, getLatestPostComments(entityManager).size());
});
printCacheRegionStatistics(StandardQueryCache.class.getName());
```

Hibernate generates the following output:

```java
Region: org.hibernate.cache.internal.StandardQueryCache,
Statistics: SecondLevelCacheStatistics[hitCount=0,missCount=1,putCount=1],
Entries: {sql: ; named parameters: {}; max rows: 10;=[5992617470844929, 1]}
```

* - Insert a new PostComment

```sql
INSERT INTO post_comment (post_id, review, id)
VALUES (1, 'JDBC part review', 2)
```

UpdateTimestampsCache - Pre-invalidating space [post_comment], timestamp: 5992617717362689 UpdateTimestampsCache - [post_comment] last update timestamp: 5992617717362689, result set timestamp: 5992617470844929 StandardQueryCache - Cached query results were not up-to-date

```sql
SELECT pc.id AS id1_1_, pc.post_id AS post_id3_1_, pc.review AS review2_1_
FROM
post_comment pc ORDER BY pc.post_id DESC LIMIT 10
Region: org.hibernate.cache.internal.StandardQueryCache,
Statistics: SecondLevelCacheStatistics[hitCount=0,missCount=2,putCount=2],
Entries: {sql: ; named parameters: {}; max rows: 10; =[5992617470844929, 2, 1]}
```

UpdateTimestampsCache - Invalidating space [post_comment], timestamp: 5992617471619075

* -After transaction commit

```java
Region: org.hibernate.cache.internal.StandardQueryCache,
Statistics: SecondLevelCacheStatistics[hitCount=0,missCount=2,putCount=2],
Entries: {sql: ; named parameters: {}; max rows: 10; =[5992617470844929, 2, 1]}
```

* -Check query cache

StandardQueryCache - Checking query spaces are up-to-date: [post_comment] UpdateTimestampsCache - [post_comment] last update timestamp: 5992617471619075, result set timestamp: 5992617470844929 StandardQueryCache - Cached query results were not up-to-date

```java
Region: org.hibernate.cache.internal.StandardQueryCache,
Statistics: SecondLevelCacheStatistics[hitCount=0,missCount=3,putCount=3],
Entries: {sql: ; named parameters: {}; max rows: 10;=[5992617471627265, 2, 1]}
```

Hibernate second-level cache favors strong-consistency and the query cache is no different.

Whenever tablespaces are changing, the query cache invalidates all entries that are using the aforementioned tablespaces. The flow goes like this:

* Once the PostComment persist event is flushed, Hibernate pre-invalidates the post_comment tablespace timestamp (5992617717362689).
* When a tablespace is pre-invalidated, its timestamp is set to the cache region timeout timestamp value, which, by default, is set to 60 seconds.
* The query cache compares the cache entry timestamp with the tablespace pre-invalidation timeout timestamp value.
* Because the post_comment tablespace timestamp (5992617717362689) is greater than query result fetch timestamp (5992617470844929), the query cache ignores the cached entry value, and Hibernate executes the database query.
* The result set that is now fetched from the database goes to the cache without updating the result set timestamp (5992617470844929).
* When the current database transaction is committed, the post_comment tablespace is invalidated. Therefore, the tablespace timestamp is set to the transaction commit timestamp (5992617471619075).
* Even after the current database transaction is committed, the query cache timestamp is still seeing the old query result (5992617470844929).
* A new Session wants to execute the query, and because the query cache timestamp (5992617471619075) is still older than the post_comment tablespace timestamp, Hibernate executes the database query.
* Because this Session has not modified any tablespace, Hibernate updates the query cache with the current result set and the cache entry timestamp is set to the current Session timestamp (5992617471627265).

This flow guarantees strict consistency, and the query cache timestamp acts like a soft locking mechanism, preventing other concurrent transactions from reading stale entries.

15.5.7.2 Native SQL statement query cache invalidation

Hibernate can only parse JPQL and HQL statements, so it knows what tablespaces are required by a particular entity statement. For native statements, Hibernate cannot know if a tablespace is going to be affected directly or indirectly, and, by default, every native update statement is going to invalidate all query cache entries.

When executing the following example:

```java
assertEquals(1, getLatestPostComments(entityManager).size());
printCacheRegionStatistics(StandardQueryCache.class.getName());
```

entityManager.createNativeQuery(

```java
"UPDATE post SET title = '\"'||title||'\"' ")
.executeUpdate();
assertEquals(1, getLatestPostComments(entityManager).size());
printCacheRegionStatistics(StandardQueryCache.class.getName());
```

Hibernate generates the following output:

```java
Region: org.hibernate.cache.internal.StandardQueryCache,
Statistics: SecondLevelCacheStatistics[hitCount=0,missCount=1,putCount=1],
Entries: {sql: ; named parameters: {}; max rows: 10;=[5992657080082432, 1]}
```

UpdateTimestampsCache - Pre-invalidating space [post_comment], timestamp: 5992657328578560 UpdateTimestampsCache - Pre-invalidating space [post], timestamp: 5992657328578560

```sql
UPDATE post SET title = '"'||title||'"'
```

StandardQueryCache - Checking query spaces are up-to-date: [post_comment] UpdateTimestampsCache - [post_comment] last update timestamp: 5992657328578560, result set timestamp: 5992657080082432 StandardQueryCache - Cached query results were not up-to-date

```sql
SELECT pc.id AS id1_1_, pc.post_id AS post_id3_1_, pc.review AS review2_1_
FROM
post_comment pc
ORDER BY pc.post_id DESC
LIMIT 10
Region: org.hibernate.cache.internal.StandardQueryCache,
Statistics: SecondLevelCacheStatistics[hitCount=0,missCount=2,putCount=2],
Entries: {sql: ; named parameters: {}; max rows: 10;=[5992657080082432, 1]}
```

UpdateTimestampsCache - Invalidating space [post], timestamp: 5992668528799744 UpdateTimestampsCache - Invalidating space [post_comment], timestamp: 5992668528799744

The flow goes like this:

* Initially, the query result is stored in the cache.
* Upon executing the native DML statement, Hibernate pre-invalidates all tablespaces (e.g.

post and post_comment).

* When the data access layer executes the previously cached PostComment query, Hibernate checks the cache entry timestamp validity.
* Because the post_comment timestamp was set to the timeout value, Hibernate is prevented from using the cached result, so it executes the database query.
* When the transaction is committed, all tablespaces are invalidated, their associated timestamps being set to the current transaction commit timestamp.

To prevent Hibernate from invalidating all entries in the StandardQueryCache region, the native query must explicitly specify the tablespaces that are going to be affected:

entityManager.createNativeQuery(

```sql
"UPDATE post SET title = '\"'||title||'\"' ")
.unwrap(SQLQuery.class).addSynchronizedEntityClass(Post.class)
.executeUpdate();
```

This time, Hibernate generates the following output:

```java
Region: org.hibernate.cache.internal.StandardQueryCache,
Statistics: SecondLevelCacheStatistics[hitCount=0,missCount=1,putCount=1],
Entries: {sql: ; named parameters: {}; max rows: 10;=[5992666396459009, 1]}
```

UpdateTimestampsCache - Pre-invalidating space [post], timestamp: 5992666644185088

```sql
UPDATE post SET title = '"'||title||'"'
```

StandardQueryCache - Checking query spaces are up-to-date: [post_comment] UpdateTimestampsCache - [post_comment] last update timestamp: 5992666396422146, result set timestamp: 5992666396459009 StandardQueryCache - Returning cached query results

```java
Region: org.hibernate.cache.internal.StandardQueryCache,
Statistics: SecondLevelCacheStatistics[hitCount=1,missCount=1,putCount=1],
Entries: {sql:; named parameters: {}; max rows: 10;f2=[5992666396459009, 1]}
```

UpdateTimestampsCache - Invalidating space [post], timestamp: 5992666398470144

Because this time only the post tablespace is invalidated, and since the entity query uses the

post_comment table, the previously cached query result can be reused to satisfy the current entity query fetching requirements.

Query cache applicability

As explained in the Fetching chapter, DTO projections are suitable for executing read-only queries. For this purpose, the query cache is not a general purpose solution since it can only select entities.

However, fetching entities is appropriate for read-write transactions, and any entity modification can trigger a ripple effect in the StandardQueryCache second-level cache region. For this purpose, the query cache works better for immutable entities, or for entities that rarely change.
