# Performance Antipatterns Catalog

In this appendix, we will present a short catalog of performance antipatterns. The list is by no means complete, and there are doubtless many more still to be discovered.

---

## Distracted by Shiny

The newest or coolest technology is often the first tuning target. This is because it can be more exciting to explore how newer technology works than to dig around in old code. It may also be that the code accompanying the newer technology is better-written code that is easier to maintain. Both of these facts push developers toward looking at the newer components of the application.

### Example Comments

* “It’s early trouble—we need to get to the bottom of it.”
* “It is likely component X that I introduced and have been reading more about.”

### Reality

* This is often just a guess in the dark rather than an effort at targeted tuning or measuring the application.
* The developer may not fully understand the new technology yet and will tinker around rather than examine the documentation. In reality, this often causes other problems.
* In the case of new technologies, examples online are often for small or sample datasets and do not discuss good practice about scaling to a large business size.

### Discussion

This antipattern is common in newly formed or less experienced teams. Eager to prove themselves, or to avoid becoming tied to what they see as old systems, they often support newer, “hotter” technologies. By chance, these may be exactly the sort of technologies that would give a salary increase in any new job.

Therefore, the logical subconscious conclusion is that any performance issue should be approached by first taking a look at the new technology. After all, it is not properly understood, so a fresh pair of eyes would be helpful, right?

### Resolutions

* **Measure** to determine the real location of the bottleneck.
* **Ensure adequate logging** around the new component.
* **Look at best practices** as well as simplified demos.
* **Ensure the team understands the new technology**, and establish a level of best practice across the team.

---

## Distracted by Simple

The team targets the simplest parts of the system first. This is chosen instead of profiling the application overall and objectively looking for pain points in it. There may be parts of the system considered “specialist” that only the original expert who wrote them can edit.

### Example Comments

* “Let's get into this by starting with the parts we understand.”
* “John wrote that part of the system, and he’s on holiday. Let’s wait until he’s back to look at the performance.”

### Reality

* The original developer understands how to tune only that part of the system.
* There has been no knowledge sharing or pair programming on the various system components, creating single experts.

### Discussion

The **Distracted by Simple** antipattern is often seen in a more established team. Such a team may be more used to a maintenance or keep-the-lights-on role. If the application has recently been merged or paired with newer technology, the team may feel intimidated or not want to work with the new systems.

Under these circumstances, developers may feel more comfortable profiling only those parts of the system that are familiar. They hope that they will be able to achieve the desired goals without going outside of their comfort zone.

Of particular note is that both of these first two antipatterns are driven by a reaction to the unknown. In **Distracted by Shiny**, this shows itself as a desire by the developer (or team) to learn more and gain advantage—essentially an offensive play. By contrast, **Distracted by Simple** is a defensive reaction, playing to the familiar rather than working with a potentially threatening new technology.

### Resolutions

* **Measure** to determine the real location of the bottleneck.
* **Ask for help** from domain experts if the problem is in an unfamiliar component.
* **Ensure that developers understand** all components of the system.

---

## Performance Tuning Wizard

Management has bought into the Hollywood image of a “lone genius” hacker and hired someone who fits the stereotype to move around the company and fix all performance issues, using their perceived superior performance tuning skills.

### Example Comment

* “I’m sure I know just where the problem is…”

### Reality

* Not many performance problems are exactly the same. A perceived wizard or superhero is unlikely to magically know how to address all issues at first glance.

### Discussion

This antipattern can alienate developers in the team who feel they are not good enough to address performance issues. It is a concern because, in many cases, a small amount of profiler-guided optimization can lead to good performance increases (see Chapter 12).

This is not to say there are not specialists who can help with specific technologies, but the thought that there is a lone genius who will understand all performance issues from the beginning is ridiculous. Many technologists that are performance experts are specialists at measuring and problem-solving based on those measurements.

Superhero types in teams can be very counterproductive if they are not willing to share knowledge or the approaches they took to resolving a particular issue.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//e6fea6ad-ffe0-4f9c-a3ef-612bebb52c1f/markdown_3/imgs/img_in_image_box_177_820_252_920.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A10%3A59Z%2F-1%2F%2F2d3fa7a0f064a64dff7a2040dc36f48d0d49529c833e2b31721b6d9e8488452a" alt="Image" width="7%" /></div>

> [!NOTE]
> There are genuine performance tuning experts and companies out there, but most would agree that you have to measure and investigate any problem. It is unlikely the same solution will apply to all uses of a particular technology in all situations.

### Resolutions

* **Measure** to determine the real location of the bottleneck.
* **Ensure that any experts** hired onto a team are willing to share and act as part of the team.

---

## Tuning by Folklore

While desperate to try to find a solution to a performance problem in production, a team member finds a “magic” configuration parameter on a website. Without testing the parameter, the team applies it to production because it must improve things exactly as it did for the person on the internet...

### Example Comment

* “I found these great tips on Stack Overflow. This changes everything.”

### Reality

* The developer does not understand the context or basis of the performance tip, and the true impact is unknown.
* It may have worked for that specific system, but that does not mean the change will even have a benefit in another. In reality, it could make things worse.

### Discussion

A performance tip is a workaround for a known problem—essentially, a solution looking for a problem. Performance tips have a short shelf life and usually age badly. Someone will come up with a solution that will make the tip useless (at best) in a later release of the software or platform.

One particularly bad source of performance advice is admin manuals. They contain general advice without context. Lawyers often insist on this vague advice and “recommended configurations” as an additional line of defense if the vendor is sued.

Java performance happens in a specific context, with a large number of contributing factors. If we strip away this context, then what is left is almost impossible to reason about, due to the complexity of the execution environment.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//45e10598-f297-45fe-a6f1-31cb1a21a077/markdown_0/imgs/img_in_image_box_176_454_252_554.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A07Z%2F-1%2F%2F08c7ee2f8cf6a6e60606f289caf429459308e1ef256a846c56425ca21206f4ba" alt="Image" width="7%" /></div>

> [!NOTE]
> The Java platform is also constantly evolving, which means a parameter that provided a performance workaround in one version of Java may not work in another.

For example, the switches that control garbage collection algorithms frequently change between releases. What works in older VM versions may not be applied in the current JVM versions. Even switches that are valid and useful in older versions are ignored or will prevent startup in newer versions of the JVM.

Configuration can be a one- or two-character change but have significant impact in a production environment if not carefully managed.

### Resolutions

* **Apply only well-tested** and well-understood techniques that directly affect the most important aspects of the system.
* **Look for and try out parameters** in UAT, but as with any change, it is important to prove and profile the benefit.
* **Review and discuss configuration** with other developers and operations staff or DevOps.

---

## The Blame Donkey

Certain components are always identified as the issue, even if they had nothing to do with the problem.

For example, one of the authors saw a massive outage in UAT the day before go-live. A certain path through the code caused a table lock on one of the central database tables. An error occurred in the code, and the lock was retained, rendering the rest of the application unusable until a full restart was performed. Hibernate was used as the data access layer and immediately blamed for the issue. However, in this case, the culprit wasn't Hibernate but an empty catch block for the timeout exception that did not clean up the database connection. It took a full day for developers to stop blaming Hibernate and actually look at their code to find the real bug.

### Example Comment

* “It’s always JMS/Hibernate/A_N_OTHER_LIB.”

### Reality

* Insufficient analysis has been done to reach this conclusion.
* The usual suspect is the only suspect in the investigation.
* The team is unwilling to look wider to establish a true cause.

### Discussion

This antipattern is often displayed by management or the business. In many cases they do not have a full understanding of the technical stack and have acknowledged cognitive biases, so they proceed by pattern matching. However, technologists are far from immune to it.

Technologists often fall victim to this antipattern when they have little understanding about the codebase or libraries outside of the ones usually blamed. It is often easier to name a part of the application that is commonly the problem, rather than perform a new investigation. It can be the sign of a tired team with many production issues at hand.

Hibernate is the perfect example of this. In many situations, Hibernate grows to the point where it is not set up or used correctly. The team then tends to criticize the technology, as they have seen it fail or not perform in the past. However, the problem could just as easily be the underlying query, use of an inappropriate index, the physical connection to the database, the object mapping layer, or something else. Profiling to isolate the exact cause is essential.

### Resolutions

* **Resist the pressure** to rush to conclusions.
* **Perform analysis** as normal.
* **Communicate the results** of the analysis to all stakeholders to encourage a more accurate picture of the causes of problems.

---

## Missing the Bigger Picture

The team becomes obsessed with trying out changes or profiling smaller parts of the application without fully appreciating the full impact of the changes. Engineers start tweaking JVM switches in an effort to gain better performance, perhaps based on an example or a different application in the same company.

The team may also look to profile smaller parts of the application using microbenchmarking (which is well-known for being difficult to get right, as we explored in Appendix A).

### Example Comments

* "If I just change these settings, we'll get better performance."
* “If we can just speed up method dispatch time...”

### Reality

* The team does not fully understand the impact of changes.
* The team has not profiled the application fully under the new JVM settings.
* The overall system impact from a microbenchmark has not been determined.

### Discussion

The JVM has literally hundreds of switches. This gives a very highly configurable runtime, but it also creates a great temptation to use all of this configurability. This is usually a mistake—the defaults and self-management capabilities are usually sufficient. Some of the switches also combine with one another in unexpected ways, which makes blind changes even more dangerous. Even in the same company, applications are likely to operate and profile in a completely different way. So, it is important to spend time trying out settings that are recommended.

Performance tuning is a statistical activity, which relies on a highly specific context for execution. This implies that larger systems are usually easier to benchmark than smaller ones. This is because with larger systems, the law of large numbers works in the engineer's favor, helping to correct for effects in the platform that distort individual events.

By contrast, the more we try to focus on a single aspect of the system, the harder we have to work to separate the separate subsystems (e.g., threading, GC, scheduling, JIT compilation) of the complex environment that makes up the platform (at least in the Java/C# case). This is extremely hard to do. Also, handling the statistics is sensitive and is often not a skillset that software engineers have acquired along the way. This makes it very easy to produce numbers that do not accurately represent the behavior of the system aspect that the engineer believed they were benchmarking.

This has an unfortunate tendency to combine with the human bias to see patterns even when none exist. Together, these effects lead us to the spectacle of a performance engineer who has been deeply seduced by bad statistics or a poor control—an engineer arguing passionately for a performance benchmark or effect that their peers are simply not able to replicate.

There are a few other points to be aware of here. First, it is difficult to evaluate the effectiveness of optimizations without a UAT environment that fully emulates production. Second, there is no point in having an optimization that helps your application only in high-stress situations and kills performance in the general case. However, obtaining sets of data that are typical of general application usage but also provide a meaningful test under load can be difficult.

### Resolutions

Before making any change to switches live:

1. **Measure** in production.
2. **Change one switch at a time** in UAT.
3. **Ensure** that your UAT environment has the same stress points as production.
4. **Ensure** that test data is available that represents normal load in the production system.
5. **Test** the change in UAT.
6. **Retest** in UAT.
7. **Have someone recheck** your reasoning.
8. **Pair** with them to discuss your conclusions.

---

## Fiddling with Switches

**Tuning by Folklore** and **Missing the Bigger Picture** (abuse of microbenchmarks) are examples of antipatterns that are caused at least in part by a combination of oversimplification and confirmation biases. One particularly extreme example is a subtype of Tuning by Folklore known as **Fiddling with Switches**.

This antipattern arises because, although the VM attempts to choose settings appropriate for the detected hardware, there are some circumstances where the engineer will need to manually set flags to tune the performance of code. This is not harmful in itself, but there is a hidden cognitive trap here, in the extremely configurable nature of the JVM with command-line switches.

To see a list of the VM flags, use the following switch:

`-XX:+PrintFlagsFinal`

As of Java 8u131, this produces over 700 possible switches. Not only that, but there are also additional tuning options available only when the VM is running in diagnostic mode. To see these, add this switch:

`-XX:+UnlockDiagnosticVMOptions`

This unlocks around another 100 switches. There is no way that any human can correctly reason about the combined effect of applying the possible combinations of these switches. Moreover, in most cases, experimental observations will show that the effect of changing switch values is small—often much smaller than developers expect.

---

## UAT Is My Desktop

UAT environments often differ significantly from production, although not always in a way that is expected or fully understood. Many developers will have worked in situations where a low-powered desktop is used to write code for high-powered production servers. However, it is also common that a developer's machine is massively more powerful than the small servers deployed in production. Low-powered micro-environments are usually not a problem, as they can often be virtualized for a developer to have one of each. This is not true of high-powered production machines, which will often have significantly more cores, RAM, and efficient I/O than a developer's machine.

### Example Comment

* “A full-size UAT environment would be too expensive.”

### Reality

* Outages caused by differences in environments are almost always more expensive than a few more machines.

### Discussion

The **UAT Is My Desktop** antipattern stems from a different kind of cognitive bias than we have previously seen. This bias insists that doing some sort of UAT must be better than doing none at all. Unfortunately, this hopefulness fundamentally misunderstands the complex nature of enterprise environments. For any kind of meaningful prediction to be possible, the UAT environment must be production-like.

In modern adaptive environments, the runtime subsystems will make best use of the available resources. If these differ radically from those in the target deployment, they will make different decisions under the differing circumstances—rendering our hopeful prediction useless at best.

In “Working with Remote Containers Using “Remote” Development” on page 223, we introduced remote development. This enables developers to directly connect their local environment to a production-like environment. With the introduction of CNCF platforms, **UAT Is My Desktop** has a lot more solutions than ever before. Container constraints do introduce a separate set of issues, which you can read more about in “Building Images” on page 203.

### Resolutions

* **Track the cost** of outages and opportunity cost related to lost customers.
* **Buy a UAT environment** that is identical to production and look at technologies supporting remote development.
* **In most cases**, the cost of a full UAT environment outweighs the cost of critical business impact, and sometimes the right case needs to be made to managers.

---

## Production-Like Data Is Hard

Also known as the **DataLite** antipattern, this antipattern relates to a few common pitfalls that people encounter while trying to represent production-like data. Consider a trade processing plant at a large bank that processes futures and options trades that have been booked but need to be settled. Such a system would typically handle millions of messages a day. Now consider the following UAT strategies and their potential issues:

* **To make things easy to test**, the mechanism is to capture a small selection of these messages during the course of the day. The messages are then all run through the UAT system.

  This approach fails to capture burst-like behavior that the system could see. It may also not capture the warmup caused by more futures trading on a particular market before another market opens that trades options.

* **To make the scenario easier to test**, the trades and options are updated to use only simple values for assertion.

  This does not give us the “realness” of production data. Considering that we are using an external library or system for options pricing, it would be impossible for us to determine with our UAT dataset that this production dependency has not now caused a performance issue. This is because the range of calculations we are performing is a simplified subset of production data.

* **To make things easier**, all values are pushed through the system at once.

  This is often done in UAT, but misses key warmup and optimizations that may happen when the data is fed at a different rate.

Most of the time in UAT, the test dataset is simplified to make things easier. However, it rarely makes results useful.

### Example Comments

* “It’s too hard to keep production and UAT in sync.”
* “It’s too hard to manipulate data to match what the system expects.”
* “Production data is protected by security considerations. Developers should not have access to it.”

### Reality

* Data in UAT must be production-like for accurate results.
* If data is not available for security reasons, then it should be scrambled, masked, or hidden so it can still be used for a meaningful test. Another option is to partition UAT so developers still don't see the data, but can see the output of the performance tests to be able to identify problems.

### Discussion

This antipattern also falls into the trap of “something must be better than nothing.” The idea is that testing against even out-of-date and unrepresentative data is better than not testing.

As before, this is an extremely dangerous line of reasoning. While testing against something (even if it is nothing like production data) at scale can reveal flaws and omissions in the system testing, it provides a false sense of security.

When the system goes live, and the usage patterns fail to conform to the expected norms that have been anchored by UAT data, the development and ops teams may well find that they have become careless due to the warm glow that UAT has provided. They may be unprepared for the complete terror that can quickly follow an at-scale production release.

### Resolutions

* **Consult data domain experts** and invest in a process to migrate production data back into UAT, scrambling, masking, or hiding data if necessary.
* **Over-prepare** for releases for which you expect high volumes of customers or transactions.
