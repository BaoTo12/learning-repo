# Profiling

The term **profiling** is used in different ways by programmers. There are several different ways to do profiling. The two most common ways are:
* **Execution profiling**
* **Allocation profiling**

In this chapter, we will cover both of these topics. We will start by focusing on execution profiling, using this subject to introduce the tools available to profile applications. Later in the chapter, we will look at memory profiling and see how different tools provide this feature.

One of the main themes we will study is how important it is for Java developers and performance engineers to understand how profilers work. Profilers can show application behavior incorrectly and show clear biases.

Execution profiling is one of the areas of performance analysis where these biases are most visible. A careful performance engineer will know about this possibility. They will adjust for it in different ways, including profiling with several tools to understand what is really happening.

It is just as important for engineers to handle their own mental biases and not look only for the performance behavior they expect. The antipatterns and thinking traps we saw in Chapter 2 (and also Appendix B) are a good place to start when training ourselves to avoid these problems.

---

## Introduction to Profiling

In general, JVM profiling and monitoring tools work by using low-level instrumentation. They either send (stream) data to an outside tool (sometimes a visual console or a SaaS platform) or save it in a log for later analysis. The low-level instrumentation often takes the form of either an agent loaded when the application starts, or a part that connects dynamically to a running JVM.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//72acc003-247c-4ba8-9aaf-48184cf76c1b/markdown_4/imgs/img_in_image_box_176_312_253_412.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A01Z%2F-1%2F%2F6c8882cfe6669c0525b9e6395afaa22c1d4aa4189c2c2b20ff2dac3d6c4f419c" alt="Image" width="7%" /></div>

> [!NOTE]
> Agents were introduced in “Monitoring and Tooling for the JVM” (Chapter 3). They are a very common technique used widely in the Java tooling field.

In broad terms, we need to separate:
* **Monitoring tools**: Whose main goal is watching the system and its current state.
* **Alerting systems**: For finding unusual or abnormal behavior.
* **Profilers**: Which give deep, detailed information about running applications.

These tools have different, though often related, goals. A well-run live application can use all of them.

However, the focus of this chapter is profiling. Its goal is to find user-written code that needs to be refactored and optimized for performance.

As discussed in “A Simple System Model” (Chapter 8), the first step in finding and fixing a performance problem is to identify which resource is causing the issue. A mistake at this step can be very costly.

> The scary thing about benchmarks is that they always produce a number, even if that number is meaningless. They measure something; we're just not sure what.
> 
> — Brian Goetz, “Anatomy of a flawed microbenchmark”

In other words, profiling tools will always give you a number. However, it is not always clear if that number is related to the problem you are trying to fix. For this reason, we introduced some of the main types of bias in Chapter 2 and waited to discuss profiling methods until now.

> A good programmer...will be wise to look carefully at the critical code; but only after that code has been identified. $^{1}$
> 
> — Donald Knuth

This means that before starting to profile, performance engineers should have already found a performance problem. You can find these problems from several sources, including:
* Performance regression tests in development or CI pipelines.
* UAT or special performance testing environments.
* Changes in production—for example, by watching how a canary behaves.
* Performance that was acceptable at first but has now become a problem—for example, by running out of capacity or due to data growth, which shows that indexing is not enough.

Note that performance regression tests can be hard to write well. Most applications should write them as integration tests rather than microbenchmarks.

Once a performance problem has been found, the next step is to figure out what caused it. It might be that the application code is the cause, but it could also be something like a library upgrade that has brought a performance drop (regression). If you have performance regression tests as part of CI/CD, you will want the build (deployment) to fail to stop it from going to Production.

In general, if the application uses close to 100% of CPU in user mode (which we can find using metrics or alerts), then this is strong proof of a performance problem. You should handle this with execution profiling. However, we must also remember that—even if the CPU is completely busy in user mode (not kernel time)—there is another possible cause that we must rule out before profiling: garbage collection.

All applications that need high performance should log GC events, so this check is simple: look at the GC log and application logs for the machine. Make sure that the GC log is quiet and the application log shows activity. If the GC log is active, then GC tuning should be the next step, not execution profiling.

A busy CPU is not the only situation where execution profiling is useful. For example, if the application is not meeting latency SLAs in Production, you might choose to see what the profiler can tell you. If it has high lock contention (which a profiler will show), that will stop it from using all available cores.

As a second example, an application that is waiting on database I/O because a code change has added a new, expensive `SELECT` query would also show up in an execution profiling run. $^{2}$ Some problems will only show up in profiling data from Production. This can happen when Staging does not have enough data in it for the missing index or expensive `SELECT` to cause a big delay, but Production definitely does.

---

## GUI Profiling Tools

In this section, we will discuss two different profiling tools with graphical UIs. There are many tools available in the market, so we focus on two of the most common open-source tools instead of trying to show all of them. We will focus on execution profiling here, but these tools offer a variety of other features too.

### VisualVM

As a first example of a profiling tool, let's look at **VisualVM**, which we saw in "Monitoring and Tooling for the JVM" (Chapter 3). It includes both an execution and a memory profiler and is a very simple, free profiling tool.

It is quite limited. It is rarely useful as a production profiler, but it can be helpful to performance engineers who want to understand how their applications behave in development and QA environments.

We have already seen some of the common screens in VisualVM. Let's look at the **Monitor** tab again. This shows basic telemetry data, as we can see in Figure 12-1, and is often the starting point for a profiling study.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//5a86b3d5-1941-4640-a497-91b9dc304d07/markdown_2/imgs/img_in_image_box_148_110_856_579.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A10%3A56Z%2F-1%2F%2F8cda6a322182731ec703bf9740422f4b662c85828c2662a640c4d14053c57aa1" alt="Image" width="70%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 12-1. VisualVM monitor view</div> </div>

In Figure 12-2, we can see the execution profiling view of VisualVM from the **Profiler** tab.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//5a86b3d5-1941-4640-a497-91b9dc304d07/markdown_2/imgs/img_in_image_box_144_704_857_968.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A10%3A56Z%2F-1%2F%2F1fa7ceb2ea5e9df837240a3303e00ba675a41397a127f5c94c29457ce46aea26" alt="Image" width="70%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 12-2. VisualVM execution profiler</div> </div>

This shows a simple view of running methods and how much CPU they use. It can be a useful first tool for performance engineers who are new to the skill and the trade-offs of profiling. However, the amount of profiling details you can see in VisualVM's UI is quite limited. Most performance engineers quickly outgrow it and turn to more complete tools on the market.

### JDK Mission Control

The **JDK Flight Recorder** and **JDK Mission Control** tools (called **JFR/JMC**) are profiling and monitoring technologies that Oracle got when it bought BEA Systems.

The two technologies are separate but related:
* **JFR** is a low-level, event-based performance data collection feature that is built into the HotSpot JVM. It provides events for the OS, the JVM, and JDK libraries. $^{3}$
* **JMC** is the visual part. When you first install it, it has a JMX Console and a handler for JFR data, though you can easily install more plug-ins from inside Mission Control.

These tools were first part of the tools offered for BEA's JRockit JVM. They were moved to the commercial version of Oracle JDK when JRockit was retired. To support the move from JRockit, the HotSpot VM was updated to add a large number of extra performance counters.

When Java 11 was released, JFR was given to OpenJDK, and JMC was moved to a standalone project. Later, JFR was added back to OpenJDK 8 as part of Update 272. This means that recent versions of OpenJDK 8 have JFR available.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//5a86b3d5-1941-4640-a497-91b9dc304d07/markdown_3/imgs/img_in_image_box_176_679_253_779.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A10%3A57Z%2F-1%2F%2F5512970b7b9926a3e7eee944844277483c553c159e7ebce843765e74ae4e8b29" alt="Image" width="7%" /></div>

> [!NOTE]
> You can build the JMC desktop application from source or download it from several places, including the Eclipse Adoptium project.

You start JMC by running the `jmc` binary. The startup screen for Mission Control is shown in Figure 12-3.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//5a86b3d5-1941-4640-a497-91b9dc304d07/markdown_4/imgs/img_in_image_box_143_108_860_425.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A10%3A57Z%2F-1%2F%2F17362eb7d7ab24d87f68d20f162662a2a9e3747d59c6b247c50a07a3620895a4" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 12-3. JMC startup screen</div> </div>

To profile, you must turn on Flight Recorder on the target application. You can do this in one of three ways:
1. Start the application with the JFR flags turned on.
2. Connect dynamically after the application has already started.
3. Start the application, and then use the `jcmd` command to start a JFR recording in a JVM on the local machine. $^{4}$

Once it is connected, enter the settings for the recording session and the profiling events, as shown in Figure 12-4.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//09b4e570-2fd7-4c21-b6ba-5eb239838786/markdown_0/imgs/img_in_image_box_146_109_858_661.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A15Z%2F-1%2F%2F939595134ed6cfcbf2a96a7aa91381e4bbd5f6b4e5a0f6361391d343ee71ae25" alt="Image" width="70%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 12-4. JMC recording setup</div> </div>

As discussed, execution profiling is not a perfect solution, and engineers must proceed carefully to avoid confusion and wrong ideas. There are unavoidable performance trade-offs in the settings of the tool, and you must also be aware of the extra work (overhead) that profiling causes.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//09b4e570-2fd7-4c21-b6ba-5eb239838786/markdown_0/imgs/img_in_image_box_176_854_253_955.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A15Z%2F-1%2F%2Ffe25473ea890aa308369aa1ef00ac19a18acaabc5c18d5914145e00c0fc062da" alt="Image" width="7%" /></div>

> [!NOTE]
> These screenshots show an application that is idle—meaning it is not doing much work. The images are only for showing how the tool looks.

When the recording finishes, an automated analysis is shown in the main window, with the left side showing many different available events. It looks like the view shown in Figure 12-5.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//09b4e570-2fd7-4c21-b6ba-5eb239838786/markdown_1/imgs/img_in_image_box_145_109_863_546.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A20Z%2F-1%2F%2Fd2e52c8e61802b0e885179905b40d6a5c6087fed977a9d8f1b5f5253b7bfa8c1" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 12-5. JMC automated analysis</div> </div>

Let's start by choosing the **Method Profiling** item from the left navigation. This shows a screen like Figure 12-6.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//09b4e570-2fd7-4c21-b6ba-5eb239838786/markdown_1/imgs/img_in_image_box_143_670_860_1106.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A21Z%2F-1%2F%2F03a5f36fa514c899eb6c80ef6e81a6b25564b0f4a1551a4422d1658fa9d05a33" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 12-6. JMC Method Profiling</div> </div>

From here, we can start to look at which hot methods are taking up most of the application run time. We can also use techniques like flame graphs (which we will discuss in more detail later), as long as our profiling setup supports them.

Overall, JMC is a solid, visual profiling tool, but there are limits to this kind of tool. In particular, it can be hard to see how to use desktop-based profiling with the kinds of observability methods we saw in Chapters 10 and 11.

We will see how to bridge this gap soon, but first we need to discuss some details of how execution profilers actually work.

---

## Sampling and Safepointing Bias

Traditionally, execution profiling uses regular sampling of stack traces to get a view of what code is running on each thread. This is because taking measurements is not free. Tracking every single method entry and exit would cause too much data collection work. So, instead, the system takes a sampled snapshot. However, you can only do this at a low frequency to avoid high overhead.

For example, the thread profiler in the New Relic Java agent samples every 100 ms. This is often considered a general rule (or best guess) of the limit on how often you can take samples without causing too much overhead.

In other words, the sampling time period represents a trade-off for the performance engineer. If you sample too often, the overhead becomes too high, especially for an application that needs high performance. On the other hand, if you sample too rarely, the chance of missing important behavior becomes too large because the samples might not show the real performance of the application.

> By the time you're using a profiler it should be filling in detail—it shouldn't be surprising you.
> 
> — Kirk Pepperdine (personal correspondence)

Sampling not only lets problems hide in the data, but in many profilers, samples are only taken at JVM safepoints. This is called **safepointing bias** and has two main results:
* All threads must reach a safepoint before the system can take a sample.
* The sample can only show an application state that is at a safepoint.

The first result adds extra overhead when creating a profiling sample from a running process. The second result distorts (skews) the spread of sample points because it only samples the state when the thread is at a safepoint.

Sampling execution profilers use the `GetCallTrace()` function from HotSpot's C++ API to collect stack samples for each thread. The usual design is to collect the samples inside an agent, and then log the data or do other processing later.

However, in its first version, `GetCallTrace()` had a very large overhead: if there are $N$ active threads, collecting a stack sample made the JVM safepoint $N$ times. This overhead is one of the main reasons that set a limit on how often you could take samples, at least in Java 8 and older versions.

This limit was partly fixed by JEP 312, “Thread-Local Handshakes”. This was also needed to prepare for the Shenandoah and ZGC collectors we discussed in Chapter 5. More recent versions, from Java 11 onward, have a much lower overhead for thread profiling because of this change.

Therefore, a careful performance engineer will watch how much safepointing time the application uses. If the application spends too much time in safepoints, its performance will drop. Any tuning work might then use incorrect data. A JVM flag that is very useful for finding cases of high safepointing time is:

```
-XX:+PrintGCApplicationStoppedTime
```

This will write extra information about safepointing time into the GC log. Some tools can automatically find problems in the data from this flag. They can separate safepointing time from pause times caused by the OS kernel.

We can show an example of the problems caused by safepointing bias with a counted loop. This is a simple loop, similar to this snippet:

```java
for (int i = 0; i < LIMIT; i += 1) {
    // only "simple" operations in the loop body
}
```

We have intentionally not defined what a “simple” operation means in this example, because the behavior depends on the exact optimizations the JIT compiler does. You can find more details in “Diagnosing Application Problems Using Observability” (Chapter 11).

Examples of simple operations include math operations on basic types (primitives) and method calls that are fully inlined (so that there are no actual method calls inside the loop).

If `LIMIT` is large, the JIT compiler will translate this Java code directly into compiled code. This includes a loop-back path to return to the top of the loop. As discussed in "JVM Safepoints" (Chapter 3), the JIT compiler puts safepoint checks at loop-back edges. This means that for a large loop, the thread can safepoint once for every loop run (iteration).

However, for a small `LIMIT`, this will not happen. Instead, the JIT compiler will unroll the loop. This means the thread running the small counted loop will not safepoint until after the loop finishes.

Thus, sampling only at safepoints leads directly to a bias that depends on the size of the loops and the types of operations we run in them.

This is clearly not good for getting precise and reliable performance results. This is also not just a theoretical problem: loop unrolling can create large amounts of code, leading to long sections of code where the system never takes samples.

However, there is another option to sampling profilers, and that is the subject of our next section.

---

## Modern Profilers

In this section, we will discuss three modern open-source tools that can give better insight and more accurate performance numbers than old sampling profilers. These tools are:
* `perf`
* Async Profiler
* Honest Profiler

We will discuss each in turn. Let's start with the `perf` tool.

### perf

perf is a useful, lightweight profiling tool for applications that run on Linux. It is not specific to Java/JVM applications. Instead, it reads hardware performance counters and is included in the Linux kernel under `tools/perf`.

Performance counters are physical hardware registers that count hardware events that performance analysts care about. These include executed instructions, cache misses, and branch mispredictions. This forms the basis for profiling applications.

Java brings some extra challenges for `perf` because of the dynamic nature of the Java runtime. To use `perf` with JVM applications, we also need a bridge to map the dynamic parts of the VM execution.

This bridge is `perf-map-agent`. It is an agent that creates dynamic symbols for `perf` from unknown memory regions, including JIT-compiled methods. Because HotSpot creates its interpreter and jump tables for virtual dispatch dynamically, the agent must also create symbol entries for them. `perf-map-agent` consists of an agent written in C and a small Java loader (bootstrap) that connects the agent to a running Java process if needed.

In Java 8u60, a new flag was added to allow better interaction with `perf`:

```
-XX:+PreserveFramePointer
```

Unfortunately, this flag is off (`false`) by default. So when using `perf` to profile Java applications, we strongly recommend that you turn it on explicitly.

> [!NOTE]
> Turning on this flag disables a JIT compiler optimization, so it can lower performance slightly.

One clear way to show the numbers that `perf` produces is the **flame graph**. This shows a very detailed breakdown of exactly where execution time is spent. Figure 12-7 shows an example.

The flame graph method has changed over time, so there are some important details you should know about reading a flame graph:
* The x-axis shows the stack profile population, sorted alphabetically.
* The y-axis shows stack depth, counting from the bottom.
* Each rectangle represents a stack frame. The wider a frame is, the more often it was present in the stacks.
* The top rectangle shows what is running on the CPU, and below it is its parent methods (ancestry).
* At first, flame graphs used random colors to help you tell adjacent frames apart.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//0bd84c63-d2ea-41b0-a7a3-8897d2047ac1/markdown_1/imgs/img_in_image_box_155_113_849_844.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A10%3A56Z%2F-1%2F%2Fb83c59fc5931cddb5c5b2ab66a4659847cee4e400b330f20ddefe1d710c679df" alt="Image" width="68%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 12-7. Java flame graph</div> </div>

Of these points, understanding that the x-axis does not show the passage of time is probably the most important. Flame graphs organize the samples alphabetically and merge frames wherever possible. This gives a better view of the overall profile.

There have been several improvements and changes to Gregg's first concept of flame graphs. For example, some tools have begun using a consistent coloring style. In this style, the color of a rectangle has a specific meaning (such as whether it is a Java or a native frame), instead of just using random colors to make the graphs easy to read.

One important variation is the **flame chart**. These were first created for Google Chrome's WebKit Web Inspector. Flame charts have time on the x-axis instead of alphabetical sorting. This has the advantage that you can see time-based patterns, but it can only show the pattern for a single thread. This is often fine for JavaScript applications, which are usually single-threaded, but it is much less useful for Java applications.

The Netflix Technology Blog has detailed articles about how the team uses flame graphs on its JVMs.

Remember that `perf` is based on hardware performance counters. The events that `perf` needs for CPU profiling might not be available in containers, or in restricted security (seccomp) environments.

Let's move on to look at Async Profiler, which uses `perf` as a building block for JVM profiling.

### Async Profiler

The main goals of **Async Profiler** are to:
1. Remove the safepointing bias that most other profilers have.
2. Run with much lower overhead than old profilers.

To do this, Async Profiler uses a private API call: `AsyncGetCallTrace` (or **AGCT**) inside HotSpot. This means, of course, that Async Profiler will not work on a non-OpenJDK JVM. It works with OpenJDK-based JVMs (including builds from Adoptium, Amazon, Microsoft, Oracle, Red Hat, and Zulu from Azul), and HotSpot JVMs built from scratch.

> [!NOTE]
> Usually, tools like Async Profiler run in headless mode (without a GUI) as data collection tools. With this method, you use other tools or custom scripts to view the data.

Because it depends on `perf`, Async Profiler only works on operating systems where `perf` works (mostly Linux). Async Profiler uses the Unix OS signal `SIGPROF` to interrupt a running thread. The system can then collect the call stack using the private `AsyncGetCallTrace()` method.

This only interrupts threads one by one, so there is never a global synchronization event. This avoids the conflict (contention) and overhead usually seen in old sampling profilers. Inside the asynchronous callback, the call trace is written into a lock-free ring buffer. A separate, dedicated thread then writes the details to a log without pausing the application.

There are some extra details about how non-sampling profilers work that you should know. First, let's look at this question:
> When a CPU receives an outside interrupt (such as a cache miss), at what point in the instructions is the CPU interrupted?

This question is very important for modern out-of-order (OOO) CPUs. Almost all modern servers use these CPUs.

If you look at the output of a low-level profiler (like `perf`), you might see an instruction marked with an L1 cache miss event that was not actually caused by this instruction. This is called **skid**. It is defined as the distance between the instruction that caused the event and the instruction that is marked with the event.

A related problem for the JVM is that there is still a hidden form of safepoint bias. Even though non-sampling profilers using AGCT are not safepoint biased when collecting stack traces, finding the name of the last method (resolving the last frame) is still biased toward the saved debug data. Unfortunately, by default, this debug data is only saved at safepoints.

To fix this, non-sampling profilers try to turn on the flag `-XX:+DebugNonSafepoints` as soon as possible to get more precise details.

Async Profiler also tries to solve the `perf_events` problem in containers by adding a new CPU sampling engine based on `timer_create`. This combines the benefits of the older sampling engines, with the small trade-off that it cannot collect OS kernel stacks.

This means that recent versions of Async Profiler work in containers by default, have fewer timing biases, and do not use up file descriptors. $^{5}$

> [!NOTE]
> To use Async Profiler on its own, you will need to write some scripts specific to your application. Instead of going into those complex details, you should look at outside resources, like the Async Profiler GitHub page.

Finally, another choice instead of Async Profiler that was popular a few years ago is **Honest Profiler**. It uses the same internal API as Async Profiler. It is also an open-source tool that runs only on HotSpot JVMs. However, it is no longer active, so you should not use it for new projects. You should move away from any existing setups that use it.

In the next section, we will look at JFR, a built-in profiler that is similar to Async Profiler in many ways.

---

## JDK Flight Recorder (JFR)

We saw JFR in “GUI Profiling Tools”. It is a low-overhead tool included with OpenJDK to collect diagnostic and profiling data. It is meant to be used by a running Java application on the HotSpot JVM in live production.

For a production profiler, the overhead must be small enough to handle during both normal and high-use times. JFR achieves this by using profiles. Remember that JFR is event-based, so different profiles enable different sets of events for JFR to watch.

Out of the box, JFR includes two profiles: “Continuous” (sometimes called “Default”) and “Profiling.” The XML configuration files for these profiles are in the JDK installation as `default.jfc` and `profile.jfc`.

Of these two standard profiles, Continuous is designed for always-on profiling but might not have enough detail, especially for allocation profiling. The “Profiling” profile has much more detail but also has a higher overhead while running.

> [!NOTE]
> Advanced users of JFR can choose to create a custom profile with a different set of events. This can better track the performance areas that the team cares about.

On the subject of overhead, according to Oracle presentations and demos, JFR profiling has about a 1% impact on normal application performance when using the Continuous profile. The authors agree: they have usually seen an impact of about 3% when using a profile that includes allocation profiling.

Alternatively, a more structured study (done on microbenchmarks rather than complete systems) can be found in “Don’t Trust Your Profiler: An Empirical Study on the Precision and Accuracy of Java Profilers”.

This paper follows the general methods of Georges et al. (2007), which we briefly discussed in Chapter 2. It compares JFR with several other profilers (including Async Profiler and Honest Profiler).

The general agreement is that JFR causes an overhead that is within the acceptable range for profilers. You can use it for always-on profiling, though some applications might have resource needs that make the overhead too expensive.

Because of this, JFR is used as a base to build many other observability and monitoring tools. For example, both Datadog and New Relic include execution profilers that use JFR data.

The main way to understand what JFR can do is to look at the events and the data inside them. Let's take a closer look.

JFR events are typed data, and each event type has a name and a structure. For example, the `jdk.CPULoad` event shows a time series of CPU data. It has several fields like `jvmUser`, `jvmSystem`, and `machineTotal`, and a timestamp shown by the event start time.

Other events have different structures. For example, GC events are very detailed (fine-grained) and might show just a single part of a collection cycle. Lock events, like `jdk.JavaMonitorEnter`, have a limit (threshold) value. This lets JFR record only the times when a Java monitor was held for longer than a set time (such as 10 ms).

The JDK includes a simple command-line tool to analyze JFR dump files. You can create these dump files in one of three ways: using the JMC GUI, using `jcmd` on the command line to control a running Java process, or by adding a command-line flag to your Java startup.

For the `jcmd` method, we must run three separate commands to create a file: one to start, one to dump the data, and one to stop the recording after we have collected enough data:

```bash
jcmd <pid> JFR.start name=MyRecording settings=default
jcmd <pid> JFR.dump filename=my-recording.jfr
jcmd <pid> JFR.stop
```

To start a JFR recording when the application starts, we must add this command-line flag and give the right options:

```
-XX:StartFlightRecording=<options>
```

These recordings can run for a set time or use a ring-buffer mode (which we will discuss later). Once we have the dump file, we can use the `jfr` tool included with the JDK to look at the events inside it.

> [!NOTE]
> The `jfr` tool has many subcommands. Use `jfr --help` to see them all.

For example, we can see the `CPULoad` and `JavaMonitorEnter` events with a single `jfr print` command:

```bash
jfr print --events CPULoad,JavaMonitorEnter recording.jfr
```

This can produce output similar to this:

```
jdk.CPULoad {
    startTime = 11:51:57.745
    jvmUser = 8.75%
    jvmSystem = 0.57%
    machineTotal = 13.50%
}

jdk.JavaMonitorEnter {
    startTime = 11:51:58.065
    duration = 12.1 ms
    monitorClass = jdk.jfr.internal.PlatformRecorder (classLoader = bootstrap)
    previousOwner = "RMI TCP Connection(idle)" (javaThreadId = 32)
    address = 0x12CE66508
    eventThread = "JFR Periodic Tasks" (javaThreadId = 26)
}
```

By trying a few `jfr print` commands, you can see the different shapes of each event type. The `jfr` tool can also output data in XML and JSON formats.

> [!NOTE]
> An event browser for JFR events is run by the team at SAP. It covers LTS and recent versions of OpenJDK.

You can also easily read JFR dump files in your Java code by looping through a `RecordingFile` object:

```java
String fileName = // ... some JFR file
var recording = new RecordingFile(Paths.get(fileName));
while (recording.hasMoreEvents()) {
    var event = recording.readEvent();
    if (event != null) {
        var details = decodeEvent(event);
        if (details == null) {
            System.err.println("Failed to recognize details");
        } else {
            // We'd process details here, for now just log
            System.out.println(details);
        }
    }
}
```

Of course, you still need to decode the events of interest in the `decodeEvent()` method. One way to do this is to use a static collection of mappers, which we use like this:

```java
public Map<String, String> decodeEvent(final RecordedEvent e) {
    for (var ent : mappers.entrySet()) {
        if (ent.getKey().test(e)) {
            return ent.getValue().apply(e);
        }
    }
    return null;
}

private static Predicate<RecordedEvent> makePredicate(String s) {
    return e -> e.getEventType().getName().startsWith(s);
}

private static final Map<Predicate<RecordedEvent>, Function<RecordedEvent, Map<String, String>>> mappers =
    Map.of(
        makePredicate("jdk.CPULoad"),
        ev -> Map.of(
            "timestamp", "" + ev.getStartTime(),
            "user", "" + ev.getDouble("jvmUser"),
            "system", "" + ev.getDouble("jvmSystem"),
            "total", "" + ev.getDouble("machineTotal")
        )
    );
```

There are also many open-source tools available to handle JFR data. An interesting one is **JFR Analytics** by Gunnar Morling. It gives a SQL-like interface to query JFR recording files, and you can use it with standard JDBC code.

Now that we understand other options instead of sampling profilers and have seen JFR in context, let's return to how we use profiling in our daily operations.

---

## Operational Aspects of Profiling

Profilers are developer tools used to find problems or understand application behavior at a low level. On the other side of tools are observability and operational monitoring tools. These exist to help a team see the current state of the system and decide if the system is running normally or has a problem.

The area of these tools is huge, and a single book cannot cover every tool in this area. Instead, we will choose a few main tools to focus on.

These examples can be a starting point for you to study the options and decide which one is right for your applications. In observability and performance analysis, there is no easy way: you must study your systems and find the methods that work for your specific area.

### Using JFR As an Operational Tool

JFR has a long history, which has both good and bad sides (a double-edged sword). On one hand, it has been tested for years in production and is one of the best tools because it is deeply built into HotSpot.

However, it was created in the past, when production profiling meant creating a binary dump file (which is not human-readable) and copying it to a developer's machine to analyze it offline.

In our new world of cloud-native applications, this is not always easy or convenient. Simply put, we need new patterns and methods to make JFR useful in the cloud-native world.

One common way to use JFR is in a **ring buffer** setup. This is usually done by starting the application with JFR options passed to the `-XX:StartFlightRecording` flag, like this:

```
-XX:StartFlightRecording=disk=true,filename=/sandbox/service.jfr,maxage=4h,settings=profile
```

This tells JFR to keep events from the “Profiling” profile that are up to four hours old in memory. It deletes older events as new ones arrive. When we ask for a recording, JFR dumps the current buffer state into `/sandbox/service.jfr`.

This lets an operator dump a file when needed and “go back in time” to see what happened after an incident started, as long as the ring buffer is large enough. This is a very useful method during outage recovery.

Of course, you must allow for the extra memory used to buffer events in the container. This has a hidden result you should know about.

Note that in our example, we use the `maxage` setting to say how long we want to keep events. Because JFR is event-based, the amount of data it creates depends on the JVM's activity (such as the number of garbage collections) and does not have a fixed limit.

In turn, if an application is close to its container memory limit, a burst of unexpected activity can cause the JFR buffer to go over that limit. This can make the container runtime or the OS OOM-killer stop the application process.

For this reason, some teams prefer to use the `maxsize` setting instead. This guarantees that JFR will not cause the container to be killed. However, you will not know exactly how far back in time you can look in the JFR buffer.

In addition, JFR writes to a file on the disk, so you must make sure there is enough free disk space. You must also make sure the container is not stopped (evicted) by Docker or Kubernetes for doing too much disk I/O in what should be a stateless container.

Newer versions of Java, like Java 17 and 21, also include a **JFR Event Streaming** feature. This is an API that lets programs receive callbacks for JFR events. This allows the application (or an observability thread in a Java agent) to respond to events as they happen. The main class here is the `RecordingStream`. It lets a developer register interest in specific event types and provide a callback object to handle them.

This is much better as a base for building observability tools, but it has the problem that Java 17+ has only about a 35% market share as of April 2024. Instead, other tool features have been created.

### Red Hat Cryostat

Cryostat is a JFR tool for containerized Java applications. Red Hat first created it, and it is supported on the OpenShift cloud platform. However, it is also available as an open-source project that works on any Kubernetes setup.

Cryostat tries to make working with JFR files in a Kubernetes cluster simpler. It lets users start, stop, get, and analyze JFR event data remotely.

Cryostat needs `cert-manager`, Operator Lifecycle Manager (OLM), and Operator Hub to install successfully. It offers features like:
* Application topology view
* Notifications
* Grafana view (for metrics)
* Smart triggers
* Automated rules

In Figure 12-8, we can see the topology view that the general Kubernetes version of Cryostat provides.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//6cfb42d7-873d-4172-aaf5-ce29c7f04707/markdown_0/imgs/img_in_image_box_148_437_862_795.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A12Z%2F-1%2F%2F33cc0cf52e4dbc113979f9d924d6df3580c3a3423c2565093f0d1ea73fc44c07" alt="Image" width="70%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 12-8. Cryostat topology view</div> </div>

The image shows a Kubernetes setup of several pods, including both sample applications and the Cryostat pods (another example of how observability services should themselves be observable).

Cryostat is a very useful tool for working with JFR, but a full discussion of it is outside the scope of this book. For completeness, in the commercial tools space, both Datadog and New Relic (and others) provide execution profilers based on JFR.

### JFR and OTel Profiling

In “The Three Pillars” (Chapter 10), we saw the three pillars of observability. We also discussed the possibility of using profiling as a fourth pillar. This improvement is being discussed in the OpenTelemetry working groups. For Java, several different profilers could be used as data sources for a future OTel profiling signal type.

JFR could be one of the data sources that gives the profiling signal, but there are some difficulties. For example, a practical OTel profiling setup would need to use JFR Event Streaming because of OTel's time window limits. This means it would only work on Java 17 and newer.

Also, at the time of writing (August 2024), there is no simple way to connect a trace ID to a JFR profiling sample. Work in this area is ongoing, not just for Java but for other languages in OpenTelemetry.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//6cfb42d7-873d-4172-aaf5-ce29c7f04707/markdown_1/imgs/img_in_image_box_176_413_252_513.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A13Z%2F-1%2F%2F1647d7f5a77d549110caa82ffd590f4fe90fd8c68d9c958267049470dd92759b" alt="Image" width="7%" /></div>

> [!NOTE]
> The `opentelemetry-java-instrumentation` project includes an OpenTelemetry JVM metrics setup based on JFR. This defines a standard set of JVM metrics.

Overall, JFR is an important data source for the OTel ecosystem and is part of the general move toward open instrumentation. However, it is not a complete execution profiling tool by itself.

### Choosing a Profiler

There are several things to think about when choosing a profiler, such as:
* Do I need a tool with a visual GUI?
* Is this tool for live production profiling, or for development and CI use?
* How much time and effort can I spend on setting up my profiler?
* How much overhead can my application handle from the profiling tool?

In general, you can describe open-source profilers like this:
* **VisualVM**: A visual GUI tool that is easy to set up, but needs a direct JMX connection or a snapshot file to work.
* **JMC**: A more advanced GUI tool that can use JFR, but only through dump files. It does not support streaming events.
* **JFR**: A low-overhead, headless profiling engine built into the JVM. It can connect with many other tools for both offline and operational use.
* **perf**: A very low-level tool that looks at hardware events on Linux. It is not Java-specific and needs extra bridging tools.
* **Async Profiler**: Builds on top of `perf_events`. It provides a low-overhead tool that does not have safepoint bias, but it has fewer integrations than JFR.

Finally, there are commercial profilers available, like JProfiler and YourKit. These were once much better than the free tools, but that gap has closed in recent years. Some teams still find value in them, but we do not discuss them in this book because our focus is on open-source products.

To end this chapter, let's move on from execution profiling and look at the other main form of profiling: memory.

---

## Memory Profiling

Execution profiling is an important part of profiling, but it is not the only one. Many applications also need some level of memory analysis. Here we will look at two main types: allocation profiling and heap dump analysis.

### Allocation Profiling

As we discussed in Chapter 4, one of the most important parts of performance analysis is looking at how the application allocates memory. This leads to **allocation profiling**, and you can use several different methods.

For example, we could use the Visitor pattern that tools like `jmap` depend on. $^{7}$ Figure 12-9 shows the memory profiling view of VisualVM, which uses this method to create a list (histogram) of memory used by each type of object.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//6cfb42d7-873d-4172-aaf5-ce29c7f04707/markdown_3/imgs/img_in_image_box_146_108_856_567.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A14Z%2F-1%2F%2Fccd42b34207d05f97b13d6730b5fdf5f4ce65f35e9a27ef7e536b9703e23dc45" alt="Image" width="70%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 12-9. VisualVM memory profiler</div> </div>

This is a simple view of memory, but there are two things to point out here. First, when creating this list (histogram), you have two options:
* A snapshot that is quick to make but contains both live objects and garbage. This matches the `jmap -histo` command.
* An accurate snapshot that needs a stop-the-world (STW) GC before it is made. This matches the `jmap -histo:live` command.

Second, even a simple list can tell us a lot about an application's memory usage.

In most applications, strings are by far the most common data type. Inside a string is a reference to a `byte[]` (or a `char[]` in Java 8. This implementation changed in JEP 254). Therefore, we expect to see at least as many `byte[]` objects as strings.

We also usually see other common objects, like `HashMap` entries and `Object[]`. Business applications will also often see their own domain objects appear in the list of most common objects. This can give you a quick check by asking: “Is the number of domain objects in the right range for my application?”

Moving on from VisualVM, and shifting our focus from heap usage to profiling GC, we can use the JMC tool to collect statistics. These contain some values that are not available in the old Serviceability Agent, though most of the counters shown are duplicates of the SA counters.

The benefit is that the cost for JFR to collect these values for JMC is much lower than with the SA. The JMC views also give the performance engineer more flexibility in how they see the details.

Another way to do allocation profiling is to look at TLABs, which you saw in Chapter 4. JFR uses events to get alerts when an object is allocated:
* In a TLAB (the `jdk.ObjectAllocationInNewTLAB` event)
* Outside of a TLAB (the “slow path”, `jdk.ObjectAllocationOutsideTLAB` event)

This lets JFR calculate how fast the application allocates memory.

The Allocations view in JMC/JFR can show this TLAB allocation view. Figure 12-10 shows JMC's view of allocations.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//6cfb42d7-873d-4172-aaf5-ce29c7f04707/markdown_4/imgs/img_in_image_box_143_559_859_993.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A14Z%2F-1%2F%2Fa9243c3f807bac35fa27417c8d5149ae97b159a60a472cad3fd886666f2f550d" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 12-10. JMC Allocations profiling view</div> </div>

JFR also has events that can act as a memory leak profiler. It samples object allocations to track how long they live, using the `jdk.OldObjectSample` event. Over time, it can suggest where to start looking for a possible memory leak.

### Heap Dumps

Another memory profiling method is **heap dump analysis**. Unlike allocation profiling, this is an offline process where you create a snapshot of the whole heap and save (dump) it to a file.

You can do this with the `jmap` command, for example:

```bash
jmap -dump:live,format=b,file=heap.bin <pid>
```

You can then use a separate tool to look at and analyze this dump file. This helps you find important facts, such as the active objects (live set), the numbers and types of objects, and the shape of the object graph. These tools can run in batch mode or let you interact with them.

When you load a heap dump in an interactive tool, you can go through and analyze the snapshot of the heap from when it was created. You will be able to see live objects and objects that are dead but have not been collected yet.

One big problem with heap dumps is their size. A heap dump is often 300% to 400% the size of the memory you dump. For a live, multi-gigabyte heap, this is very large. You must write the heap to disk, and for a real production system, you must also download it over the network, which might be hard for a container application.

Once you download it, you must load it on a computer with enough resources (especially memory) to handle the dump without causing long delays. Working with large heap dumps on a machine that cannot load the whole dump at once is very slow because the computer must constantly move parts of the dump file on and off the disk.

Creating a heap dump file also requires the same trade-off as the heap histogram: either garbage shows up along with the live objects, or the application stops completely (STW) while the system goes through the heap and writes the dump. In a modern cloud system, this stop-the-world pause can make the JVM process look dead while it goes through a large heap. This can cause Kubernetes to kill the pod.

Despite these difficulties, there are times (like hard-to-find memory leaks) when heap dumps are useful. However, you should know about their limits so that you do not slow down or kill your production pods by accident. Let's look at how to create and work with heap dumps.

As we saw in Figure 12-9, VisualVM can create a heap dump. You can also use the tool to view the contents of a heap dump file. However, in practice, live production heap dumps are hard to work with in VisualVM. An alternative is the **Eclipse Memory Analyzer** (also called **MAT**), which is a standalone tool used to analyze heap dumps.

Much of the power of MAT comes from its ability to go through the object graph and create reports based on the shape of the heap. For example, you can use MAT to find possible memory leaks, analyze what uses the most memory, and do other memory tasks.

Figure 12-11 shows an example of MAT with several standard reports open in tabs.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//bd0fd6c9-76e1-4151-8804-bf5cd42a4c69/markdown_1/imgs/img_in_image_box_143_260_858_561.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A09Z%2F-1%2F%2F6f602706b285921fead7ac055eb46e7aba70b34c8ac948d96408bb1abdbd76e8" alt="Image" width="70%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 12-11. Example MAT view</div> </div>

In general, MAT is an advanced tool. While the basic, ready-to-use reports are useful, the real power of MAT comes from spending time learning how to use it well.

Allocation and heap profiling are important for most applications that need to be profiled. Performance engineers should not focus only on execution profiling while ignoring memory.

As a final note, older books might mention the `hprof` heap profiling agent. This was meant to be a reference tool for JVMTI technology, not a production-grade profiler. The documentation often points this out.

Despite this, many developers started to think of `hprof` as a good tool for real use. For this reason, the `hprof` tool was removed in Java 9, though you can still create heap dumps in the `hprof` format using tools like `jmap`. If your current tools use `hprof`, you should switch to a supported tool like MAT.

---

## Summary

The subject of profiling is often misunderstood by developers. Both execution and memory profiling are needed methods. However, it is very important that performance engineers understand what they are doing and why. Using the tools blindly can give you completely incorrect or useless results and waste a lot of time.

Profiling modern applications requires using tools. There are many options to choose from, including both commercial and open-source options.

In the next chapter, we will move on from profiling. We will talk specifically about concurrency and how to use it efficiently in your Java applications. This will include key methods that also work for distributed systems, so they will be useful for cloud-native systems.

---

$^{1}$ Donald Knuth's paper “Structured Programming with go to Statements” is the source for this quote.
$^{2}$ Database I/O is a classic example of "off-CPU" time, where execution profiling can help find what the thread is waiting for.
$^{3}$ JFR was first created as a commercial feature of Oracle JDK before it was open-sourced.
$^{4}$ The `jcmd` command is the standard command-line tool for sending diagnostic commands to a running Java process.
$^{5}$ This is a major improvement for container deployments.
$^{7}$ The Serviceability Agent (SA) is the low-level part that `jmap` uses to inspect the JVM process memory.
