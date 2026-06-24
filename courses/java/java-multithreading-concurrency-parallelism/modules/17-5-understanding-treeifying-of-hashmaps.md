# Understanding Treeifying of HashMaps

In the previous , we have seen how the ConcurrentHashMap offers better performance than Collections.synchronizedMap() with a simple test. Here we will understand one of the important performance enhancements done in Java8 HashMap and ConcurrentHashMap. This enhancement that we are talking about is NOT really related to thread safety but about reducing the complexity of searching for a key in a particular bin — *The TreeNodes*.

_Note: For you to understand this article, you are required to know how HashMap’s put() method works._

The concept here is very simple. Whenever two or more keys land in the same bin, they will get added to the end of the list that the bin represents. To simulate this scenario let’s write a class that has poor hashcode implementation.

\*Note: We are using the words ***bin*** and ***bucket*** interchangeably. Both are the same and represent the index in the underlying table array.\*

```java
public final class Student {


    private final int stdId;
    private final String stdName;
    private final int deptNo;


    public Student(int stdId, String stdName, int deptNo) {
        this.stdId = stdId;
        this.stdName = stdName;
        this.deptNo = deptNo;
    }


    // Getters


    @Override
    public int hashCode() {
        return 4; // Poor Hashcode implementation
    }


    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (o == null || getClass() != o.getClass()) return false;
        Student student = (Student) o;
        return stdId == student.stdId &&
                deptNo == student.deptNo &&
                stdName.equals(student.stdName);
    }
}
```

hosted with ❤ by 

Illustration 17.5.1. Student.java class with Poor hashcode() implementation

You can see this class has a poor hashcode function, in the sense that for every Student object the hashcode returns the same value. If we add the Student objects having the same hashcode to the HashMap as keys, all the entries will land in the same bucket. For example, let’s assume we have added 5 student objects as below. Now all these objects will end up in the same bucket.

```java
Map<Student, String> studentMap = new HashMap<>();
studentMap.put(new Student(103, "STD03", 1003), "STD03");
studentMap.put(new Student(102, "STD02", 1002), "STD02");
studentMap.put(new Student(101, "STD01", 1001), "STD01");
studentMap.put(new Student(104, "STD04", 1004), "STD04");
studentMap.put(new Student(105, "STD05", 1005), "STD05");
```

Let’s calculate in which bucket they will land. So we know how Java’s HashMap calculates the bucket index: **i = (n - 1) & hash**.

**i = (n - 1) & hash**: **n** is 16 as the initial table size is 16. And the hash is 4 because every Student object will return the same hashcode value 4.

**n - 1** = 16 - 1 => 15 (1111 in binary)
**hash** = 4 ( 0100 in binary)
**(n -  1) & hash** = 15 & 4 = 1111 & 0100 = 0100
i = 0100 => 4

So the result value will always be 4. This is the case for every Student object. So all the entries will end up in the same bucket 4. This is depicted as below.
![alt text](../images/image18.png)
Now, what is the problem with this?

As you can notice, the get() operation sucks due to the bad hashcode. The worst-case complexity of theget() operation goes up to **O(N)** where **N **is the size of the bin, because it has to scan through each node in that bin, and if none of the nodes are equal to the key it has to add the new node at the end of the list.

Not only the get operation but all the subsequent put operations take the time complexity of **O(N)**. As we keep on adding the new nodes this gets even worse.

Why do we need to worry about this? Well, we use hash-based collections to get the insert, remove, update and read to be in constant time complexity. That is **O(1)**.

So who is the culprit here: Java’s HashMap or the Programmer who has written the client code?

Well, it is the programmer that has messed up the hashcode implementation.  clearly specifies that we should follow hashcode and equals contract.

Though it is the programmer's responsibility to provide good hashcode implementation, Java 8 is very kind enough to optimize this. What it does is convert that singly linked list to a *Balanced Binary Search Tree*. This operation is known as ***Treeifying***. This conversion happens only when the length of the bin goes beyond a threshold that has been set. Now, what is that threshold? You can look at the source code to find out. But here it is.

```java
static final int ***TREEIFY_THRESHOLD**** *= 8;
```

So if the length of the bin goes beyond or equal to 8, the list will be converted to *Balanced Binary Search Tree*. Now the advantage of treeifying is that all the operations get, put, remove, update will now be done in **O(Log N)** complexity, where **N** is the size of the bin.
![alt text](../images/image19.png)
_Note: The treeifying enhancement is there from Java 8 onwards._

Can we actually see that the bin is treeified?

Yes, we can definitely see it. We know that each entry is an object of type Node<Key, Value>. But this is the only case with the bin representing the single linked list. But after it is treeified, every node in that bin is an object of type TreeNode<Key, Value>. So, one way to check whether the bin is treeified or not is just to debug in the IDE and check the entry object is of type TreeNode or not. Or the other way is to just print the class name of each entry on the console. The below code snippet illustrates this.

```java
public static void main(String[] args) {
    Map<Student, String> studentMap = new HashMap<>();
    studentMap.put(new Student(103, "STD03", 1003), "STD03");
    studentMap.put(new Student(102, "STD02", 1002), "STD02");
    studentMap.put(new Student(101, "STD01", 1001), "STD01");
    studentMap.put(new Student(104, "STD04", 1004), "STD04");
    studentMap.put(new Student(105, "STD05", 1005), "STD05");
    studentMap.put(new Student(108, "STD08", 1008), "STD08");
    studentMap.put(new Student(106, "STD06", 1006), "STD06");
    studentMap.put(new Student(107, "STD07", 1007), "STD07");
    studentMap.put(new Student(110, "STD10", 1010), "STD10");
    studentMap.put(new Student(109, "STD09", 1009), "STD09");
    studentMap.put(new Student(111, "STD11", 1011), "STD11");

    studentMap.entrySet().forEach(entry ->
                System.*out*.println(entry.getClass().getName()));
}
```

What I have done is put eleven entries on the map. All eleven will be in the same bucket crossing the TREEIFY_THRESHOLD***,*** thereby converted to *TreeNodes*. Here is the output.

java.util.HashMap$TreeNode
java.util.HashMap$TreeNode
java.util.HashMap$TreeNode
java.util.HashMap$TreeNode
java.util.HashMap$TreeNode
java.util.HashMap$TreeNode
java.util.HashMap$TreeNode
java.util.HashMap$TreeNode
java.util.HashMap$TreeNode
java.util.HashMap$TreeNode
java.util.HashMap$TreeNode

What will be output if we have the nodes less then specified by TREEIFY_THRESHOLD. Well, they are simply Nodes, right? Here is the output when we have lesser nodes than specified by TREEIFY_THRESHOLD.

java.util.HashMap$Node
java.util.HashMap$Node
java.util.HashMap$Node
java.util.HashMap$Node
java.util.HashMap$Node

That is the story of *Treeifying*. The logic is simple — Converting the LinkedList to *Balanced Binary Search Trees*. But how does it happen in ConcurrentHashMap? Because this operation has to be done in a thread-safe manner. Well, it uses the built-in monitor(The Intrinsic Lock) on the first node itself the same way as specified in the putVal.

## Summary

Bad hashcode results in bad performance. The programmer’s should always ensure to write good hash functions to ensure the uniform random distribution of the hashcode in the table.

The Java8’s HashMap transforms the bin from List to *Balanced Binary Search Tree *to make the operations on map efficient.

All the nodes are of type TreeNode once the bin is treeified.
