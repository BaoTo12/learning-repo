# Hardware and Operating Systems

Why should Java developers care about hardware?

For many years the computer industry has been driven by **Moore's law**, an idea made by Intel founder Gordon Moore about long-term trends in processor capability. The law (really an observation or guess) can be framed in a variety of ways, but one of the most common is:

> **Moore's Law**
> The number of transistors on a mass-produced chip roughly doubles every 18 months.
> — *Moore's law (informally)*

This trend represents a very fast increase in computer power over time. It was originally stated in 1965, representing an amazing long-term trend, unequaled in the history of computer science. The effects of Moore's law have been transformational in almost all areas of the modern world. The death of Moore's law has been repeatedly announced for decades. However, there are very good reasons to believe that, for all practical purposes, this progress in chip technology has finally ended:

> Transistors can only get so small and, eventually, the more permanent laws of physics get in the way. Already transistors can be measured on an atomic scale, with the smallest ones commercially available only 3 nanometers wide, barely wider than a strand of human DNA (2.5nm). While there's still room to make them smaller (in 2021, IBM announced the successful creation of 2-nanometer chips), such progress has become too expensive and slow, making future gains doubtful. And there's still the physical limitation in that wires can't be thinner than atoms, at least not with our current understanding of material physics.
>
> — Audrey Woods, *“The Death of Moore’s Law: What it means and what might fill the gap going forward”*

Hardware has become increasingly complex to make good use of the "transistor budget" available in modern computers. The software platforms running on that hardware have also increased in complexity to use these new capabilities. More horsepower is available, but engineers must do more work in software to use it, meaning the delivered performance is often reduced by this overhead.

Software applications now are in almost every part of global society. This software is becoming increasingly complex, as application developers take advantage of the available performance.

Or, to put it another way:

> **Software is eating the world.**
> — *Marc Andreessen*

As we will see, Java has been a major winner of the increasing amount of computer power. The design of the language and runtime has been well-suited to use this trend in processor capability. However, the truly performance-minded Java programmer needs to understand the principles and technology that support the platform to best use the available resources.

This is especially important because the development of cloud native applications has somewhat changed how we view performance. But before turning to those subjects, let's take a quick look at modern hardware and operating systems, as an understanding of those subjects will help with everything that follows.

---

## Introduction to Modern Hardware

Many university courses on hardware architectures still teach a simple-to-understand, classical view of hardware. This simplified logical view focuses on a simple register-based machine, with arithmetic, logic, and load and store operations. Since the 1990s, the world of the application developer has focused mostly on the Intel x86/x64 architecture (and more recently, the rise of the ARM chip).

However, this is an area of technology that has changed completely. The simple mental model of a processor's operation is now incorrect, and simple reasoning based on it is likely to lead to completely wrong conclusions.

To help address this, we will discuss several of these improvements in CPU technology. We will start with memory behavior, as this is by far the most important to a modern Java developer.

---

## Memory

As Moore's law advanced, the rapidly growing number of transistors was first used for faster and faster clock speeds. The reasons for this are obvious: faster clock speed means more instructions completed per second. So, processor speeds have grown hugely, and the 2+ GHz processors we have today are hundreds of times faster than the original 4.77 MHz chips found in the first IBM PC.

However, increasing clock speeds uncovered another problem: faster chips require a faster stream of data to act upon. As Figure 7-1 shows, $ ^{1} $ over time, main memory could not keep up with the processor core's demand for new data.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//2bc0d1d2-4655-4c75-82ea-9af074b1eaba/markdown_4/imgs/img_in_chart_box_144_386_864_768.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A34Z%2F-1%2F%2Fbcc3709bde6f14829aa2ad67926d90034231a08a540833993b213a3c7f7d59b0" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 7-1. Gap between processor and memory performance capabilities (Hennessy and Patterson, 2011)</div> </div>

This results in a problem: if the CPU is waiting for data, then faster cycles do not help, as the CPU will just have to remain idle until the required data arrives.

---

## Memory Caches

To solve this problem, **CPU caches** were introduced. These are memory areas on the CPU that are slower than CPU registers but faster than main memory. The idea is for the CPU to fill the cache with copies of frequently accessed memory locations rather than repeatedly having to access main memory.

Modern CPUs have several layers of cache, with the most frequently accessed caches located close to the processing core:
- **L1 Cache (Level 1)**: Closest to the CPU, fastest, and smallest.
- **L2 Cache (Level 2)**: Slightly larger and slower than L1.
- **L3 Cache (Level 3)**: Shared across some or all of the execution cores on the CPU.

Typically, each execution core has a dedicated, private L1 and L2 cache, while the L3 cache is shared. The effect of these caches in speeding up access times is shown in Figure 7-2. $ ^{2} $

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//56487fdf-6a28-4a2e-856f-1ef6131af725/markdown_0/imgs/img_in_chart_box_143_459_865_792.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A04Z%2F-1%2F%2Ff690de82f4f7e007bb7a26bdced10ab06d5ec07365d82e25a8e7cbf8d1a6df7e" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 7-2. Access times for various types of memory</div> </div>

This cache architecture improves access times and keeps the core supplied with data to operate on. Due to the clock speed versus access time gap, more of the transistor budget is devoted to caches on a modern CPU.

The resulting design can be seen in Figure 7-3. This shows the private L1 and L2 caches for each CPU core and the shared L3 cache. Main memory is accessed over the Northbridge component, and crossing this bus causes the large drop in access speed to main memory.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//56487fdf-6a28-4a2e-856f-1ef6131af725/markdown_1/imgs/img_in_image_box_142_110_864_452.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A05Z%2F-1%2F%2F944ba6f2b336c33d220c8131167dd6be2c6146151b0a722dc6cdcba29684a7dc" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 7-3. Overall CPU and memory architecture</div> </div>

Although a caching architecture hugely improves processor throughput, it introduces a new set of problems, including determining how memory is fetched into and written back from the cache. The solutions to this problem are usually referred to as **cache consistency protocols**.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//56487fdf-6a28-4a2e-856f-1ef6131af725/markdown_1/imgs/img_in_image_box_176_642_253_743.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A05Z%2F-1%2F%2Fc4335a93c97b8729d61f61fcc1afb9427f280d8d992500c0cd2df22a43223eb5" alt="Image" width="7%" /></div>

> [!NOTE]
> There are other problems that crop up when this type of caching is applied in a parallel processing environment, as we will see later in this book.

At the lowest level, a protocol called **MESI** (and its variants) is commonly found on a wide range of processors. It defines four states for any cache line (usually 64 bytes):

- **Modified**: The cache line is valid but has been modified and is different from main memory (not yet flushed).
- **Exclusive**: The cache line matches main memory and is present only in this private cache.
- **Shared**: The cache line matches main memory and may be present in other private caches.
- **Invalid**: The cache line is invalid and may not be used; it will be dropped as soon as practical.

The idea of the protocol is that multiple processors can simultaneously be in the **Shared** state. However, if a processor transitions to **Exclusive** or **Modified**, this forces all other processors' copies of that line into the **Invalid** state. This is shown in Table 7-1, where `Y` indicates a permitted state combination between two processors, and `-` represents a combination that is not permitted.

<div style="text-align: center;"><div style="text-align: center;">Table 7-1. MESI allowable states between processors</div> </div>

| | M | E | S | I |
| :---: | :---: | :---: | :---: | :---: |
| **M** | - | - | - | Y |
| **E** | - | - | - | Y |
| **S** | - | - | Y | Y |
| **I** | Y | Y | Y | Y |

The protocol works by sending a signal that a processor wants to change state. An electrical signal is sent across the shared memory bus, making the other processors aware. The full logic for the state transitions is shown in Figure 7-4.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//56487fdf-6a28-4a2e-856f-1ef6131af725/markdown_2/imgs/img_in_image_box_143_408_862_722.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A06Z%2F-1%2F%2F332eb45457629290345ba17fa13d86fd171b5ebf2fbd95aaff65a8bdcdf0ae78" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 7-4. MESI state transition diagram</div> </div>

Originally, processors wrote every cache operation directly into main memory. This was called **write-through** behavior, but it was highly inefficient and required a large amount of memory bandwidth. More recent processors implement **write-back** behavior, where traffic to main memory is significantly reduced by writing only modified (dirty) cache blocks back to memory when they are evicted or replaced.

The overall effect of caching technology is to greatly increase the speed at which data can be read from or written to memory, expressed in terms of **memory bandwidth**. The burst rate, or theoretical maximum, is calculated using several factors:
- Clock frequency of the memory
- Width of the memory bus (usually 64 bits)
- Number of interfaces (usually two in modern machines)

This is multiplied by two in the case of **DDR RAM** (Double Data Rate, which communicates on both edges of a clock signal).

Applying this formula to 2024 commodity hardware gives a theoretical maximum write speed of 17+ GB/s per core, with an overall system bandwidth of 70–90 GB/s. $ ^{3} $ In practice, this could be limited by many other factors in the system. As it stands, this gives a useful baseline to evaluate how close hardware and software can get to physical limits.

Let's write some simple code to exercise the cache hardware, as seen in Example 7-1.

##### Example 7-1. Caching example

```java
public class Caching {
    private final int ARR_SIZE = 2 * 1024 * 1024;
    private final int[] testData = new int[ARR_SIZE];

    private void run() {
        System.err.println("Start: " + System.currentTimeMillis());
        for (int i = 0; i < 15_000; i++) {
            touchEveryLine();
            touchEveryItem();
        }
        System.err.println("Warmup finished: " + System.currentTimeMillis());
        System.err.println("Item Line");
        for (int i = 0; i < 100; i++) {
            long t0 = System.nanoTime();
            touchEveryLine();
            long t1 = System.nanoTime();
            touchEveryItem();
            long t2 = System.nanoTime();
            long elItem = t2 - t1;
            long elLine = t1 - t0;
            double diff = elItem - elLine;
            System.err.println(elItem + " " + elLine + " " + (100 * diff / elLine));
        }
    }

    private void touchEveryItem() {
        for (int i = 0; i < testData.length; i++) {
            testData[i]++;
        }
    }

    private void touchEveryLine() {
        for (int i = 0; i < testData.length; i += 16) {
            testData[i]++;
        }
    }

    public static void main(String[] args) {
        Caching c = new Caching();
        c.run();
    }
}
```

Normally, we might think `touchEveryItem()` does 16 times as much work as `touchEveryLine()`, as 16 times as many data items must be updated. However, the point of this simple example is to show how easily simple guesses can be wrong when dealing with JVM performance. Let's look at some sample output from the `Caching` class, as shown in Figure 7-5.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//56487fdf-6a28-4a2e-856f-1ef6131af725/markdown_4/imgs/img_in_chart_box_143_411_861_735.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A08Z%2F-1%2F%2Fb2a245288af405824838a190787052328b25f06d9bbe5ad3ab26b7fafb545bfc" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 7-5. Time (ns) elapsed for caching example</div> </div>

The graph shows 100 runs of each function and is intended to show several different effects. First, notice that the results for both functions are very similar in the time taken, so the intuitive expectation of “16 times as much work” is clearly false.

Instead, the main effect of this code is to use the memory bus by transferring the contents of the array from main memory into the cache to be operated on by `touchEveryItem()` and `touchEveryLine()`.

In terms of the statistics of the numbers, although the results are reasonably consistent, there are individual outliers that are 30%–35% different from the median value.

Overall, we can see that each iteration of the simple memory function takes around 3 milliseconds (2.86 ms on average) to traverse a 100 MB chunk of memory, giving an effective memory bandwidth of just under 3.5 GB/s. This is less than the theoretical maximum, but is still a reasonable number. Designing for theoretical limits can be a path to disappointment. Empirical numbers are useful for baselines and planning purposes. Results that are significantly different—i.e., by orders of magnitude—from theoretical limits might be considered unreasonable and warrant further exploration.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//595cd472-6087-4eac-b8c0-4240e7f64019/markdown_0/imgs/img_in_image_box_176_212_252_312.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A10%3A57Z%2F-1%2F%2F29b689efa9e1435e562abffd4a520f8bc95d8eead53a5770e8f23b39b2001191" alt="Image" width="7%" /></div>

> [!TIP]
> Modern CPUs have a hardware prefetcher that can detect predictable patterns in data access (usually a regular "stride" through memory). In this example, we are taking advantage of that fact to get closer to a realistic maximum for memory access bandwidth.

One of the key themes in Java performance is the sensitivity of applications to object allocation rates. We will return to this point several times, but this simple example gives us a basic yardstick for the upper limit of allocation rates.

---

## Modern Processor Features

Hardware engineers sometimes refer to the new features made possible by Moore's law as "spending the transistor budget." Memory caches are the most obvious use of the growing number of transistors, but other techniques have also appeared over the years.

### Translation Lookaside Buffer (TLB)

One very important use of hardware caching is the **Translation Lookaside Buffer (TLB)**, a hardware cache for the page tables that map virtual memory locations (which are the ones seen by application code) to physical hardware locations. This greatly speeds up virtual-to-physical address translation.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//595cd472-6087-4eac-b8c0-4240e7f64019/markdown_0/imgs/img_in_image_box_176_816_252_916.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A10%3A57Z%2F-1%2F%2F5c7336888088e494fb9cac3dfd10fd28136637b707a2a036cf4a157f08d2e415" alt="Image" width="7%" /></div>

> [!WARNING]
> We have already met the **TLAB** (Thread Local Allocation Buffer) feature of HotSpot's GC in Chapter 4. Some texts refer to a TLAB as a TLB, which can be confusing as the two concepts are not related. Always check which feature is being discussed when you see the term mentioned.

Without the TLB, all virtual address lookups would take roughly 16 cycles, even if the page table was held in the L1 cache. The resulting performance would be unacceptable, making the TLB essential for modern chips.

### Branch Prediction and Speculative Execution

One of the advanced tricks on modern processors is **branch prediction**. This is used to prevent the processor from having to wait to evaluate a value needed for a conditional branch. Modern processors have multistage instruction pipelines, meaning the execution of a single CPU cycle is broken down into a number of separate stages, with several instructions in flight at once.

In this model, a conditional branch is problematic because until the condition is evaluated, the processor does not know which instruction follows the branch. This can cause the processor to stall for up to 20 cycles as it empties the multistage pipeline behind the branch.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//595cd472-6087-4eac-b8c0-4240e7f64019/markdown_1/imgs/img_in_image_box_176_325_252_425.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A10%3A57Z%2F-1%2F%2Fed6fdc8aa878e15cd21ff7065cb4848a10d5a921fa7a4179a8b0eb29091a4cfa" alt="Image" width="7%" /></div>

> [!NOTE]
> Speculative execution was, famously, the cause of major security vulnerabilities (including Meltdown and Spectre) discovered to affect large numbers of CPUs in early 2018.

To avoid this pipeline stall, the processor uses dedicated transistors to build up a simple guess to guess which branch is more likely to be taken. Using this guess, the CPU speculatively fills the pipeline. If the guess is correct, the CPU carries on without pausing. If it is wrong, the speculatively executed instructions are discarded, and the CPU pays the penalty of emptying and refilling the pipeline.

### Hardware Memory Models

The core question about memory that must be answered in a multicore system is: *"How can multiple different CPUs access the same memory location consistently?"*

The answer is highly hardware-dependent. In general, `javac`, the JIT compiler, and the CPU are all allowed to reorder execution instructions, provided those changes do not affect the outcome as observed by the executing thread itself.

For example, suppose we have a piece of code like this:

```java
myInt = otherInt;
intChanged = true;
```

There is no dependency between the two assignments, so the executing thread does not care about what order they happen in, leaving the execution environment free to change the instruction order.

However, in another thread that has visibility of these data items, the order could change, and the value of `myInt` read by the other thread could be the old value, despite `intChanged` being seen as `true`.

This type of reordering (stores moved after stores) is not possible on x86 chips, but as Table 7-2 shows, there are other architectures where it can, and does, happen.

<div style="text-align: center;"><div style="text-align: center;">Table 7-2. Hardware memory support</div> </div>

| Reordering Type | ARMv7 | POWER | SPARC | x86 | AMD64 | zSeries |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Loads moved after loads** | Y | Y | - | - | - | - |
| **Loads moved after stores** | Y | Y | - | - | - | - |
| **Stores moved after stores** | Y | Y | - | - | - | - |
| **Stores moved after loads** | Y | Y | Y | Y | Y | Y |
| **Atomic moved with loads** | Y | Y | - | - | - | - |
| **Atomic moved with stores** | Y | Y | - | - | - | - |
| **Incoherent instructions** | Y | Y | Y | Y | - | Y |

In the Java environment, the **Java Memory Model (JMM)** is explicitly designed to be a weak model to accommodate the differences in consistency of memory access between processor types. Correct use of locks and `volatile` access is a major part of ensuring that multithreaded code works properly. This is a very important topic that we will return to in Chapter 13.

A trend in recent years has been for software developers to seek a greater understanding of the workings of hardware to get better performance. The term **mechanical sympathy** has been used to describe this approach, especially as applied to the low-latency and high-performance spaces. This can be seen in recent research into lock-free algorithms and data structures, which we will meet in Chapter 13.

> The name “mechanical sympathy” comes from the great racing driver Jackie Stewart, who was a three times world Formula 1 champion. He believed the best drivers had enough understanding of how a machine worked so they could work in harmony with it.
> — *Martin Thompson*

---

## Operating Systems

The point of an operating system is to control access to resources that must be shared between multiple executing processes. All resources are finite, and all processes are greedy, making a central system to manage and control access essential. Among these scarce resources, the two most important are usually memory and CPU time.

Virtual addressing via the **Memory Management Unit (MMU)** and its page tables is the key feature that enables memory access control and prevents one process from damaging the memory areas owned by another.

The TLBs we met earlier in the chapter are a hardware feature that improves lookup times to physical memory, improving access times. However, the MMU is usually too low-level for developers to measure.

Instead, let's take a closer look at the OS **process scheduler**, as this controls access to the CPU and is a far more user-visible piece of the operating system kernel.

### The Scheduler

The job of the process scheduler is to manage access to the CPU cores (and to respond to interrupts). On a modern system, there are almost always more threads wanting to run than can run simultaneously, requiring an access control way to resolve CPU contention.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//595cd472-6087-4eac-b8c0-4240e7f64019/markdown_3/imgs/img_in_image_box_176_466_253_566.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A10%3A58Z%2F-1%2F%2F860a8ab40b7b2f95da9d2df2edd0d7ac3b6da98b86a84fb5df584b889dab9e62" alt="Image" width="7%" /></div>

> [!NOTE]
> In this section, we are explicitly talking about the OS-level platform threads. Java 21+ virtual threads do not follow this model directly—instead, it is the carrier threads that virtual threads are multiplexed onto that obey this model. See Chapter 13 for more details.

This access control uses a queue known as the **run queue** as a waiting area for the platform threads that are eligible to run but must wait their turn for the CPU. The overall lifecycle of a platform thread is shown in Figure 7-6.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//595cd472-6087-4eac-b8c0-4240e7f64019/markdown_3/imgs/img_in_image_box_143_685_864_1124.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A10%3A58Z%2F-1%2F%2F4db1b14cbd25574286ad7fedd6273b5b5ba5c117554cd83d81b5ba857e40e7bd" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 7-6. Thread lifecycle</div> </div>

In this model, the OS scheduler moves platform threads on and off the core. At the end of the **time quantum** (often 10 ms to 100 ms), the scheduler moves the running thread to the back of the run queue to wait until it reaches the front again.

If a thread wants to voluntarily give up its time quantum, it can do so either for a fixed duration (via `Thread.sleep()`) or until a condition is met (using `Object.wait()`). Finally, a thread can also block on I/O or a software lock.

Real hardware is complex, and modern machines have multiple cores, permitting true simultaneous execution. This makes reasoning about execution in a true multiprocessing environment highly complex and counterintuitive.

An often-overlooked feature of operating systems is that they introduce periods of time when code of interest is not running on the CPU. A process that has completed its time quantum will not get back on the CPU until it arrives at the front of the run queue again. Combined with the fact that CPU is a scarce resource, this means that code is waiting more often than it is running.

This means that the statistics we want to generate from processes we observe are affected by the behavior of other processes on the system. This "jitter" and the overhead of scheduling is a primary cause of noise in observed results. We discussed the statistical properties and handling of real results in Chapter 2 and observed this in the `Caching` example.

One of the easiest ways to see the action of a scheduler is to measure the overhead imposed by the OS during scheduling. The following code executes 1,000 separate 1 ms sleeps. Each sleep involves the thread being sent to the back of the run queue and waiting for a new time quantum, so the total elapsed time reveals the overhead of scheduling:

```java
long start = System.currentTimeMillis();
for (int i = 0; i < 1000; i++) {
    Thread.sleep(1);
}
long end = System.currentTimeMillis();
System.out.println("Seconds elapsed: " + (end - start) / 1000.0);
```

Running this code will cause wildly divergent results depending on the operating system. Most Unixes will report roughly 10%–20% overhead. Earlier versions of Windows had notorious scheduling latencies, with some versions of Windows XP reporting up to 180% overhead (taking 2.8 seconds for 1,000 sleeps of 1 ms).

Now that we understand the scheduling quantum and its impact, let's delve into how the JVM typically calls into the operating system.

### The JVM and the Operating System

The JVM provides a portable execution environment that is independent of the operating system by providing a common interface to Java code. However, for some fundamental services, such as thread scheduling or getting the time from the system clock, the underlying operating system must be accessed.

This capability is provided by native methods, denoted by the keyword `native`. They are written in C/C++ but are accessible as ordinary Java methods. This interface is referred to as the **Java Native Interface (JNI)**. For example, `java.lang.Object` declares multiple non-private native methods that deal with low-level platform concerns.

Let's look at a familiar example: getting the system time.

Consider the `os::javaTimeMillis()` function. This is the system-specific code responsible for implementing the `System.currentTimeMillis()` static method. The code that does the actual work is implemented in C++ but is accessed from Java via a "bridge" of C code. Let's look at how this code is actually called in HotSpot.

As you can see in Figure 7-7, the native `System.currentTimeMillis()` method is mapped to the JVM entry point method `JVM_CurrentTimeMillis()`. This mapping is achieved via the JNI `Java_java_lang_System_registerNatives()` mechanism contained in `java/lang/System.c`.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//05df4b02-cf02-4325-8c3a-ec219813b799/markdown_0/imgs/img_in_image_box_142_860_864_1100.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A30Z%2F-1%2F%2Fdb136575fe7c6a40367192a711f0b301d8e8123d4995165801873a53e9ede671" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 7-7. The HotSpot calling stack</div> </div>

`JVM_CurrentTimeMillis()` is a call to the VM entry point method. This presents as a C function but is really a C++ function exported with a C calling convention. The call boils down to the call `os::javaTimeMillis()` wrapped in OpenJDK macros.

This method is defined in the `os` namespace and is operating system dependent. Definitions for this method are provided by the OS-specific subdirectories of source code within OpenJDK. This provides a simple demonstration of how the platform-independent parts of Java can call into services provided by the underlying operating system and hardware.

Let's look at what happens when the scheduler needs to change which threads are currently executing.

### Context Switches

A **context switch** is the process by which the OS scheduler removes a currently running platform thread and replaces it with another. Broadly speaking, this involves swapping the executing instructions and the stack state of the thread.

A context switch can be a costly operation, whether between user threads or from user mode into kernel mode (sometimes called a **mode switch**). The latter case is particularly important because a user thread may need to swap into kernel mode to perform some function partway through its time slice. This switch will force instruction and other caches to be emptied, as the memory areas accessed by the user space code will not normally have anything in common with the kernel.

A context switch into kernel mode will invalidate the TLBs and potentially other caches. When the call returns, these caches will have to be refilled, so the effect of a kernel mode switch persists even after control has returned to user space, masking the true cost of a system call. $ ^{4} $

For example, Figure 7-8 highlights the cost of an inter-process communication (IPC) call—it is made in user mode but requires a switch to kernel mode. After the switch happens (represented as a "SYSCALL exception," which is a hardware interrupt, not a Java exception), performance drops and only slowly recovers as the cache refills.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//05df4b02-cf02-4325-8c3a-ec219813b799/markdown_2/imgs/img_in_chart_box_206_111_829_424.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A33Z%2F-1%2F%2F581f20515e6a05a198249e77ed2de6daeb9561c9618f44416010fadf63b82c98" alt="Image" width="61%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 7-8. Impact of a system call (Soares and Stumm, 2010)</div> </div>

To mitigate this, Linux provides a mechanism known as the **Virtual Dynamic Shared Object (vDSO)**. This is a memory area in user space used to speed up syscalls that do not require kernel privileges. It achieves this speed increase by avoiding a full context switch into kernel mode.

For example, a very common Unix system call is `gettimeofday()`. This returns the "wallclock time" as understood by the operating system. Behind the scenes, it just reads a kernel data structure to obtain the system clock time. As this is side-effect free, it does not need privileged access.

If we can use the vDSO to map this kernel data structure into the address space of the user process, there is no need to perform a context switch to kernel mode, avoiding the refill penalty shown in Figure 7-8.

Given how often Java applications need to access timing data, this provides a major performance boost. The vDSO mechanism generalizes this optimization, although it is primarily available on Linux.

---

## A Simple System Model

This section covers a simple model for describing basic sources of possible performance problems. The model is expressed in terms of operating system observables of fundamental subsystems and can be directly related back to the outputs of standard Unix command-line tools.

Although this may seem low level, the point is to establish a foundational model that we can relate back to the observability data we actually use to diagnose problems.

The model is based on a simple conception of a Java application running on a Unix-like operating system. Figure 7-9 shows the basic components of the model, which consist of:
- The hardware and operating system the application runs on.
- The JVM (or container) the application runs in.
- The application code itself.
- Any external systems the application calls.
- The incoming request traffic arriving at the application.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//05df4b02-cf02-4325-8c3a-ec219813b799/markdown_3/imgs/img_in_image_box_144_510_863_831.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A35Z%2F-1%2F%2F1b15b5e457ab4d1fef951d4459108f7770ab18cbab508bbd24a202015f7cd54e" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 7-9. Simple system model</div> </div>

Any of these aspects of a system can be responsible for a performance bottleneck. Simple diagnostic techniques can be used to narrow down or isolate particular parts of the system as potential culprits.

One definition for a well-performing application is that it makes efficient use of system resources, including CPU, memory, and network or I/O bandwidth.

The first step in any performance diagnosis is to recognize which resource limit is being hit. We cannot tune performance without dealing with the resource shortage—either by increasing the available resources or the efficiency of their use.

The operating system itself should not normally be a major contributor to system utilization; its role is to manage resources on behalf of user processes, not to consume them. The only real exception is when resources are so scarce that the OS struggles to satisfy user requirements, which usually occurs when I/O (or memory) requirements greatly exceed hardware capability.

### Utilizing the CPU

A key metric for application performance is **CPU utilization**. CPU cycles are often the most critical resource, so their efficient use is essential. CPU-bound applications should aim for as close to 100% usage as possible during periods of high load, although this is difficult to achieve in practice due to other application dependencies.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//05df4b02-cf02-4325-8c3a-ec219813b799/markdown_4/imgs/img_in_image_box_167_752_253_867.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A37Z%2F-1%2F%2F027492ef2c61742ee64a41c28419af3c3c6fb943d0cdbb3733f33fc92a2ca467" alt="Image" width="8%" /></div>

> [!NOTE]
> When you are analyzing application performance, the system must be under enough load to exercise it. The behavior of an idle application is usually meaningless for performance work.

Three basic tools that every performance engineer should be aware of are `vmstat`, `ifstat`, and `iostat`:
- **`vmstat`**: Reports statistics on virtual memory, including information about sizing, I/O, and CPU activity.
- **`ifstat`**: Provides statistics on the network interfaces and is used to debug network-level process interactions.
- **`iostat`**: Monitors input/output on devices and is used to identify device-level interactions causing issues.

On Unix-like systems, these command-line tools provide immediate and useful insight. Although they only provide numbers at the host level, this is frequently enough to point the way. Let's look at how to use `vmstat` as an example:

```shell
$ vmstat 1
```

| r | b | swpd | free | buff | cache | si | so | bi | bo | in | cs | us | sy | id | wa | st |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 2 | 0 | 0 | 759860 | 248412 | 2572248 | 0 | 0 | 0 | 80 | 63 | 127 | 8 | 0 | 92 | 0 | 0 |
| 2 | 0 | 0 | 759002 | 248412 | 2572248 | 0 | 0 | 0 | 0 | 55 | 103 | 12 | 0 | 88 | 0 | 0 |
| 1 | 0 | 0 | 758854 | 248412 | 2572248 | 0 | 0 | 0 | 80 | 57 | 116 | 5 | 1 | 94 | 0 | 0 |
| 3 | 0 | 0 | 758604 | 248412 | 2572248 | 0 | 0 | 0 | 14 | 65 | 142 | 10 | 0 | 90 | 0 | 0 |
| 2 | 0 | 0 | 758932 | 248412 | 2572248 | 0 | 0 | 0 | 96 | 52 | 100 | 8 | 0 | 92 | 0 | 0 |
| 2 | 0 | 0 | 759860 | 248412 | 2572248 | 0 | 0 | 0 | 0 | 60 | 112 | 3 | 0 | 97 | 0 | 0 |

The parameter `1` following `vmstat` indicates that we want ongoing output at a frequency of 1 sample per second (until interrupted via `Ctrl-C`). This enables a performance engineer to leave this running while a performance test is executed.

The output of `vmstat` is divided into several sections:
1. **Processes**: The first two columns show the number of runnable (`r`) and blocked (`b`) processes.
2. **Memory**: The amount of swapped and free memory, followed by memory used as buffers and cache.
3. **Swap**: Memory swapped in from (`si`) and out to (`so`) disk. Modern server-class machines should not experience significant swap activity.
4. **I/O**: Block in (`bi`) and block out (`bo`) counts show the number of 512-byte blocks received from and sent to a block device.
5. **System**: The number of interrupts (`in`) and context switches (`cs`) per second.
6. **CPU**: Metrics expressed as percentages of CPU time: user time (`us`), kernel/system time (`sy`), idle time (`id`), waiting time (`wa`), and stolen time (`st`, for virtual machines).

While complex profiling tools can sometimes mislead us, simple tools operating close to the OS convey clear, uncluttered views of system behavior.

For example, context switches introduce unavoidable waste of CPU resources. For CPU-bound workloads, the aim is to achieve close to 100% CPU utilization for userland work (`us`). If CPU utilization is not approaching 100% user time, we must ask what is preventing it. Are involuntary context switches caused by locks the problem? Or is it due to blocking caused by I/O contention?

A `vmstat 1` run allows the analyst to see the real-time effect of context switching. A process that fails to achieve high userland CPU usage while displaying a high context switch rate is likely blocked on I/O, experiencing thread lock contention, or experiencing excessive scheduling overhead.

### Garbage Collection

In the HotSpot JVM, memory is allocated at startup and managed within user space, meaning system calls (such as `sbrk()`) are not needed to allocate memory. In turn, kernel-switching activity for garbage collection is minimal.

Thus, if a system exhibits high levels of system/kernel CPU usage (`sy`), it is definitely not spending a significant amount of time in GC. GC activity burns user space CPU cycles (`us`) and does not impact kernel space utilization.

On the other hand, if a JVM process is using close to 100% of CPU in user space, garbage collection could be the culprit. If simple tools show consistent 100% user space CPU usage, we should check if the JVM or user code is responsible. In many cases, high user space utilization by the JVM is caused by the GC subsystem, so checking the GC log for activity frequency is a useful diagnostic step.

GC logging in the JVM is extremely cheap, so its overall cost cannot be reliably distinguished from random background noise. It is therefore essential that GC logs be turned on for all JVM processes, especially in production.

While observability tools report aggregated GC metrics, the detailed timing of individual GC events is lost, which can be critical for root-cause diagnosis.

### Input/Output (I/O)

File I/O has traditionally been one of the murkier aspects of system performance. Partly, this is due to its relationship with physical hardware ("spinning rust"), but it is also because I/O lacks abstractions as clean as virtual memory.

Fortunately, while most Java programs involve some simple I/O, the class of applications that heavily saturate the I/O subsystems is relatively small. Most applications do not simultaneously saturate I/O and CPU or memory. Production engineers typically actively monitor processes for heavy I/O usage.

For the performance analyst, it suffices to have an awareness of the I/O behavior of our applications. Tools such as `iostat` (and `vmstat`) provide the basic counters (e.g., blocks in or out) needed for basic diagnosis.

In virtualized and cloud environments, I/O-intensive applications can give rise to the **noisy neighbor** problem—where one container saturates physical disk or network I/O and negatively affects the performance of other containers running on the same physical host. This can be difficult to detect directly and requires close attention.

### Mechanical Sympathy

Mechanical sympathy is the idea that having an appreciation of the hardware is invaluable when you need to get the best performance.

> You don't have to be an engineer to be a racing driver, but you do have to have mechanical sympathy.
> — *Jackie Stewart (attributed)*

The phrase was originally coined by Martin Thompson as a reference to Jackie Stewart. For many Java developers, mechanical sympathy is a concern that is possible to ignore because the JVM abstracts the hardware away. However, developers can use Java and the JVM successfully in the high-performance and low-latency space by gaining an understanding of the JVM's interaction with the underlying hardware.

Whether mechanical sympathy is important to your project depends upon the application's business goals and service-level agreements.

Consider the behavior of cache lines in a multithreaded environment. Cache lines can cause a performance bottleneck known as **false sharing** when two threads attempt to read or write to different variables located on the same cache line. The first thread's write invalidates the cache line on the second thread's core, forcing it to be reread from memory, and vice versa. This ping-pong behavior results in a severe drop-off in performance.

Mechanical sympathy suggests that we must first understand this phenomenon, and then determine how to resolve it. In Java, the order of fields in an object is not guaranteed, making it easy for unrelated variables to share a cache line. To resolve this, we can add padding around variables (such as using the `@Contended` annotation in Java 8+) to force them onto different cache lines.

---

## Summary

Processor design and modern hardware have changed greatly. Driven by Moore's law and by engineering limitations (notably the relatively slow speed of memory), advances in processor design have become complex. The cache miss rate has become a primary indicator of application performance.

In the Java space, the design of the JVM allows it to use additional processor cores even for single-threaded application code. This means that Java applications have received significant performance advantages from hardware trends compared to other environments.

As Moore's law fades, attention will turn once again to the relative performance of software. Performance-minded engineers need to understand at least the basic points of modern hardware and operating systems to ensure they can make the most of their hardware and not fight against it.

In the next chapter, we will move from a single host to the highly virtualized/containerized environments that increasingly represent the standard deployment targets for modern Java applications.
