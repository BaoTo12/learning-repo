# 1. Performance and Scaling

An enterprise application needs to store and retrieve data as fast as possible. In application performance management, the two most important metrics are response time and throughput.

The lower the response time, the more responsive an application becomes. Response time is, therefore, the measure of performance. Scaling is about maintaining low response times while increasing system load, so throughput is the measure of scalability.

## 1.1 Response time and throughput

Because this book is focused on high-performance data access, the boundaries of the system under test are located at the transaction manager level. The transaction response time is measured as the time it takes to complete a transaction, and so it encompasses the following time segments:

* the database connection acquisition time
* the time it takes to send all database statements over the wire
* the execution time for all incoming statements
* the time it takes for sending the result sets back to the database client
* the time the transaction is idle due to application-level computations prior to releasing the database connection.

T = tacq + treq + texec + tres + tidle

Throughput is defined as the rate of completing incoming load. In a database context, throughput can be calculated as the number of transactions executed within a given time interval.

X = transaction count

time

From this definition, we can conclude that by lowering the time it takes to execute a transaction, the system can accommodate more requests.

Testing against a single database connection, the measured throughput becomes the baseline for further concurrency-based improvements.

X (N) = X (1) × C (N)

Ideally, if the system were scaling linearly, adding more database connections would yield a proportional throughput increase. Due to contention on database resources and the cost of maintaining coherency across multiple concurrent database sessions, the relative throughput gain follows a curve instead of a straight line.

USL (Universal Scalability Law)[^1] can approximate the maximum relative throughput (system capacity) in relation to the number of load generators (database connections).

C (N) = N 1 + α (N −1) + βN (N −1)

* C - the relative throughput gain for the given concurrency level
* α - the contention coefficient (the serializable portion of the data processing routine)
* β - the coherency coefficient (the cost of maintaining consistency across all concurrent database sessions).

When the coherency coefficient is zero, USL overlaps with Amdahl’s Law[^2]. The contention has the effect of leveling up scalability. On the other hand, coherency is responsible for the inflection point in the scalability curve, and its effect becomes more significant as the number of concurrent sessions increases.

The following graph depicts the relative throughput gain when the USL coefficients (α, β) are set to the following values (0.1, 0.0001). The x-axis represents the number of concurrent sessions (N), and the y-axis shows the relative capacity gain (C).

**Figure 1.1: Universal Scalability Law**

The number of load generators (database connections), for which the system hits its maximum capacity, depends on the USL coefficients solely.

[^1]: <http://www.perfdynamics.com/Manifesto/USLscalability.html>

[^2]: <http://en.wikipedia.org/wiki/Amdahl%27s_law>

√

(1 −α)

Nmax =

β

The resulting capacity gain is relative to the minimum throughput, so the absolute system capacity is obtained as follows:

Xmax = X (1) × C (Nmax)

## 1.2 Database connections boundaries

Every connection requires a TCP socket from the client (application) to the server (database).

The total number of connections offered by a database server depends on the underlying hardware resources, and finding how many connections a server can handle is possible through measurements and proven scalability models.

SQL Server 2016a and MySQL 5.7b use thread-based connection handling.

PostgreSQL 9.5c uses one operating system process for each individual connection.

On Windows systems, Oracle uses threads, while on Linux, it uses process-based connections. Oracle 12cd comes with a thread-based connection model for Linux systems too.

ahttps://msdn.microsoft.com/en-us/library/ms[^190219].aspx bhttps://dev.mysql.com/doc/refman/5.7/en/connection-threads.html chttp://www.postgresql.org/docs/current/static/connect-estab.html dhttp://docs.oracle.com/database/121/CNCPT/process.htm

A look into database system internals reveals the tight dependency on CPU, Memory, and Disk resources. Because I/O operations are costly, the database uses a buffer pool to map into memory the underlying data and index pages. Changes are first applied in memory and flushed to disk in batches to achieve better write performance.

Even if all indexes are entirely cached in memory, disk access might still occur if the requested data blocks are not cached into the memory buffer pool. Not just queries may generate I/O traffic, but the transaction and the redo logs require flushing in-memory data structures periodically so that durability is not compromised.

To provide data integrity, any relational database system must use exclusive locks to protect data blocks (rows and indexes) from being updated concurrently. This is true even if the database system uses MVCC (Multi-Version Concurrency Control) because otherwise atomicity would be compromised. This topic is going to be discussed in greater detail in the Transactions chapter.

This means that high-throughput database applications experience contention on CPU, Memory, Disk, and Locks. When all the database server resources are in use, adding more workload only increases contention, therefore lowering throughput.

Resources might get saturated due to improper system configuration, so the first step to improving a system throughput is to tune it according to the current data access patterns.

Lowering response time not only makes the application more responsive, but it can also increase throughput.

However, response time alone is not sufficient in a highly concurrent environment. To maintain a fixed upper bound response time, the system capacity must increase relative to the incoming request throughput. Adding more resources can improve scalability up to a certain point, beyond which the capacity gain starts dropping.

At the Velocity conferencea, both Google Search and Microsoft Bing teams have concluded that higher response times can escalate and even impact the business metrics.

Capacity planning is a feedback-driven mechanism, and it requires constant application monitoring, and so, any optimization must be reinforced by application performance metrics.

ahttp://radar.oreilly.com/2009/06/bing-and-google-agree-slow-pag.html

## 1.3 Scaling up and scaling out

Scaling is the effect of increasing capacity by adding more resources. Scaling vertically (scaling up) means adding resources to a single machine. Increasing the number of available machines is called horizontal scaling (scaling out).

Traditionally, adding more hardware resources to a database server has been the preferred way of increasing database capacity. Relational databases have emerged in the late seventies, and, for two and a half decades, the database vendors took advantage of the hardware advancements following the trends in Moore’s Law.

Distributed systems are much more complex to manage than centralized ones, and that is why horizontal scaling is more challenging than scaling vertically. On the other hand, for the same price of a dedicated high-performance server, one could buy multiple commodity machines whose sum of available resources (CPU, Memory, Disk Storage) is greater than of the single dedicated server. When deciding which scaling method is better suited for a given enterprise system, one must take into account both the price (hardware and licenses) and the inherent developing and operational costs.

Being built on top of many open source projects (e.g. PHP, MySQL), Facebook[^3] uses a horizontal scaling architecture to accommodate its massive amounts of traffic.

StackOverflow[^4] is the best example of a vertical scaling architecture. In one of his blog posts[^5], Jeff Atwood explained that the price of Windows and SQL Server licenses was one of the reasons for not choosing a horizontal scaling approach.

No matter how powerful it might be, one dedicated server is still a single point of failure, and throughput drops to zero if the system is no longer available. For this reason, database replication is not optional in many enterprise systems.

### 1.3.1 Master-Slave replication

For enterprise systems where the read/write ratio is high, a Master-Slave replication scheme is suitable for increasing availability.

**Figure 1.2: Master-Slave replication**

The Master is the system of record and the only node accepting writes. All changes recorded by the Master node are replayed onto Slaves as well. A binary replication uses the Master node WAL (Write Ahead Log) while a statement-based replication replays on the Slave machines the exact statements executed on Master.

Asynchronous replication is very common, especially when there are more Slave nodes to update.

[^3]: <https://www.facebook.com/note.php?note_id=409881258919>

[^4]: <http://stackexchange.com/performance>

[^5]: <http://blog.codinghorror.com/scaling-up-vs-scaling-out-hidden-costs/>

The Slave nodes are eventual consistent as they might lag behind the Master. In case the Master node crashes, a cluster-wide voting process must elect the new Master (usually the node with the most recent update record) from the list of all available Slaves.

The asynchronous replication topology is also referred as warm standby because the election process does not happen instantaneously.

Most database systems allow one synchronous Slave node, at the price of increasing transaction response time (the Master has to block waiting for the synchronous Slave node to acknowledge the update). In case of Master node failure, the automatic failover mechanism can promote the synchronous Slave node to become the new Master.

Having one synchronous Slave allows the system to ensure data consistency in case of Master node failures since the synchronous Slave is an exact copy of the Master. The synchronous Master-Slave replication is also called a hot standby topology because the synchronous Slave is readily available for replacing the Master node.

When only asynchronous Slave nodes are available, the newly elected Slave node might lag behind the failed Master, in which case consistency and durability are traded for lower latencies and higher throughput.

Aside from eliminating the single point of failure, database replication can also increase transaction throughput without affecting response time. In a Master-Slave topology, the Slave nodes can accept read-only transactions, therefore routing read traffic away from the Master node.

The Slave nodes increase the available read-only connections and reduce Master node resource contention, which, in turn, can also lower read-write transaction response time. If the Master node can no longer keep up with the ever-increasing read-write traffic, a MultiMaster replication might be a better alternative.

### 1.3.2 Multi-Master replication

In a Multi-Master replication scheme, all nodes are equal and can accept both read-only and read-write transactions. Splitting the load among multiple nodes can only increase transaction throughput and reduce response time as well.

However, because distributed systems are all about trade-offs, ensuring data consistency is challenging in a Multi-Master replication scheme because there is no longer a single source of truth. The same data can be modified concurrently on separate nodes, so there is a possibility of conflicting updates. The replication scheme can either avoid conflicts or it can detect them and apply an automatic conflict resolution algorithm.

To avoid conflicts, the two-phase commit protocol can be used to enlist all participating nodes in one distributed transaction. This design allows all nodes to be in sync at all time, at the cost of increasing transaction response time (by slowing down write operations).

**Figure 1.3: Multi-Master replication**

If nodes are separated by a WAN (Wide Area Network), synchronization latencies may increase dramatically. If one node is no longer reachable, the synchronization will fail, and the transaction will roll back on all Masters.

Although avoiding conflicts is better from a data consistency perspective, synchronous replication might incur high transaction response times. On the other hand, at the price of having to resolve update conflicts, asynchronous replication can provide better throughput,

The asynchronous Multi-Master replication requires a conflict detection and an automatic conflict resolution algorithm. When a conflict is detected, the automatic resolution tries to merge the two conflicting branches, and, in case it fails, manual intervention is required.

### 1.3.3 Sharding

When data size grows beyond the overall capacity of a replicated multi-node environment, splitting data becomes unavoidable. Sharding means distributing data across multiple nodes, so each instance contains only a subset of the overall data.

Traditionally, relational databases have offered horizontal partitioning to distribute data across multiple tables within the same database server. As opposed to horizontal partitioning, sharding requires a distributed system topology so that data is spread across multiple machines.

Each shard must be self-contained because a user transaction can only use data from within a single shard. Joining across shards is usually prohibited because the cost of distributed locking and the networking overhead would lead to long transaction response times.

By reducing data size per node, indexes also require less space, and they can better fit into main memory. With less data to query, the transaction response time can also get shorter too.

The typical sharding topology includes, at least, two separate data centers.

**Figure 1.4: Sharding**

Each data center can serve a dedicated geographical region, so the load is balanced across geographical areas. Not all tables need to be partitioned across shards, smaller size ones being duplicated on each partition. To keep the shards in sync, an asynchronous replication mechanism can be employed.

In the previous diagram, the country table is mirrored from one data center to the other, and partitioning happens on the user table only. To eliminate the need for inter-shard data processing, each user along with all user-related data are contained in one data center only.

In the quest for increasing system capacity, sharding is usually a last resort strategy, employed after exhausting all other available options, such as:

* optimizing the data layer to deliver lower transaction response times
* scaling each replicated node to a cost-effective configuration
* adding more replicated nodes until synchronization latencies start dropping below an acceptable threshold.

MySQL cluster auto-sharding

MySQL Clustera offers automatic sharding, so data is evenly distributed (using a primary key hashing function) over multiple commodity hardware machines. Every node accepts both read and write transactions and, just like Multi-Master replication, conflicts are automatically discovered and resolved.

**Figure 1.5: Auto-sharding**

The auto-sharding topology is similar to the Multi-Master replication architecture as it can increase throughput by distributing incoming load to multiple machines. While in a MultiMaster replicated environment every node stores the whole database, the auto-sharding cluster distributes data so that each shard is only a subset of the whole database.

Because the cluster takes care of distributing data, the application does not have to provide a data shard routing layer, and SQL joins are possible even across different shards. MySQL Cluster 7.3 uses the NDB storage engine, and so it lacks some features provided by InnoDBb

like multiple transaction isolation levels or MVCC (Multi-Version Concurrency Control).

ahttps://www.mysql.com/products/cluster/scalability.html bhttp://dev.mysql.com/doc/mysql-cluster-excerpt/5.6/en/mysql-cluster-ndb-innodb-engines.html

Little’s Law

In any given system, the ultimate relationship between response time and throughput is given by Little’s Lawa and, high values of incoming throughput can cause an exponential growth in response time due to resource saturation.

Nevertheless, when taking a single database connection, by lowering the average transaction response time, more transactions can be accommodated in a given time unit. For this reason, the following chapters explain in greater detail what is needed to be done in order to reduce transaction response time as much as possible.

ahttps://people.cs.umass.edu/~emery/classes/cmpsci691st/readings/OS/Littles-Law-50-Years-Later.pdf
