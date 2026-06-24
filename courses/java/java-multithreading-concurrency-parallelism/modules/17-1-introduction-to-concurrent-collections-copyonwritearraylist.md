# Introduction to Concurrent Collections — CopyOnWriteArrayList

In the previous module, we explored the `ReentrantLock` and `Condition` objects to implement custom blocking collections for producer-consumer patterns. In this module, we will begin our journey into the high-performance **concurrent collections** provided by the Java Concurrency Utilities. 

Most of these concurrent collections internally leverage a combination of `ReentrantLock`, `volatile` variables, and low-level **Compare-And-Swap (CAS)** operations to achieve thread safety. CAS offers a powerful technique to implement non-blocking mechanisms, which we will explore in-depth in the next module.

---

## The Legacy: Synchronized Collections

Before diving into concurrent collections, it is important to understand their historical predecessors: **synchronized collections**. 

Synchronized collections achieve thread safety by wrapping standard, non-thread-safe collections and synchronizing every single method on a common lock (mutex). The `java.util.Collections` class provides static utility methods to create these wrappers, such as `Collections.synchronizedList()`.

Below is an extract from the JDK source code demonstrating how `SynchronizedList` wraps a standard list:

```java
static class SynchronizedList<E> extends SynchronizedCollection<E> implements List<E> {
    private static final long serialVersionUID = -7754090372962971524L;

    final List<E> list;

    SynchronizedList(List<E> list) {
        super(list);
        this.list = list;
    }
    
    SynchronizedList(List<E> list, Object mutex) {
        super(list, mutex);
        this.list = list;
    }

    public boolean equals(Object o) {
        if (this == o) return true;
        synchronized (mutex) { return list.equals(o); }
    }
    
    public int hashCode() {
        synchronized (mutex) { return list.hashCode(); }
    }

    public E get(int index) {
        synchronized (mutex) { return list.get(index); }
    }
    
    public E set(int index, E element) {
        synchronized (mutex) { return list.set(index, element); }
    }
    
    public void add(int index, E element) {
        synchronized (mutex) { list.add(index, element); }
    }
    
    public E remove(int index) {
        synchronized (mutex) { return list.remove(index); }
    }

    public int indexOf(Object o) {
        synchronized (mutex) { return list.indexOf(o); }
    }
    
    public int lastIndexOf(Object o) {
        synchronized (mutex) { return list.lastIndexOf(o); }
    }

    public boolean addAll(int index, Collection<? extends E> c) {
        synchronized (mutex) { return list.addAll(index, c); }
    }

    @Override
    public void replaceAll(UnaryOperator<E> operator) {
        synchronized (mutex) { list.replaceAll(operator); }
    }
    
    @Override
    public void sort(Comparator<? super E> c) {
        synchronized (mutex) { list.sort(c); }
    }
}
```

*Figure 17.1.1: SynchronizedList wrapper from JDK java.util.Collections*

The JDK provides utility methods to wrap all primary collection types:
*   **List**: `Collections.synchronizedList(new ArrayList<>())`
*   **Set**: `Collections.synchronizedSet(new HashSet<>())`
*   **SortedSet**: `Collections.synchronizedSortedSet(new TreeSet<>())`
*   **NavigableSet**: `Collections.synchronizedNavigableSet(new TreeSet<>())`
*   **Map**: `Collections.synchronizedMap(new HashMap<>())`
*   **SortedMap**: `Collections.synchronizedSortedMap(new TreeMap<>())`
*   **NavigableMap**: `Collections.synchronizedNavigableMap(new TreeMap<>())`

---

## Example: Using Synchronized Collections

Synchronized collections are straightforward to use. Let's look at an example that creates a thread-safe `SortedMap` using a generic helper method:

```java
import java.util.Arrays;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.SortedMap;
import java.util.TreeMap;

public class SynchronizedMapDemo {

    public static <Key extends Comparable<Key>, Value> Map<Key, Value> getSynchronizedSortedMapFrom(
            List<Key> keys,
            List<Value> values,
            int nKeysToBeCopied) {
        
        if (keys.size() < nKeysToBeCopied || values.size() < nKeysToBeCopied) {
            throw new IllegalArgumentException("Not enough keys or values to copy!");
        }
        
        // Wrap a standard TreeMap in a synchronized decorator
        Map<Key, Value> map = Collections.synchronizedSortedMap(new TreeMap<>());
        for (int i = 0; i < nKeysToBeCopied; i++) {
            map.put(keys.get(i), values.get(i));
        }
        return map;
    }

    public static void main(String[] args) {
        Map<Integer, String> synchronizedMap = getSynchronizedSortedMapFrom(
                Arrays.asList(1, 2, 5, 4, 3),
                Arrays.asList("ONE", "TWO", "FIVE", "FOUR", "THREE"),
                5);
        
        System.out.println("Synchronized Implementation Class: " + synchronizedMap.getClass().getName());
        System.out.println(synchronizedMap);
    }
}
```

### Output
```text
Synchronized Implementation Class: java.util.Collections$SynchronizedSortedMap
{1=ONE, 2=TWO, 3=THREE, 4=FOUR, 5=FIVE}
```

### Understanding the Generics
Let's break down the generic method signature of `getSynchronizedSortedMapFrom()`:
1.  **Type Parameter Declaration**: The declaration `<Key extends Comparable<Key>, Value>` specifies that the type `Key` must implement the `Comparable` interface. 
2.  **Why enforce Comparable?**: Because the method wraps a `TreeMap` (which implements `SortedMap`). A `TreeMap` keeps its keys sorted. If a client attempts to pass keys that are not comparable, a `ClassCastException` would occur at runtime. By declaring `Key extends Comparable<Key>`, we force the compiler to check and guarantee type safety at compile time.

---

## Critical Limitation: Iterators are NOT Thread-Safe

> [!WARNING]
> **Iterator Thread-Safety Pitfall**
> While individual operations like `put()`, `get()`, and `remove()` on a synchronized collection are thread-safe, **iterating** over a synchronized collection is **not** thread-safe.

If one thread iterates over a synchronized collection while another thread attempts to modify it, the iterator will fail and throw a `ConcurrentModificationException`. 

To prevent this, you must **manually synchronize** on the collection instance itself during iteration:

```java
SortedMap<Integer, String> m = Collections.synchronizedSortedMap(new TreeMap<>());
Set<Integer> s = m.keySet(); // This call does not need to be synchronized

synchronized (m) { // You must synchronize on m, not on the key set s!
    Iterator<Integer> i = s.iterator(); // Must be inside the synchronized block
    while (i.hasNext()) {
        foo(i.next());
    }
}
```

Because synchronized collections serialise all access via a single lock, they suffer from poor performance and scalability under high thread contention. This is where **concurrent collections** come in.

---

## CopyOnWriteArrayList

**`CopyOnWriteArrayList`** is the concurrent, thread-safe counterpart to `ArrayList`. To understand how it works, we must look at its name: **Copy-On-Write**.

### Underlying Structure
Like a standard `ArrayList`, `CopyOnWriteArrayList` maintains elements in a backing `Object` array:

```java
private transient volatile Object[] array;
```

Notice that this array is declared **`volatile`**. This guarantees that any thread reading the array will immediately see any updates made to the reference.

### Mutating Operations
Whenever a thread performs a write operation—such as `add()`, `set()`, or `remove()`—the collection does not modify the existing array. Instead, it:
1.  Acquires an internal lock.
2.  Creates a **fresh copy** of the underlying array.
3.  Performs the modification (e.g., appends the new element) on the copy.
4.  Updates the `array` reference to point to the new copy, discarding the old array.
5.  Releases the lock.

---

## Dynamic Growing Semantics

A key difference between `ArrayList` and `CopyOnWriteArrayList` is how the underlying array grows:
- A standard `ArrayList` pre-allocates space, starting with a default capacity of 10 and growing by roughly 50% when full.
- `CopyOnWriteArrayList` starts with a capacity of 0. Since it must copy the array on every write anyway, it only allocates exactly the space it needs: **`length + 1`** on every insert.

Let's look at the JDK source code for `CopyOnWriteArrayList.add()`:

```java
public boolean add(E e) {
    synchronized (lock) {
        Object[] es = getArray();
        int len = es.length;
        es = Arrays.copyOf(es, len + 1);
        es[len] = e;
        setArray(es);
        return true;
    }
}
```

### How `add()` Works
1.  **Locking**: The operation is guarded by a `synchronized(lock)` block, ensuring only one write occurs at a time.
2.  **`getArray()`**: Retrieves the current backing array.
3.  **`Arrays.copyOf()`**: Allocates a new array with a size of `len + 1` and copies all existing elements into it.
4.  **Assignment**: The new element is placed at the index `len` (the last slot).
5.  **`setArray(es)`**: Updates the volatile `array` reference to point to the new array.

The same copy-on-write pattern is applied to other modifying operations like `remove()` and `set()`. 
- For `add()`, a new array of size `len + 1` is created.
- For `set()`, a new array of the **same size** is created to override the element at a specific index.

---

## Performance Characteristics and Trade-offs

While `CopyOnWriteArrayList` is simple and elegant, it has distinct trade-offs:

### 1. High Write Overhead
Every single write operation allocates a new array and copies all elements. If you have a large list or many write operations, this leads to:
- **Severe Performance Degradation**: The copying time grows linearly with the size of the array ($O(n)$ time complexity per write, leading to quadratic $O(n^2)$ complexity for multiple writes).
- **Garbage Collection Pressure**: The discarded arrays must be collected by the Garbage Collector (GC). Frequent allocations and deallocations can cause GC pauses, reducing application throughput.

### 2. Thread-Safe, Snapshot-Style Iterators
The backing array of a `CopyOnWriteArrayList` is **effectively immutable**. When a thread obtains an iterator, the iterator holds a reference to the **snapshot** of the array that existed at the moment the iterator was created.
- **No ConcurrentModificationException**: Even if other threads modify the list, the iterating thread can traverse its snapshot without interference, locks, or exceptions.
- **Isolation**: The iterator will not reflect any modifications made to the list after the iterator was created, because those modifications were written to a separate, new array.

---

## When to Use CopyOnWriteArrayList

> [!TIP]
> **Optimal Use Case**
> Use `CopyOnWriteArrayList` **only** in scenarios where **read operations vastly outnumber write operations**, and the list size remains relatively small.
> 
> Typical examples include:
> - Maintaining a list of event listeners.
> - Storing configuration settings that are read frequently but updated rarely.
> - Caching static lookup data.

---

## Summary

*   **Synchronized Collections**: Simple wrappers (e.g., `Collections.synchronizedList`) that synchronize all operations on a single lock. They suffer from poor performance under write contention.
*   **Iterator Vulnerability**: Iterators of synchronized collections are not thread-safe and throw `ConcurrentModificationException` unless manually synchronized on the collection's monitor lock.
*   **Copy-On-Write Principle**: Modifying operations on a `CopyOnWriteArrayList` create a new copy of the underlying array, modify it, and update the volatile array reference atomically.
*   **Snapshot Iterators**: Iterators traverse a static snapshot of the array taken at the time of iterator creation. They are completely thread-safe, require no locking, and do not throw `ConcurrentModificationException`.
*   **Use Cases**: Best suited for read-heavy, write-rare scenarios with relatively small datasets (e.g., listener lists, configuration caches).