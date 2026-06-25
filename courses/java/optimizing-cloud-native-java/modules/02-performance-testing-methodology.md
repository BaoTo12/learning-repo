# Performance Testing Methodology

**Performance testing** is done (conducted) for many different reasons. In this chapter, we will introduce the different types of performance tests a team can run. We will also discuss the best ways (best practices) to run each type.

Later in this chapter, we will cover basic statistical ideas (concepts). We will also talk about very important human behaviors (factors) that are often forgotten (overlooked) when we find and solve performance problems (troubleshooting).

---

## Types of Performance Tests

> [!WARNING]
> **Pitfall: Believing that Doing Something is Always Better than Doing Nothing**
> Performance tests are often run for the wrong reasons. They are also often done badly (executed poorly). This usually happens because teams do not fully understand performance analysis. Or, they believe that "doing something is always better than doing nothing." As we will see throughout this book, this belief is a dangerous idea that is only partly true at best.

One of the more common mistakes is to talk generally about "performance testing" without talking about the details (specifics). In fact, there are many different types of large-scale performance tests that you can do on a system.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//94cfe331-6ca6-4d2f-8507-f2fac3fb0d26/markdown_0/imgs/img_in_image_box_176_940_252_1040.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A14Z%2F-1%2F%2F6c09882b29be7f41ffc3aac6e5ab59ce66d1e007128ec04d8136b0e88f2c6c17" alt="Image" width="7%" /></div>

Good performance tests are **quantitative** (based on numbers). They ask questions that produce a number as an answer. You can treat this answer as a result of a science experiment (an experimental output) and study it using statistics (statistical analysis).

The types of performance tests we will talk about in this book usually have separate goals, though some goals are similar and cover the same areas (overlap). So (therefore), it is important to understand the questions based on numbers (quantitative questions) you want to answer. You must do this before you decide what type of testing to do.

This does not have to be difficult. Simply writing down the questions the test is meant to answer can be enough. However, it is common to think about why these tests are important for the application. You should check (confirm) this reason with the owner of the application (or key customers).

Some of the most common test types, and an example question for each, are as follows:

| Test Type | Key Question to Answer | Focus & Goal (Objective) |
| :--- | :--- | :--- |
| **Latency Test** | What is the total time to complete a transaction from start to finish? | It directly affects the user experience, or it helps meet service-level agreements (SLAs). |
| **Throughput Test** | How many simultaneous (concurrent) transactions can the system's current capacity handle? | It measures the highest stable throughput before the system's performance starts to drop (degrade). |
| **Stress Test** | What is the point where the system breaks? | It finds extra room (headroom) and turning points (inflection points) by slowly increasing the load to the limit. |
| **Load Test** | Can the system handle a specific planned (projected) load? | A simple yes/no (binary) test done before known business events, such as marketing campaigns. |
| **Endurance Test (Soak Test)** | What unusual performance behaviors (anomalies) appear when the system runs for a long time? | It finds slow memory leaks, run-out resources (exhaustion), cache filling with bad data (pollution), or GC memory fragmentation. |
| **Capacity Planning Test** | Does the system scale as expected when you add more hardware resources? | A test that looks to the future to find the resources needed for planned growth. |
| **Degradation Test (Partial Failure)** | What happens when parts of the system stop working (partial failure)? | It measures how the system behaves under load when a server node or a part of the cluster is lost. |

Let's look in more detail at each of these test types in turn.

---

### Latency Test

**Latency** is one of the most common metrics (measurements) tested because it directly affects the user experience: how long must a customer wait for a transaction or page load to finish?

This can be a double-edged sword (having both good and bad sides). Because the question is so simple, teams often focus too much on latency. They forget to write down clear questions for other types of performance tests.

The main goal of a latency tuning project is to improve user experience or meet a **service-level agreement (SLA)**. An SLA is a formal agreement on how fast the system must respond.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//94cfe331-6ca6-4d2f-8507-f2fac3fb0d26/markdown_1/imgs/img_in_image_box_176_1068_253_1168.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A18Z%2F-1%2F%2F8d61e739f4ea3adf9eabfdafd39e9ed36fc6b374593c809c904ceff09ebb6ad8" alt="Image" width="7%" /></div>

However, even in the simplest cases, a latency test has some hidden details (subtleties) that you must treat carefully. One of the most important is that a simple average (mean) is not very useful to measure how well an application responds to requests. We will discuss this topic more in “Statistics for JVM Performance” on page 29 and look at other measurements.

### Throughput Test

**Throughput** measures the rate of work a system can do. It is closely connected to latency, and you should study the two together.

- **Controlling Variables (factors that you keep constant)**: When you test latency, you must keep the number of simultaneous transactions constant. On the other hand (conversely), during a throughput test, you must watch latency. This is to ensure latency does not rise to unacceptable levels as the load increases.
- **Interdependence (how they depend on each other)**: You should always report the system's latency alongside the specific throughput level at which you measured it, and vice versa.

We find the **maximum throughput** by watching for a sudden change in the way latency is spread out (latency distribution). This change shows a **breaking point** (or **inflection point**). A **stress test** finds these breaking points. In contrast, a **throughput test** measures the highest stable throughput a system can keep up (sustain) before performance starts to drop (degrade).

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//94cfe331-6ca6-4d2f-8507-f2fac3fb0d26/markdown_2/imgs/img_in_image_box_176_517_253_617.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A22Z%2F-1%2F%2F63c799f66a49bf51c2cb8fb9a819b49d0acab5168173ab3a242cba29bf57e87d" alt="Image" width="7%" /></div>

> **Insight: The Dual Nature of Latency and Throughput**
> You should state the system's latency at known and controlled throughput levels, and you should state the throughput at known and controlled latency levels.

Once again, we talk about these test types separately, but they are rarely completely independent in the real world.

### Stress Test

A **stress test** finds the system's extra capacity (headroom). The process is:

1. Place the system in a steady state at a specific throughput level. This level often matches the current peak in production.
2. Slowly increase the number of simultaneous (concurrent) transactions.
3. Watch the system measurements (metrics) until they start to drop (degrade).

The load level the system kept up just before the metrics started to drop represents the maximum capacity reached in the stress test.

### Load Test

A **load test** is a simple yes/no (binary) check: *Can the system handle a specific planned (projected) load?*

Teams usually run load tests before major business events that are expected to bring high traffic. Examples include:
- Bringing in a large new customer or expanding into a new market.
- Starting advertising or marketing campaigns.
- Handling sudden traffic spikes from events on social media or content that spreads very fast (viral content).

### Endurance Test

Some performance problems only appear after a system runs for a long time (often several days). These problems include:
- Slow **memory leaks**.
- **Cache pollution** (where a cache fills with old or useless data).
- **Memory fragmentation** (which can eventually cause a garbage collection failure; see Chapter 5).

To find these problems, teams run an **endurance test** (also called a **soak test**, which means running a test for a very long time). These tests run at realistic, stable levels of resource use. During the test, engineers watch resources to see if they slowly run out (exhaustion) or fail.

- **Low-Latency Systems**: Soak tests are very important in low-latency environments. These environments cannot tolerate the long pauses of a full **stop-the-world (STW)** garbage collection cycle.
- **Challenges**: Teams often ignore (neglect) endurance tests because they are slow and expensive to run. Simulating realistic user behavior over several days is also difficult. Because of this, some teams rely on "testing in the live environment" (testing in production).
- **System Design Limitations**: This style of testing is harder to use with modern microservices or fast-changing system designs (agile architectures) where code changes are run in production multiple times a day.

### Capacity Planning Test

While similar to stress tests, **capacity planning tests** have a different focus:
- **Stress Test**: Finds what the *current* system setup can handle.
- **Capacity Planning Test**: A plan for the future (forward-looking exercise) that finds what workload an *upgraded system* (a system with more resources) can support.

Teams usually run these tests as part of a regular plan for infrastructure, rather than in response to an immediate performance emergency (crisis).

### Degradation Test

In the past, strict failover testing was done only in strictly controlled industries (highly regulated industries) like banking. Today, because applications run in groups of servers in the cloud (such as `Kubernetes`), developers must understand how these groups fail.

In this section, we focus on the **degradation test** (also called a **partial failure test**, which tests what happens when part of the system fails):
- **The Approach**: The test looks at how a system behaves when a part or subsystem suddenly loses its capacity while running under normal production load. Examples include dropping a server node from a group of servers (cluster) or experiencing a sudden loss of network speed.
- **Key Metrics**: Latency distribution (how response times are spread out) and throughput are the main things we watch during a degradation test.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//94cfe331-6ca6-4d2f-8507-f2fac3fb0d26/markdown_4/imgs/img_in_image_box_176_330_252_430.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A29Z%2F-1%2F%2F85574e3cb09decf93fb7ab9a7176a06bfd9014458acda5a68637023e3d3a521d" alt="Image" width="7%" /></div>

A full discussion of all aspects of strength and recovery (resilience and failover) testing is outside the scope of this book. In Chapter 14, we will talk about some of the simpler effects that you can see in cloud systems when a cluster partially fails or needs to recover.

#### Chaos Monkey and Resilience

A famous type of partial failure testing is Netflix's **Chaos Monkey**:
- **The Philosophy**: In a strong system that can recover (resilient system), the failure of a single part should not cause a chain reaction of failures (cascading failure) or make the user experience worse.
- **The Method**: Chaos Monkey tests this strength by randomly stopping live production processes.
- **Requirements**: Using this level of testing requires excellent system cleanliness (hygiene), strong service design, and excellent operations.

#### Cloud vs. Static Infrastructure

- **Designed for Failure**: Large cloud systems work on the idea that some part is always broken. A perfectly working system only exists in small setups.
- **Separating Software from Hardware**: Cloud-native software is written with very few assumptions about the physical hardware underneath. It is designed to run across multiple platforms for backups (redundancy). In contrast, traditional static infrastructure is designed to fail as little as possible. This shift completely changes how we write code for the cloud.

---

## Best Practices Primer

When deciding where to focus your optimization efforts, follow these **three golden rules**:

1. **Identify and Measure**: Pinpoint the metrics that impact the business or users, and establish how to measure them accurately.
2. **Optimize What Matters**: Focus on critical bottlenecks (slow points) rather than what is easiest to fix.
3. **Focus on the Largest Contributors**: Target the areas (the largest contributors) that add the most to latency or resource use.

> [!IMPORTANT]
> **Pitfall: The Streetlight Effect (Measuring Only What is Easy)**
> Avoid the trap of focusing on a measurement (metric) simply because it is easy to measure. It is easy to report on simple measurements (metrics) rather than the ones that truly impact the business. Similarly, do not waste time optimizing minor code paths just for the sake of optimizing.

### Top-Down Performance

Many engineers do not realize that benchmarking an entire Java application is much easier than obtaining accurate performance numbers for isolated, small sections of code.

Because microbenchmarking is so widely misunderstood and misapplied, we do not cover it in the main text. Instead, it is located in Appendix A, reflecting its limited use (niche utility).

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//10f66167-7fdd-4a16-aae5-9412423b84ab/markdown_0/imgs/img_in_image_box_176_999_252_1099.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A14Z%2F-1%2F%2F02feaeaf4c300897374be13033f8b6006b482176df0ebb1f609fcbd59ca5568b" alt="Image" width="7%" /></div>

Starting with the performance of the entire system is known as **top-down performance (starting from the whole system)**. To succeed with this approach, a team requires:
- A production-like **test environment**.
- A clear understanding of the specific metrics they need to measure.
- A plan for how performance testing integrates into the overall software development lifecycle (`SDLC`).

### Creating a Test Environment

A primary task for a performance team is establishing a test environment. Ideally, this environment should be an **exact duplicate of the production environment** in all aspects.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//10f66167-7fdd-4a16-aae5-9412423b84ab/markdown_1/imgs/img_in_image_box_176_328_252_430.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A18Z%2F-1%2F%2F811c6e6e5401b4ac9d0bfcf6e8c4145b920e022e3f8ce4982219d6acb33541da" alt="Image" width="7%" /></div>

Some teams may be in a position where they are forced to skip (forgo) testing environments and simply measure in production using modern deployment and observability techniques. This is the subject of Chapter 10, but it is not recommended as an approach unless it is necessary.

#### What Must Be Replicated

- **Application Servers**: Replicate hardware (CPUs, memory), operating system versions, and `JVM` runtimes.
- **Infrastructure Components**: Duplicate web servers, databases, and message queues.
- **External Integrations**: Create fake (mock) versions of third-party network services that cannot be replicated or cannot handle production-level load.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//10f66167-7fdd-4a16-aae5-9412423b84ab/markdown_1/imgs/img_in_image_box_176_655_252_755.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A19Z%2F-1%2F%2F672d3164addbd4d6febe5741294058742d7b3429dbb5f771c4a7fddb70ae47a8" alt="Image" width="7%" /></div>

> [!WARNING]
> **Pitfall: Non-Representative QA Environments**
> Performance testing environments that differ significantly from production are ineffective. They fail to produce results with any ability to predict performance (predictive power) or usefulness for the live system.

#### The Economics of Test Environments

- **Traditional Environments**: Replicating a traditional static environment is simple but expensive, requiring the purchase of identical hardware. Management often resists this cost, which is a **false savings (false economy, where trying to save money costs more in the long run)** that fails to account for the massive financial risk of production outages.
- **Cloud Environments**: The cloud enables dynamic infrastructure management, such as automatic scaling (autoscaling) and unchanging systems (immutable infrastructure). This treats servers as "livestock (easily replaced), not pets (uniquely cared for)." This allows teams to spin up a production-like environment for a test run and tear it down afterward, resulting in significant cost savings.

#### Cloud Test Environment Subtleties

When managing cloud-based test environments, watch out for these challenges:
- Establish a clear process to deploy changes to the test environment before migrating them to production.
- Ensure the test environment has no hidden dependencies written directly in the code (hardcoded dependencies) on production services.
- Use realistic authentication and authorization systems rather than simplified dummy components.

### Identifying Performance Requirements

System performance is not determined by application code alone. The container, operating system, and physical hardware all play critical roles.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//10f66167-7fdd-4a16-aae5-9412423b84ab/markdown_2/imgs/img_in_image_box_176_636_252_736.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A23Z%2F-1%2F%2F65c5ce5139e8ac265b246d01f318867fc7020ef32bd454caa13d9e150937f3d5" alt="Image" width="7%" /></div>

In “A Simple System Model” on page 184, we will meet a simple system model that describes in more detail how the interaction between OS, hardware, JVM, and code impacts performance.

Therefore, the metrics that we will use to evaluate performance should not be thought about solely in terms of the code. Instead, we must consider systems as a whole and the observable values that are important to customers and management. These are usually referred to as performance **non-functional requirements (NFRs)** and are the key indicators that we want to optimize.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//10f66167-7fdd-4a16-aae5-9412423b84ab/markdown_2/imgs/img_in_image_box_177_923_253_1024.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A24Z%2F-1%2F%2Fa567ed5373db8e37dadb075c995a2e91b9ec4c5dd7351c0ccde07c137f5f14bb" alt="Image" width="7%" /></div>

One useful approach is that of service level objectives (SLOs), which we will discuss in Chapter 10.

#### Common Performance Goals (NFRs)

*Obvious Goals:*
- Reduce the **95th percentile** transaction latency by 100 ms.
- Increase throughput by 5x on existing hardware.
- Improve average response times by 30%.

*Business-Centric Goals:*
- Reduce the infrastructure cost to serve the average customer by 50%.
- Maintain response times within 25% of targets even when the application cluster is 50% degraded.
- Reduce customer drop-off rates by 25% by shaving off 10 ms of latency.

An open discussion with stakeholders to align on these goals is essential and should occur during the project kickoff (start of the project).

### Performance Testing as Part of the SDLC

While some teams treat performance testing as a rare, one-off event, mature teams integrate ongoing **performance regression testing** (testing if code changes made the system slower) directly into their **software development lifecycle (SDLC)**.

This requires:
- Close collaboration between developers and infrastructure teams to manage code versions in the test environment.
- A dedicated, production-like testing environment.

### Java-Specific Issues

> **Insight: Dynamic JVM Self-Management**
> While general performance science applies universally, the `JVM` introduces unique behaviors due to its dynamic self-management capabilities, including dynamic memory tuning and **Just-in-Time (JIT) compilation (where the JVM compiles bytecode to native machine code at runtime)**.

For example, modern `JVM`s monitor method execution to select methods to compile to native machine code. If a method is not being JIT-compiled, it is because:
- It does not run frequently enough to justify the extra work of compiling (compilation overhead).
- The method is too large or complex for the compiler to analyze (which is much rarer).

We cover `JIT` mechanics and optimization techniques in Chapter 6. Having discussed some of the most common best practices for performance, let's now turn our attention to the pitfalls and antipatterns that teams can fall prey to.

---

## Causes of Performance Antipatterns

An **antipattern** is a recurring, counterproductive behavior (a bad practice that happens often) observed across many software projects and teams. [^1]

- Some antipatterns seem logical at first, with their negative consequences hidden (e.g., *Distracted by Shiny*).
- Others accumulate over time due to poor operational habits (e.g., *Tuning by Folklore*).

A partial catalog of antipatterns can be found in Appendix B. By categorizing these behaviors, we create a shared vocabulary to identify and eliminate them from our projects.

### Human Factors over Technical Factors

Performance tuning must be an objective process with clear, early goals. Under pressure, however, this discipline often falls apart. When an unexpected outage occurs during a launch, teams scramble to resolve bottlenecks. This panic is usually the result of neglecting performance testing or relying on a single "ninja" (expert) developer who made unverified assumptions and has since departed.

Ultimately, human elements—such as poor communication and pressure—are far more likely to cause performance crises than pure technical failures.

### Why Developers Make Poor Technology Choices

Writer Carey Flichel identifies five core human drivers behind bad technical decisions:

1. **Boredom**: Developers seeking a new challenge may write unnecessarily complex custom code (like writing a custom sorting algorithm instead of using `Collections.sort()`) or introduce ill-fitting technologies just to play with them.
2. **Résumé Padding**: Developers may introduce complex technologies into a project solely to add them to their resumes, increasing their marketability for their next job (adding skills to a resume). This leaves the team with long-term maintenance overhead.
3. **Social Pressure**: Technical decisions suffer when team members stay silent. Junior developers may fear making mistakes or appearing uninformed in front of senior peers. Toxic competitive pressure can also lead teams to rush critical architectural decisions.
4. **Lack of Understanding**: Developers often adopt new tools because they do not understand the full capabilities of their existing stack. For example, a team might use `Hibernate` to simplify database operations without understanding its complexities, leading to overcomplicated code and outages, when simple `JDBC` calls would have sufficed.
5. **Misunderstood or Nonexistent Problems**: Developers sometimes implement a technology to solve a problem that was never properly measured or investigated. Without baseline metrics, it is impossible to know if a solution succeeded.

To avoid antipatterns, it is important to ensure that communication about technical issues is open to all participants in the team and actively encouraged. Where things are unclear, gathering factual evidence and working on simple test versions (prototypes) can help to steer team decisions. A technology may look attractive; however, if the prototype does not measure up, then the team can make a more informed decision.

To see how these underlying causes can lead to a variety of performance antipatterns, interested readers should consult Appendix B.

---

## Statistics for JVM Performance

If performance analysis is truly an experimental science, then we will inevitably find ourselves dealing with spreads of results data (distributions). Statisticians and scientists know that results that stem from the real world are virtually never represented by clean, stand-out signals (clear patterns). We must deal with the world as we find it, rather than the overdetailed state in which we would like to find it.

> "In God we trust; all others must use data." [^2]
> — W. Edwards Deming (attr)

All measurements contain some amount of error. So, repeated runs must be used to try to minimize the effect of errors in any individual run. The gold standard for Java performance was established in 2007 in the paper “Statistically Rigorous Java Performance Evaluation”.[^3] This contains the frequently repeated rule that 30 runs are necessary for reasonable statistical behavior in a highly dynamic software system, such as the JVM.

In the next section, we'll describe the two main types of error that a Java developer can expect to encounter when doing performance analysis.

### Types of Error

Engineers encounter two primary types of measurement error:
- **Random error**: A measurement error or an unconnected factor affects results in an uncorrelated way.
- **Systematic error**: An unaccounted factor affects measurement of the observable in a correlated way.

Specific words are associated with each type of error. For example, **accuracy** is used to describe the level of systematic error in a measurement; high accuracy (how close a measurement is to the true value) corresponds to low systematic error. Similarly, **precision** is the term corresponding to random error; high precision (how close measurements are to each other) is low random error.

The graphics in Figure 2-1 show the effect of these two types of error on a measurement. The extreme left image shows a clustering of shots (which represent our measurements) around the true result (the center of the target). These measurements have both high precision and high accuracy.

The second image has a systematic effect (sights that are set incorrectly, miscalibrated sights, perhaps?) that is causing all the shots to be off-target, so these measurements have high precision but low accuracy. The third image shows shots basically on target but loosely clustered around the center, so low precision but high accuracy. The final image shows no clear pattern, a result of having both low precision and low accuracy.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//37cedb8c-b940-4b76-a504-35e997a34f86/markdown_3/imgs/img_in_image_box_155_250_865_399.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A10%3A57Z%2F-1%2F%2F049018a7094fec9590f3cd9b65614ae17c8e2c006099c54f07fa612c5e7fb2ec" alt="Image" width="70%" /></div>

<div style="text-align: center;">Figure 2-1. Different types of error</div>

Let's move on to explore these types of error in more detail, starting with random error.

#### Random Error

Random errors are hopefully familiar to most people—they are a very well-trodden path. However, they still deserve a mention here, as any handling of observed or experimental data needs to contend with them to some degree.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//37cedb8c-b940-4b76-a504-35e997a34f86/markdown_3/imgs/img_in_image_box_176_676_253_776.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A10%3A57Z%2F-1%2F%2F8e44b393b10641be1ade8a62dc33f5699342a04a9ab11557b247ec91ef4e9c46" alt="Image" width="7%" /></div>

The discussion assumes readers are familiar with basic statistical handling of normally distributed measurements (mean, mode, standard deviation, etc.); readers who aren't should consult a basic textbook, such as the Handbook of Biological Statistics.[^4]

Random errors are caused by unknown or unpredictable changes in the environment. In general scientific usage, these changes can occur in either the measuring instrument or the environment, but for software, we assume that our measuring harness is reliable, so the source of random error can only be the operating environment.

Random error is usually considered to obey a Gaussian (also called normal) distribution or bell curve. A couple of typical examples of Gaussian distributions are shown in Figure 2-2.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//37cedb8c-b940-4b76-a504-35e997a34f86/markdown_4/imgs/img_in_chart_box_146_169_863_447.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A10%3A57Z%2F-1%2F%2F64d398fc7039a047c7b598196dac7cadee488711ff3d799bf3e623eaf939a90f" alt="Image" width="71%" /></div>

<div style="text-align: center;">Figure 2-2. A Gaussian distribution (also called normal distribution or bell curve)</div>

The distribution is a good model for the case where an error is equally likely to make a positive or negative contribution to an observable. However, as we will see in the section on non-normal statistics, the situation for JVM measurements is a little more complicated.

#### Systematic Error

As an example of systematic error, consider a performance test running against a group of backend Java web services that send and receive JSON. This type of test is very common when it is problematic to directly use the application frontend for load testing.

Figure 2-3 was generated from the Apache JMeter load-generation tool. In it, there are actually two systematic effects at work. The first is the linear pattern observed in the topmost line (the outlier service), which represents slow exhaustion of some limited server resource.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//fa9cbda0-711a-47d2-92bc-d6168aa921af/markdown_0/imgs/img_in_chart_box_154_110_862_637.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A20Z%2F-1%2F%2Fd5a8cbdf6db69e42f7d82d509ea53ad93ed006228515819fddfd8a16e0be9d21" alt="Image" width="70%" /></div>

<div style="text-align: center;">Figure 2-3. Systematic error</div>

This type of pattern is often associated with a memory leak or some other resource being used and not released by a thread during request handling, and it represents a candidate for investigation—this looks like it could be a genuine problem.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//fa9cbda0-711a-47d2-92bc-d6168aa921af/markdown_0/imgs/img_in_image_box_176_810_252_909.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A20Z%2F-1%2F%2F81ebdcfa3ac206be8898bbc6de498ed38e1f26577ef9e869fb86192e36304c6d" alt="Image" width="7%" /></div>

Further analysis would be needed to confirm the type of resource that was being affected; we cannot just conclude that it is a memory leak.

The second effect that should be noticed is the consistency of the majority of the other services at around the 180 ms level. This is suspicious, as the services are doing very different amounts of work in response to a request. So why are the results so consistent?

The answer is that while the services under test are located in London, this load test was conducted from Mumbai, India. The observed response time includes the irreducible round-trip network latency from Mumbai to London. This is in the range of 120–150 ms, so it accounts for the vast majority of the observed time for the services other than the outlier.

This large, systematic effect is drowning out the differences in the actual response time (as the services are actually responding in much less than 120 ms). This is an example of a systematic error that does not represent a problem with our application.

Instead, this error stems from a problem in our test setup not duplicating production, so the good news is that this artifact completely disappeared (as expected) when the test was rerun from London.

We have met some examples of sources of error and mentioned some notorious pitfalls, so let's move on to discuss an aspect of JVM performance measurement that requires some special care and attention to detail.

---

### Non-Normal Statistics

Statistics based on the normal distribution do not require much mathematical sophistication (advanced math skills). For this reason, the standard approach to statistics that is typically taught at precollege or undergraduate level focuses heavily on the analysis of normally distributed data.

Students are taught to calculate the mean and the standard deviation (or variance), and sometimes higher moments, such as skew (symmetry of the curve) and kurtosis (thickness of the curve tails). However, these techniques have a serious drawback, in that the results can easily become distorted if the distribution has even relatively few far-flung outlying points.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//fa9cbda0-711a-47d2-92bc-d6168aa921af/markdown_1/imgs/img_in_image_box_176_804_252_905.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A22Z%2F-1%2F%2Fb065dfe1f6a07c750ce03b1199e749269b833a91e897388d528bdb9750831d47" alt="Image" width="7%" /></div>

In Java performance, the outliers represent slow transactions and unhappy customers. We need to pay special attention to these points and avoid techniques that weaken the importance (dilute) of outliers.

In Figure 2-4 we can see a more realistic curve for the likely distribution of method (or transaction) times. It is clearly not a normal distribution.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//fa9cbda0-711a-47d2-92bc-d6168aa921af/markdown_2/imgs/img_in_chart_box_143_107_865_462.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A24Z%2F-1%2F%2F5e9a42974717a611ea72ad656b7056d2b9de3a132784ee5205300be76f7464c6" alt="Image" width="71%" /></div>

<div style="text-align: center;">Figure 2-4. A more realistic view of the distribution of transaction times</div>

The shape of the distribution in Figure 2-4 shows something that we know intuitively about the JVM: it has “hot paths” (frequently run pieces of code) where all the relevant code is already JIT-compiled, there are no GC cycles, and so on. These represent a best-case scenario (albeit a common one); there simply are no calls that are “a bit faster” due to random effects.

This violates a fundamental assumption of Gaussian statistics and forces us to consider distributions that are **non-normal**.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//fa9cbda0-711a-47d2-92bc-d6168aa921af/markdown_2/imgs/img_in_image_box_176_713_252_813.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A24Z%2F-1%2F%2Fc3b0dff5331523964da40927d1624a217a7586a6123de97bf1ab94eb7fd9ac50" alt="Image" width="7%" /></div>

For distributions that are non-normal, many “basic rules” of normally distributed statistics are violated. In particular, standard deviation/variance and other higher moments are basically useless.

To consider it from another viewpoint: unless a large number of customers are already complaining, it is unlikely that improving the average response time is a useful performance goal. For sure, doing so will improve the experience for everyone, but it is far more usual for a few disgruntled customers to be the cause of a latency tuning exercise. This implies that the outlier events are likely to be of more interest than the experience of the majority who are receiving satisfactory service.

One technique that is very useful for handling the non-normal, “long-tail” (distributions with a long line of extreme values) distributions the JVM produces is to use a modified scheme of percentiles (values that show what percentage of data falls below them). Remember that a distribution is a whole collection of points—a shape of data, and is not well-represented by a single number.

Instead of computing just the mean, which tries to express the whole distribution in a single result, we can use a sampling of the distribution at intervals. When used for normally distributed data, the samples are usually taken at regular intervals. However, a small adaptation allows the technique to be used more effectively for JVM statistics.

The modification is to use a sampling that takes into account the long-tail distribution by starting from the mean, then the 90th percentile, and then moving out logarithmically (using steps that multiply rather than add), as shown in the following method timing results. This means that we are sampling according to a pattern that better corresponds to the shape of the data:

```text
50.0% level was 23 ns
90.0% level was 30 ns
99.0% level was 43 ns
99.9% level was 164 ns
99.99% level was 248 ns
99.999% level was 3,458 ns
99.9999% level was 17,463 ns
```

The samples show us that while the average time was 23 ns to execute a getter method (a method that reads a variable), for 1 request in 1,000, the time was 10 times (an order of magnitude) worse, and for 1 request in 100,000, it was 100 times (two orders of magnitude) worse than average.

Long-tail distributions can also be referred to as high dynamic range (HDR) distributions. The dynamic range of an observable is usually defined as the maximum recorded value divided by the minimum (assuming the latter is nonzero).

Logarithmic percentiles are a useful simple tool for understanding the long tail. However, for more sophisticated analysis, we can use a public domain library for handling datasets with high dynamic range. The library, called **HdrHistogram**, is available from GitHub. It was originally created by Gil Tene (Azul Systems), with additional work by Mike Barker and other contributors.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//fa9cbda0-711a-47d2-92bc-d6168aa921af/markdown_3/imgs/img_in_image_box_176_768_253_868.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A26Z%2F-1%2F%2Fec8778225aa76b64d844857bac01907cca867ce4bf1fed6024ef2b3f1bc1c160" alt="Image" width="7%" /></div>

A histogram is a way of summarizing data by using a finite set of ranges (called buckets) and displaying how often data falls into each bucket.

HdrHistogram is also available on Maven Central. At the time of writing, the current version is 2.1.12, and you can add it to your projects by adding this dependency block (stanza) to `pom.xml`:

```xml
<dependency>
    <groupId>org.hdrhistogram</groupId>
    <artifactId>HdrHistogram</artifactId>
    <version>2.1.12</version>
</dependency>
```

Let's look at a simple example using HdrHistogram. This example takes in a file of numbers and computes the HdrHistogram for the difference between successive results:

```java
public class BenchmarkWithHdrHistogram {
    private static final long NORMALIZER = 1_000_000;
    private static final Histogram HISTOGRAM = new Histogram(TimeUnit.MINUTES.toMicros(1, 2));

    public static void main(String[] args) throws Exception {
        final List<String> values = Files.readAllLines(Paths.get(args[0]));
        double last = 0;
        for (final String tVal : values) {
            double parsed = Double.parseDouble(tVal);
            double gcInterval = parsed - last;
            last = parsed;
            HISTOGRAM.recordValue((long)(gcInterval * NORMALIZER));
        }
        HISTOGRAM.outputPercentileDistribution(System.out, 1000.0);
    }
}
```

The output shows the times between successive garbage collections. As we'll see in Chapters 4 and 5, GC does not occur at regular intervals, and understanding the distribution of how frequently it occurs could be useful. Here's what the histogram plotter produces for a sample GC log:

```text
Value Percentile TotalCount 1/(1-Percentile)
14.02 0.00000000000001 1.00
1245.18 0.100000000000037 1.11
1949.70 0.200000000000082 1.25
1966.08 0.3000000000000126 1.43
1982.46 0.4000000000000157 1.67
28180.48 0.996484375000368 284.44
28180.48 0.996875000000368 320.00
28180.48 0.997265625000368 365.71
36438.02 0.997656250000369 426.67
36438.02 1.0000000000000369 428.67
#[Mean = 2715.12, StdDeviation = 2875.87]
#[Max = 36438.02, Total count = 369]
#[Buckets = 19, SubBuckets = 256]
```

The raw output of the formatter is rather hard to analyze, but fortunately, the HdrHistogram project includes an online formatter that can be used to generate visual histograms from the raw output.

For this example, it produces output like that shown in Figure 2-5.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//c447a516-2a0c-42f9-a55a-fe1ad89723d6/markdown_0/imgs/img_in_chart_box_143_107_863_447.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A14Z%2F-1%2F%2F9b69fc553ab8964a0aa8c014ac5ebe6e92d6837122b4d4c8c77dfd10e1fc49e8" alt="Image" width="71%" /></div>

<div style="text-align: center;">Figure 2-5. Example HdrHistogram visualization</div>

For many observables that we wish to measure in Java performance tuning, the statistics are often highly non-normal, and HdrHistogram can be a very useful tool in helping to understand and visualize the shape of the data.

The tool can also help with detecting and understanding **coordinated omission**. This is a term that describes the phenomenon in which the measuring system inadvertently coordinates with the system being measured in a way that either incorrectly measures outliers or causes some requests to be skipped and not sent (coordinated omission). [^5]

---

## Interpretation of Statistics

Empirical data and observed results do not exist in a vacuum, and it is quite common that one of the hardest jobs lies in interpreting the results we obtain from measuring our applications.

> "No matter what the problem is, it's always a people problem."
> — Gerald Weinberg (attr)

Quite a few different problems are associated with interpretation. Let's start by taking a quick look at one notorious issue that frequently accompanies systematic error—**spurious correlation**.

### Spurious Correlation

One of the most famous aphorisms about statistics is “correlation does not imply causation”—that is, just because two variables appear to behave similarly does not imply that there is an underlying connection (causation) between them.

This is a very important concept for a performance engineer to grasp and warrants a bit of unpacking. Wikipedia enumerates four different options. For any two correlated events, A and B, there are these possible relationships:
1. A causes B (direct causation).
2. B causes A (reverse causation).
3. A and B are both caused by C (common causation).
4. There is no connection between A and B; the correlation is a coincidence.

The first two cases are relatively straightforward. The third case, common causation, is the situation when two variables are linked, but we draw an incorrect causal link. That is, it's a true correlation, not a spurious one, but that doesn't mean we can infer a causal relationship.

For example, in healthcare, breastfeeding babies in infancy correlates with higher IQ scores later in childhood. This is well-evidenced, but in this case, there's a third factor that is causal and drives the correlation—essentially, that higher rates of breastfeeding tend to occur with higher social class, which in turn leads to more time spent on encouraging a child's mental development.

In the most extreme examples of the fourth case, if a practitioner looks hard enough, then a correlation can be found between entirely unrelated measurements. For example, in Figure 2-6 we can see that chicken eating in the US is very similar to the amount of crude oil imported. [^6]

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//c447a516-2a0c-42f9-a55a-fe1ad89723d6/markdown_2/imgs/img_in_chart_box_143_108_862_397.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A21Z%2F-1%2F%2Fd5ae7e1d4e4337adb46052601e7e22f31b3eae1f2b8cf28909f613ecd1e147fb" alt="Image" width="71%" /></div>

<div style="text-align: center;">Figure 2-6. A completely spurious correlation (Vigen)</div>

These numbers are clearly not causally related; there is no factor that drives both the import of crude oil and the eating of chicken. However, it isn't the absurd and ridiculous correlations that the practitioner needs to be wary of.

In Figure 2-7, we see the revenue generated by video arcades correlated to the number of computer science PhDs awarded. It isn't too much of a stretch to imagine a sociological study that claimed a link between these observables, perhaps arguing that “stressed doctoral students were finding relaxation with a few hours of video games.” These types of claim are depressingly common, despite no such common factor actually existing.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//c447a516-2a0c-42f9-a55a-fe1ad89723d6/markdown_2/imgs/img_in_chart_box_142_713_862_1004.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A22Z%2F-1%2F%2Fe3b63f6cc47799361f795df5e1dc6734044430d1463c8a0b821deaeb81e9ad10" alt="Image" width="71%" /></div>

<div style="text-align: center;">Figure 2-7. A less spurious correlation? (Vigen)</div>

In the realm of the JVM and performance analysis, we need to be especially careful not to attribute a causal relationship between measurements based solely on correlation and that the connection “seems plausible.”

> "The first principle is that you must not fool yourself—and you are the easiest person to fool." [^7]
> — Richard Feynman

In Figure 2-8, we show an example memory allocation rate for a real Java application. This example is for a reasonably well-performing application.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//c447a516-2a0c-42f9-a55a-fe1ad89723d6/markdown_3/imgs/img_in_chart_box_145_259_865_740.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A26Z%2F-1%2F%2F7ba577da88691ca9edd5c80c63f6f51a9f0d5c2eb1d0e9ec2f115ba884f1ac8b" alt="Image" width="71%" /></div>

<div style="text-align: center;">Figure 2-8. Example allocation rate</div>

The interpretation of the allocation data is relatively straightforward, as there is a clear signal present. Over the time period covered (almost a day), allocation rates were basically stable between 350 and 700 MB per second. There is a downward trend starting approximately 5 hours after the JVM started up, and a clear minimum between 9 and 10 hours, after which the allocation rate starts to rise again.

These types of trends in observables are very common, as the allocation rate will usually reflect the amount of work an application is actually doing, and this will vary widely depending on the time of day. However, when we are interpreting real observables, the picture can rapidly become more complicated.

### The Hat/Elephant Problem

This can lead to what is sometimes called the “hat/elephant” problem, after a passage in *The Little Prince* by Antoine de Saint-Exupéry. In the book, the narrator describes drawing, at age six, a picture of a boa constrictor (a large snake that squeezes its prey) that has eaten an elephant. However, as the view is external, the picture just resembles (at least to the uninformed eyes of the adults in the story) a slightly shapeless hat.

The metaphor stands as an admonition (warning) to the reader to have some imagination and to think more deeply about what you are really seeing, rather than just accepting a simple, surface-level explanation at face value (exactly what it looks like).

The problem, as applied to software, is illustrated by Figure 2-9. All we can initially see is a complex histogram of HTTP request-response times. However, just like the narrator of the book, if we can imagine or analyze a bit more, we can see that the complex picture is actually made up of several fairly simple pieces.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//c447a516-2a0c-42f9-a55a-fe1ad89723d6/markdown_4/imgs/img_in_chart_box_144_487_864_841.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A30Z%2F-1%2F%2Fb2b3686b8dd8f53243af4a110b6ba307f63f60c6557da3a70c0be7b9cfeef3f2" alt="Image" width="71%" /></div>

<div style="text-align: center;">Figure 2-9. Hat or elephant eaten by a boa?</div>

The key to decoding the response histogram is to realize that “web application responses” is a very general category, including successful requests (so-called 2xx responses), client errors (4xx, including the infamous 404 error), and server errors (5xx, especially 500 Internal Server Error).

Each type of response has a different characteristic distribution for response times. If a client makes a request for a URL that has no mapping (a 404), then the web server can immediately reply with a response. This means that the histogram for only client error responses looks more like Figure 2-10.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//e44b8fd6-b617-4461-bfe3-847cc879d8c6/markdown_0/imgs/img_in_chart_box_142_104_865_462.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A14Z%2F-1%2F%2Fcd8e07c71416d39aa4a4e781eac923c051067667bae18563e4486333aa6fab76" alt="Image" width="71%" /></div>

<div style="text-align: center;">Figure 2-10. Client errors</div>

By contrast, server errors often occur after a large amount of processing time has been expended (for example, due to backend resources being under stress or timing out). So, the histogram for server error responses might look like Figure 2-11.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//e44b8fd6-b617-4461-bfe3-847cc879d8c6/markdown_0/imgs/img_in_image_box_142_606_865_962.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A15Z%2F-1%2F%2F45fafa9d2c0c6422d8a70a9dfc76a2b20ac0116cedaea82a94dea203791eb031" alt="Image" width="71%" /></div>

<div style="text-align: center;">Figure 2-11. Server errors</div>

The successful requests will have a long-tail distribution, but in reality, we can expect the response distribution to be “multimodal” (having more than one peak value) and have several local peaks (local maxima). An example is shown in Figure 2-12 and represents the possibility that there could be two common execution paths through the application with quite different response times.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//e44b8fd6-b617-4461-bfe3-847cc879d8c6/markdown_1/imgs/img_in_chart_box_143_105_865_461.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A19Z%2F-1%2F%2F9286d9de9dc0565e88b83f6e9150f8634d98e53568afddfaddeaeb484556b835" alt="Image" width="71%" /></div>

<div style="text-align: center;">Figure 2-12. Successful requests</div>

Combining these different types of responses into a single graph results in the structure shown in Figure 2-13. We have recreated (rederived) our original “hat” shape from the separate histograms.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//e44b8fd6-b617-4461-bfe3-847cc879d8c6/markdown_1/imgs/img_in_chart_box_145_606_863_961.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A20Z%2F-1%2F%2Fd68bb8ef1bf6fb3ad6939d90ba7bded647b35e9f46763016b399bb44355b4f80" alt="Image" width="71%" /></div>

<div style="text-align: center;">Figure 2-13. Hat or elephant revisited</div>

The concept of breaking down a general observable into more meaningful subpopulations is a very useful one. It shows that we need to make sure that we understand our data and domain well enough before trying to infer conclusions from our results. We may well want to further break down our data into smaller sets; for example, the successful requests may have very different distributions for requests that are predominantly read, as opposed to requests that are updates or uploads.

The engineering team at PayPal has written extensively about its use of statistics and analysis; they have a blog that contains excellent resources. In particular, the piece “Statistics for Software” by Mahmoud Hashemi is a great introduction to their methodologies and includes a version of the hat/elephant problem discussed earlier. [^8]

Also worth mentioning is the “Datasaurus Dozen”—a collection of 13 datasets that have the same basic statistics but wildly different appearances. [^9]

---

## Cognitive Biases and Performance Testing

Humans can be bad at forming accurate opinions quickly—even when faced with a problem where they can draw upon past experiences and similar situations.

A **cognitive bias** is a trick of the mind that makes you think in a wrong way (a cognitive bias). It is especially problematic because the person having this bias is usually unaware of it and may believe they are being rational.

Many of the antipatterns we observe in performance analysis (such as those in Appendix B, which you might want to read in conjunction with this section) are caused, in whole or in part, by one or more cognitive biases that are, in turn, based on unconscious assumptions.

For example, with the Blame Donkey antipattern, if a component has caused several recent outages, the team may be biased to expect that same component to be the cause of any new performance problem. Any data that is analyzed may be more likely to be considered credible if it confirms the idea that the Blame Donkey component is responsible.

The antipattern combines aspects of the biases known as **confirmation bias** and **recency bias** (a tendency to assume that whatever has been happening recently will keep happening).

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//e44b8fd6-b617-4461-bfe3-847cc879d8c6/markdown_2/imgs/img_in_image_box_176_851_253_952.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A24Z%2F-1%2F%2F29064b7eb0087c8d5633daa15e899128f3286b5c6cc51e2c1a1aaf17e94cede3" alt="Image" width="7%" /></div>

A single component in Java can behave differently from application to application depending on how it is optimized at runtime. To remove any pre-existing bias, it is important to look at the application as a whole.

Biases can be complementary or dual to each other. For example, some developers may be biased to assume that the problem is not software-related at all, and the cause must be the infrastructure the software is running on; this is common in the Works for Me antipattern, characterized by statements like: "This worked fine in UAT, so there must be a problem with the production kit." The converse is to assume that every problem must be caused by software, because that's the part of the system the developer knows about and can directly affect.

Let's meet some of the most common biases that every performance engineer should look out for.

> "Knowing where the trap is—that’s the first step in evading it." [^10]
> — Duke Leto Atreides I

By recognizing these biases in ourselves, and others, we increase the chance of being able to do sound performance analysis and solve the problems in our systems.

### Reductionist Thinking

The **reductionist thinking** cognitive bias is based on an analytical approach that presupposes that if you break a system into small enough pieces, you can understand it by understanding its constituent parts. Understanding each part means reducing the chance of incorrect assumptions being made (reductionist thinking, the belief that you can understand a complex system by only looking at its individual parts).

The major problem with this view is simple to explain—in complex systems, it just isn't true. Nontrivial software (or physical) systems almost always display emergent behavior, where the whole is greater than a simple summation of its parts would indicate (emergent behavior, where a system displays behaviors that its individual parts do not have).

### Confirmation Bias

Confirmation bias can lead to significant problems when it comes to performance testing or attempting to look at an application subjectively. A confirmation bias is introduced, usually not intentionally, when a poor test set is selected or results from the test are not analyzed in a statistically sound way. Confirmation bias is quite hard to counter, because there are often strong motivational or emotional factors at play (such as someone in the team trying to prove a point).

Consider an antipattern such as Distracted by Shiny, where a team member is looking to bring in the latest and greatest NoSQL database. They run some tests against data that isn't like production data, because representing the full schema is too complicated for evaluation purposes (testing purposes).

They quickly prove that on a test set the NoSQL database produces superior access times on their local machine. The developer has already told everyone this would be the case, and on seeing the results, they proceed with a full implementation. There are several antipatterns at work here, all leading to new, unproved assumptions in the new library stack.

### Fog of War (Action Bias)

The **fog of war** bias (confusion during a busy or stressful event) usually manifests itself during outages or situations where the system is not performing as expected and the team is under pressure. Some common causes include:
- Changes to infrastructure that the system runs on, perhaps without notification or realizing there would be an impact.
- Changes to libraries that the system is dependent on.
- A strange bug or race condition (a bug where two threads try to access the same resource at the same time, causing unexpected results) that manifests itself, but only on busy days.

In a well-maintained application with sufficient observability tooling (monitoring tools), these should generate clear signals that will lead the support team to the cause of the problem.

However, too many applications have not tested failure scenarios and lack appropriate tooling. Under these circumstances even experienced engineers can fall into the trap of needing to feel that they're doing something to resolve the outage and mistaking motion for velocity (unfocused activity for real progress)—the "fog of war" descends.

At this time, many of the human elements discussed in this chapter can come into play if participants are not systematic about their approach to the problem.

For example, an antipattern such as Blame Donkey can shortcut a full investigation and lead the production team down a particular path of investigation—often missing the bigger picture. Similarly, the team may be tempted to break the system down into its constituent parts and look through the code at a low level without first establishing in which subsystem the problem truly resides.

### Risk Bias

Humans are naturally risk averse and resistant to change. Mostly this is because people have seen examples of how change can cause things to go wrong—this leads them to attempt to avoid that risk. This can be incredibly frustrating when taking small, calculated risks could move the product forward. Much of this risk aversion arises from teams that are reluctant to make changes that might modify the performance profile of the application.

We can reduce this **risk bias** (fear of taking risks) significantly by having a robust set of unit tests and production regression tests. The performance regression tests are a great place to link in the system's non-functional requirements (NFRs) and ensure that the concerns the NFRs represent are reflected in the regression tests.

However, if either of these is not sufficiently trusted by the team, change becomes extremely difficult, and the risk factor is not controlled. This bias often manifests in a failure to learn from application problems (including service outages) and implement appropriate mitigation.

---

## Summary

When you are evaluating performance results, it is essential to handle the data appropriately and avoid falling into unscientific and subjective thinking. This includes avoiding the statistical pitfalls of relying upon Gaussian models when they are not appropriate.

In this chapter, we have met some different types of performance tests, testing best practices, and human problems that are native to performance analysis.

In the next chapter, we're going to move on to an overview of the JVM, introducing the basic subsystems, the lifecycle of a “classic” Java application, and a first look at monitoring and tooling.

---

[^1]: Martin Fowler has written widely about design smells and coding antipatterns.
[^2]: W. Edwards Deming was a pioneer of quality control and statistical methods.
[^3]: Georges, A. et al. (2007) “Statistically Rigorous Java Performance Evaluation”, OOPSLA.
[^4]: John H. McDonald (2014) *Handbook of Biological Statistics*, Sparky House Publishing.
[^5]: Coordinated omission is a common pitfall in load testing tools that distort latency graphs.
[^6]: Spurious correlations are common when analyzing large, unrelated datasets.
[^7]: Richard Feynman (1974) Cargo Cult Science, Caltech commencement address.
[^8]: Mahmoud Hashemi's article discusses how PayPal applies statistical modeling to real-world software metrics.
[^9]: The Datasaurus Dozen shows that visual analysis is critical alongside summary statistics.
[^10]: Frank Herbert (1965) *Dune*, Chilton Books.
