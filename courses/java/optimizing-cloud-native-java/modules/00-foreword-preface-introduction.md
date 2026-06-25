# Optimizing Cloud Native Java

**Practical Techniques for Improving JVM Application Performance**

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//c71c8410-1399-4202-a1b4-14894c51e91a/markdown_0/imgs/img_in_image_box_168_389_927_1123.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A02Z%2F-1%2F%2Fabf68c90272b4343c5ba9eef58c2816fb53033cae95f0b38f962ada7b05b38aa" alt="Image" width="75%" /></div>

**Benjamin J. Evans & James Gough**

Foreword by Holly Cummins

---

> "Highly recommended for experienced Java engineers and performance practitioners. This book dives deep into garbage collection, observability strategy, and performance tuning of Java applications in the cloud."
>
> — *Guus Bosman, Distinguished Engineer, Executive Director, Morgan Stanley*

> "A good understanding of Java performance is core to getting the most out of cloud platforms. This book provides practical steps on how to investigate performance problems, as well as advice on how to avoid them in the first place."
>
> — *Elspeth Minty, Managing Director, RBC Capital Markets*

---

## About This Book

**Performance tuning** is an experimental science. But that does not mean engineers should turn (resort) to guesswork and stories (folklore) to get the job done. Yet that is often the case. With this practical book, intermediate to advanced Java developers (technologists) working with complex platforms will learn how to tune Java cloud applications for performance using a quantitative, verifiable, and repeatable approach.

In response to the presence (ubiquity) of cloud computing, this updated edition of *Optimizing Cloud Native Java* discusses (addresses) topics that are key to high performance of Java applications in the cloud. Many resources on performance focus on the theory and workings (internals) of Java virtual machines, but this book discusses the low-level technical parts (aspects) within the context of performance-tuning realities (practicalities) and studies (examines) a wide range of parts (aspects).

### With this book, you will:
- Study (examine) the dangers (pitfalls) of measuring Java performance numbers and the disadvantages (drawbacks) of microbenchmarking.
- Understand how to package, deploy, run (operate), and fix (debug) Java/JVM applications in modern cloud environments.
- Apply emerging observability methods (approaches) to get (obtain) a deep understanding of cloud-native applications.

---

**Benjamin Evans**, senior principal software engineer and observability lead at Red Hat Runtimes, is a Java Champion and author of several books, including *Optimizing Java* and *Java in a Nutshell*.

**James Gough** is a Distinguished Engineer at Morgan Stanley working on cloud-native architecture and API programs. He is a Java Champion and coauthor of *Mastering API Architecture*.

---

*JAVA PROGRAMMING — US $69.99 CAN $87.99 — ISBN: 978-1-098-14934-5*

---

## Publication Details

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//c71c8410-1399-4202-a1b4-14894c51e91a/markdown_2/imgs/img_in_image_box_665_1140_868_1186.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A05Z%2F-1%2F%2Ff51b9ec820d4a0957bedfb9498e1194830e6c2090908e482266db4b75716cfd8" alt="Image" width="20%" /></div>

**Optimizing Cloud Native Java**  
by Benjamin J. Evans and James Gough  

Copyright © 2025 Benjamin J. Evans and James Gough Ltd. All rights reserved.  
Printed in the United States of America.  
Published by **O'Reilly Media, Inc.**, 1005 Gravenstein Highway North, Sebastopol, CA 95472.  

O'Reilly books may be purchased for educational, business, or sales promotional use. Online editions are also available for most titles (http://oreilly.com). For more information, contact our corporate/institutional sales department: 800-998-9938 or corporate@oreilly.com.

### Editorial and Production Team

| Role | Name |
|---|---|
| **Acquisitions Editor** | Brian Guerin |
| **Development Editor** | Rita Fernando |
| **Indexer** | Potomac Indexing, LLC |
| **Production Editor** | Christopher Faucher |
| **Interior Designer** | David Futato |
| **Copyeditor** | Emily Wydeven |
| **Cover Designer** | Karen Montgomery |
| **Proofreader** | Piper Editorial Consulting, LLC |
| **Illustrator** | Anna Evans |

* **May 2018:** First Edition  
* **October 2024:** Second Edition  

### Revision History for the Second Edition
- **2024-10-10:** First Release  

See http://oreilly.com/catalog/errata.csp?isbn=9781098149345 for release details.

The O'Reilly logo is a registered trademark of O'Reilly Media, Inc. *Optimizing Cloud Native Java*, the cover image, and related trade dress are trademarks of O'Reilly Media, Inc.

The views expressed in this work are those of the authors and do not represent the publisher's views. While the publisher and the authors have used good faith efforts to ensure that the information and instructions contained in this work are accurate, the publisher and the authors disclaim all responsibility for errors or omissions, including without limitation responsibility for damages resulting from the use of or reliance on this work. Use of the information and instructions contained in this work is at your own risk. If any code samples or other technology this work contains or describes is subject to open source licenses or the intellectual property rights of others, it is your responsibility to ensure that your use thereof complies with such licenses and/or rights.

---

### Dedications

*This book is dedicated to my wife, Anna, who not only illustrated it beautifully but also helped edit portions and, crucially, was often the first person I bounced ideas off.*  
— *Ben Evans*

*This book is dedicated to my incredible family Megan, Emily, and Anna. Writing would not have been possible without their help and support. I'd also like to thank my parents, Heather and Paul, for encouraging me to learn and their constant support.*  
*I'd also like to thank Ben Evans for his guidance and friendship—it's been a pleasure working together again.*  
— *James Gough*

---

## Table of Contents

| Chapter | Title | Page |
|---|---|---|
| **Foreword** | | xv |
| **Preface** | | xvii |
| **1** | Optimization and Performance Defined | 1 |
| **2** | Performance Testing Methodology | 17 |
| **3** | Overview of the JVM | 49 |
| **4** | Understanding Garbage Collection | 75 |
| **5** | Advanced Garbage Collection | 105 |
| **6** | Code Execution on the JVM | 137 |
| **7** | Hardware and Operating Systems | 169 |
| **8** | Components of the Cloud Stack | 193 |
| **9** | Deploying Java in the Cloud | 211 |
| **10** | Introduction to Observability | 235 |
| **11** | Implementing Observability in Java | 265 |
| **12** | Profiling | 305 |
| **13** | Concurrent Performance Techniques | 335 |
| **14** | Distributed Systems Techniques and Patterns | 377 |
| **15** | Modern Performance and The Future | 405 |
| **A** | Microbenchmarking | 427 |
| **B** | Performance Antipatterns Catalog | 443 |
| **Index** | | 455 |

---

## Foreword

> Optimization is a game of "what," and "why," and "where," but mostly "why." Why is my application slow? Where is the time being spent? Why are so many resources being used (consumed)? Which metrics matter? What problem am I actually trying to solve? Why is this innocent-looking microbenchmark confusing (misleading)? Why do my users need this?

Many of us are taught how to program Java, but very few of us are taught how to optimize Java. We may not even know that we need to be able to optimize—until we hit a problem. But optimization is important. There's a saying that "slow is the new down"; outages are terrible, but slow (sluggish) performance is expensive, and annoying, and wasteful, and also pretty terrible. There's also greenness (sustainability) to think about; in general, optimized software uses (consumes) less energy and needs (requires) less hardware to run. The digital world has a large (substantial) carbon footprint, but we can reduce that by optimizing.

But people are perhaps the most important reason to optimize. Slow applications annoy (frustrate) users, and in the worst case, may even drive them—and their business—elsewhere. Studies have found even small worsening (deterioration) in response times can reduce happiness (satisfaction) and retention rates.

So how do we make applications go faster? As Ben and James point out in this book, there are no magic fixes or one-click answers. Ben and James do not give a set of guides (recipes) for performance adjustments (tweaks), for the very good reason that this kind of advice becomes old (stale), very quickly.

Instead, Ben and James focus on principles and methods (methodologies). They begin by introducing the basic measurements (observables) of performance: throughput, latency, capacity, utilization, efficiency, scalability, and degradation. It is important to know which of these matters to you, because you cannot optimize them all—or at least, not all at the same time. It's very (exceedingly) silly to spend time optimizing throughput if your users actually care about latency, or if the main challenge for your business is hardware costs. Performance is about trade-off (compromise), and about chasing the right rabbit.

Ben and James give an overview of how to measure performance and how to use statistical analysis to explain (interpret) the results. They then dive into a thorough (comprehensive) overview of how the Java virtual machine works. They cover memory layouts, garbage collection, code execution, and the just-in-time compiler. This is important because performance tuning is a process of discovery and problem-solving, which has to be based (rooted) in an understanding of the whole system. “The whole system” means software, but also hardware, so Ben and James give a guide (primer) on modern hardware. In a practical (realistic) software setup (deployment), the edge of “the whole” system is not the plastic case of a single computer. Performance analysis must consider the special (distinctive) features (characteristics) of cloud environments and the dangers (risks) and benefits (rewards) of distributed computing. It’s a lot, but Ben and James cover it. This is a broad book because what a modern software engineer needs to know is equally broad.

When trying to solve a performance problem, it's easy to be distracted by shiny things or influenced by our own prejudices (biases). Especially in a complex system, one can easily end up chasing the wrong rabbit. To find (identify) the right rabbit, it's necessary to go wide, across a spread (diffuse) and distributed application, and deep, into the workings (internals) of Java garbage collection and threading. One must be ordered (systematic) and strict (rigorous) but also, as Ben and James point out, caring (empathetic) and business-aware. Performance is not a fixed (absolute) quantity; slow only matters if it has results (consequences).

In *Spice World*, Roger Moore's character advised that "when the rabbit of chaos is pursued by the ferret of disorder through the fields of anarchy, it is time to hang your pants on the hook of darkness." With the help of this book, I believe you will be able to chase the right rabbit and hang your pants on the hooks of reason and understanding.

— **Holly Cummins**  
*Senior Principal Software Engineer, Red Hat Middleware*

---

## Preface

### Why Did We Write This Book?

This book is an updated edition of our *Optimizing Java* title, which was released in 2018. The world has changed greatly (markedly) since then—in many ways. For Java programmers, the cloud has become ever-more important, and it is now probably more likely than not that Java applications are run (deployed) in the cloud.

**Cloud-native deployment** completely (fundamentally) changes a number of parts (aspects) of performance engineering (or whatever we want to call this field (specialism)), so it seemed appropriate to produce a new edition of the book that turns (reorients) the material toward this new reality.

### Why Should You Read This Book?

Java developers have, in many cases, not necessarily had a lot to do with the running (deployment) and management of their applications in production. That is, they have tended not to be leaders (trailblazers) in the adoption of trends like **DevOps**. With the increasing tide of cloud adoption, this has led to a possible knowledge gap, which this book aims to fix.

Otherwise (alternatively), **DevOps** professionals may not have had much contact (exposure) to Java/JVM technologies but are now finding themselves needing to manage Java applications, or pieces of infrastructure that are written (implemented) in it (e.g., Cassandra, Infinispan, Kafka, etc.). Java processes are completely (fundamentally) different from those written (implemented) in Go, Python, Node.js, etc. To get the best out of them, you need some level of understanding of those differences and how to work with them.

Whichever background (tradition) you have come from, the end goal is the same—to help (enable) you to have confidence in managing your cloud-based production applications and be able to find (diagnose) issues with them as they arise.

### Who This Book Is For

Java performance improvement (optimization) is of interest to several different groups of professionals, not just developers. As such, it is important that we provide entries (on-ramps) for people who may be coming from different backgrounds and approaching the subject with a different base (grounding).

The sorts of jobs that our readers might do include:
- **Developers**
- **Application support and operations staff**
- **DevOps engineers**
- **Architects**

Each of these groups is likely to have a different focus and view (take) of the material, but they all share a common interest in looking after production business applications in the cloud. They will need to understand the performance behavior of both a **single-JVM application** and a **cloud-deployed, distributed system**. In this book we will consider cloud deployments to be public cloud, private cloud, and also a hybrid (mixture) cloud.

An awareness of performance methods (methodology) and the relevant parts (aspects) of statistics is also important, so that observability and other performance data can be correctly (accurately) studied (analyzed) once it has been collected.

It is also to be expected that the most (majority) of people who read this book will have a need for, or at least an interest in, some of the workings (internals) of the systems they support. This understanding is often very important when finding (diagnosing) certain types of performance problems, as well as being attractive to the intellectually curious engineer.

### What You Will Learn

The material in this book covers a range (variety) of topics. This is because this field goes (extends) beyond the limits (boundaries) of software development and mixes (overlaps) into a range (variety) of other fields.

### What This Book Is Not

You will find almost no discussion of the proprietary (vendor-specific) technologies present on the cloud platforms (hyperscalers) (AWS, Azure, GCP, OpenShift, and so on) in this book.

This is for two main reasons:
- It would expand the range (scope) of the book and make it too (unmanageably) long.
- It is impossible to remain (stay) current with such a large topic area.

The progress made by teams working on those products would make any detailed information about them out of date by the time the book is published. So, instead, in the cloud chapters, we focus on basics (fundamentals) and designs (patterns), which remain effective regardless of which cloud your applications are run (deployed) upon.

### Conventions Used in This Book

The following text (typographical) conventions are used in this book:
- ***Italic*** — Indicates new terms, URLs, email addresses, filenames, and file extensions.
- **`Constant width`** — Used for program examples (listings), as well as within paragraphs to refer to program elements such as variable or function names, databases, data types, environment variables, statements, and keywords.
- **`<constant width> in angle brackets`** — Shows text that should be replaced with user-supplied values or by values determined by context.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//5f1c6adb-dbae-484c-805f-c4656c82c8cf/markdown_0/imgs/img_in_image_box_167_724_254_840.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A07Z%2F-1%2F%2Fd03fda23e86b2953a8cd7417ce8270ea4fa2e36e0fb4f3577fa6985a6e702611" alt="Image" width="8%" /></div>

This box shows a **tip or suggestion**.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//5f1c6adb-dbae-484c-805f-c4656c82c8cf/markdown_0/imgs/img_in_image_box_176_863_254_963.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A07Z%2F-1%2F%2Fee461c404bbe306bb8744bc60e3aecd61302186a5472b3cf08a798f58520d217" alt="Image" width="7%" /></div>

This box shows a **general note**.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//5f1c6adb-dbae-484c-805f-c4656c82c8cf/markdown_0/imgs/img_in_image_box_163_995_269_1094.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A08Z%2F-1%2F%2F0d4b20edf371b539b7e62cfafe7d9af5624ed1f7011ea49c40df44d65f705325" alt="Image" width="10%" /></div>

This box shows a **warning or caution**.

---

## O'Reilly Online Learning

For more than 40 years, **O'Reilly Media** has provided technology and business training, knowledge, and understanding (insight) to help companies succeed.

Our unique network of experts and innovators share their knowledge and expertise through books, articles, and our online learning platform. O'Reilly's online learning platform gives you on-demand access to live training courses, in-depth learning paths, interactive coding environments, and a large (vast) collection of text and video from O'Reilly and 200+ other publishers. For more information, visit http://oreilly.com.

### How to Contact Us

Please address comments and questions concerning this book to the publisher:

**O'Reilly Media, Inc.**  
1005 Gravenstein Highway North  
Sebastopol, CA 95472  

* **800-889-8969** (in the United States or Canada)
* **707-827-7019** (international or local)
* **707-829-0104** (fax)
* **support@oreilly.com**
* **https://oreilly.com/about/contact.html**

We have a web page for this book, where we list errata, examples, and any additional information. You can access this page at https://oreil.ly/optimizing-java-2e.

For news and information about our books and courses, visit https://oreilly.com.

* Find us on LinkedIn: https://linkedin.com/company/oreilly-media
* Watch us on YouTube: https://youtube.com/oreillymedia

---

## Acknowledgments

The authors would like to thank a large number of people for their invaluable assistance.

### Foreword and Technical Review
- **Holly Cummins**

### Specialized Technical Help
- **Christine Flood**
- **Bela Ban**
- **Kirk Pepperdine**
- **Bruno Baptista**
- **Roman Kennke**
- **Stefan Karlsson**
- **Guus Bosman**
- **Fabio Massimo Ercoli**
- **Jonathan Halliday**
- **Katia Aresti Gonzalez**

### General Encouragement, Advice, and Introductions
- **Stuart Douglas**

### Technical Reviewers
- **Tony Mancill**
- **José Bolina**
- **Dov Katz**
- **Elspeth Minty**

### Technical Illustrations
- **Anna Evans**

### The O'Reilly Team
- **Rita Fernando**
- **Brian Guerin**
- **Jeff Bleiel**
- **Zan McQuade**
- **Christopher Faucher**
- **Emily Wydeven**
