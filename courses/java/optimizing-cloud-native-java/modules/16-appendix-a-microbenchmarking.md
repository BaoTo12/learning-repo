# Microbenchmarking

In this appendix, we will consider the specifics of measuring low-level Java performance numbers directly. The dynamic nature of the JVM means that performance numbers are often harder to handle than many developers expect. As a result, there are a lot of inaccurate or misleading performance numbers floating around on the internet.

A primary goal of this appendix is to ensure that you are aware of these possible pitfalls and only produce performance numbers that you and others can rely upon. In particular, the measurement of small pieces of Java code (microbenchmarking) is well-known for being hard to do correctly. This subject and its proper use by performance engineers is a major theme throughout this appendix.

The Feynman quote we met way back in Chapter 2 is especially relevant when applied to microbenchmarks.

The second portion of this appendix describes how to use the gold standard of microbenchmarking tools: **JMH**. If, even after all the warnings, you really feel that your application and use cases warrant the use of microbenchmarks, then you will need to avoid numerous well-known pitfalls and “bear traps” by starting with the most reliable and advanced of the available tools.

---

## Introduction to Measuring Low-Level Java Performance

In “Java Performance Overview” on page 4, we described performance analysis as a combination of different aspects of the craft that has resulted in a discipline that is basically an experimental science.

That is, if we want to write a good benchmark (or microbenchmark), then it can be very helpful to consider it as though it were a science experiment.

This approach leads us to view the benchmark as an “opaque box”—it has inputs and outputs, and we want to collect data from which we can guess or infer results. However, we must be cautious: it is not enough to simply collect data. We need to ensure that we are not deceived by our data.

> Benchmark numbers don't matter on their own. It's important what models you derive from those numbers.
> 
> — Aleksey Shipilëv

Our ideal goal is, therefore, to make our benchmark a fair test—meaning that, as far as possible, we only want to change a single aspect of the system and ensure any other external factors in our benchmark are controlled. In an ideal world, the other possibly changeable aspects of the system would be completely unchanged between tests, but we are rarely so fortunate in practice.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//d4ca6807-4bd2-4ecd-b8c1-532aace69306/markdown_1/imgs/img_in_image_box_176_468_252_567.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A07Z%2F-1%2F%2F9112136a185a6cf2a4d0fe257c8f5436d5e7fbfb57d106c40a5a17822c317120" alt="Image" width="7%" /></div>

> [!NOTE]
> Even if the goal of a scientifically pure fair test is unachievable in practice, it is essential that our benchmarks are at least repeatable, as this is the basis of any empirical result.

One central problem with writing a benchmark for the Java platform is the sophistication of the Java runtime. A considerable portion of this book is devoted to explaining the automatic optimizations that are applied to a developer's code by the JVM. When we think of our benchmark as a scientific test in the context of these optimizations, then our options become limited.

That is, to fully understand and account for the precise impact of these optimizations is all but impossible. Accurate models of the “real” performance of our application code are difficult to create and tend to be limited in their applicability.

Put another way, we cannot truly separate the executing Java code from the JIT compiler, memory management, and other subsystems provided by the Java runtime. Neither can we ignore the effects of operating system, hardware, or runtime conditions (e.g., load) that are current when our tests are run.

> No man is an island, entire of itself.
> 
> — John Donne

It is easier to smooth out these effects by dealing with a larger group (a whole system or subsystem). Conversely, when we are dealing with small-scale or microbenchmarks, it is much more difficult to truly isolate application code from the background behavior of the runtime. This is the fundamental reason why microbenchmarking is so hard, as we will discuss.

Let's consider what appears to be a very simple example—a benchmark of code that sorts a list of 1,000 numbers. We want to examine it with the point of view of trying to create a truly fair test:

```java
public class ClassicSort {
    private static final int N = 1_000;
    private static final int I = 150_000;
    private static final List<Integer> testData = new ArrayList<>();

    public static void main(String[] args) {
        Random randomGenerator = new Random();
        for (int i = 0; i < N; i++) {
            testData.add(randomGenerator.nextInt(Integer.MAX_VALUE));
        }

        System.out.println("Testing Sort Algorithm");

        double startTime = System.nanoTime();

        for (int i = 0; i < I; i++) {
            List<Integer> copy = new ArrayList<Integer>(testData);
            Collections.sort(copy);
        }

        double endTime = System.nanoTime();
        double timePerOperation = ((endTime - startTime) / (1_000_000_000L * I));
        System.out.println("Result: " + (1 / timePerOperation) + " op/s");
    }
}
```

The benchmark creates an array of random integers and, once this is complete, logs the start time of the benchmark. The benchmark then loops around, copying the template array, and then runs a sort over the data. Once this has run for `I` times, the duration is converted to seconds and divided by the number of iterations to give us the time taken per operation.

The first concern with the benchmark is that it goes straight into testing the code, without any consideration for warming up the JVM. Consider the case where the sort is running in a server application in production. It is likely to have been running for hours, maybe even days. However, we know that the JVM includes a just-in-time compiler that will convert interpreted bytecode to highly optimized machine code. This compiler only kicks in after the method has been run a certain number of times.

The test we are conducting, therefore, is not representative of how it will behave in production. The JVM will spend time optimizing the call while we are trying to benchmark. We can see this effect by running the sort with a few JVM flags:

```bash
java -Xms2048m -Xmx2048m -XX:+PrintCompilation ClassicSort
```

The `-Xms` and `-Xmx` options control the size of the heap, in this case, pinning the heap size to 2 GB. The `PrintCompilation` flag outputs a log line whenever a method is compiled (or some other compilation event happens). Here is a fragment of the output:

| Timestamp (ms) | Compilation ID | Attributes | Method |
| :--- | :--- | :--- | :--- |
| 73 | 29 | 3 | `java.util.ArrayList::ensureExplicitCapacity` (26 bytes) |
| 73 | 31 | 3 | `java.lang.Integer::valueOf` (32 bytes) |
| 74 | 32 | 3 | `java.util.concurrent.atomic.AtomicLong::get` (5 bytes) |
| 74 | 33 | 3 | `java.util.concurrent.atomic.AtomicLong::compareAndSet` (13 bytes) |
| 74 | 35 | 3 | `java.util.Random::next` (47 bytes) |
| 74 | 36 | 3 | `java.lang.Integer::compareTo` (9 bytes) |
| 74 | 38 | 3 | `java.lang.Integer::compare` (20 bytes) |
| 74 | 37 | 3 | `java.lang.Integer::compareTo` (12 bytes) |
| 74 | 39 | 4 | `java.lang.Integer::compareTo` (9 bytes) |
| 75 | 36 | 3 | `java.lang.Integer::compareTo` (9 bytes) made not entrant |
| 76 | 40 | 3 | `java.util.ComparableTimSort::binarySort` (223 bytes) |
| 77 | 41 | 3 | `java.util.ComparableTimSort::mergeLo` (656 bytes) |
| 79 | 42 | 3 | `java.util.ComparableTimSort::countRunAndMakeAscending` (123 bytes) |
| 79 | 45 | 3 | `java.util.ComparableTimSort::gallOpRight` (327 bytes) |
| 80 | 43 | 3 | `java.util.ComparableTimSort::pushRun` (31 bytes) |

The JIT compiler is working overtime to optimize parts of the call hierarchy to make our code more efficient. This means the performance of the benchmark changes over the duration of our timing capture, and we have accidentally left a variable uncontrolled in our experiment. A warmup period is, therefore, desirable—it will allow the JVM to settle down before we capture our timings. Usually this involves running the code we are about to benchmark for a number of iterations without capturing the timing details.

Another external factor that we need to consider is garbage collection. Ideally, we want GC to be prevented from running during our time capturing, and also to be normalized after setup. Due to the unpredictable nature of garbage collection, this is incredibly difficult to control.

One improvement we could definitely make is to ensure that we are not capturing timings while GC is likely to be running. We could potentially ask the system for a GC to be run and wait a short time, but the system could decide to ignore this call. As it stands, the timing in this benchmark is far too broad, so we need more detail about the garbage collection events that could be occurring.

Not only that, but as well as selecting our timing points we also want to select a reasonable number of iterations, which can be tricky to figure out through trial and improvement. The effects of garbage collection can be seen with another VM flag:

```bash
java -Xms2048m -Xmx2048m -verbose:gc ClassicSort
```

This will produce GC log entries similar to the following:

```
Testing Sort Algorithm
[GC (Allocation Failure) 524800K->632K(2010112K), 0.0009038 secs]
[GC (Allocation Failure) 525432K->672K(2010112K), 0.0008671 secs]
Result: 9838.556465303362 op/s
```

Another common mistake made in benchmarks is to not actually use the result generated from the code we are testing. In the benchmark, `copy` is effectively dead code, and it is, therefore, possible for the JIT compiler to identify it as a dead-code path and optimize away what we are, in fact, trying to benchmark.

A further consideration is that looking at a single timed result, even though averaged, does not give us the full story of how our benchmark performed. Ideally, we want to capture the margin of error to understand the reliability of the collected value. If the error margin is high, it may point to an uncontrolled variable or, indeed, that the code we have written is not performant. Either way, without capturing the margin of error, there is no way to identify that there is even an issue.

Benchmarking even a very simple sort can have pitfalls that mean the benchmark is wildly thrown out; however, as the complexity increases, things rapidly get much, much worse. Consider a benchmark that looks to assess multithreaded code. Multithreaded code is extremely difficult to benchmark, as it requires ensuring that all the threads are held until each has fully started up, from the beginning of the benchmark to making certain accurate results. If this is not the case, the margin of error will be high.

There are also hardware considerations when it comes to benchmarking concurrent code, and they go beyond simply the hardware configuration. Consider if power management were to kick in or if there were other contentions on the machine.

Getting the benchmark code correct is complicated and involves considering a lot of factors. As developers, our primary concern is the code we are looking to profile rather than all the issues just highlighted. All the aforementioned concerns combine to create a situation in which, unless you are a JVM expert, it is extremely easy to miss something and get an incorrect benchmark result.

There are two ways to deal with this problem. The first is to only benchmark systems as a whole. In this case, the low-level numbers are simply ignored and not collected. The overall outcome of so many copies of separate effects is to average out and allow meaningful large-scale results to be obtained. This approach is the one needed in most situations and by most developers.

The second approach is to try to address many of the aforementioned concerns by using a common framework, to allow meaningful comparison of related low-level results. The ideal framework would take away some of the pressures just discussed.

Such a tool would have to follow the mainline development of OpenJDK to ensure that new optimizations and other external control variables were managed.

Fortunately, such a tool exists, and it is the subject of our next section.

---

## Introduction to JMH

We open with an example (and a cautionary tale) of how and why microbenchmarking can easily go wrong if it is approached naively. From there, we introduce a set of guidelines that indicate whether your use case is one where microbenchmarking is appropriate. For the vast majority of applications, the outcome will be that the technique is not suitable.

### Don't Microbenchmark If You Can Help It (A True Story)

After a very long day in the office, one of the authors was leaving the building when he passed a colleague still working at her desk, staring intensely at a single Java method. Thinking nothing of it, he left to catch a train home. However, two days later a very similar scenario played out—with a very similar method on the colleague's screen and a tired, annoyed look on her face. Clearly, some deeper investigation was required.

The application she was improving had an easily observed performance problem. The new version was not performing as well as the version that the team was looking to replace, despite using new versions of well-known libraries. She had been spending some of her time removing parts of the code and writing small benchmarks in an attempt to find where the problem was hiding.

The approach somehow felt wrong, like looking for a needle in a haystack. Instead, the pair worked together on another approach and quickly confirmed that the application was maxing out CPU utilization. As this is a known good use case for execution profilers (see Chapter 12 for the full details of when to use profilers), ten minutes profiling the application found the true cause. Sure enough, the problem wasn't in the application code at all, but in a new infrastructure library the team was using.

This story illustrates an approach to Java performance that is, unfortunately, all too common. Developers can become obsessed with the idea that their own code must be to blame, and thus miss the bigger picture.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//e45fd046-40ef-4eab-b076-787aec5f453c/markdown_0/imgs/img_in_image_box_168_1048_253_1163.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A13Z%2F-1%2F%2Fcc77609f26557e17171626ac42239d4b773fccdb46798f8d3bb2c043654c2f41" alt="Image" width="8%" /></div>

> [!WARNING]
> Developers often want to start hunting for problems by looking closely at small-scale code constructs, but benchmarking at this level is extremely difficult and has some dangerous “bear traps.”

### Heuristics for When to Microbenchmark

As we discussed briefly in Chapter 3, the dynamic nature of the Java platform, and features like garbage collection and aggressive JIT optimization, lead to performance that is hard to reason about directly. Worse still, performance numbers frequently depend on the exact runtime circumstances in play when the application is being measured.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//e45fd046-40ef-4eab-b076-787aec5f453c/markdown_1/imgs/img_in_image_box_176_304_253_404.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A13Z%2F-1%2F%2F19f8d8a60d9558af6ef2c8ce9b226ac6cab56866c047f8edcef5b0602d7b0152" alt="Image" width="7%" /></div>

> [!NOTE]
> It is almost always easier to analyze the true performance of an entire Java application than a small Java code fragment.

However, occasionally there are times when we need to directly analyze the performance of an individual method or even a single code fragment. This analysis should not be undertaken lightly, though. In general, there are three main use cases for low-level analysis or microbenchmarking:
* You are a developer on OpenJDK or another Java platform implementation.
* You are developing general-purpose library code with broad use cases.
* You are developing extremely latency-sensitive code.

The rationale for each of the three use cases is slightly different.

Platform developers are a key user community for microbenchmarks, and the JMH tool was created by the OpenJDK team primarily for its own use. However, the tool has proved to be useful to the wider community of performance experts.

General-purpose libraries (by definition) have limited knowledge about the contexts in which they will be used. Examples of these types of libraries include Google Guava or Eclipse Collections. They need to provide acceptable or better performance across a very wide range of use cases—from datasets containing a few dozen elements up to hundreds of millions of elements.

Due to the broad nature of how they will be used, general-purpose libraries are sometimes forced to use microbenchmarking as a proxy for more conventional performance and capacity testing techniques.

Finally, some developers working at the front line of Java performance may wish to use microbenchmarks to select algorithms and techniques that best suit their applications and extreme use cases. This would include low-latency financial trading but relatively few other cases. [[^1]]

For the second two cases, it will normally make sense to include your JMH-based tests as part of your CI/CD pipeline and fail on a performance drop. This will detect not only changes in your own code but also in any library dependencies.

While it should be apparent if you are a developer working on OpenJDK or a general-purpose library, there may be developers who are confused about whether their requirements are such that they should consider microbenchmarks.

Generally, only the most extreme applications should use microbenchmarks. There are no definitive rules, but unless your application meets most or all of these criteria, you are unlikely to derive genuine benefit from microbenchmarking your application:
* Your total code path execution time should certainly be less than 1 ms, and probably less than 100 μs.
* You should have measured your memory (object) allocation rate (see “Allocation and Lifetime” on page 85 for details), and it should be <1 MB/s, and ideally, very close to zero.
* You should be using close to 100% of available CPU, and the system utilization rate should be consistently low (under 10%).
* You should have already used an execution profiler (see Chapter 12) to understand the distribution of methods that are consuming CPU. There should be at most two or three dominant methods in the distribution.

With all of this said, it is hopefully obvious that microbenchmarking is an advanced, though rarely used, technique. However, it is useful to understand some of the basic theory and complexity that it reflects, as it leads to a better understanding of the difficulties of performance work in less extreme applications on the Java platform.

The rest of this section explores microbenchmarking more thoroughly and introduces some of the tools and the considerations developers must take into account to produce results that are reliable and don't lead to incorrect conclusions. It should be useful background for all performance analysts, regardless of whether it is directly relevant to your current projects.

### The JMH Framework

JMH is designed to be the framework that resolves the issues we have just discussed.

> JMH is a Java harness for building, running, and analyzing nano/micro/milli/macro benchmarks written in Java and other languages targeting the JVM.
> 
> — OpenJDK

There have been several attempts at simple benchmarking libraries in the past, with Google Caliper being one of the most well-regarded among developers. However, all of these frameworks have had their challenges, and often what seems like a rational way of setting up or measuring code performance can have some subtle bear traps to contend with. This is especially true with the continually evolving nature of the JVM as new optimizations are applied.

JMH is very different in that regard and has been worked on by the same engineers that build the JVM. Therefore, the JMH authors know how to avoid the gotchas and optimization bear traps that exist within each version of the JVM. JMH evolves as a benchmarking harness with each release of the JVM, allowing developers to simply focus on using the tool and on the benchmark code itself.

JMH takes into account some key benchmark harness design issues, in addition to some of the problems already highlighted. A benchmark framework has to be dynamic, as it does not know the contents of the benchmark at compile time.

One obvious choice to get around this would be to execute benchmarks the user has written using reflection. However, this involves another complex JVM subsystem in the benchmark execution path. Instead, JMH operates by generating additional Java source from the benchmark, via annotation processing.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//e45fd046-40ef-4eab-b076-787aec5f453c/markdown_3/imgs/img_in_image_box_176_797_253_897.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A14Z%2F-1%2F%2F291f719eca281190689201e2744170930e2f7854eb7e103f3d0b40faaaa0f611" alt="Image" width="7%" /></div>

> [!NOTE]
> Many common annotation-based Java frameworks (e.g., JUnit) use reflection to achieve their goals, so the use of a processor that generates additional source may be somewhat unexpected to some Java developers.

One issue is that if the benchmark framework were to call the user's code for a large number of iterations, loop optimizations might be triggered. This means the actual process of running the benchmark can cause issues with reliable results.

To avoid hitting loop optimization limits, JMH generates code for the benchmark, wrapping the benchmark code in a loop with the iteration count carefully set to a value that avoids optimization.

### Executing Benchmarks

The complexities involved in JMH execution are mostly hidden from the user, and setting up a simple benchmark using Maven is straightforward. We can set up a new JMH project by executing the following command:

```bash
mvn archetype:generate \
  -DinteractiveMode=false \
  -DarchetypeGroupId=org.openjdk.jmh \
  -DarchetypeArtifactId=jmh-java-benchmark-archetype \
  -DgroupId=org.sample \
  -DartifactId=test \
  -Dversion=1.0
```

This downloads the required dependencies and creates a single benchmark stub to house the code.

The benchmark is annotated with `@Benchmark`, indicating that the harness will execute the method to benchmark it (after the framework has performed various setup tasks):

```java
public class MyBenchmark {
    @Benchmark
    public void testMethod() {
        // Stub for code
    }
}
```

The author of the benchmark can configure parameters to set up the benchmark execution. The parameters can be set either on the command line or in the `main()` method of the benchmark as shown here:

```java
public class MyBenchmark {
    public static void main(String[] args) throws RunnerException {
        Options opt = new OptionsBuilder()
            .include(SortBenchmark.class.getSimpleName())
            .warmupIterations(100)
            .measurementIterations(5).forks(1)
            .jvmArgs("-server", "-Xms2048m", "-Xmx2048m").build();

        new Runner(opt).run();
    }
}
```

The parameters on the command line override any parameters that have been set in the `main()` method.

Usually a benchmark requires some setup—for example, creating a dataset or setting up the conditions required for an orthogonal set of benchmarks to compare performance.

State, and controlling state, is another feature that is baked into the JMH framework. The `@State` annotation can be used to define that state, and it accepts the `Scope` enum to define where the state is visible: `Benchmark`, `Group`, or `Thread`. Objects that are annotated with `@State` are reachable for the lifetime of the benchmark; it may be necessary to perform some setup.

Multithreaded code also requires careful handling to ensure that benchmarks are not skewed by state that is not well managed.

In general, if the code executed in a method has no side effects and the result is not used, then the method is a candidate for removal by the JVM. JMH needs to prevent this from occurring, and, in fact, makes this extremely straightforward for the benchmark author. Single results can be returned from the benchmark method, and the framework ensures that the value is implicitly assigned to a blackhole, a mechanism developed by the framework authors to have very small performance overhead.

If a benchmark performs multiple calculations, it may be costly to combine and return the results from the benchmark method. In that scenario, it may be necessary for the author to use an explicit blackhole by creating a benchmark that takes a blackhole as a parameter, which the benchmark will inject.

Blackholes provide four protections related to optimizations that could potentially impact the benchmark. Some protections are about preventing the benchmark from over-optimizing due to its limited scope, and the others are about avoiding predictable runtime patterns of data, which would not happen in a typical run of the system. The protections are:
* **Remove the potential for dead code** to be removed as an optimization at runtime.
* **Prevent repeated calculations** from being folded into constants.
* **Prevent false sharing**, where the reading or writing of a value can cause the current cache line to be impacted.
* **Protect against “write walls.”**

The term *wall* in performance generally refers to a point at which your resources become saturated, and the impact to the application is effectively a bottleneck. Hitting the write wall can impact caches and pollute buffers that are being used for writing. If you do this within your benchmark, you are potentially impacting it in a big way.

As documented in the `Blackhole` Javadoc (and as noted earlier), to provide these protections, you must have deep knowledge of the JIT compiler so you can build a benchmark that avoids optimizations.

Let's take a quick look at the two `consume()` methods used by blackholes to give us insight into some of the tricks JMH uses (feel free to skip this bit if you're not interested in how JMH is implemented):

```java
public volatile int i1 = 1, i2 = 2;

/**
 * Consume object. This call provides a side effect preventing JIT to eliminate
 * dependent computations.
 *
 * @param i int to consume.
 */
public final void consume(int i) {
    if (i == i1 & i == i2) {
        // SHOULD NEVER HAPPEN
        nullBait.i1 = i; // implicit null pointer exception
    }
}
```

We repeat this code for consuming all primitives (changing `int` for the corresponding primitive type). The variables `i1` and `i2` are declared as `volatile`, which means the runtime must re-evaluate them. The `if` statement can never be true, but the compiler must allow the code to run. Also note the use of the bitwise AND operator (`&`) inside the `if` statement. This avoids additional branch logic being a problem and results in a more uniform performance.

Here is the second method:

```java
public int tlr = (int) System.nanoTime();

/**
 * Consume object. This call provides a side effect preventing JIT to eliminate
 * dependent computations.
 *
 * @param obj object to consume.
 */
public final void consume(Object obj) {
    int tlr = (this.tlr = (this.tlr * 1664525 + 1013904223));
    if ((tlr & tlrMask) == 0) {
        // SHOULD ALMOST NEVER HAPPEN IN MEASUREMENT
        this.obj1 = obj;
        this.tlrMask = (this.tlrMask << 1) + 1;
    }
}
```

When it comes to objects, it would seem at first the same logic could be applied, as nothing the user has could be equal to objects that the `Blackhole` holds. However, the compiler is also trying to be smart about this. If the compiler asserts that the object is never equal to something else due to escape analysis, it is possible that the comparison itself could be optimized to return false.

Instead, objects are consumed under a condition that executes only in rare scenarios. The value for `tlr` is computed and bitwise compared to the `tlrMask` to reduce the chance of a 0 value, but not outright eliminate it. This ensures objects are consumed largely without the requirement to assign the objects. Benchmark framework code is extremely fun to review, as it is so different from real-world Java applications. In fact, if code like that were found anywhere in a production Java application, the developer responsible should probably be fired.

As well as writing an extremely accurate microbenchmarking tool, the authors have also managed to create impressive documentation on the classes. If you're interested in the magic going on behind the scenes, the comments explain it well.

It doesn't take much with the preceding information to get a simple benchmark up and running, but JMH also has some fairly advanced features. The official documentation has examples of each, all of which are worth reviewing.

Interesting features that demonstrate the power of JMH and its relative closeness to the JVM include:
* Being able to control the compiler.
* Simulating CPU usage levels during a benchmark.

Another cool feature is using blackholes to actually consume CPU cycles to allow you to simulate a benchmark under various CPU loads.

The `@CompilerControl` annotation can be used to ask the compiler not to inline, explicitly inline, or exclude the method from compilation. This is extremely useful if you come across a performance issue where you suspect that the JVM is causing specific problems due to inlining or compilation:

```java
@State(Scope.Benchmark)
@BenchmarkMode(Mode.Throughput)
@Warmup(iterations = 5, time = 1, timeUnit = TimeUnit.SECONDS)
@Measurement(iterations = 5, time = 1, timeUnit = TimeUnit.SECONDS)
@OutputTimeUnit(TimeUnit.SECONDS)
@Fork(1)
public class SortBenchmark {
    private static final int N = 1_000;
    private static final List<Integer> testData = new ArrayList<>();

    @Setup
    public static final void setup() {
        Random randomGenerator = new Random();
        for (int i = 0; i < N; i++) {
            testData.add(randomGenerator.nextInt(Integer.MAX_VALUE));
        }
        System.out.println("Setup Complete");
    }

    @Benchmark
    public List<Integer> classicSort() {
        List<Integer> copy = new ArrayList<Integer>(testData);
        Collections.sort(copy);
        return copy;
    }

    @Benchmark
    public List<Integer> standardSort() {
        return testData.stream().sorted().collect(Collectors.toList());
    }

    @Benchmark
    public List<Integer> parallelSort() {
        return testData.parallelStream().sorted().collect(Collectors.toList());
    }

    public static void main(String[] args) throws RunnerException {
        Options opt = new OptionsBuilder()
            .include(SortBenchmark.class.getSimpleName())
            .warmupIterations(100)
            .measurementIterations(5).forks(1)
            .jvmArgs("-server", "-Xms2048m", "-Xmx2048m")
            .addProfiler(GCProfiler.class)
            .addProfiler(StackProfiler.class)
            .build();

        new Runner(opt).run();
    }
}
```

Running the benchmark produces the following output:

```
Benchmark                          Mode  Cnt      Score     Error  Units
SortBenchmark.classicSort         thrpt  200  14373.039 ± 111.586  ops/s
SortBenchmark.parallelSort        thrpt  200   7917.702 ±  87.757  ops/s
SortBenchmark.standardSort        thrpt  200  12656.107 ±  84.849  ops/s
```

Looking at this benchmark, you could easily jump to the quick conclusion that a classic method of sorting is more effective than using streams. Both code runs use one array copy and one sort, so it should be OK. Developers may look at the low error rate and high throughput and conclude that the benchmark must be correct.

But let's consider some reasons why our benchmark might not be giving an accurate picture of performance—basically trying to answer the question: "Is this a controlled test?" To begin with, let's look at the impact of garbage collection on the `classicSort` test:

```
Iteration 1:
[GC (Allocation Failure) 65496K->1480K(239104K), 0.0012473 secs]
[GC (Allocation Failure) 63944K->1496K(237056K), 0.0013170 secs]
10830.105 ops/s

Iteration 2:
[GC (Allocation Failure) 62936K->1680K(236032K), 0.0004776 secs]
10951.704 ops/s
```

In this snapshot, it is clear that there is one GC cycle running per iteration (approximately). Comparing this to parallel sort is interesting:

```
Iteration 1:
[GC (Allocation Failure) 52952K->1848K(225792K), 0.0005354 secs]
[GC (Allocation Failure) 52024K->1848K(226816K), 0.0005341 secs]
[GC (Allocation Failure) 51000K->1784K(223744K), 0.0005509 secs]
[GC (Allocation Failure) 49912K->1784K(225280K), 0.0003952 secs]
9526.212 ops/s

Iteration 2:
[GC (Allocation Failure) 49400K->1912K(222720K), 0.0005589 secs]
[GC (Allocation Failure) 49016K->1832K(223744K), 0.0004594 secs]
[GC (Allocation Failure) 48424K->1864K(221696K), 0.0005370 secs]
[GC (Allocation Failure) 47944K->1832K(222720K), 0.0004966 secs]
[GC (Allocation Failure) 47400K->1864K(220672K), 0.0005004 secs]
```

So, by adding in flags to see what is causing this unexpected difference, we can see that something else in the benchmark is causing noise—in this case, garbage collection.

The takeaway is that it is easy to assume that the benchmark represents a controlled environment, but the truth can be far more slippery. Often the uncontrolled variables are hard to spot, so even with a harness like JMH, caution is still required. We also need to take care to correct for our confirmation biases and ensure we are measuring the observables that truly reflect the behavior of our system.

In Chapter 6, we met JITWatch, which gave us another view into what the JIT compiler is doing with bytecode. This can often lend insight into why bytecode generated for a particular method may be causing the benchmark to not perform as expected.

Microbenchmarking is the closest that Java performance comes to a dark art. While this characterization is interesting, it is not completely deserved. It is still an engineering discipline undertaken by working developers. However, microbenchmarks should be used with caution:
* Do not microbenchmark unless you know you are a known use case for it.
* If you must microbenchmark, use JMH.
* Discuss your results as publicly as you can, and in the company of your peers.
* Be prepared to be wrong a lot and have your thinking challenged repeatedly.

One of the positive aspects of working with microbenchmarks is that it exposes the highly dynamic behavior and non-normal distributions produced by low-level subsystems. This, in turn, leads to a better understanding and mental models of the complexities of the JVM.

This, once again, raises the subject of statistics, as discussed in Chapter 2. The JVM routinely produces performance numbers that require careful handling—and the numbers produced by microbenchmarks are especially sensitive. It is the duty of the performance engineer to treat the observed results with a degree of statistical sophistication.

---

[^1]: High-frequency trading systems represent a tiny fraction of Java applications.
