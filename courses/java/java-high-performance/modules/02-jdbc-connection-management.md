# 2. JDBC Connection Management

The JDBC (Java Database Connectivity) API provides a common interface for communicating with a database server. All the networking logic and the database-specific communication protocol are hidden away behind the vendor-independent JDBC API. For this reason, all the JDBC interfaces must be implemented according to the database vendor-specific requirements. The java.sql.Driver is the main entry point for interacting with the JDBC API, defining the implementation version details and providing access to a database connection.

**Figure 2.1: JDBC plugin architecture**

JDBC defines four driver types:

* Type 1: It is only a bridge to an actual ODBC driver implementation.
* Type 2: It uses a database-specific native client implementation (e.g. Oracle Call Interface).
* Type 3: It delegates calls to an application server offering database connectivity support.
* Type 4: The JDBC driver implements the database communication protocol solely in Java.

Being easier to setup and debug, the Type 4 driver is usually the preferred alternative.

To communicate with a database server, a Java program must first obtain a java.sql.Connection. Although the java.sql.Driver is the actual database connection provider, it is more convenient to use the java.sql.DriverManager since it can also resolve the JDBC driver associated with the current database connection URL.

Previously, the application required to load the driver prior to establishing a connection but, since JDBC 4.0, the Service Provider Interfaces mechanism can automatically discover all the available drivers in the current application classpath.

## 2.1 DriverManager

The DriverManager defines the following methods:

```java
public static Connection getConnection(
String url, Properties info) throws SQLException;
public static Connection getConnection(
String url, String user, String password) throws SQLException;
public static Connection getConnection(
String url) throws SQLException;
```

Every time the getConnection() method is called, the DriverManager requests a new physical connection from the underlying Driver.

**Figure 2.2: DriverManager connection**

The first version of JDBC was launched in 1997, and it only supported the DriverManager utility for fetching database connections. Back then, Java was offering support for desktop applications which were often employing a two-tier architecture:

**Figure 2.3: Two-tier architecture**

In a two-tier architecture, the application is run by a single user, and each instance uses a dedicated database connection. The more users, the more database connections are required, and based on the underlying resources (hardware, operating system or licensing restrictions), each database server can offer a limited number of connections.

Oracle mainframe legacy

Oracle had gained its popularity in the era of mainframe computers when each client got a dedicated database connection.

Oracle assigns a distinct schema for each individual user, as opposed to other database systems where a schema is shared by multiple user accounts.

In PL/SQL, the Packaged public variables scope is bound to a session, instead of to the currently running transaction. The application developer must be extra cautious to unbind these variables properly since connections are often reused and old values might leak into newer transactions.

## 2.2 DataSource

In 1999, J2EE was launched along with JDBC 2.0 and an initial draft of JTA (Java Transaction API)[^1], marking the beginning of Enterprise Java. Enterprise applications use a three-tier architecture, where the middle tier acts as a bridge between user requests and various data sources (e.g. relational databases, messaging queues).

**Figure 2.4: Three-tier architecture**

Having an intermediate layer between the client and the database server has numerous advantages.

In a typical enterprise application, the user request throughput is greater than the available database connection capacity. As long as the connection acquisition time is tolerable (from the end-user perspective), the user request can wait for a database connection to become available. The middle layer acts as a database connection buffer that can mitigate user request traffic spikes by increasing request response time, without depleting database connections or discarding incoming traffic.

Because the intermediate layer manages database connections, the application server can also monitor connection usage and provide statistics to the operations team.

For this reason, instead of serving physical database connections, the application server

[^1]: <https://jcp.org/en/jsr/detail?id=907>

provides only logical connections (proxies or handles), so it can intercept and register how the client API interacts with the connection object.

A three-tier architecture can accommodate multiple data sources or messaging queue implementations. To span a single transaction over multiple sources of data, a distributed transaction manager becomes mandatory. In a JTA environment, the transaction manager must be aware of all logical connections the client has acquired as it has to commit or roll them back according to the global transaction outcome. By providing logical connections, the application server can decorate the database connection handles with JTA transaction semantics.

If the DriverManager is a physical connection factory, the javax.sql.DataSource interface is a logical connection provider:

```java
Connection getConnection() throws SQLException;
Connection getConnection(String username, String password) throws SQLException;
```

The simplest javax.sql.DataSource implementation could delegate connection acquisition requests to the underlying DriverManager, and the connection request workflow would look like this:

**Figure 2.5: DataSource without connection pooling**

1. The application data layer asks the DataSource for a database connection. 2. The DataSource uses the underlying driver to open a physical connection. 3. A physical connection is created, and a TCP socket is opened. 4. The DataSource under test does not wrap the physical connection, and it simply lends it to the application layer. 5. The application executes statements using the acquired database connection. 6. When the connection is no longer needed, the application closes the physical connection along with the underlying TCP socket.

Opening and closing database connections is a very expensive operation, so reusing them has the following advantages:

* It avoids both the database and the driver overhead for establishing a TCP connection.
* It prevents destroying the temporary memory buffers associated with each database connection.
* It reduces client-side JVM object garbage.

To visualize the cumulated overhead of establishing and closing database connections, the following test compares the total time it takes to open and close 1000 database connections of four different RDBMS against HikariCP[^2] (one of the fastest stand-alone connection pooling solutions in the Java ecosystem).

Table 2.1: Database connection establishing overhead vs. connection pooling

Metric Time (ms) DB_A Time (ms) DB_B Time (ms) DB_C Time (ms) DB_D Time (ms) HikariCP min 11.174 5.441 24.468 0.860 0.001230 max 129.400 26.110 74.634 74.313 1.014051 mean 13.829 6.477 28.910 1.590 0.003458 p[^99] 20.432 9.944 54.952 3.022 0.010263

When using a connection pooling solution, the connection acquisition time is between two and four orders of magnitude smaller. By reducing the connection acquisition interval, the overall transaction response time gets shorter too. All in all, in an enterprise application, reusing connections is a much better choice than always establishing them on a transaction basis.

Oracle XE connection handling limitation

While the Enterprise Edition does not entail any limitations, the Oracle 11g Express Edition throws the following exception when running very short transactions without using a connection pooling solution:

ORA-12516, TNS:listener could not find available handler with matching protocol stack

A connection pooling solution can prevent these intermittent connection establishment failures and reduce the connection acquisition time as well.

[^2]: <http://brettwooldridge.github.io/HikariCP/>

### 2.2.1 Why is pooling so much faster?

To understand why the connection pooling solution performs so much better, it is important to figure out the connection pooling mechanism:

**Figure 2.6: Connection acquisition request flow**

1. When a connection is being requested, the pool looks for unallocated connections. 2. If the pool finds a free one, it will be handled to the client. 3. If there is no free connection, the pool will try to grow to its maximum allowed size. 4. If the pool already reached its maximum size, it will retry several times before giving up with a connection acquisition failure exception. 5. When the client closes the logical connection, the connection is released and returns to the pool without closing the underlying physical connection.

Most connection pooling solutions expose a DataSource implementation that either wraps an actual database-specific DataSource or the underlying DriverManager utility.

The logical connection lifecycle looks like this:

**Figure 2.7: DataSource connection**

The connection pool does not return the physical connection to the client, but instead it offers a proxy or a handle. When a connection is in use, the pool changes its state to allocated to prevent two concurrent threads from using the same database connection. The proxy intercepts the connection close method call, and it notifies the pool to change the connection state to unallocated.

Apart from reducing connection acquisition time, the pooling mechanism can also limit the number of connections an application can use at once.

The connection pool acts as a bounded buffer for the incoming connection requests. If there is a traffic spike, the connection pool will level it, instead of saturating all the available database resources.

All these benefits come at a price since configuring the right pool size is not a trivial thing to do. Provisioning the connection pool requires understanding the application-specific database access patterns and also connection usage monitoring.

Whenever the number of incoming requests surpasses the available request handlers, there are basically two options to avoid system overloading:

* discarding the overflowing traffic (affecting availability)
* queuing requests and wait for busy resources to become available (increasing response time).

Discarding the surplus traffic is usually a last resort measure, so most connection pooling solutions first attempt to enqueue overflowing incoming requests.

By putting an upper bound on the connection request wait time, the queue is prevented from growing indefinitely and saturating application server resources.

For a given incoming request rate, the relation between the queue size and the average enqueuing time is given by one of the most fundamental laws of queuing theory.

## 2.3 Queuing theory capacity planning

Little’s Law[^3] is a general-purpose equation applicable to any queueing system being in a stable state (the arrival rate is not greater than the departure rate).

According to Little’s Law, the average time for a request to be serviced depends only on the long-term request arrival rate and the average number of requests in the system.

L = λ × W

* L - average number of requests in the system (including both the requests being serviced and the ones waiting in the queue)
* λ - long-term average arrival rate
* W - average time a request spends in a system.

Assuming that an application-level transaction uses the same database connection throughout its whole lifecycle, and the average transaction response time is 100 milliseconds:

W = 100 ms = 0.1 s

If the average connection acquisition rate is 50 requests per second:

λ = 50 connection requests

s

Then the average number of connection requests in the system will be:

L = λ × W = 50 × 0.1 = 5 connection requests

A pool size of 5 can accommodate the average incoming traffic without having to enqueue any connection request. If the pool size is 3, then, on average, 2 requests will be enqueued and waiting for a connection to become available.

Little’s Law operates with long-term averages, and that might not be suitable when taking into consideration intermittent traffic bursts. In a real-life scenario, the connection pool must adapt to short-term traffic spikes, and so it is important to consider the actual connection pool throughput.

[^3]: <http://en.wikipedia.org/wiki/Little%27s_law>

In queueing theory, throughput is represented by the departure rate (￿), and, for a connection pool, it represents the number of connections offered in a given unit of time:

µ = Ls

Ws = pool size connection lease time

The following exercise demonstrates how queuing theory can help provisioning a connection pool to support various incoming traffic spikes.

Reusing the previous example configuration, the connection pool defines the following variables:

* There are at most 5 in-service requests (Ls), meaning that the pool can offer at most 5 connections.
* The average service time (Ws) or the connection lease time is 100 milliseconds.

As expected, the connection pool can deliver up to 50 connections per second.

Ws = 50 connection requests

µ = Ls

s

When the arrival rate equals departure rate, the system is saturated with all connections being in use.

λ = µ = Ls

Ws

If the arrival rate outgrows the connection pool throughput, the overflowing requests must wait for connections to become available.

A one-second traffic burst of 150 requests is handled as follows:

* The first 50 requests can be served in the first second.
* The next 100 requests are first enqueued and processed in the following 2 seconds.

µ = Ls

Ws = 5

0.1 = Lq

Wq = 10

0.2

**Figure 2.8: Little’s Law queue**

For a constant throughput, the number of enqueued connection requests (Lq) is proportional to the connection acquisition time (Wq).

The total number of requests in any given spike is calculated as follows:

Lspike = λspike × Wspike

The total time required to process the spike is given by the following formula:

µ = λspike × Wspike

W = Lspike

λ

The number of enqueued connection requests and the time it takes to process them is expressed by the following equations:

Lq = Lspike −Ls

Wq = W −1

Assuming there is a traffic spike of 250 requests per second, lasting for 3 seconds.

λspike = 250 requests

s

Wspike = 3 s

The 750 requests spike takes 15 seconds to be fully processed.

Lspike = 250 requests

s × 3 s = 750 requests

W = 750 requests

s = 15 s

50 requests

The queue size grows to 700 entries, and it requires 14 seconds for all connection requests to be serviced.

Lq = Lspike −Ls = 700 requests

Wq = W −1 = 14 s

## 2.4 Practical database connection provisioning

Even if queuing theory provides insight into the connection pool behavior, the dynamics of enterprise systems are much more difficult to express with general-purpose equations, and metrics become fundamental for resource provisioning. By continuously monitoring the connection usage patterns, it is much easier to react and adjust the pool size when the initial configuration does not hold anymore.

Unfortunately, many connection pooling solutions only offer limited support for monitoring and failover strategies, and that was the main reason for building FlexyPool[^4]. Supporting the most common connection pooling frameworks, this open source project offers the following connection usage metrics:

Table 2.2: FlexyPool metrics

Name Description concurrent connection requests How many connections are being requested at once

concurrent connections How many connections are being used at once

maximum pool size If the target DataSource uses adaptive pool sizing, this metric will show how the pool size varies with time

connection acquisition time The time it takes to acquire a connection from the target

DataSource

overall connection acquisition time The total connection acquisition interval (including retries)

retry attempts The connection acquisition retry attempts

overflow pool size How much the pool size can grow over the maximum size until timing out the connection acquisition request

connection lease time The duration between the moment a connection is acquired and the time it gets released

While metrics are important for visualizing connection usage trends, in case of an unforeseen traffic spike, the connection acquisition time could reach the DataSource timeout threshold.

The failover mechanism applies various strategies to prevent timed-out connection requests from being discarded. While a batch processor can retry a failing request (although it increases transaction response time), in a web application, the user is much more sensitive to unavailability or long-running transactions.

[^4]: <https://github.com/vladmihalcea/flexy-pool>

FlexyPool comes with the following default failover strategies:

Table 2.3: FlexyPool failover strategies

Name Description Increment pool size on timeout The connection pool has a minimum size and, on demand, it can grow up to its maximum size.

This strategy increments the target connection pool maximum size on connection acquisition timeout.

The overflow is a buffer of extra connections allowing the pool to grow beyond its initial maximum size until it reaches the overflow size threshold

Retrying attempts This strategy is useful for those connection pools lacking a connection acquiring retry mechanism, and it simply reattempts to fetch a connection for a given number of tries

### 2.4.1 A real-life connection pool monitoring example

The following example demonstrates how FlexyPool failover strategies can determine the right connection pool size. The application under test is a batch processor using Bitronix transaction manager[^5] as the database connection pooling provider.

The batch processor is given a certain data load, and the pool size automatically grows upon detecting a connection acquisition timeout occurrence. The average and the maximum pool size are determined experimentally, without the need of any prior mathematical calculations.

Prior to running the load testing experiment, it is better to know the current application connection pool settings. According to the Bitronix connection pool documentation[^6] the default acquisitionTimeout (the maximum time a connection request waits before throwing a timeout exception) is 30 seconds.

A connection acquisition timeout threshold of one second is sufficient for the current experiment, allowing the application to react more quickly to a traffic spike and apply a compensating failover strategy.

The initial maxPoolSize is set to one connection, and, upon receiving a connection acquisition timeout, it grows until the maxOverflow threshold is reached.

The retryAttempts value is intentionally set to a reasonably large value because, for a batch processor, dropping a connection request is a much bigger problem than some occasional transaction response time spikes.

[^5]: <https://github.com/bitronix/btm>

[^6]: <https://github.com/bitronix/btm/wiki/JDBC-pools-configuration>

The experiment starts with the following initial connection pool settings:

Table 2.4: Initial connection pool settings

Name Value Description minPoolSize 0 The pool starts with an initial size of 0

maxPoolSize 1 The pool starts with a maximum size of 1

acquisitionTimeout 1 A connection request waits for 1s before giving up with a timeout exception

maxOverflow 4 The pool can grow up to 5 connections (initial maxPoolSize +

maxOverflow)

retryAttempts 30 If the final maxPoolSize is reached, and there is no connection available, a request will retry 30 times before giving up.

2.4.1.1 Concurrent connection request count metric

**Figure 2.9: Concurrent connection requests**

The more incoming concurrent connection requests, the higher the response time (for obtaining a pooled connection) gets. This graph shows the incoming request distribution, making it ideal for spotting traffic spikes.

The average value levels up all outliers, so it cannot reflect the application response to a given traffic spike.

When the recorded values fluctuate dramatically, the average and the maximum value alone offer only a limited view over the actual range of data, and that is why percentiles are preferred in application performance monitoring.

By offering the maximum value, relevant to only a percentage of the whole population, percentiles make outliers visible while capturing the immediate effect of a given traffic change.

2.4.1.2 Concurrent connection count metric

**Figure 2.10: Concurrent connections**

The average concurrent connection metric follows a gradual slope up to 1.5 connections. Unfortunately, this value is of little use for configuring the right pool size. On the other hand, the 99th percentile is much more informative, showing that 3 to 5 connections are sufficient. The maximum connections graph reconfirms that the pool size should be limited to 5 connections (in case the connection acquisition time is acceptable).

If the connection pool supports it, it is very important to set the idle connection timeout threshold. This way, the pool can release unused connections so the database can provide them to other clients as well.

2.4.1.3 Maximum pool size metric

**Figure 2.11: Maximum pool size**

According to the 99th percentile, the pool gets saturated soon after the job process starts.

2.4.1.4 Connection acquisition time metric

**Figure 2.12: Connection acquisition time**

The traffic spikes are captured by the maximum graph only. The timeout threshold is hit multiple times as the pool either grows its size or it retries the connection acquisition request.

2.4.1.5 Retry attempts metric

**Figure 2.13: Retry attempts**

When limiting the connection pool to 5 connections, there are only 3 retry attempts.

2.4.1.6 Overall connection acquisition time metric

**Figure 2.14: Overall connection acquisition time**

While the retry attempts graph only shows how the retry count increases with time, the actual effect of reattempting is visible in the overall connection acquisition time.

2.4.1.7 Connection lease time metric

**Figure 2.15: Connection lease time**

The 99th percentile indicates a rather stable connection lease time throughout the whole job execution. On the other hand, the maximum graph shows a long-running transaction lasting over 35 seconds.

Holding connections for long periods of time can increase the connection acquisition time, and fewer resources are available to other incoming clients.

Most often, connections are leased for the whole duration of a database transaction. Longrunning transactions might hold database locks, which, in turn, might lead to increasing the serial portion of the current execution context, therefore hindering parallelism.

Long-running transactions can be addressed by properly indexing slow queries or by splitting the application-level transaction over multiple database transactions like it is the case in many ETL (Extract, Transform, and Load) systems.

## 2.5 Programmatic Connection Pool Configuration

To configure connection pooling in Java, HikariCP is the recommended choice due to its performance and reliability. Below is an example of programmatically configuring a `HikariDataSource`, establishing a connection pool, and managing connection acquisition.

```java
import com.zaxxer.hikari.HikariConfig;
import com.zaxxer.hikari.HikariDataSource;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;

public class ConnectionPoolManager {

    private static HikariDataSource dataSource;

    static {
        HikariConfig config = new HikariConfig();
        
        // Database credentials & driver URL
        config.setJdbcUrl("jdbc:postgresql://localhost:5432/high_performance_db");
        config.setUsername("postgres");
        config.setPassword("admin");
        
        // Pool Size Settings
        config.setMinimumIdle(5);
        config.setMaximumPoolSize(10);
        
        // Timeouts and Thresholds (in milliseconds)
        config.setConnectionTimeout(1000); // Wait up to 1 second to acquire a connection
        config.setIdleTimeout(300000);      // Max idle time (5 minutes)
        config.setMaxLifetime(1800000);     // Max connection lifetime (30 minutes)
        config.setLeakDetectionThreshold(2000); // Warns if connection is held out of pool for > 2 seconds
        
        // Performance Tweaks for Postgres/MySQL
        config.addDataSourceProperty("cachePrepStmts", "true");
        config.addDataSourceProperty("prepStmtCacheSize", "250");
        config.addDataSourceProperty("prepStmtCacheSqlLimit", "2048");

        dataSource = new HikariDataSource(config);
    }

    public static Connection getConnection() throws SQLException {
        return dataSource.getConnection();
    }

    public static void shutdown() {
        if (dataSource != null) {
            dataSource.close();
        }
    }

    public static void main(String[] args) {
        // Example of acquiring a connection from the pool and executing a query
        try (Connection connection = getConnection();
             PreparedStatement statement = connection.prepareStatement("SELECT 1");
             ResultSet resultSet = statement.executeQuery()) {
            
            if (resultSet.next()) {
                System.out.println("Connection acquired successfully. Result: " + resultSet.getInt(1));
            }
        } catch (SQLException e) {
            System.err.println("Failed to acquire connection or execute query: " + e.getMessage());
        } finally {
            shutdown();
        }
    }
}
```

