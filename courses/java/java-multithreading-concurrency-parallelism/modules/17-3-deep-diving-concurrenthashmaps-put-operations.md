# Deep Diving ConcurrentHashMap's put Operations

In the previous module, we explored how **Compare-And-Swap (CAS)** operates at the hardware level. A solid understanding of CAS is crucial for exploring the internal mechanics of Java 8's **`ConcurrentHashMap`**, one of the most sophisticated concurrent collections in the Java Concurrency Utilities.

While a standard `java.util.HashMap` is not thread-safe, and `java.util.Hashtable` synchronizes every method on a single global lock (blocking all concurrent threads), `ConcurrentHashMap` provides high throughput by allowing multiple threads to read and write concurrently. 

It achieves this through two core design principles:
1.  **Lock-Free Reads**: All concurrent read operations are completely non-blocking and require no locks.
2.  **Minimally Blocking Writes (Lock Striping)**: Concurrent write operations block only at the level of individual bins (buckets), allowing non-overlapping writes to execute in parallel.

---

## Underlying Data Structure

At its core, `ConcurrentHashMap` uses a bucketed (binned) hash table, which is an array of `Node` objects:

```java
// The backing hash table: a volatile array of Node elements
transient volatile Node<K,V>[] table;
```

Each bin in the `table` array is a single linked list composed of `Node` instances. The `Node` class contains the following fields:

```java
static class Node<K,V> implements Map.Entry<K,V> {
    final int hash;
    final K key;
    volatile V val;
    volatile Node<K,V> next;
    
    // Constructors, Getters, equals(), and hashCode() implementations
}
```

*   **`next`**: Points to the next node in the chain, enabling **separate chaining** to handle hash collisions.
*   **`volatile` fields**: The `val` and `next` references are declared `volatile`. Combined with the volatile `table` array, this ensures that all threads immediately see modifications to the table structure and node values, enabling lock-free reads and CAS-based writes.

If a bin's collision chain grows beyond a certain threshold (typically 8 elements), `ConcurrentHashMap` converts the linked list into a balanced red-black tree composed of `TreeNode` instances to maintain $O(\log n)$ search performance.

Below is a visual representation of the binned hash table structure:

![Binned Hash Table](../images/image13.png)

*Figure 17.3.1: Structural layout of a binned hash table using separate chaining*

---

## Detailed Mechanics of the put Operation

From Java 8 onwards, the `put` operation (and its variants like `putIfAbsent`) implements a highly optimized combination of CAS and synchronized locking. 

Let's break down the execution flow of a `put` operation through six key points.

### 1. Lazy Table Initialization
The backing `table` array is not allocated when the map is instantiated. Instead, it is **lazily initialized** upon the first insertion. The initialization process is coordinated atomically using CAS to prevent multiple threads from allocating the array simultaneously. The default initial size of the table is **16** (a power of two).

### 2. Hash-to-Bin Mapping
The table is represented as an array of bins. When an element is inserted, its key's hash code is mapped to a specific array index. As the map grows, these bins are filled with individual nodes, linked list chains, or red-black trees.

### 3. Hybrid Synchronization (CAS + Locks)
Java 8 `ConcurrentHashMap` does not lock the entire table, nor does it use a fixed pool of locks. Instead, it uses a hybrid approach:
- If the target bin is **empty**, the node is inserted using **lock-free CAS**.
- If the target bin is **not empty**, the thread acquires an **intrinsic lock** on the first node of that bin.

### 4. Java 7 Segments vs. Java 8 Lock Striping
In Java 7, `ConcurrentHashMap` used an array of **`Segment`** objects. Each `Segment` acted as a small, independent hash table with its own lock. A thread performing a write operation had to lock the entire segment. 

Java 8 completely discards the concept of `Segment` objects. Instead, it implements fine-grained **Lock Striping** directly on the individual bins of a single, flat hash table. The lock is acquired on the first node of the target bin itself, allowing the map to scale its concurrency level directly with the table size.

### 5. Inserting into an Empty Bin (Lock-Free CAS)
If a thread calculates the target bin index and finds that the bin is empty (`null`), it attempts to insert the new node using CAS without acquiring any lock. 

Let's look at the first part of the `putVal` implementation:

```java
final V putVal(K key, V value, boolean onlyIfAbsent) {
    int hash = spread(key.hashCode());
    int binCount = 0;
    for (Node<K,V>[] tab = table;;) {
        Node<K,V> f; int n, i, fh; K fk; V fv;
        if (tab == null || (n = tab.length) == 0) {
            tab = initTable(); // Atomically initialize the table
        }
        else if ((f = tabAt(tab, i = (n - 1) & hash)) == null) {
            // Target bin is empty. Attempt lock-free insertion via CAS.
            if (casTabAt(tab, i, null, new Node<K,V>(hash, key, value))) {
                break; // Insertion successful, no lock was acquired
            }
        }
        // ... (continued below)
    }
}
```

*Figure 17.3.2: Lock-free empty bin insertion phase in ConcurrentHashMap.putVal*

*   **`initTable()`**: Allocates the backing array. If multiple threads call `put()` concurrently on an uninitialized map, they compete via CAS to perform the allocation, ensuring it occurs exactly once.
*   **`i = (n - 1) & hash`**: A fast bitwise AND operation used to calculate the bin index `i`. For this mathematical shortcut to distribute keys uniformly, the table capacity `n` **must always be a power of two**. 
*   **`tabAt(tab, i)`**: Atomically retrieves the node reference at index `i` using volatile memory semantics.
*   **`casTabAt(tab, i, null, node)`**: Performs a CAS operation on `table[i]`. It expects the bin to be `null`. If another thread has inserted a node in the split second between the `tabAt` read and the `casTabAt` write, the CAS fails (returns `false`). The thread then spins, enters the next iteration of the loop, detects that the bin is no longer empty, and falls back to the locking phase.

### 6. Inserting into a Non-Empty Bin (Lock Striping)
If the target bin is not empty, the thread must traverse the existing chain (or tree) to either update an existing key or append the new node. To prevent concurrent modifications to the chain, the thread locks the bin.

To avoid the memory overhead of maintaining separate lock objects for every bin, **`ConcurrentHashMap` uses the first node of the bin itself as the lock object**, utilizing Java's built-in intrinsic monitor locks (`synchronized` blocks):

```java
        else {
            V oldVal = null;
            synchronized (f) { // Lock on the first node of the bin
                if (tabAt(tab, i) == f) { // Double-checked locking validation
                    if (fh >= 0) { // Positive hash indicates a standard linked list
                        binCount = 1;
                        for (Node<K,V> e = f;; ++binCount) {
                            K ek;
                            if (e.hash == hash &&
                                ((ek = e.key) == key ||
                                 (ek != null && key.equals(ek)))) {
                                oldVal = e.val;
                                if (!onlyIfAbsent) {
                                    e.val = value; // Update value
                                }
                                break;
                            }
                            Node<K,V> pred = e;
                            if ((e = e.next) == null) {
                                pred.next = new Node<K,V>(hash, key, value); // Append to end
                                break;
                            }
                        }
                    }
                    else if (f instanceof TreeBin) {
                        // ... Tree-based insertion logic (omitted for brevity)
                    }
                }
            }
            // ... (rehashing and treeification checks)
        }
```

*Figure 17.3.3: Locked insertion phase in ConcurrentHashMap.putVal*

---

## The Critical Double-Checked Locking Check

Notice the statement `if (tabAt(tab, i) == f)` immediately after acquiring the lock `synchronized(f)`. 

Even though we have acquired a lock on `f` (which was read as the first node of the bin), we must re-verify that `f` is **still** the first node of the bin. This double-check is mandatory due to two highly concurrent scenarios:

### 1. Concurrent Table Resizing (Rehashing)
When the map exceeds its load factor, it resizes the table. Table resizing in `ConcurrentHashMap` is a highly concurrent, non-blocking operation where multiple threads help transfer nodes from the old table to a new, larger table. During this transfer, a bin is marked as a forwarding bin, and its nodes are moved. If a resize operation occurs concurrently, the node `f` might be relocated, making it no longer the head of the active bin.

### 2. Concurrent Node Deletion
If another thread calls `remove()` and deletes the first node `f` from the bin, the garbage collector will eventually reclaim `f`. However, because our thread held a reference to `f` before the deletion, our local variable `f` still points to the node in memory. 
- Without the `tabAt(tab, i) == f` check, our thread would append the new node to `f`.
- But from the perspective of the active hash table, `f` is a "zombie" node that has been unlinked. Any node appended to `f` would be lost, resulting in silent data loss.

By performing this double-check, if `tabAt(tab, i)` no longer equals `f`, the thread releases the lock, retries the loop, reads the new head of the bin, and attempts the operation again.

---

## Why Use synchronized Over Non-Blocking Algorithms?

It is technically possible to implement a completely lock-free linked list insertion using complex non-blocking algorithms (such as Harris's non-blocking linked list deletion algorithm). However, the JDK designers opted for intrinsic locks (`synchronized`) on non-empty bins for three reasons:

1.  **Complexity vs. Value**: A lock-free linked list insertion algorithm is exceptionally complex and prone to subtle concurrency bugs. The performance gain over fine-grained locking is negligible.
2.  **Statistical Frequency of Empty Bins**: Under a uniform hash distribution, most `put` operations land in empty bins. This means the vast majority of insertions are completed lock-free via CAS (Point 5). Locking only occurs during hash collisions, which are kept rare by the map's automatic resizing and load factor management.
3.  **JVM Optimizations**: Modern JVMs have highly optimized monitor locks (`synchronized`). Under low contention (which is guaranteed by lock striping across hundreds of bins), lock acquisition is extremely fast, often involving only a cheap biased or biased-like lock acquisition.

---

## Summary

*   **Lock-Free Reads**: Reading elements from `ConcurrentHashMap` is entirely non-blocking and requires no locks, providing high read throughput.
*   **Lock Striping**: Discards Java 7's heavy `Segment` locks in favor of locking individual bins in a flat hash table, allowing multiple writer threads to operate concurrently on different bins.
*   **Volatile Backing Table**: The backing `table` array and the `val` and `next` references of each `Node` are volatile, guaranteeing immediate memory visibility across threads.
*   **Optimistic Insertion**: The first insertion into an empty bin is performed completely lock-free using a CAS operation.
*   **Pessimistic Insertion**: If a bin is not empty, the thread acquires an intrinsic monitor lock (`synchronized`) on the first node of the bin, appending the new element to the end of the list.
*   **Double-Checked Locking**: Inside the synchronized block, the thread must verify that the locked node is still the head of the bin to guard against concurrent table resizing or head-node deletion (zombie nodes).
