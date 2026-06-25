# Understanding Garbage Collection

In this chapter, we will explain the **garbage collection (GC)** subsystems of the **Java Virtual Machine (JVM)**. We will start with a basic look at the theory of **mark and sweep** (also known as **tracing garbage collection**). Next, we will look at the low-level features of the **HotSpot runtime** and how it represents Java objects in memory at runtime.

In the second half of the chapter, we will explain the main ideas of **allocation** and **lifetime**, followed by two key methods that HotSpot uses to tune allocation. Finally, we will bring these concepts together to explain the simplest of HotSpot's production collectors—the **parallel collectors**— and explain the details that make them highly effective for many production workloads.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//fa6ce24a-216c-4e59-bc7b-1c0c7304de98/markdown_3/imgs/img_in_image_box_176_752_253_852.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A13Z%2F-1%2F%2Fadd373282d0866c9392412d789b62dab0d91acbd752c61756c55a7575c01f54e" alt="Image" width="7%" /></div>

Garbage collection is a huge subject; so, we can only cover basic material in this chapter. In Chapter 5, we will study a selection of more advanced GC topics.

---

## The Philosophy of Managed Memory

Garbage collection is one of the most defining and known features of the Java environment. The core concept is simple: instead of forcing the developer to track the exact lifetime and deleting of every single object, the runtime manages memory for the programmer. It automatically finds and removes objects that are no longer needed, clearing and reclaiming the memory for reuse.

When Java was first released, this approach faced a lot of doubt. This was mostly because Java provides no direct language-level tool to control the collector's behavior—a design decision that remains in new versions.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//fa6ce24a-216c-4e59-bc7b-1c0c7304de98/markdown_4/imgs/img_in_image_box_176_187_253_287.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A14Z%2F-1%2F%2F55e057e6e22f4a571266c9687c5745681d4879d193ebc5613edc2a39f2f5c64e" alt="Image" width="7%" /></div>

> [!WARNING]
> The `System.gc()` method exists, but it is almost useless for production performance management. Calling it only "suggests" that the JVM run a collection, which the runtime can (and often does) ignore. $ ^{1} $

This lack of control, along with the poor performance of early Java GCs, led to a long-held belief that garbage collection is an unavoidable performance slowdown. Today, however, Java's GC subsystems are extremely fast, show industry best-in-class engineering, and are well-suited for most demanding production workloads.

In the end, the idea of required, automatic GC has been completely proven. Very few developers today would argue for going back to manual memory management. Even newer systems languages, such as **Rust** (using compile-time ownership tracking) and **Go** (using a runtime collector), treat memory safety and management as the job of the toolchain and runtime rather than the programmer. $ ^{2} $

### The Two Golden Rules of Garbage Collection

Every garbage collection algorithm must follow two basic rules:

1. **No live object must ever be cleared.**
2. **Algorithms must collect all garbage.**

Of these two, **Rule 1 must always be followed**. Clearing an active, live object leads to segmentation faults, unpredictable behavior, or silent data corruption. GC algorithms must be completely sure that an object is no longer in use before reclaiming its space.

If an algorithm fails to collect some garbage (**Rule 2**), the worst-case result is a gradual memory leak that eventually causes an `OutOfMemoryError` and crashes the process. While a crash is bad, it is still much better than silent data corruption. So, GC designs make trade-offs with Rule 2.

For example, the generational collectors we will discuss later leave older objects uncollected for long periods to reduce the cost. Similarly, the regional collectors discussed in Chapter 5 avoid reclaiming areas of memory that have not yet gathered enough garbage to justify the cost of collection.

In the end, giving up low-level memory control for runtime safety and productivity is the core of Java's managed approach—directly matching James Gosling's opinion of Java as a practical, productive language for getting things done.

---

## Tracing and Mark-and-Sweep

Most Java developers know that the platform's garbage collection depends on an algorithm called **mark and sweep** (or **tracing garbage collection**), but few can recall how it actually works.

This section introduces a simple version of the mark-and-sweep algorithm to show how memory is recovered. Note that this model is purposely basic and does not show the highly optimized changes used in production JVMs.

### The Basic Mark-and-Sweep Algorithm

This simple version of the algorithm keeps an **allocated object list** containing pointers to every object currently allocated in the heap. The collection process works in four steps:

1. **Clear Mark Bits**: Loop through the allocated object list and clear the mark bit of every object.
2. **Trace Pointers**: Starting from known external entry points (**GC roots**), traverse the object graph.
3. **Mark Reachable Objects**: Set the mark bit on every object reached during the search. The resulting subgraph of reachable objects is called the **live object graph** (or the **transitive closure** of reachable objects), as shown in Figure 4-1. Any unreachable objects are considered **dead**.
4. **Sweep**: Loop through the allocated object list. For every object whose mark bit remains cleared:
   * Reclaim its heap memory and return it to the free list.
   * Remove the object from the allocated object list.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//f83d94cb-90d4-44ac-abbd-91cb9a4c9c64/markdown_1/imgs/img_in_image_box_141_107_865_434.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A22Z%2F-1%2F%2Fbd97c3dd43c16fd605b4c1c7bff6fd959ced03e7c3eb05167530e76423703e34" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 4-1. Simple view of memory layout</div> </div>

### Visualizing and Analyzing the Heap

The state of the heap can be hard to visualize, but the JDK provides simple tools to help. One of the most basic is the `jmap -histo` command-line tool. It prints a histogram showing the number of instances and bytes allocated per class type. A typical output looks like this:

```shell
 num #instances #bytes class name
 ----------------------------------------------
  1: 20839 14983608 [B
  2: 118743 12370760 [C
  3: 14528 9385360 [I
  4: 282 6461584 [D
  5: 115231 3687392 java.util.HashMap$Node
  6: 102237 2453688 java.lang.String
  7: 68388 2188416 java.util.Hashtable$Entry
  8: 8708 1764328 [Ljava.util.HashMap$Node;
  9: 39047 1561880 jdk.nashorn.internal.runtime.CompiledFunction
 10: 23688 1516032 com.mysql.jdbc.Co...$BooleanConnectionProperty
 11: 24217 1356152 jdk.nashorn.internal.runtime.ScriptFunction
 12: 27344 1301896 [Ljava.lang.Object;
 13: 10040 1107896 java.lang.Class
 14: 44090 1058160 java.util.LinkedList$Node
 15: 29375 940000 java.util.LinkedList
 16: 25944 830208 jdk.nashorn.interna...FinalScriptFunctionData
 17: 20 655680 [Lscala.concurrent.forkjoin.ForkJoinTask;
 18: 19943 638176 java.util.concurrent.ConcurrentHashMap$Node
 19: 730 614744 [Ljava.util.Hashtable$Entry;
 20: 24022 578560 [Ljava.lang.Class;
```

This gives a quick snapshot of the heap. For more detailed offline analysis, powerful tools like the Eclipse Memory Analyzer Tool (MAT) are available. For live, real-time heap checking, developers can use visual interfaces like the Sampling tab of VisualVM (introduced in Chapter 3) or the VisualGC plug-in.

However, a short-term view is rarely enough for deep analysis. For questions like "How large is the heap?", "How is usage trending?", or "Is there a memory leak?", engineers should rely on JDK Flight Recorder (JFR) or analyze raw garbage collection (GC) logs.

---

## Garbage Collection Glossary

The technical terms used to describe GC algorithms can be confusing, and some terms have changed over time. To ensure clarity, this book uses the following definitions:

| Term | Definition & Behavior |
| :--- | :--- |
| **Stop-the-World (STW)** | The collection cycle stops all application threads. This stops the application from changing the heap and invalidating the collector's view while garbage is being reclaimed. |
| **Concurrent** | The GC threads run concurrently with active application threads. This is difficult to implement and introduces CPU overhead, but greatly reduces pause times. |
| **Parallel** | The collector uses multiple GC threads (and CPU cores) to do work concurrently, tuning throughput. |
| **Exact** | The GC has complete type information at runtime, allowing it to reliably distinguish between primitive values (e.g., `int`) and object references, ensuring all dead objects are collected in a single cycle. |
| **Conservative** | The GC lacks exact type metadata, making conservative guesses about stack values. This can lead to uncollected garbage and lower efficiency. |
| **Moving** | The collector moves surviving objects to different memory addresses. Java's lack of raw pointer access makes it well-suited for moving collectors. |
| **Compacting** | At the end of the cycle, surviving objects are moved into a single contiguous region (usually at the start of the memory pool), leaving a single connected free space and avoiding memory fragmentation. |
| **Evacuating** | All live objects are moved from the source memory region to a totally different region, leaving the original region completely empty and defragmented. |

These terms are standard across different runtimes, though some platforms may swap "concurrent" and "parallel" or refer to "moving" as "copying."

Also, "concurrency" is best understood as a spectrum rather than a binary state. Depending on the collector, a larger or smaller part of the collection work is done concurrently with the application threads.

---

## Introducing the HotSpot Runtime

To understand how garbage collection works on HotSpot, we must examine the internal design of the JVM.

First, recall that Java has only two types of values:
* **Primitive types** (e.g., `byte`, `int`, `char`)
* **Object references**

Java programmers often speak of "objects," but unlike C++, Java gives no raw memory address dereferencing. Instead, Java relies entirely on the dot (`.`) offset operator to access fields and call methods on object references.

Also, Java's method call behavior is strictly **call-by-value**. For object references, the "value" copied and passed is the memory address of the object in the heap.

### Representing Objects at Runtime: Oops

HotSpot represents Java objects at runtime using a C++ structure called an **oop** (ordinary object pointer). An `oop` is a real pointer in the C/C++ sense. These pointers live in local variables within a method's stack frame and point directly to the memory address of the object in the Java heap.

> [!NOTE]
> HotSpot does not use operating system-level system calls to manage the Java heap actively. Instead, it manages its memory pool completely in user space. As we will discuss in Chapter 5, this allows us to find performance bottlenecks using simple, high-level observables.

The `oop` family includes several distinct data structures. Instances of a Java class are represented as `instanceOop` structures, while Java arrays are represented as `arrayOop` structures.

#### Anatomy of an instanceOop

Every object in the Java heap must begin with an **object header**. For a typical `instanceOop`, this header is composed of two machine words:

1. **Mark Word**: The first word of the header. It points to instance-specific metadata and holds runtime state such as synchronization locks, identity hashcodes, and GC generational age.
2. **Klass Word**: The second word of the header. It points to class-wide metadata (`klass`), which lives outside the main Java heap in the Metaspace (part of the JVM process's native C heap). Because these class structures live outside the Java heap, they do not need object headers.

> [!NOTE]
> The `k` at the start of `klass` is used to distinguish the internal virtual machine-level `klass` structure from a Java-level `java.lang.Class` object instance—they are completely different structures.

Figure 4-2 shows this difference. On the top left is an `Entry` object (similar to a `Map.Entry` in a `HashMap`), and on the top right is the matching `Entry.class` object (obtained by `getClass()`). Below the dotted line are the internal `klass` metadata structures:

```java
record Entry<K,V> (int hash, K key, V value, Entry<K,V> next) {}
```

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//355c01bf-35e5-40d6-a30e-81089be1b893/markdown_0/imgs/img_in_image_box_143_110_864_466.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A02Z%2F-1%2F%2F2c55bf7592b6a64cf5f5ea8ab8dd72c24dc07ebf98316cdfcf53df4a3198f9c9" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 4-2. Klass and Class objects</div> </div>

The `klass` structure contains the class's **virtual function table** (the `vtable`), which is used for dynamic method dispatch. In contrast, the Java `Class` object contains arrays of references to `Method` and `Field` objects used for reflective access. We will study this further in Chapter 6 when discussing JIT compilation.

### Compressed Oops

On a modern 64-bit architecture, an `oop` is a 64-bit native machine pointer. While this allows using huge amounts of memory, it also wastes a lot of space compared to old 32-bit pointers.

To reduce this overhead, HotSpot provides a feature called **compressed oops** via the JVM flag:

```shell
-XX:+UseCompressedOops
```

This flag is enabled by default for 64-bit heaps under 32 GB. When active, the JVM compresses the following references to 32 bits:
* The `klass` word in every object header.
* Any instance fields of reference type.
* Every element of an object array (`objArrayOop`).

With compressed oops active, a HotSpot object header is composed of:
* A full-size native **Mark Word** (64 bits).
* A compressed **Klass Word** (32 bits).
* A **Length Word** (32 bits) if the object is an array.
* A 32-bit padding gap (if required for 8-byte memory alignment).

The instance fields directly follow the header. The resulting memory layout is shown in Figure 4-3.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//355c01bf-35e5-40d6-a30e-81089be1b893/markdown_1/imgs/img_in_image_box_142_169_864_730.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A03Z%2F-1%2F%2F75f60553ee2bdd15bf9b3772363c69a4fb5fa7eb2bc137098cc60f8818b052c1" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 4-3. Compressed oops</div> </div>

> [!NOTE]
> In the past, extremely latency-sensitive applications would sometimes turn off compressed oops to avoid the decompression CPU cost, giving up 10%–50% of their heap capacity. For modern workloads, however, manually disabling this feature is almost always a bad practice—a classic example of the **Fiddling with Switches** antipattern (see Appendix B).

Because Java arrays are objects, they are also represented as `oops` in memory. This explains why they contain a third header word to store the array's length. It also explains why Java array indices are historically limited to 32-bit integers: Java was originally designed for 32-bit architectures, and storing a 32-bit length in the header was a natural fit.

This built-in length metadata removes a major class of buffer overflow vulnerabilities and programming errors common in C and C++, where arrays lack size metadata and must be passed alongside separate length variables.

### The Low-Level oop Rules

At the virtual machine level, the managed runtime enforces strict rules:
* A Java reference can only point directly to the start of an `oop` (or be `null`). It cannot point to random memory offsets.
* The memory address pointed to by a Java reference must begin with a mark word, followed by a klass word.
* An internal `klass` metadata structure and a Java-level `Class<?>` object are distinct; the former lives in native Metaspace, and cannot be directly assigned to a Java-level variable.

The C++ source code defining the `oop` class hierarchy lives in the OpenJDK source tree under `src/hotspot/share/oops/`. As of Java 22, the core inheritance hierarchy is structured as follows:

```text
oop (abstract base)
    instanceOop (instance objects)
        stackChunkOop
    arrayOop (array abstract base)
        objArrayOop (array of object references)
        typeArrayOop (array of primitive types)
```

This model of using two pointers—one for instance-specific state and one for class-level metadata—is a common design pattern shared by many modern virtual machines and dynamic language runtimes.

### GC Roots

In GC literature, **GC roots** are the essential "anchor points" of memory. They are defined as active, known references starting from outside a target memory pool and pointing into it. This distinguishes them from internal pointers, which start and end within the same memory pool.

We saw a simple example of a GC root in Figure 4-1. In a production JVM, the main types of GC roots include:
* **Stack frames**: Local variables and active parameters in running thread stacks.
- **Java Native Interface (JNI)**: Global and local native C/C++ references pointing to Java objects.
* **Registers**: Native CPU registers currently holding object references. $ ^{3} $
* **Code roots**: References living within the JVM's code cache (compiled JIT code).
* **Globals**: Static fields or system-level references stored globally by the JVM.
* **Class metadata**: Loaded classes and their associated classloaders.

Simply put, the most common example of a GC root is any local reference variable in a running method that points to an object on the heap.

---

## Allocation and Lifetime

The garbage collection behavior of any Java application is primarily driven by two factors:

* **Allocation rate**
* **Object lifetime**

The **allocation rate** is the amount of memory allocated for newly created objects over time, usually measured in megabytes per second (MB/s). While the JVM does not expose this metric directly by default, it can be estimated using tools like JFR (though turning on high-resolution allocation profiling can introduce a slight performance overhead).

In contrast, **object lifetime** is far more difficult to measure or estimate. Indeed, the difficulty of manually tracking and predicting object lifetimes in large systems is a primary argument against manual memory management. Because of this complexity, object lifetime is even more fundamental to GC performance than the allocation rate.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//355c01bf-35e5-40d6-a30e-81089be1b893/markdown_3/imgs/img_in_image_box_176_1008_252_1108.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A06Z%2F-1%2F%2F8a9308fdee8096d4b9c37ab0bbacfa2202168739e8927006c31915a079ec1103" alt="Image" width="7%" /></div>

Garbage collection is fundamentally a system of "memory recovery and reuse." The main assumption is that because most objects are short-lived, the same physical memory addresses can be reclaimed and reused repeatedly. Without this assumption, garbage collection would be mathematically impossible to sustain.

As we will see in Chapter 5, the design trade-offs of different garbage collectors are heavily driven by these lifetime and allocation dynamics.

### The Weak Generational Hypothesis

The JVM's memory management design relies heavily on an observed fact of software systems known as the **Weak Generational Hypothesis (WGH)**:

> **The Weak Generational Hypothesis (WGH)**
> The distribution of object lifetimes in the JVM and similar managed runtimes is bimodal: the great majority of objects die very young, while a much smaller secondary group lives for a much longer time.

This relationship is shown in Figure 4-4.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//355c01bf-35e5-40d6-a30e-81089be1b893/markdown_4/imgs/img_in_chart_box_271_494_865_796.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A07Z%2F-1%2F%2F9ef1fec650f81181ea93d1f9c7070d18bf331e876d79f82183249e901be5da7b" alt="Image" width="58%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 4-4. Weak generational hypothesis</div> </div>

This observation leads to a clear design conclusion: heap memory should be partitioned so that short-lived objects can be collected quickly and cheaply, while long-lived objects are segregated to prevent them from being repeatedly scanned.

This division results in a generational heap composed of two main areas: a young generation for short-lived allocations and an old (or tenured) generation for long-lived data. These areas are collected separately by young collections and full collections, respectively.

A key optimization is using an evacuating collector on the recently allocated region—called **Eden**. During a young collection, the JVM finds live objects in Eden and moves them to the long-lived space, compacting them in the process. The entire Eden space is then instantly reclaimed in a single operation, as shown in Figure 4-5.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//dda2f2f1-5ac3-4d8d-b7f1-956ee8ec8ffa/markdown_0/imgs/img_in_image_box_276_148_722_427.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A03Z%2F-1%2F%2F54943a375d0e1541c2447ee1bfdfb6216a55043216ac186a3d62b8d00c9c9e30" alt="Image" width="44%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 4-5. Simple generational heap</div> </div>

> [!TIP]
> A major benefit of a generational heap is that **dead objects cost nothing to reclaim**. The collector only traces and moves live objects; dead objects are simply ignored and overwritten when the space is cleared.

HotSpot uses several optimizations to exploit the bimodal lifetime distribution of the WGH. Let's examine these techniques.

---

## Production GC Techniques in HotSpot

### Thread-Local Allocation Buffers (TLABs)

Eden is the allocation area where almost all new objects are created. Because the WGH shows that most of these objects will die young, managing Eden efficiently is essential to system throughput.

To increase allocation speed, HotSpot divides Eden into multiple private buffers and allocates one to each application thread. These are called **thread-local allocation buffers (TLABs)**. Because a thread has exclusive control over its TLAB, it can allocate objects without acquiring global locks or coordinating with other threads.

HotSpot dynamically sizes TLABs based on thread behavior. A thread allocating memory rapidly is granted larger TLABs to reduce buffer synchronization overhead.

As a result, object allocation on HotSpot is an $O(1)$ operation. The thread simply increments a local pointer to reserve space for the new object and updates the "next free" pointer—a highly optimized operation that compiles to a single CPU instruction.

This design is shown in Figure 4-6, where each thread allocates independently within its chosen buffer:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//dda2f2f1-5ac3-4d8d-b7f1-956ee8ec8ffa/markdown_1/imgs/img_in_image_box_145_439_863_757.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A04Z%2F-1%2F%2Fd1876cdd04e694a14785351529a7472c4d57ab20f6006fb21fac97e318ff28dc" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 4-6. Thread-local allocation</div> </div>

When a thread fills its TLAB, it requests a new buffer from Eden. A young GC is triggered when Eden has no more free space to allocate as TLABs.

### Hemispheric survivor spaces

To further improve young collections, HotSpot uses a hemispheric evacuating collector within the young generation. It introduces two smaller, equal-sized areas called survivor spaces (formerly named Survivor 1 and Survivor 2, or To and From).

These survivor spaces work as temporary aging areas for objects that survive their first few young GCs but are not yet proven to be truly long-lived. This prevents short-lived objects from prematurely filling the old generation, reducing the frequency of costly full GCs.

The survivor spaces work under two strict rules:
1. One survivor space is marked as active and holds aging objects, while the other remains completely empty.
2. During a young collection, live objects from Eden and the active survivor space are moved and compacted into the empty survivor space. The roles of the survivor spaces then swap, and the original spaces are cleared.

While this approach keeps half of the survivor capacity empty and unused at any given time, it is highly effective because survivor spaces are configured to be quite small compared to Eden. Figure 4-7 shows a view of this layout in `VisualGC`.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//dda2f2f1-5ac3-4d8d-b7f1-956ee8ec8ffa/markdown_2/imgs/img_in_image_box_145_500_857_1035.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A04Z%2F-1%2F%2F93aecfc901df15d7a2faa399d9f8ae120b0494002d0ac6ccaaab1d0525401457" alt="Image" width="70%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 4-7. The VisualGC plug-in</div> </div>

The `VisualGC` plug-in for `VisualVM` is an excellent tool for initial GC debugging, allowing developers to easily track memory movement and the cycling of survivor spaces. However, for deep analysis, raw GC logs and JFR data provide far more precise details.

### The Classic HotSpot Heap

In summary, the classic HotSpot heap is structured as follows:
* It tracks the **generational age** (tenure) of each object—i.e., the number of collection cycles it has survived.
* Except for very large allocations, all new objects are created in **Eden**.
* Objects surviving a young collection are moved to the active **survivor space**.
* Objects that survive a set number of cycles (the tenuring limit) are promoted to the **old (tenured) generation**, which holds long-lived data.

This layout is shown in Figure 4-8.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//dda2f2f1-5ac3-4d8d-b7f1-956ee8ec8ffa/markdown_3/imgs/img_in_image_box_141_709_778_1026.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A05Z%2F-1%2F%2F064e64050395d055897220606e48dbe16859d017418a363f3a7734c6c4ea7e3c" alt="Image" width="63%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 4-8. HotSpot's heap</div> </div>

Generational collection needs tracking cross-generational pointers—particularly, pointers starting in the old generation and pointing to objects in the young generation. Without this optimization, a young collection would have to scan the entire old generation to find all live young objects, negating the performance benefits of a generational design.

> [!NOTE]
> **Weak Generational Hypothesis Corollary**
> "There are relatively few references from old to young objects" is sometimes stated as a corollary of the weak generational hypothesis.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//dda2f2f1-5ac3-4d8d-b7f1-956ee8ec8ffa/markdown_4/imgs/img_in_image_box_176_187_253_288.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A05Z%2F-1%2F%2F17bdd122fcb3675522008a56ad254d71d4bc361e68a4d9b44e5fe1af938f58c3" alt="Image" width="7%" /></div>

To track these cross-generational references, HotSpot uses a card table. The card table is a native byte array where each byte represents a 512-byte block of heap memory in the old generation.

Later on, we will examine remembered sets, which are a more complex version of the card table.

When an old-generation object is modified to point to a young-generation object, the JVM runs a write barrier to mark the matching card table entry as dirty:

```c
cards[*oop >> 9] = 0;
```

Here, `0` represents a dirty card, and shifting the pointer right by 9 bits (`>> 9`) maps the address to its matching 512-byte card index. During a young collection, the GC scans only the dirty cards in the card table rather than the entire old generation.

Note that this contiguous layout of young and old generations is a legacy design. Modern regional collectors, such as G1 (discussed in Chapter 5), do not need generations to be stored contiguously. Instead, they partition the heap into thousands of small, separated areas that are dynamically assigned young or old status.

---

## The Parallel Collectors

In Java 8 and earlier, the default JVM garbage collectors were the parallel collectors. These collectors are fully stop-the-world (STW) and are deeply tuned to increase application throughput. When a collection is triggered, they stop all application threads and use all available CPU cores to reclaim memory as quickly as possible.

The core parallel collectors include:
* **Parallel GC**: The simplest collector for the young generation.
* **ParNew**: A variant of Parallel GC tuned to work with the legacy Concurrent Mark Sweep (CMS) collector.
* **ParallelOld**: The parallel collector for the old (tenured) generation.

All parallel collectors share a common philosophy: use all available CPU resources to find and reclaim memory fast with minimal tracking overhead.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//47ce3866-60ff-4ebf-816e-a2e6013ef15e/markdown_0/imgs/img_in_image_box_176_844_252_944.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A10%3A54Z%2F-1%2F%2Fde966e8d3052a4ef317f34499725fe5926d1b0502174c90b7e1b3f17acd3e0fd" alt="Image" width="7%" /></div>

> [!IMPORTANT]
> From Java 17 onward, the **Concurrent Mark Sweep (CMS)** collector has been removed. There is now only one Parallel GC implementation, made of the young and old parallel collections.

### Young Parallel Collections

A young collection is triggered when a thread tries to allocate an object but Eden has no free space to allocate a new TLAB. At this point, the JVM must stop all application threads. Because Java threads allocate continuously, if one thread is stopped due to lack of memory, all other threads will soon halt as well.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//47ce3866-60ff-4ebf-816e-a2e6013ef15e/markdown_1/imgs/img_in_image_box_176_303_253_406.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A10%3A55Z%2F-1%2F%2F3c728ab216e6045c19261c856b65d15ea4143c66a4948b072c3dfc8f6e376ff1" alt="Image" width="7%" /></div>

> [!NOTE]
> Threads can also allocate outside of TLABs (for example, for large blocks of memory). Keeping the rate of non-TLAB allocation low is highly desirable. Too many allocations of short-lived large objects will bypass TLABs and force extra full GCs, which are far more costly than young collections.

Once all application threads are stopped, the collection works as follows:

1. **Marking**: The GC scans the young generation (Eden and the active survivor space) to find all live objects. It uses GC roots and the card table (to find references starting in the old generation) as entry points.
2. **Evacuation**: Live objects are moved to the empty survivor space, and their generational age is increased by 1.
3. **Reclamation**: Eden and the previously active survivor space are marked as empty.
4. **Resumption**: The application threads are restarted, and the JVM resumes allocating TLABs.

This process is shown in Figures 4-9 and 4-10.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//47ce3866-60ff-4ebf-816e-a2e6013ef15e/markdown_1/imgs/img_in_image_box_245_731_762_1058.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A10%3A55Z%2F-1%2F%2F42bf127db98949ab1e86bbab799e1ccf1c20695cb3bf2d08662da64691edf69d" alt="Image" width="51%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 4-9. Collecting the young generation</div> </div>

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//47ce3866-60ff-4ebf-816e-a2e6013ef15e/markdown_2/imgs/img_in_image_box_166_109_842_485.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A10%3A56Z%2F-1%2F%2F29e79b05035206268f8e00a372cc301c0479d2e2bbb7fd96afa2fffa6990af0d" alt="Image" width="67%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 4-10. Evacuating the young generation</div> </div>

By only touching live objects, this approach exploits the WGH, keeping young collection pauses highly efficient and brief.

### Old Parallel Collections

The **ParallelOld** collector manages the old generation. While it was the default collector up to Java 8, it can still outperform newer collectors like G1 in workloads that favor maximum throughput over low latency. $ ^{4} $

> [!NOTE]
> As we will see in Chapter 5, the standard garbage collector for Java 11+ is the **G1** collector.

While ParallelOld shares main concepts with young parallel collection, its behavior differs. Young collection is hemispheric and moves objects between separate spaces. In contrast, the old generation is a single contiguous memory space.

Because there is no "target" space to move to, ParallelOld performs in-place compaction. It finds live objects and moves them to the beginning of the old generation space, compacting them to fill gaps left by dead objects. This achieves high memory density and avoids fragmentation.

The difference between hemispheric evacuation and in-place compaction is shown in Figure 4-11.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//47ce3866-60ff-4ebf-816e-a2e6013ef15e/markdown_3/imgs/img_in_image_box_144_286_763_639.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A10%3A56Z%2F-1%2F%2F5df3360ac721f13aa1e39e00da7aa2ddf4d3bc1b3ad8804a6677b8e22db8e9ad" alt="Image" width="61%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 4-11. Evacuating collection</div> </div>

The young and old generations work very differently because they have different objectives. The young generation is highly dynamic, experiencing rapid allocation and complete clearing on nearly every cycle. The old generation, however, is relatively static. Except for rare large objects allocated directly in tenured space, it only changes when objects are promoted from the young generation or compacted during a full collection.

### Serial and SerialOld

The **Serial** and **SerialOld** collectors are legacy collectors that are rarely used in modern systems.

While they work similarly to the parallel collectors, they use only a single CPU core to do GC. They are not concurrent and are fully stop-the-world.

On multicore systems, using these collectors is highly inefficient, as all but one CPU core will remain idle during collection, causing long pause times for no benefit. They should not be used unless explicitly configured for single-core resource-constrained environments (see Chapter 9 for details about containers).

### Limitations of Parallel Collectors

The parallel collectors manage whole generations in a single pass. While highly efficient, this design has significant limitations:

1. **Fully Stop-the-World**: All application threads must stop. For young collections, this is rarely an issue because young generations are quite small and the WGH ensures very few objects survive. Marking time is proportional to the number of live objects, meaning dead objects are never touched.

   > [!NOTE]
   > The design of the young parallel collectors is such that dead objects are never touched. So, the length of the marking phase is proportional to the (small) number of living objects rather than the size of the heap.

   For a typical 2 GB heap, a young parallel collection pause is usually short—often just a few milliseconds or even submillisecond.
2. **Poor Scalability with Heap Size**: Collecting the old generation is a different story. The old generation is seven times larger than the young generation by default. More importantly, because old objects are long-lived, a large proportion of them will survive.

   Because marking time scales with live objects and compaction scales with the total used space, ParallelOld pause times scale roughly linearly with the size of the heap. As application heaps grow to tens or hundreds of gigabytes, parallel full GC pauses become unacceptably high.

Newcomers to GC theory often suggest simple changes to mark-and-sweep algorithms to eliminate STW pauses. However, GC has been a mature field of research for over 40 years. Production collectors are highly optimized, and simple modifications are unlikely to provide significant benefits.

As we will see in Chapter 5, concurrent collectors solve this by running concurrently with application threads, but they introduce their own complex trade-offs.

For example, while TLABs improve allocation, they do not help during collection. Consider this code:

```java
public static void main(String[] args) {
    int[] anInt = new int[1];
    anInt[0] = 42;
    Runnable r = () -> {
        anInt[0]++;
        System.out.println("Changed: " + anInt[0]);
    };
    new Thread(r).start();
}
```

The array `anInt` is allocated from the main thread's private TLAB, but it is passed to a new thread. Thus, the thread-local privacy of a TLAB is violated the moment allocation completes. Because Java allows threads to share objects arbitrarily, the collector must trace the whole heap across all thread stacks, which represent primary sources of GC roots.

---

## The Role of Allocation

Java GC is triggered on demand—particularly, when an allocation request cannot be met because a memory area is full. It does not run on a fixed schedule.

This on-demand, unpredictable nature makes GC events difficult to analyze using standard time-series analysis techniques, which usually assume evenly spaced data points. $ ^{5} $ Instead, we must treat GC events as single events and aggregate them to derive meaningful performance metrics.

To demonstrate how allocation rates and object lifetimes drive GC behavior, consider this very simplified case study of an application with a fixed-size heap:

### Case Study: Heap Configuration

| Heap Area | Size |
| :--- | :--- |
| **Overall** | 2 GB |
| **Old generation** | 1.5 GB |
| **Young generation** | 500 MB |
| **Eden** | 400 MB |
| **SS1 (Survivor Space 1)** | 50 MB |
| **SS2 (Survivor Space 2)** | 50 MB |

### Steady-State Metrics

| Metric | Values |
| :--- | :--- |
| **Allocation rate** | 100 MB/s |
| **Young GC time** | 2 ms |
| **Full GC time** | 100 ms |
| **Object lifetime** | 200 ms |

At this allocation rate, the 400 MB Eden space fills every 4 seconds, triggering a young GC:

* **GC0 (at 4s)**: Eden is full. The GC runs. Objects allocated in the last 200 ms are still alive and must be moved. This shows 20 MB of live data ($100\text{ MB/s} \times 0.2\text{ s}$). The GC moves this 20 MB to SS1.
  * *State*: `Eden` is cleared. `SS1` holds 20 MB. `Old` is empty.
* **GC1 (at 8.002s)**: Eden fills again. The GC runs. The 20 MB of objects in SS1 are now older than 200 ms and have died, so they require no relocation. The 20 MB of new live objects in Eden are moved to SS2.
  * *State*: `Eden` is cleared. `SS2` holds 20 MB. `SS1` is empty. `Old` remains empty.
* **GC2 (at 12.004s)**: The cycle repeats, moving the new 20 MB of live objects back to SS1.
  * *State*: `Eden` is cleared. `SS1` holds 20 MB. `SS2` is empty. `Old` remains empty.

In this idealized model, no objects ever survive long enough to cross the tenuring limit, keeping the old generation completely empty.

In reality, object lifetimes follow a distribution. Due to this variation, a small proportion of objects will always survive long enough to be promoted to the old generation.

### Simulating Allocation and Lifetime

We can simulate this behavior using a simple program that allocates objects with a bimodal lifetime distribution. The simulator takes several parameters: object size factors (`x` and `y`), allocation rate (`mbPerSec`), short-lived object lifetime (`shortLivedMs`), and thread count (`nThreads`).

```java
import java.util.concurrent.Executor;
import java.util.concurrent.Executors;

public class ModelAllocator implements Runnable {
    private volatile boolean shutdown = false;

    private double chanceOfLongLived = 0.02;
    private int multiplierForLongLived = 20;
    private int x = 1024;
    private int y = 1024;
    private int mbPerSec = 50;
    private int shortLivedMs = 100;
    private int nThreads = 8;
    private Executor exec = Executors.newFixedThreadPool(nThreads);

    // ... Omitting main() and other startup/parameter-setting code ...

    @Override
    public void run() {
        final int mainSleep = (int) (1000.0 / mbPerSec);

        while (!shutdown) {
            for (int i = 0; i < mbPerSec; i++) {
                ModelObjectAllocation to =
                    new ModelObjectAllocation(x, y, lifetime());
                exec.execute(to);
                try {
                    Thread.sleep(mainSleep);
                } catch (InterruptedException ex) {
                    shutdown = true;
                }
            }
        }
    }

    // Simple function to model the weak generational hypothesis
    // Returns the expected lifetime of an object - usually this
    // is very short, but there is a small chance of being "long-lived"
    public int lifetime() {
        if (Math.random() < chanceOfLongLived) {
            return multiplierForLongLived * shortLivedMs;
        }
        return shortLivedMs;
    }
}
```

The allocator is paired with a mock class representing the individual allocations:

```java
public class ModelObjectAllocation implements Runnable {
    private final int[][] allocated;
    private final int lifetime;

    public ModelObjectAllocation(final int x, final int y, final int liveFor) {
        allocated = new int[x][y];
        lifetime = liveFor;
    }

    @Override
    public void run() {
        try {
            Thread.sleep(lifetime);
            System.err.println(System.currentTimeMillis() + " : "
                               + allocated.length);
        } catch (InterruptedException ex) {
            // Intentionally ignored
        }
    }
}
```

When seen in `VisualVM`, this simulation shows the classic **sawtooth pattern** typical of healthy heap usage, as shown in Figure 4-12.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//92e0120d-4a21-456e-aa93-ee97a0b4f8dd/markdown_4/imgs/img_in_image_box_146_112_862_651.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A10%3E58Z%2F-1%2F%2F8b5bf9fe34d1e65a3bc63ede82c931411af6207c170bab7e9784c3cc1a9259ee" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 4-12. Simple sawtooth pattern</div> </div>

> [!NOTE]
> Amazon provides the **HyperAlloc** tool as part of its **Heapothesys** project. This benchmarking tool is a synthetic workload designed to mimic fundamental application characteristics that affect garbage collector latency.

### The Impact of Bursty Allocation: Premature Promotion

In the real world, allocation rates are rarely constant; they are often highly bursty. Consider what happens when our steady-state application experiences a sudden traffic spike:

* **Steady State**: Allocating 100 MB/s.
* **Traffic Spike**: Allocation rate jumps to 1 GB/s for 1 second.
* **Recovery**: Returns to 100 MB/s.

During the spike, the 400 MB Eden space fills in just 400 ms. A young GC is triggered:

* **GC0 (at 2.2s)**: 200 MB of objects have been allocated during the last 200 ms of the spike, meaning they are younger than the 200 ms lifetime limit and are still live.
* **The Problem**: The GC tries to move these 200 MB of live objects to the active survivor space. However, the survivor space size is only 50 MB.
* **The Result**: Because the survivor space cannot hold the live objects, the JVM must promote the remaining 150 MB of objects directly to the old generation.

```text
GC0 @ 2.2s: 100 MB Eden → Tenured (100 MB)
```

This event is called **premature promotion**. Even though these promoted objects are short-lived and will die a few milliseconds later, they are now trapped in the old generation. They cannot be recovered until a full GC cycle runs, increasing heap use and speeding up the path toward an expensive full GC.

```text
GC1 @ 2.602 s: 200 MB Eden → Tenured (300 MB)
```

```text
GC2 @ 3.004 s: 200 MB Eden → Tenured (500 MB)
```

```text
GC3 @ 7.006 s: 20 MB Eden → SS1 (20 MB) [+ Tenured (500 MB)]
```

As this sequence shows, GC runs as needed. High allocation rates trigger more frequent GCs, and sudden spikes force objects to be promoted early. Managing and reducing premature promotion is a primary objective of JVM performance tuning, which we will cover in Chapter 5.

---

## Summary

Garbage collection has been a central topic of JVM engineering and community discussion since Java's start. In this chapter, we studied the basic concepts needed to work well with the JVM's GC subsystem:

* **Mark-and-sweep collection** and the mechanics of object tracing.
* HotSpot's internal **oop** and **klass** runtime representations.
* The **Weak Generational Hypothesis** and its design implications.
* The structure of the **classic HotSpot heap** (Eden, survivor spaces, and tenured generation).
* The **parallel and serial collectors**, their execution phases, and their limitations.
* The critical role of **allocation rates** and the mechanics of **premature promotion**.

In Chapter 5, we will examine modern garbage collection—including concurrent collectors, HotSpot's standard **G1** collector, and low-latency alternatives like **Shenandoah** and **ZGC**.

Several of these concepts—particularly allocation rates and premature promotion—are essential to understanding modern GC tuning, and we will refer back to them often.
