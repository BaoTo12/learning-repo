# Introduction to Concurrent Collections — CopyOnWriteArrayList

In the previous , we have seen the ReentrantLock and Condition objects to implement Producer-Consumer patterns. Now we will look at the concurrent collections offered by the java concurrency framework. Most of these collections internally use ReentrantLocks along with Volatiles and Compare-And-Swap (CAS). CAS offers a technique to implement non-blocking mechanisms. We will look at CAS in-depth in later parts.

As we all know concurrent collections provide thread safety as they yield consistent results if multiple threads add or delete elements to and from the collection. If you had read and understood all the previous parts of this series, you might have understood why we need to go for concurrent collections. Why not synchronized collections? Ah! we didn’t mention synchronized collections so far, right?. Here are they. The synchronized collections are very simple. All the methods in these collections like add, remove, get, insert and etc are synchronized. We have the following *static* utility methods in java.util.Collections class to create synchronized collections. The below code snippet is extracted from java.util.Collections.synchronizedList() method that returns the SynchronizedList object.

```java
static class SynchronizedList<E>
    extends SynchronizedCollection<E>
    implements List<E> {
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
        if (this == o)
            return true;
        synchronized (mutex) {return list.equals(o);}
    }
    public int hashCode() {
        synchronized (mutex) {return list.hashCode();}
    }


    public E get(int index) {
        synchronized (mutex) {return list.get(index);}
    }
    public E set(int index, E element) {
        synchronized (mutex) {return list.set(index, element);}
    }
    public void add(int index, E element) {
        synchronized (mutex) {list.add(index, element);}
    }
    public E remove(int index) {
        synchronized (mutex) {return list.remove(index);}
    }


    public int indexOf(Object o) {
        synchronized (mutex) {return list.indexOf(o);}
    }
    public int lastIndexOf(Object o) {
        synchronized (mutex) {return list.lastIndexOf(o);}
    }


    public boolean addAll(int index, Collection<? extends E> c) {
        synchronized (mutex) {return list.addAll(index, c);}
    }


    @Override
    public void replaceAll(UnaryOperator<E> operator) {
        synchronized (mutex) {list.replaceAll(operator);}
    }
    @Override
    public void sort(Comparator<? super E> c) {
        synchronized (mutex) {list.sort(c);}
    }
}
```

hosted with ❤ by 

Illustration 17.1.1 SynchronizedList from JDK java.util.Collections.$SynchronizedList

## Synchronized Collections

As you can see from the above illustration all the methods in synchronized collections are synchronized on a mutex object. This is the case with every synchronized collection that is returned from java.util.Collections class utility methods. They all return the synchronized version of the List, Set, and Map. Below are the collections and their utility method.

List: Collections.synchronizedList()

Set: Collections.synchronizedSet()

Sorted Set: Collections.synchronizedSortedSet()

NavigableSet: Collections.synchronizedNavigableSet()

Map: Collections.synchronizedMap()

SortedMap: Collections.synchronizedSortedMap()

NavigableMap: Collections.synchronizedNavigableMap()

All the collections returned from Collections.synchronizedXXX() are thread-safe and are implemented with synchronized statement for every mutating operation.

All the synchronized collections are just wrappers on the existing non-synchronized collections. For every synchrnozedXXX() method we have to pass a collection object. For example, if we want to create a SortedMap we need to send an empty collection object that implements SortedMap. Look at the example below.

```java
import java.util.*;


public class SynchronizedMapDemo {


    public static <Key extends Comparable<Key>, Value> Map<Key, Value> getSynchronizedSortedMapFrom(
            List<Key> keys,
            List<Value> values,
            int nKeysToBeCopied) {
        if (keys.size() < nKeysToBeCopied || values.size() < nKeysToBeCopied) {
            throw new IllegalArgumentException("Not Enough number of Keys/Values to be copied!!");
        }
        Map<Key, Value> map = Collections.synchronizedSortedMap(new TreeMap<>());
        for (int i = 0; i < nKeysToBeCopied; i++) {
            map.put(keys.get(i), values.get(i));
        }
        return map;
    }


    public static void main(String[] args) {
        Map<Integer, String> synchronizedMap = getSynchronizedMapFrom(
                Arrays.asList(1, 2, 5, 4, 3),
                Arrays.asList("ONE", "TWO", "FIVE", "FOUR", "THREE"),
                5);
        System.out.println("Synchronized Implementation Class: " + synchronizedMap.getClass().getName());
        System.out.println(synchronizedMap);
    }


}
```

hosted with ❤ by 

The static method getSynchronizedSortedMapFrom() from lines 5 to 8 accepts three parameters list of keys, values, and number of keys to be copied. The method signature looks a bit complex. I have just made this method very generic so that it can work with all types.

Here is the output of the above program.

```java
Synchronized Implementation Class: java.util.Collections$SynchronizedSortedMap
{1=ONE, 2=TWO, 3=THREE, 4=FOUR, 5=FIVE}
Let me explain the method signature bit by bit.
```

Leaving the public and static aside, because everyone knows what they are, the first question is what is <Key extends Comparable<Key>, Value>? This is how we declare the type parameters while defining the generic methods. Why am I mentioning this is because beginners confuse it with Key and Value being some Java classes. We are actually being more verbose here, it could also be written as<K extends Comparable<K>, V>.

The second question is, why the extends Comparable<Key> with the Key, why not simply <Key, Value>? Well this is because we are returning a SortedMap. And SortedMap expects the keys to be Comparable. Otherwise, this compiles fine but at run time it may throw a ClassCastException. We are actually forcing the client code(The code that calls this method) to give the correct types while invoking this method.

The function accepts three arguments: List of Keys, List of Values, number of keys to be copied. If the client code calls this method with a List of Keys that are not Comparable then it will report a compile-time error.

The method getSynchronizedSortedMapFrom() makes a SortedMap taking the keys from the first argument and values from the second argument. It only takes the number of keys mentioned in the third argument, if those many keys are not available it simply throws as IllegalArgumentException.

That’s about the generic method that we defined. Sorry for digressing a bit from the main point. I thought it would be worth explaining this otherwise beginners won’t continue after they see the above example with that generic method signature. I think I should have made the example a bit simple rather. I would write another article on generic methods and embed the link here. Anyways, the main point here is, any synchronized collection that is returned from the Collections.synchronizedXXX() is a wrapper around the collection that we sent as a parameter. Look at line 12, we have given a new TreeMap object while calling the synchronizedSortedMap(). And as the above output shows, it creates a java.util.Collections$SynchronizedSortedMap which is wrapper around TreeMap collection.

The other main important point about the synchronized collections is that the iterators are any of the collection views are not synchronized. The client code should manually synchronize, as shown below, on the returned sorted map when traversing any of its collection views, or the collections views of any of its subMap, headMap or tailMap views, via Iterator, Spliterator or Stream:

```java
SortedMap m = Collections.*synchronizedSortedMap*(new TreeMap());
Set s = m.keySet();  *// Needn't be in synchronized block**
    *...
synchronized (m) {  *// Synchronizing on m, not s!**
    *Iterator i = s.iterator(); *// Must be in synchronized block**
    *while (i.hasNext())
        foo(i.next());
}
So that's about the synchronized collections. As a quick review:
The Synchronized Collections are implemented with the synchronized statements internally.
They are just the wrapper around the collection object that we provide as parameters.
```

The traversing of the synchronized collection, or any collection views such as subXXX, headXXX, tailXXX, must explicitly be synchronized.

All this story is to say that the synchronized collections are not better candidates if we take performance and flexibility concerns into account.

That is where the concurrent collections chip in. Most of the synchronized collections have their concurrent counterparts. For example, the CopyOnWriteArrayList is the concurrent counterpart for SynchronizedList. Now is the time to deep dive into CopyOnWriteArrayList.

## CopyOnWriteArrayList

As we mentioned, CopyOnWriteArrayList is a concurrent array list. But why the name CopyOnWriteArrayList, why didn’t they name it as ConcurrentArrayList? If we find the answer to this question, it means, we understand the CopyOnWriteArrayList.

The name comes from its behavior. We all know that ArrayList has an underlying Object array on which it operates. The same way CopyOnWriteArrayList has an underlying Object array.

```java
private transient volatile **Object**[] array;
```

When any write operation, such as, add, set, or remove is performed, it makes a fresh copy of this underlying array. For example, if we are adding an element to the collection by calling add, it makes the copy of this existing array. And adds that element, and then sets this new copy as the original and discards the old one for garbage collection. All this is done atomically, which means inside a synchronized block.

## Dynamic Growing Semantics:

The main difference, apart from the thread-safety, between the normal ArrayList and the CopyOnWriteArrayList , which most people don’t talk about, is the growth of the underlying array. Unlike ArrayList which start with the initial size of 10, the CopyOnWriteArrayList starts with size 0. Since for every add call it anyways needs to create a new array, it creates that with the len + 1(where len is the current length of the array). Look at the code snippet of CopyOnWriteArrayList.add()

```java
public boolean add(E e) {
    synchronized (lock) {
        Object[] es = **getArray**();
        int len = es.length;
        es = Arrays.***copyOf***(es, len + 1);
        es[len] = e;
        **setArray**(es);
        return true;
    }
}
```

In the above code snippet, the call to getArray() returns the current underlying Object array. The new array returned from Arrays.copyOf will have all the elements from the old array and an extra single space to put the new element. And setArray(es) sets the new array as the underlying array. This whole thing is guarded by the synchronized block — Very simple and clean.

If you want to understand this better, look at what Arrays.copyOf() does. I am only telling this keeping in mind that this article is also read by beginners. Intermediate and expert Java programmers anyways have a better idea of what *Arrays.copyOf()* and *System.arraycopy()* does. If not, please go and have a look at what these guys are doing. These two methods are very important.

*We get this understanding by looking at the CopyOnWriteArrayList source code. I would always suggest looking at the JDK source code. That is the best way to learn. Because source code can never be wrong, if it is wrong, it is a bug — Zero Condition.*

With that being said, you can now have a look at the source code of remove() and removeAll(). Enough Gyan. Let’s continue.

Now we understand why the name CopyOnWriteArrayList. It makes a copy of the array on every write as a result of the method call to add or set. The difference between add and set is:

With add the new array of sizelen + 1 gets created to make a slot for the new element.

With set the new array will be of the same size as the existing array. Because we don’t have to add a new element. We just need to set(override) an element at a specific index. Look at the CopyOnWriteArrayList API document.

Though the implementation of CopyOnWriteArrayList looks rather simple and clean, we need to understand a few points here.

Though the CopyOnWriteArrayList is thread-safe, it doesn’t perform well where there are more writer threads than reader threads. Because for every write operation it needs to create a new copy and discards the old copy for garbage collection purposes. And as the discarded objects grow, the GC needs to kick in. And GC is a costly operation be it minor or major as it takes some of the processing of the CPUs. So this collection should not be used when there are more writer threads than reader threads.

The copying of the array becomes costlier as the size grows. In amortized analysis, it leads to quadratic time complexity and performs badly, especially when more writer operations are involved.

The good thing is that the underlying array is *effectively immutable* and no further synchronization is required when accessing or iterating it.

The bad thing is that the iterators work on the reference to the underlying array that was at the time of starting the iterator. Meanwhile, if any write operation is performed on the collection the iterator won’t have the visibility of the newly added elements. Because the newly added elements are in the copy of the array and the iterator is on the old array. Note that, unlike the plain vanilla ArrayList iterator, the CopyOnWriteArrayList iterators don’t throw ConcurrentModificationException. As a result, multiple threads can iterate the collection without interference from other mutating threads. So in simple words, the iterators won’t reflect the concurrent mutating operations like add, set, and remove.

CopyOnWriteArrayList is more suitable for scenarios with fewer writes and more reads.

That's all about CopyOnWriteArrayList and here is the summary of what we have learned so far.

## Summary

The Synchronized Collections are implemented with the synchronized statements internally.

They are just the wrapper around the collection object that we provide as parameters.

The traversing of the synchronized collection, or any collection views such as subXXX, headXXX, tailXXX, must explicitly be synchronized.

As the name suggests, the CopyOnWriteArrayList, when any write operation, such as, add, set, or remove is performed, it makes a fresh copy of this underlying array.

The iterators of CopyOnWriteArrayList won’t reflect the concurrent mutating operations such as add, set, and remove.

CopyOnWriteArrayList iterators don’t throw ConcurrentModificationException. As a result, multiple threads can iterate the collection without interference from other mutating threads.

CopyOnWriteArrayList is more suitable for scenarios with fewer writes and more reads.