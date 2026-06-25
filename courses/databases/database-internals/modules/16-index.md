### Index

##### A

ABA problem. Linearization point

abort, Transaction Processing and Recovery

acceptors, Paxos Algorithm

access methods, DBMS Architecture

access patterns, Distinctions and Optimizations

accuracy, Failure Detection

ACID properties, Transaction Processing and Recovery, Serializability, Isolation Levels, Use CAP Carefully

acknowledgments, Message acknowledgments

admission queue, LFU

after-images, Operation Versus Data Log

anti-entropy and dissemination

bitmap version vectors, Bitmap Version Vectors

digest reads, Digest Reads

gossip dissemination, Gossip Dissemination-Partial Views

hinted handoff, Hinted Handoff

Merkle trees, Merkle Trees

overview of, Anti-Entropy and Dissemination, Summary

read repair, Read Repair

Apache Cassandra

conflict resolution in, Vector clocks

hinted writes in, Hinted Handoff

range tombstones in, Updates and Deletes

time window compaction in, Size-tiered compaction

Apache Kudu, Column-Oriented Data Layout

Apache ORC, Column-Oriented Data Layout

Apache Parquet, Column-Oriented Data Layout

Apache Zookeeper, Zookeeper Atomic Broadcast (ZAB)

append-only structures, Buffering, Immutability, and Ordering, Log-

Structured Storage, LSM Trees

arbitrary faults, Arbitrary Faults

ARIES, ARIES

arrays, Solid State Drives

asynchronous communication, Two Generals' Problem, Read Repair

asynchronous systems, System Synchrony, Timeout-Free Failure

Detector

at-least-once delivery, Exactly-once delivery

at-most-once delivery, Exactly-once delivery

atomic broadcast, Atomic Broadcast-Zookeeper Atomic Broadcast (ZAB)

atomic commitment, Making Operations Appear Atomic

atomic registers, Shared Memory

atomicity, Transaction Processing and Recovery, Use CAP Carefully, Linearization point

auto-sharding, Database Partitioning

availability, Achieving Availability

availability lists, Managing Variable-Size Data

##### B

B-Trees, basics of

B-Tree hierarchy, B-Tree Hierarchy

B-Tree lookup algorithm, B-Tree Lookup Algorithm

B-Tree lookup complexity, B-Tree Lookup Complexity

B-Tree node merges, B-Tree Node Merges

B-Tree node splits, B-Tree Node Splits

counting keys, Counting Keys

point and range queries using, Ubiquitous B-Trees

separator keys in, Separator Keys

similarities between BSTs and B-Trees, Ubiquitous B-Trees

B-Trees, implementing

binary search, Binary Search-Binary Search with Indirection Pointers

compression, Compression-Compression

page headers, Page Header-Overflow Pages

rebalancing, Rebalancing

right-only appends, Right-Only Appends-Bulk Loading

vacuum and maintenance, Vacuum and Maintenance-Page

Defragmentation

B-Trees, variants of

abstracting node updates, Abstracting Node Updates

Bw-Trees, Bw-Trees-Consolidation and Garbage Collection, Part I

Conclusion

cache-oblivious B-Trees, Cache-Oblivious B-Trees

copy-on-write B-Trees, Copy-on-Write, Part I Conclusion

FD-Trees, FD-Trees-Logarithmic Runs, Part I Conclusion

lazy B-Trees, Lazy B-Trees-Lazy-Adaptive Tree

B+-Trees, B-Tree Hierarchy

backoff strategy, Cascading Failures

backpressure, Processing

backup copies, Durability in Memory-Based Stores

backward links, Sibling Links

backward-oriented validation, Optimistic Concurrency Control

balanced search trees, Tree Balancing

balancing operations, B-Tree Hierarchy

bandwidth, Fallacies of Distributed Computing

base nodes, Update Chains

before-images, Operation Versus Data Log

benchmarking tools, Storage Engines

BerkeleyDB, Storage Engines

best effort availability and consistency, Infamous CAP

best effort broadcast, Broadcast

best fit strategy, Managing Variable-Size Data

big-endian byte order, Primitive Types

BigTable, Wide Column Stores, Distributed Transactions with

Percolator

binary encoding

Booleans, enums, and flags, Bit-Packed Data: Booleans, Enums, and

Flags

page layouts, Binary Encoding

primitive types, Primitive Types

strings and variable-size data, Strings and Variable-Size Data

versioning, Versioning

binary large objects (BLOBs), Slotted Pages

binary search algorithm, Binary Search

binary search trees (BSTs)

balancing, Tree Balancing

similarities to B-Trees, Ubiquitous B-Trees

structure of, Binary Search Trees

trees for disk-based storage, Trees for Disk-Based Storage

bit rot, Cascading Failures

Bitcask, Bitcask, Part I Conclusion

bitmap version vectors, Bitmap Version Vectors

bitmasks, Bit-Packed Data: Booleans, Enums, and Flags

Blink-Trees, Node High Keys, Blink-Trees

block device, Solid State Drives

block padding, Compression

blocking atomic commitment, Coordinator Failures in 2PC

blocking operations, Read Repair

blocks, Buffering, Immutability, and Ordering, Solid State Drives,

Page Structure

Bloom filters, Bloom Filters

Booleans, Bit-Packed Data: Booleans, Enums, and Flags

branches, Separator Keys

breadcrumbs, Breadcrumbs

bridges, Fractional Cascading

broadcasting, Anti-Entropy and Dissemination, Broadcast

buffer management

cache eviction, Cache Eviction

caching semantics, Caching Semantics

circular buffers, Locking Pages in Cache, CLOCK

database-specific, Buffer Management

locking pages in cache, Locking Pages in Cache

overview of, Buffer Management

page replacement, Page Replacement-LFU

buffer manager, DBMS Architecture

buffer pools, Buffer Management

buffering, Buffering, Immutability, and Ordering, LSM Trees, Part I

Conclusion (see also buffer management)

bulk-loading, Bulk Loading

bully algorithm, Bully Algorithm

busy-wait algorithms, Readers-writer lock

Bw-Trees (Buzzword-Trees)

buffering, immutability, and ordering, Part I Conclusion

compare-and-swap, Taming Concurrency with Compare-and-Swap

consolidation and garbage collection, Consolidation and Garbage Collection

overview of, Bw-Trees

structural modification operations, Structural Modification Operations

update chains, Update Chains

byte-order, Primitive Types

Byzantine consensus, Byzantine Consensus-Recovery and Checkpointing

Byzantine faults, Arbitrary Faults

##### C

C-Store, Column-Versus Row-Oriented DBMS

cache-aware structures, Cache-Oblivious B-Trees

cache-oblivious B-Trees, Cache-Oblivious B-Trees

caching, Durability in Memory-Based Stores, Disk-Based Structures, Buffer Management-Locking Pages in Cache

Calvin, Distributed Transactions with Calvin

candidate/ordinary optimization, Candidate/Ordinary Optimization

candidates, CLOCK

CAP (consistency, availability, and partition tolerance), Infamous

CAP-Harvest and Yield

cascading failures, Cascading Failures

causal consistency, Causal Consistency-Vector clocks

cell offsets, Cell Layout

cells

cell layout, Cell Layout

organizing into pages, Combining Cells into Slotted Pages

checkpointing, Durability in Memory-Based Stores, Cache Eviction,

Log Semantics, Recovery and Checkpointing

checksumming, Checksumming

child offsets, Counting Keys

churn, Partial Views

circuit breakers, Cascading Failures

circular buffers, Locking Pages in Cache, CLOCK

clean pages, WiredTiger

ClickHouse, Column-Oriented Data Layout

client centric consistency model, Session Models

client/server model, DBMS Architecture

CLOCK algorithm, CLOCK

clocks, Distributed Systems, Clocks and Time, Vector clocks

cluster-wide metadata, Anti-Entropy and Dissemination

clustered files, Index Files

clustered indexes, Introduction and Overview, Index Files

CockroachDB, Distributed Transactions with Spanner

code examples, obtaining and using, Preface

cohorts, Two-Phase Commit

cold storage, Introduction and Overview

collisions, Fast Paxos

column families, Wide Column Stores

column keys, Wide Column Stores

column stores, Introduction and Overview

column-oriented data layout, Column- Versus Row-Oriented DBMS-

Distinctions and Optimizations

columns, Column- Versus Row-Oriented DBMS

comments and questions, How to Contact Us

commit

atomic commitment, Making Operations Appear Atomic

three-phase commits, Three-Phase Commit-Coordinator Failures in

3PC

two-phase commits (2PCs), Two-Phase Commit-Coordinator

Failures in 2PC

commit log, Recovery

commit operation, Transaction Processing and Recovery

committed version, Multiversion Concurrency Control

common ground, Failure Scenarios

common knowledge, Exactly-once delivery

compaction

defined, Page Defragmentation

leveled compaction, Leveled compaction

process of, Multicomponent LSM Trees

size-tiered compaction, Size-tiered compaction

time window compaction, Size-tiered compaction

tombstones and, Maintenance in LSM Trees

compare-and-swap instructions, Readers-writer lock, Taming

Concurrency with Compare-and-Swap, Linearization point

compensation log records (CLR), Log Semantics

complete schedules, Serializability

completeness, Failure Detection

completion events, Shared Memory

complexity, Local and Remote Execution

compression, Compression, Compression

concurrency control

categories of, Concurrency Control

concurrency in LSM trees, Concurrency in LSM Trees

in distributed systems, Concurrent Execution-Shared State in a

Distributed System

interference between operations, Latches

isolation levels, Isolation Levels

lock-based concurrency control, Lock-Based Concurrency Control-

Blink-Trees

multiversion concurrency control (MVCC), Multiversion

Concurrency Control

optimistic concurrency control (OCC), Optimistic Concurrency

Control

pessimistic (conservative) concurrency control (PCC), Pessimistic

Concurrency Control

transaction isolation. Transaction Isolation

concurrent computing, Concurrent Execution

concurrent operations, Shared Memory

conflict resolution, Reconciliation, State Consistency, Vector clocks

Conflict-Free Replicated Data Types (CRDTs), Strong Eventual

Consistency and CRDTs

consensus

Byzantine consensus, Byzantine Consensus-Recovery and

Checkpointing

linearizability using, Cost of linearizability

overview of, Consensus

Paxos, Paxos-Generalized Paxos algorithm

Raft, Raft-Failure Scenarios

conservative 2PL, Deadlocks

conservative concurrency control, Concurrency Control

consistency

consistency guarantees, Transaction Processing and Recovery

convergent consistency, Gossip Mechanics

defined, Use CAP Carefully

eventual consistency, Eventual Consistency

external consistency, Distributed Transactions with Spanner

linearizable consistency, Infamous CAP

operation consistency, Consistency Models

overview of, Replication and Consistency

state consistency, State Consistency

tunable consistency, Tunable Consistency

consistency models

causal consistency, Causal Consistency-Vector clocks

client centric consistency model, Session Models

linearizability, Linearizability-Cost of linearizability

monotonic reads/writes models, Session Models

overview of, Consistency Models

read-own-writes consistency model, Session Models

role of, Concurrent Execution. Replication and Consistency

sequential consistency, Sequential Consistency

strict consistency, Strict Consistency

writes-follow-reads model, Session Models

consistent hashing, Consistent Hashing

convergent consistency, Gossip Mechanics

cooperation, Distributed Systems

cooperative broadcasts, Anti-Entropy and Dissemination

coordination, Distributed Systems

coordination avoidance, Coordination Avoidance

coordinators, Leader Election, Two-Phase Commit

copy-on-write, Buffering, Immutability, and Ordering

copy-on-write B-Trees, Copy-on-Write, Part I Conclusion

correct schedules, Serializability

CP systems, Infamous CAP

crash faults, Crash Faults

crash-recovery, Crash Faults

cursors, Merge-Iteration

cyclic redundancy checks (CRCs), Checksumming

##### D

data

bulk-loading, Bulk Loading

deserialization of, Primitive Types

compressing, Compression, Compression

disk-based structures for, Disk-Based Structures-On-Disk

Structures

file formats, File Formats-Summary

preventing loss of, Durability in Memory-Based Stores,

Checksumming

serialization of, Primitive Types

variable-size data, Strings and Variable-Size Data, Cell Layout,

Managing Variable-Size Data

data entries. Data Files

data files, Data Files and Index Files-Data Files

data logs, Operation Versus Data Log

data records

direct versus primary key references, Primary Index as an Indirection

ordering of, Buffering, Immutability, and Ordering

storing and retrieving, Data Files and Index Files

data replication, Replication and Consistency

database management system (DBMS), Storage Engines

(see also database systems)

database partitioning, Database Partitioning-Consistent Hashing

database systems

architecture of, Storage Engines, DBMS Architecture-DBMS Architecture

buffering, immutability, and ordering in, Buffering, Immutability, and Ordering, Part I Conclusion

column- versus row-oriented, Column- Versus Row-Oriented DBMS-Wide Column Stores

comparing, Storage Engines-Storage Engines

data files and index files, Data Files and Index Files-Primary Index as an Indirection

data storage and distribution, Preface

memory- versus disk-based, Memory- Versus Disk-Based DBMS-Durability in Memory-Based Stores

performance and scalability of, Part II Conclusion

prerequisites to learning about, Preface

purpose of, Storage Engines

terminology used in, Introduction and Overview

topics covered, Preface

dead processes, Failure Detection

deadlocks, Deadlocks

decision state, FLP Impossibility

decoupling, Processing

deduplication, Problem with retransmits

defragmentation, Page Defragmentation

delete entry, Updates and Deletes

(see also tombstones)

deletion markers, Data Files and Index Files, Fragmentation Caused

by Updates and Deletes

(see also tombstones)

delta nodes, Update Chains

density, LSM Trees

deserialization, Primitive Types

dies, Solid State Drives

digest reads, Digest Reads

direct coordination, Bitmap Version Vectors

dirty pages, Buffer Management, Cache Eviction, Log Semantics

dirty reads, Read and Write Anomalies

dirty writes, Read and Write Anomalies

disk-based data structures

hard disk drives, Hard Disk Drives

on-disk structures, On-Disk Structures

solid state drives (SSDs), Solid State Drives, Log Stacking, Open-Channel SSDs

uses for, Disk-Based Structures

disk-based DBMS

durability in, Durability in Memory-Based Stores

versus memory-based, Memory- Versus Disk-Based DBMS

trees for disk-based storage, Trees for Disk-Based Storage

disk-resident tables, LSM Tree Structure

dissemination, Distributed Systems, Gossip Dissemination-Partial

Views

distinguished learners, Paxos Algorithm

distinguished proposers, Multi-Paxos

distributed algorithms, Distributed Systems

distributed systems

abstractions, Distributed Systems Abstractions

benefits of, Distributed Systems

challenges of, Distributed Systems

concurrent execution, Concurrent Execution-Shared State in a

Distributed System

failure models, Failure Models-Handling Failures

fallacies of, Fallacies of Distributed Computing-Cascading Failures

FLP Impossibility Problem, FLP Impossibility

versus single-node systems, Introduction and Overview

system synchrony, System Synchrony

terminology used in, Distributed Systems

Two Generals' Problem, Two Generals' Problem

distributed transactions

coordination avoidance, Coordination Avoidance

making operations appear atomic, Making Operations Appear

Atomic

overview of, Distributed Transactions

three-phase commits, Three-Phase Commit-Coordinator Failures in 3PC

two-phase commits (2PCs), Two-Phase Commit-Coordinator Failures in 2PC

with Calvin. Distributed Transactions with Calvin

with Percolator, Distributed Transactions with Percolator-Distributed Transactions with Percolator

with Spanner, Distributed Transactions with Spanner

divider cells, Separator Keys

(see also separator keys)

dormant certificates, Updates and Deletes

(see also tombstones)

dots, Bitmap Version Vectors

dotted causal containers, Bitmap Version Vectors

durability, Durability in Memory-Based Stores, Transaction Processing and Recovery, Cache Eviction

##### E

efficiency, Failure Detection

Egalitarian Paxos (EPaxos), Egalitarian Paxos

election timeouts, Raft

entropy, Anti-Entropy and Dissemination

enumerated types (enums), Bit-Packed Data: Booleans, Enums, and

Flags

epoch-based reclamation, Consolidation and Garbage Collection

epochs, Distributed Transactions with Calvin, Zookeeper Atomic Broadcast (ZAB)

erase blocks, Solid State Drives

eventual consistency, Preface, Eventual Consistency

eviction, Buffer Management, Cache Eviction, Locking Pages in Cache

eviction policy, Page Replacement

exactly-once delivery, Exactly-once delivery

execution engine, DBMS Architecture

execution plan, DBMS Architecture

expanding phase, Lock-Based Concurrency Control

exponent, Primitive Types

external consistency, Distributed Transactions with Spanner

##### F

fadvise flag, Buffer Management

failed processes, Failure Detection, Shared Memory

failure detection

challenges of, Failure Detection

failure sites, Failure Detection

gossip and, Gossip and Failure Detection

group failures, Reversing Failure Detection Problem Statement

heartbeats and pings, Heartbeats and Pings-Outsourced Heartbeats

overview of, Failure Detection

reversing problem statements, Reversing Failure Detection Problem Statement

terminology used in, Failure Detection

failure detectors

close enough failure detection, Phi-Accural Failure Detector

purpose of, Need to Handle Failures, Failure Detection

timeout-free, Timeout-Free Failure Detector

failure models

arbitrary faults, Arbitrary Faults

crash faults, Crash Faults

failure handling, Handling Failures

omission faults, Omission Faults

purpose of, Failure Models

role of, Shared State in a Distributed System

failure scenarios, Failure Scenarios, Failure Scenarios

fair path, Timeout-Free Failure Detector

fair-loss links, Fair-loss link

false-negatives, Failure Detection

false-positives, Failure Detection

fanout, Trees for Disk-Based Storage, On-Disk Structures, B-Tree Hierarchy, Gossip Mechanics

Fast Paxos, Fast Paxos

fastpath, Right-Only Appends

fault tolerance, Shared State in a Distributed System, Replication and Consistency

faulty processes, Failure Detection

FD-Trees (Flash Disk Trees)

fractional cascading, Fractional Cascading

logarithmic runs, Logarithmic Runs

overview of, FD-Trees

fences, Fractional Cascading

fields, Column- Versus Row-Oriented DBMS

file formats

binary encoding, Binary Encoding-Bit-Packed Data: Booleans,

Enums, and Flags

cell layout, Cell Layout

checksumming, Checksumming

general principles, General Principles

on-disk structures, File Formats-Motivation

page structure, Page Structure

slotted pages, Slotted Pages

variable-size data, Managing Variable-Size Data

versioning, Versioning

ilesystem logging, Filesystem Logging

filter entries, Logarithmic Runs

(see also tombstones)

finite duplication, Fair-loss link

first committer wins, Distributed Transactions with Percolator

first fit strategy, Managing Variable-Size Data

first in, first out (FIFO) strategy, FIFO and LRU, Message order

fit strategy, Managing Variable-Size Data

flags, Bit-Packed Data: Booleans, Enums, and Flags

flash drives, Hard Disk Drives

Flash Translation Layer (FTL), Solid State Drives, Flash Translation

Layer

Flexible Paxos, Flexible Paxos

floating-point numbers, Primitive Types

FLP Impossibility Problem, FLP Impossibility

flush finalization, Concurrency in LSM Trees

flushing, Buffer Management, Cache Eviction, Log Semantics, LSM Tree Structure

followers, Zookeeper Atomic Broadcast (ZAB)

force operation, Log Semantics

force/no-force policy, Steal and Force Policies

forward links, Sibling Links

forward-oriented validation, Optimistic Concurrency Control

fraction, Primitive Types

fractional cascading, Fractional Cascading

fractured reads, Coordination Avoidance

fragmentation, Fragmentation Caused by Updates and Deletes,

Filesystem Logging

free page list, Page Defragmentation

freeblocks, Managing Variable-Size Data

freelist, Page Defragmentation

fsync(), Recovery

FUSE (failure notification service), Reversing Failure Detection

Problem Statement

fuzzy checkpoints, Log Semantics

fuzzy reads, Read and Write Anomalies

garbage collection, Solid State Drives, Vacuum and Maintenance

ghost records, Fragmentation Caused by Updates and Deletes

gossip, Gossip and Failure Detection

gossip dissemination

gossip mechanics, Gossip Mechanics

gossip protocols, Gossip Dissemination

hybrid gossip, Hybrid Gossip

overlay networks, Overlay Networks

partial views, Partial Views

group failures, Reversing Failure Detection Problem Statement

grow-only sets (G-Sets), Strong Eventual Consistency and CRDTs

growing phase, Lock-Based Concurrency Control

H

half-split nodes, Blink-Trees, Structural Modification Operations

HaloDB, Storage Engines

hard disk drives (HDDs), Hard Disk Drives

hardware failures, Cascading Failures

harvest and yield, Harvest and Yield

hash collision, Bloom Filters, Digest Reads

hash-organized tables (hashed files), Data Files

hazard pointers, Skiplist

HBase, Wide Column Stores

head elements, Logarithmic Runs

head trees, FD-Trees

headers, General Principles

heap-organized tables (heap files), Data Files

heartbeat counters, Gossip and Failure Detection

heartbeat protocols, Need to Handle Failures, Failure Detection-

Outsourced Heartbeats

high availability, Use CAP Carefully

high keys, Node High Keys, Blink-Trees

hinted handoff, Hinted Handoff

histories, Distributed Transactions

horizontal scaling, Preface, Distributed Systems

hot data, Introduction and Overview

hotspotting, Cascading Failures

hybrid gossip, Hybrid Gossip, Partial Views

Hybrid Partial View (HyParView) protocol, Partial Views

hybrid transactional and analytical processing (HTAP), Introduction

and Overview

idempotent operations, Problem with retransmits

IEEE Standard for Floating-Point Arithmetic, Primitive Types

immediate eviction, Locking Pages in Cache

immutability, Buffering, Immutability, and Ordering, Part I

Conclusion

immutable storage structures, Log-Structured Storage, Part I

Conclusion

implicit primary keys, Index Files

in-memory database management systems, Memory- Versus Disk-Based DBMS

in-memory tables, In-memory tables

in-place updates, B-Tree Basics, Fragmentation Caused by Updates and Deletes, Log-Structured Storage

incomplete checkpoints, Log Semantics

index entries, Separator Keys

index files, Data Files and Index Files, Index Files

index-organized tables (IOT), Introduction and Overview, Data Files

indexes

clustered versus nonclustered, Introduction and Overview, Index Files

defined, Index Files

primary and secondary, Index Files

purpose of, Data Files and Index Files

SSTable-Attached Secondary Indexes (SASI), Sorted String Tables

indirection pointers, Binary Search with Indirection Pointers

indivisibility, Transaction Processing and Recovery

infective processes, Gossip Dissemination

initial state, FLP Impossibility

InnoDB, Storage Engines

insertion points, Binary Search

instantaneous processing, Processing

internal nodes, B-Tree Hierarchy

Invariant Confluence (I-Confluence), Coordination Avoidance

invitation algorithm, Invitation Algorithm

invocation events, Shared Memory

isolation, Transaction Processing and Recovery

isolation levels

already committed, Isolation Levels

purpose of, Transaction Isolation

read and write anomalies, Read and Write Anomalies

serializability, Serializability

iterators, Merge-Iteration

J

jitter, Cascading Failures

K

kernel page cache, Buffer Management

key hashes, Database Partitioning

keydir, Bitcask

Last-write-wins register (LWW register), Strong Eventual Consistency and CRDTs

latch crabbing, Latch crabbing

latch upgrading, Latch crabbing

latch-free, log-structured, access-method aware (LLAMA), LLAMA and Mindful Stacking

latches, Latches

latency, Fallacies of Distributed Computing, Gossip Mechanics

lazy B-Trees

benefits of, Lazy B-Trees

Lazy-Adaptive Tree (LA-Tree), Lazy-Adaptive Tree, Part I

Conclusion

WiredTiger, WiredTiger, Part I Conclusion

Lazy-Adaptive Tree (LA-Tree), Lazy-Adaptive Tree, Part I

Conclusion

lazy-push, Hybrid Gossip

leader election

bully algorithm, Bully Algorithm

candidate/ordinary optimization, Candidate/Ordinary Optimization

in Raft, Leader Role in Raft

invitation algorithm, Invitation Algorithm

next-in-line failover, Next-In-Line Failover

overview of, Leader Election

ring algorithm, Ring Algorithm

stable leader election, Summary

leaders, Two-Phase Commit, Zookeeper Atomic Broadcast (ZAB),

Multi-Paxos

leaf nodes, B-Tree Hierarchy, Page Structure

learners, Paxos Algorithm

leases, Cost of linearizability, Multi-Paxos

least-frequently used (LFU), LFU

least-recently used (LRU), FIFO and LRU

least-significant byte (LSB), Primitive Types

LevelDB, Storage Engines

leveled compaction, Leveled compaction

libmdbx, Storage Engines

Lightning Memory-Mapped Database (LMDB), Implementing Copy-on-Write: LMDB

linearizability, Isolation Levels, Infamous CAP, Harvest and Yield, Linearizability-Cost of linearizability

linearization point, Linearization point

links

defined, Distributed Systems

exactly-once delivery, Exactly-once delivery

failure sites, Failure Detection

fair-loss links, Fair-loss link

message acknowledgments, Message acknowledgments

message order, Message order

message retransmit problems, Problem with retransmits

message retransmits, Message retransmits

perfect links, Message order

stubborn links, Message retransmits

little-endian byte order, Primitive Types

liveness guarantees, Failure Detection, Leader Election

LMB, Storage Engines

load-balancing, Rebalancing

local clocks, Clocks and Time

local execution, Local and Remote Execution, Cost of linearizability

lock manager, DBMS Architecture, Transaction Processing and Recovery

lock table, Distributed Transactions with Spanner

lock-based concurrency control

Blink-Trees, Blink-Trees

deadlocks, Deadlocks

latch crabbing, Latch crabbing

latch upgrading and pointer chasing, Latch crabbing

latches, Latches

locks, Locks

overview of, Lock-Based Concurrency Control

readers-writer lock (RW lock), Readers-writer lock

locking, Locking Pages in Cache

log buffer, Log Semantics

log manager, Transaction Processing and Recovery

log sequence number (LSN), Log Semantics

log stacking

drawbacks of, Log Stacking

ilesystem logging, Filesystem Logging

Flash Translation Layer (FTL), Flash Translation Layer

log-structured merge-trees (LSM trees)

concurrency in LSM trees, Concurrency in LSM Trees

immutable storage offered by, Log-Structured Storage

LSM Tree lookups, LSM Tree Lookups

maintenance in, Maintenance in LSM Trees

merge-iteration, Merge-Iteration-Merge-Iteration

overview of, LSM Trees

reconciliation, Reconciliation

structure of, LSM Tree Structure-In-memory tables

updates and deletes, Updates and Deletes

log-structured storage (LSS)

implementation details, Implementation Details-Compression

LLAMA and mindful stacking, LLAMA and Mindful Stacking

log stacking, Log Stacking-Filesystem Logging

LSM Trees, LSM Trees-Size-tiered compaction

mutable versus immutable storage, Log-Structured Storage

read, write, and space amplification, Read, Write, and Space Amplification-RUM Conjecture

unordered LSM storage, Unordered LSM Storage-WiscKey

logarithmically sized sorted runs, Logarithmic Runs

logical clocks, Distributed Systems, Vector clocks

logical logs, Operation Versus Data Log

logical space, Vacuum and Maintenance

loss of interest function, Gossip Dissemination

lost update anomaly, Isolation Levels

lost updates, Read and Write Anomalies

M

magic numbers, Magic Numbers

main memory DBMS

versus disk-based, Memory- Versus Disk-Based DBMS

durability in, Durability in Memory-Based Stores

maintenance, Page Defragmentation

mapping tables, Taming Concurrency with Compare-and-Swap

memory cells, Solid State Drives

memory mapped files, On-Disk Structures

memory-resident components (memtables), LSM Tree Structure

memtable switch, Concurrency in LSM Trees

merge delta nodes, Structural Modification Operations

merge functions, Coordination Avoidance

merge reconciliation, Log-Structured Storage

merge structural modification operations, Structural Modification

Operations

merge-iteration, Merge-Iteration-Merge-Iteration

merges, B-Tree Hierarchy, B-Tree Node Merges, Propagating Splits

and Merges, Structural Modification Operations

Merkle trees, Merkle Trees

message acknowledgments, Message acknowledgments

message redundancy, Gossip Mechanics

message retransmits, Message retransmits

messages, Distributed Systems

metadata, Anti-Entropy and Dissemination

min-heap, Merge-Iteration

mindful stacking, LLAMA and Mindful Stacking

MMAPv1, Storage Engines

monarchial leader election, Bully Algorithm

MonetDB, Column- Versus Row-Oriented DBMS

MongoDB

storage engines available, Storage Engines

terminology used in, Index Files

WiredTiger storage engine, WiredTiger

monotonic reads/writes models, Session Models

most-significant byte (MSB), Primitive Types

Multi-Paxos, Multi-Paxos

multicomponent LSM Trees, Multicomponent LSM Trees, Part I

Conclusion

multiple copies, Shared State in a Distributed System

multiple partitions, Egalitarian Paxos

multishard transactions, Distributed Transactions with Spanner

multiversion concurrency control (MVCC), Concurrency Control,

Multiversion Concurrency Control

multiway trees, B-Tree Hierarchy

mutability, Buffering, Immutability, and Ordering

mutable storage structures, Log-Structured Storage, Part I

Conclusion

MyISAM, Storage Engines

MySQL

append-only write-ahead logs, Recovery

overflow pages, Overflow Pages

page header content, Page Header

storage engines available, Storage Engines

terminology used in, Index Files

##### N

network partitions, Network Partitions and Partial Failures, Infamous

CAP

network unreliability, Network Partitions and Partial Failures

next-in-line failover, Next-In-Line Failover

node crashes, Use CAP Carefully

node high keys, Node High Keys

node merges, B-Tree Node Merges, Propagating Splits and Merges

node splits, B-Tree Node Splits, Propagating Splits and Merges

node updates, Abstracting Node Updates

nodes, DBMS Architecture, Page Structure, Distributed Systems

Non-Volatile Memory (NVM), Memory- Versus Disk-Based DBMS

nonblocking atomic commitment problem, Making Operations

Appear Atomic

nonclustered indexes, Introduction and Overview, Index Files

nonleaf nodes, Page Structure

nonrepeatable reads, Read and Write Anomalies

notification broadcasts, Anti-Entropy and Dissemination

null-terminated strings, Strings and Variable-Size Data

##### O

occupancy, B-Tree Hierarchy

offsets, Data Files, General Principles, Cell Layout

omission faults, Omission Faults

on-disk data structures, On-Disk Structures, File Formats

online analytical processing (OLAP), Introduction and Overview

online transaction processing (OLTP), Storage Engines, Introduction and Overview

Open-Channel SSDs, Open-Channel SSDs

operation consistency, Consistency Models

operation logs, Operation Versus Data Log

optimistic concurrency control (OCC), Concurrency Control, Optimistic Concurrency Control

ordering, Buffering, Immutability, and Ordering, Part I Conclusion, Ordering

outsourced heartbeats. Outsourced Heartbeats

overflow, B-Tree Node Splits

overflow pages, Overflow Pages

overlay networks, Overlay Networks

overload, Cascading Failures

O_DIRECT flag, Buffer Management

##### P

PACELEC conjecture, Infamous CAP

page caches, Buffer Management, Cache Eviction

page headers

contents of, Page Header

magic numbers, Magic Numbers

node high keys, Node High Keys

overflow pages, Overflow Pages

rightmost pointers, Rightmost Pointers

sibling links, Sibling Links

page ID, Cell Layout

page reference events, LFU

page replacement

CLOCK algorithm, CLOCK

eviction policy, Page Replacement

FIFO algorithm, FIFO and LRU

least-frequently used (LFU), LFU

LRU-based cache eviction, FIFO and LRU

usage frequency, CLOCK

page-replacement policy, Page Replacement

aged binary trees, On-Disk Structures

pages, Data Files and Index Files, Solid State Drives, B-Tree

Hierarchy, File Formats, Page Structure

paging-in, Buffer Management, LFU

parallel computing, Concurrent Execution

parent updates, Structural Modification Operations

partial failures, Network Partitions and Partial Failures

partial views, Partial Views

partially synchronous systems, System Synchrony

participants, Distributed Systems

partitioning, Egalitarian Paxos

pathological trees, Tree Balancing

Paxos

distributed transactions in Spanner, Distributed Transactions with

Spanner

Egalitarian Paxos (EPaxos), Egalitarian Paxos

failure scenarios, Failure Scenarios

Fast Paxos, Fast Paxos

Flexible Paxos, Flexible Paxos

generalized solution to consensus, Generalized Solution to

Consensus

Multi-Paxos, Multi-Paxos

overview of, Paxos

Paxos algorithm, Paxos Algorithm

quorums in, Quorums in Paxos

peer sampling services, Partial Views

peer-to-peer information exchange, Anti-Entropy and Dissemination

Percolator, Distributed Transactions with Percolator-Distributed

Transactions with Percolator

perfect delivery, Two Generals' Problem

perfect links, Message order

performance evaluation tools, Storage Engines

pessimistic (conservative) concurrency control (PCC), Concurrency

Control, Pessimistic Concurrency Control

phantom reads, Read and Write Anomalies

phases, Distributed Systems

phi-accrual (φ-accrual) failure detector, Phi-Accural Failure Detector

physical clocks, Distributed Systems

physical logs, Operation Versus Data Log

pinning, Caching Semantics, Locking Pages in Cache

pipelining, Processing

platform byte order, Primitive Types

point queries, Ubiquitous B-Trees

pointer chasing, Latch crabbing

pointers, Counting Keys

Positive-Negative-Counter (PN-Counter), Strong Eventual

Consistency and CRDTs

PostgreSQL

append-only write-ahead logs, Recovery

Blink-Trees, Node High Keys

circular buffers, Locking Pages in Cache

versus fsync(), Recovery

page header content, Page Header

right-only appends (fastpath), Right-Only Appends

terminology used in, Index Files

versioning in, Versioning

Practical Byzantine Fault Tolerance (PBFT), Byzantine Consensus

Pre-Accept phase, Egalitarian Paxos

predicate deletes, Updates and Deletes

prefetching, Locking Pages in Cache

prepare operations, Making Operations Appear Atomic, Two-Phase Commit

primary files, Data Files

primary indexes, Index Files-Primary Index as an Indirection

primary keys, Index Files-Primary Index as an Indirection

primary pages, Overflow Pages

primitive types, Primitive Types

priority queues, Merge-Iteration

probabilistic interest loss, Gossip Mechanics

probation queue, LFU

process-local queues, Processing

processes

consistency models and, Consistency Models

defined, Distributed Systems

failure sites, Failure Detection

fair-loss links, Fair-loss link

infective processes, Gossip Dissemination

susceptible processes, Gossip Dissemination

processing time, Processing

promises, Cohort Failures in 2PC, Paxos Algorithm

promotion, B-Tree Node Splits

proposers, Paxos Algorithm

prospective leaders, Zookeeper Atomic Broadcast (ZAB)

protected queue, LFU

push/lazy push multicast trees (Plumtrees), Hybrid Gossip

##### Q

query optimizer, DBMS Architecture

query plan, DBMS Architecture

query processor, DBMS Architecture

questions and comments, How to Contact Us

queue capacity, Processing

queueing techniques, Readers-writer lock

quickbalance, Right-Only Appends

quorums, Tunable Consistency, Read Repair, Quorums in Paxos

##### R

Raft

failure scenarios, Failure Scenarios

leader role in, Leader Role in Raft

overview of, Raft

random I/O, Solid State Drives

random processes, Gossip Dissemination

range queries, Ubiquitous B-Trees, WiscKey

range tombstones, Updates and Deletes

RCFile, Column-Oriented Data Layout

read amplification, Read, Write, and Space Amplification-RUM

Conjecture

read anomalies

dirty read, Read and Write Anomalies

fractured read, Coordination Avoidance

nonrepeatable read, Read and Write Anomalies

phantom read, Read and Write Anomalies

read atomic isolation level, Coordination Avoidance

read committed isolation level, Isolation Levels

read performance, Log-Structured Storage

read phase, Optimistic Concurrency Control

read repair, Read Repair

read sets, Distributed Transactions with Calvin

read skews, Distributed Transactions with Percolator

read uncommitted isolation level, Isolation Levels

Read-Atomic Multi Partition (RAMP) transactions, Coordination Avoidance

read-only transactions, Distributed Transactions with Spanner

read-own-writes consistency model, Session Models

read-time data repair, State Consistency

read-write transactions, Distributed Transactions with Spanner

readers-writer lock (RW lock), Readers-writer lock

rebalancing, Rebalancing

recency conflicts, Bitmap Version Vectors

reconciliation, Reconciliation

recoverability, Distributed Transactions

recovery

ARIES algorithm, ARIES

Byzantine consensus, Recovery and Checkpointing

log semantics, Log Semantics

operation versus data logs, Operation Versus Data Log

steal and force policies, Steal and Force Policies

write-ahead log (WAL), Recovery

recovery manager, DBMS Architecture

redo operations, Operation Versus Data Log

redundancy, Shared State in a Distributed System

redundant messages, Overlay Networks

referencing, Caching Semantics

registers, Shared Memory, Strong Eventual Consistency and CRDTs

regular registers, Shared Memory

reliability, Fallacies of Distributed Computing, Message order

reliable broadcasts, Broadcast

remote execution, DBMS Architecture, Local and Remote Execution

remove delta nodes, Structural Modification Operations

removed processes, Gossip Dissemination

repeatable read isolation level, Isolation Levels

repeating history, ARIES

replica sets, Database Partitioning

replica states, Bitmap Version Vectors

replicas, Distributed Systems

replicated logs, Multi-Paxos

replication and consistency

CAP conjecture, Infamous CAP-Harvest and Yield

Conflict-Free Replicated Data Types (CRDTs), Strong Eventual

Consistency and CRDTs

consistency models, Consistency Models-Vector clocks

eventual consistency, Eventual Consistency

ordering, Ordering

overview of, Replication and Consistency, Summary

quorums, Tunable Consistency

session models, Session Models

shared memory, Shared Memory

strong eventual consistency, Strong Eventual Consistency and CRDTs

system availability, Achieving Availability

tunable consistency, Tunable Consistency

witness replicas, Witness Replicas

Reusable Infrastructure for Linearizability (RIFL), Cost of

linearizability

Riak, Index Files, Hinted Handoff

right-only appends, Right-Only Appends

rightmost pointers, Rightmost Pointers

ring algorithm, Ring Algorithm

robustness, Overlay Networks

RocksDB, Storage Engines

rollback operations, Making Operations Appear Atomic

root nodes, Binary Search Trees, B-Tree Hierarchy

routing keys, Database Partitioning

row keys, Wide Column Stores

row locators, Data Files

row-oriented data layout, Column-Versus Row-Oriented DBMS

Distinctions and Optimizations

rows, Column- Versus Row-Oriented DBMS

RUM Conjecture, RUM Conjecture

##### S

safe registers, Shared Memory

safety guarantees, Failure Detection, Leader Election

sanity checks, Magic Numbers

scaling horizontally (scaling out), Preface, Distributed Systems

scaling vertically (scaling up), Preface, Distributed Systems

schedulers, Distributed Transactions with Calvin

schedules, Serializability

search keys, Data Files and Index Files

secondary indexes, Index Files

sectors, Hard Disk Drives

seeks, Hard Disk Drives

separator keys, Separator Keys, Counting Keys, Rightmost Pointers

sequence numbers, Message acknowledgments

sequencers, Distributed Transactions with Calvin

sequential consistency, Sequential Consistency

sequential I/O, Hard Disk Drives

sequential operations, Shared Memory

serial operations, Shared Memory

serial schedules, Serializability

serializability, Serializability, Isolation Levels, Distributed

Transactions

serialization, Primitive Types

session causality, Session Models

session models, Session Models

shadow paging, Operation Versus Data Log

shadowing, Data Files and Index Files

sharding, Database Partitioning

shared memory, Concurrent Execution, Shared Memory

shared state, Shared State in a Distributed System

short-time bursts, Processing

shrinking phase, Lock-Based Concurrency Control

sibling links, Sibling Links, Blink-Trees

sign, Primitive Types

single-operation consistency models, Consistency Models

single-partition transactions, Distributed Transactions

size-tiered compaction, Size-tiered compaction

skiplists, WiredTiger, Skiplist

sloppy quorum, Hinted Handoff

slot directory, Slotted Pages

slotted pages, Data Files and Index Files, Slotted Pages, Combining

Cells into Slotted Pages, Vacuum and Maintenance

snapshot isolation (SI), Isolation Levels, Distributed Transactions with Percolator

snapshot reads, Distributed Transactions with Spanner

snapshots, Durability in Memory-Based Stores

Software Defined Flash (SDF), Open-Channel SSDs

software errors, Cascading Failures

solid state drives (SSDs), Solid State Drives, Log Stacking, Open-

Channel SSDs

Sophia, Storage Engines

Sorted String Tables (SSTables), Sorted String Tables

space amplification, Read, Write, and Space Amplification-RUM Conjecture

Spanner, Distributed Transactions with Spanner

spanning trees, Overlay Networks

spanservers, Distributed Transactions with Spanner

speculative execution, Quorums in Paxos

spinning disks, Hard Disk Drives

split brain, Leader Election, Bully Algorithm

split delta nodes, Structural Modification Operations

split point, B-Tree Node Splits

split SMOs, Structural Modification Operations

split vote, Failure Scenarios

splits, B-Tree Hierarchy, B-Tree Node Splits, Propagating Splits and

Merges, Structural Modification Operations

SQLite

overflow pages, Overflow Pages

page header content, Page Header

quickbalance, Right-Only Appends

rightmost pointers, Rightmost Pointers

unoccupied segments (freeblocks), Managing Variable-Size Data

SSTable-Attached Secondary Indexes (SASI), Sorted String Tables

stable checkpoints, Recovery and Checkpointing

stable leader election, Summary

state, Distributed Systems, Distributed Systems, Consistency Models

state consistency, State Consistency

steal/no-steal policy, Steal and Force Policies

steps, Distributed Systems

storage engines

responsibilities of, Storage Engines, DBMS Architecture

understanding trade-offs, Storage Engines

strategy, Managing Variable-Size Data

strict consistency, Strict Consistency

strings, Solid State Drives, Strings and Variable-Size Data, Slotted

Pages

strong eventual consistency, Strong Eventual Consistency and CRDTs

structural modification operations (SMOs), Structural Modification

Operations

subtrees, Binary Search Trees, Separator Keys

stubborn links, Message retransmits

super-peers, Strong Eventual Consistency and CRDTs

susceptible processes, Gossip Dissemination

suspected processes, Failure Detection

suspicion level, Phi-Accural Failure Detector

sync checkpoint, Log Semantics

synchrony, Shared State in a Distributed System, System Synchrony

system availability, Achieving Availability

system loads, Processing

table starvation, Size-tiered compaction

table views, Concurrency in LSM Trees

tables

defined, Column- Versus Row-Oriented DBMS

disk-resident tables, LSM Tree Structure

hash-organized tables (hashed files), Data Files

heap-organized tables (heap files), Data Files

in-memory tables, In-memory tables

index-organized tables, Introduction and Overview, Data Files

lock tables, Distributed Transactions with Spanner

mapping tables, Taming Concurrency with Compare-and-Swap

Sorted String Tables (SSTables), Sorted String Tables

tablets, Distributed Transactions with Spanner

TCP protocol, Exactly-once delivery

Thomas Write Rule, Pessimistic Concurrency Control

three-phase commits, Three-Phase Commit-Coordinator Failures in 3PC

threshold interest loss, Gossip Mechanics

throughput, Storage Engines

time window compaction, Size-tiered compaction

timeout-free failure detection, Timeout-Free Failure Detector

timestamp oracle, Distributed Transactions with Percolator

timestamp ordering, Pessimistic Concurrency Control

TinyLFU, LFU

tombstones, Data Files and Index Files, Updates and Deletes,

Maintenance in LSM Trees

total order multicast, Atomic Broadcast

TPC-C benchmark, Storage Engines

trailers, General Principles

transaction isolation. Transaction Isolation

transaction manager, DBMS Architecture, Deadlocks, Making

Operations Appear Atomic, Distributed Transactions with Spanner

transaction processing and recovery

ACID properties, Transaction Processing and Recovery,

Serializability, Isolation Levels, Use CAP Carefully

buffer management, Buffer Management-LFU

concurrency control, Concurrency Control-Blink-Trees

recovery, Recovery-ARIES

Transaction Processing Performance Council (TPC), Storage Engines

transitions, Distributed Systems

transitive coordination, Bitmap Version Vectors

transport subsystem, DBMS Architecture

tree balancing, Tree Balancing, Rebalancing

tree height, Trees for Disk-Based Storage, On-Disk Structures

trimming, Log Semantics, In-memory tables

TrueTime, Distributed Transactions with Spanner

tunable consistency, Tunable Consistency

Two Generals' Problem, Two Generals' Problem

two-component LSM Trees, Two-component LSM Tree, Part I

Conclusion

two-level memory hierarchy, Buffer Management

two-phase commits (2PCs)

cohort failures in, Cohort Failures in 2PC

coordinator failures in, Coordinator Failures in 2PC

overview of, Two-Phase Commit

versus two-phase locking, Lock-Based Concurrency Control

two-phase locking (2PL), Lock-Based Concurrency Control

types, Primitive Types

U

ubiquitous B-Trees, Ubiquitous B-Trees-B-Tree Node Merges

unclustered indexes, Index Files

uncommitted version, Multiversion Concurrency Control

underflow, B-Tree Node Merges

undo and redo, Steal and Force Policies

unique identifiers, Message acknowledgments

unordered storage structures

benefits of, Unordered LSM Storage

Bitcask, Bitcask, Part I Conclusion

WiscKey, WiscKey, Part I Conclusion

unresponsive processes, Failure Detection

update buffers, WiredTiger

update chains, Update Chains

upserts, Reconciliation

usage frequency, CLOCK, LFU

V

vacuum, Page Defragmentation

validation, Magic Numbers

validation phase, Optimistic Concurrency Control

van Emde Boas layout, van Emde Boas Layout

vector clocks, Vector clocks

versioning, Versioning

Vertica, Column- Versus Row-Oriented DBMS

vertical scaling, Distributed Systems

virtual disks, Buffer Management

virtual IDs, Column-Oriented Data Layout

virtual synchrony, Virtual Synchrony

vLogs (value logs), WiscKey

W

wait-die restriction, Deadlocks

waits-for graphs, Deadlocks

wall clocks, Distributed Systems

wear leveling, Flash Translation Layer

wide column stores, Introduction and Overview, Wide Column Stores

WiredTiger, Storage Engines, WiredTiger, Part I Conclusion

WiscKey, WiscKey, Part I Conclusion

witness replicas, Witness Replicas

wound-wait restriction, Deadlocks

write amplification, Read, Write, and Space Amplification-RUM

Conjecture

write anomalies, Read and Write Anomalies

write performance, Log-Structured Storage

write phase, Optimistic Concurrency Control

write sets, Distributed Transactions with Calvin

write skews, Read and Write Anomalies, Isolation Levels, Distributed

Transactions with Percolator

write-ahead log (WAL), Cache Eviction, Recovery

write-ahead log truncation, Concurrency in LSM Trees

write-once registers, Multi-Paxos

write-write conflicts, Distributed Transactions with Percolator

writes-follow-reads model, Session Models

##### Y

Yahoo! Cloud Serving Benchmark (YCSB), Storage Engines

yield, Harvest and Yield

YugaByte, Distributed Transactions with Spanner

Z

Zookeeper Atomic Broadcast (ZAB), Zookeeper Atomic Broadcast (ZAB)

#### About the Author

Alex Petrov is a data infrastructure engineer, database and storage systems enthusiast, Apache Cassandra committee, and PMC member interested in storage, distributed systems, and algorithms.

#### Colophon

The animal on the cover of Database Internals is the peacock flounder, a name given to both Bothus lunatus and Bothus mancus, inhabitants of the shallow coastal waters of the mid-Atlantic and Indo-Pacific ocean, respectively.

While the blue floral-patterned skin gives the peacock flounder its moniker, these flounders have the ability to change their appearance based on their immediate surroundings. This camouflage ability may be related to the fish's vision, because it is unable to change its appearance if one of its eyes is covered.

Adult flatfishes swim in a horizontal attitude rather than in a vertical, back-up/belly-down, orientation as most other fishes do. When they swim, flatfishes tend to glide only an inch (2.54 cm) or so off the bottom while closely following the contour of the sea floor.

One of this flat fish's eyes migrates during maturation to join the other on a single side, allowing the fish to look both forward and backward at once. Understandably, rather than swim vertically, the peacock flounder tends to glide an inch or so off the sea floor, closely following the contour of the terrain with its patterned side always facing up.

While the peacock flounder's current conservation status is designated as of Least Concern, many of the animals on O'Reilly covers are endangered; all of them are important to the world.

The cover illustration is by Karen Montgomery, based on a black and white engraving from Lowry’s The Museum of Natural History. The cover fonts are Gilroy Semibold and Guardian Sans. The text font is Adobe Minion Pro; the heading font is Adobe Myriad Condensed; and the code font is Dalton Maag’s Ubuntu Mono.

Preface

How to Contact Us

I. Storage Engines

1. Introduction and Overview

DBMS Architecture

Memory- Versus Disk-Based DBMS

Durability in Memory-Based Stores

Column- Versus Row-Oriented DBMS

Row-Oriented Data Layout

Column-Oriented Data Layout

Distinctions and Optimizations

Wide Column Stores

Data Files and Index Files

Data Files

Index Files

Primary Index as an Indirection

Buffering, Immutability, and Ordering

Summary

2. B-Tree Basics

Binary Search Trees

Tree Balancing

Trees for Disk-Based Storage

Disk-Based Structures

Hard Disk Drives

Solid State Drives

On-Disk Structures

Ubiquitous B-Trees

B-Tree Hierarchy

Separator Keys

B-Tree Lookup Complexity

B-Tree Lookup Algorithm

Counting Keys

B-Tree Node Splits

B-Tree Node Merges

Summary

3. File Formats

Motivation

Binary Encoding

Primitive Types

Strings and Variable-Size Data

Bit-Packed Data: Booleans, Enums, and Flags

General Principles

Page Structure

Slotted Pages

Cell Layout

Combining Cells into Slotted Pages

Managing Variable-Size Data

Versioning

Checksumming

Summary

4. Implementing B-Trees

Page Header

Magic Numbers

Sibling Links

Rightmost Pointers

Node High Keys

Overflow Pages

Binary Search

Binary Search with Indirection Pointers

Propagating Splits and Merges

Breadcrumbs

Rebalancing

Right-Only Appends

Bulk Loading

Compression

Vacuum and Maintenance

Fragmentation Caused by Updates and Deletes

Page Defragmentation

Summary

5. Transaction Processing and Recovery

Buffer Management

Caching Semantics

Cache Eviction

Locking Pages in Cache

Page Replacement

Recovery

Log Semantics

Operation Versus Data Log

Steal and Force Policies

ARIES

ARIES

Concurrency Control

Serializability

Transaction Isolation

Read and Write Anomalies

Isolation Levels

Optimistic Concurrency Control

Multiversion Concurrency Control

Pessimistic Concurrency Control

Lock-Based Concurrency Control

Summary

6. B-Tree Variants

Copy-on-Write

Implementing Copy-on-Write: LMDB

Abstracting Node Updates

Lazy B-Trees

WiredTiger

Lazy-Adaptive Tree

FD-Trees

Fractional Cascading

Logarithmic Runs

Bw-Trees

Update Chains

Taming Concurrency with Compare-and-Swap

Structural Modification Operations

Consolidation and Garbage Collection

Cache-Oblivious B-Trees

van Emde Boas Layout

Summary

7. Log-Structured Storage

LSM Trees

LSM Tree Structure

Updates and Deletes

LSM Tree Lookups

Merge-Iteration

Reconciliation

Maintenance in LSM Trees

Read, Write, and Space Amplification

RUM Conjecture

Implementation Details

Sorted String Tables

Bloom Filters

Skiplist

Disk Access

Compression

Unordered LSM Storage

Bitcask

WiscKey

Concurrency in LSM Trees

Log Stacking

Flash Translation Layer

Filesystem Logging

LLAMA and Mindful Stacking Open-Channel SSDs

Summary

Part I Conclusion

II. Distributed Systems

8. Introduction and Overview

Concurrent Execution

Shared State in a Distributed System

Fallacies of Distributed Computing

Processing

Clocks and Time

State Consistency

Local and Remote Execution

Need to Handle Failures

Network Partitions and Partial Failures

Cascading Failures

Distributed Systems Abstractions Links

Two Generals' Problem

FLP Impossibility

System Synchrony

Failure Models

Crash Faults

Omission Faults

Arbitrary Faults

Handling Failures

Summary

9. Failure Detection

Heartbeats and Pings

Timeout-Free Failure Detector

Outsourced Heartbeats

Phi-Accural Failure Detector

Gossip and Failure Detection

Reversing Failure Detection Problem Statement

Summary

10. Leader Election

Bully Algorithm

Next-In-Line Failover

Candidate/Ordinary Optimization

Invitation Algorithm

Ring Algorithm

Summary

11. Replication and Consistency

Achieving Availability

Infamous CAP

Use CAP Carefully

Harvest and Yield

Shared Memory

Ordering

Consistency Models

Strict Consistency

Linearizability

Sequential Consistency

Causal Consistency

Session Models

Eventual Consistency

Tunable Consistency

Witness Replicas

Strong Eventual Consistency and CRDTs

Summary

### 12. Anti-Entropy and Dissemination

12. Anti-Entropy and Dissemination

Read Repair

Digest Reads

Hinted Handoff

Merkle Trees

Bitmap Version Vectors

Gossip Dissemination

Gossip Mechanics

Overlay Networks

Hybrid Gossip

Partial Views

Summary

13. Distributed Transactions

Making Operations Appear Atomic

Two-Phase Commit

Cohort Failures in 2PC

Coordinator Failures in 2PC

Three-Phase Commit

Coordinator Failures in 3PC

Distributed Transactions with Calvin

Distributed Transactions with Spanner

Database Partitioning

Consistent Hashing

Distributed Transactions with Percolator

Coordination Avoidance

Summary

14. Consensus

Broadcast

Atomic Broadcast

Virtual Synchrony

Zookeeper Atomic Broadcast (ZAB)

Paxos

Paxos Algorithm

Quorums in Paxos

Failure Scenarios

Multi-Paxos

Fast Paxos

Egalitarian Paxos

Flexible Paxos

Generalized Solution to Consensus

##### Raft

Leader Role in Raft

Failure Scenarios

Byzantine Consensus

PBFT Algorithm

Recovery and Checkpointing

Summary

Part II Conclusion

A. Bibliography

Index

