# Components of the Cloud Stack

Reasoning about Java performance on a single machine is difficult—there are many variables coming from the JVM subsystems and the underlying hardware. Before this chapter, we have explored and discussed how to approach these challenges. We've discussed some aspects of JVM internals, diagnostics, and operating system performance tools and how they help to check a running process. Going further, mechanical sympathy—understanding the interaction between the JVM and hardware—allows us to address high-performance concerns on a single JVM.

In this chapter, we are going to break the single JVM model and look at platforms supporting a horizontal deployment model for Java processes. You will see how platforms hosting Java processes have significantly shifted. Specifically, cloud native environments have changed the landscape and, with that, the groups of topics that architects and performance engineers need to understand.

In particular, in addition to the key questions highlighted in “A Taxonomy for Performance” on page 7, developers working in cloud-based platforms will also need to consider:
- **Optimization for cost**
- **Optimization for reliability**
- **Scaling horizontally**

In other words, optimizing for cost, reliability, and elastic scale (managing performance across multiple instances of running Java processes) will be key factors in complementing the classic taxonomy for performance.

In this chapter, you will learn a summary of some of the key cloud native building blocks and associated standards. You will also learn about Java standards relevant to building cloud native applications. We will cover a basic guide to virtualization, containers, and images.

We will then cover networking, as there are some major differences that influence the way that you will need to consider designing for cloud native. Finally, we will introduce the Fighting Animals repository, which we will use in later chapters to practically show you new concepts.

---

## Java Standards for the Cloud Stack

Frameworks in Java extend the core Java libraries offered in the JDK to assist in solving real-world problems. This helps developers in solving common problems on common deployment targets and platforms. Distributed platforms based on microservices-based architectures have become more common. It is important to consider not just a single framework but also the available standards that apply to distributed deployment methodologies.

Standards create portability across a range of cloud native Java products including Quarkus, Helidon, and Open Liberty. <sup>1</sup>

Of particular importance are these two open standards:
- **Jakarta EE**: Provides a series of Enterprise Java standards and is widely used, but explaining it fully is outside the scope of this book.
- **MicroProfile**: A standard for distributed systems on a cloud native platform, and as of version 6.1, effectively splits Jakarta EE 10 into a set of related but independent standardized parts.

In particular, MicroProfile provides a set of vendor-neutral standards that support microservice-based architectures and distributed system best practices. It is of particular interest to Java developers and architects because it provides standardization for libraries for building twelve-factor apps. Without standards, it is easy to end up in a situation where developers build their own solutions or potentially get stuck with a particular framework.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//cc9991af-10ee-45eb-a93f-6db0abe5000e/markdown_2/imgs/img_in_image_box_176_976_252_1078.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A06Z%2F-1%2F%2F320199983f08349010b5ccbd60045ccaa746ec6e44ffa9efa9a6bbedd495e006" alt="Image" width="7%" /></div>

> [!NOTE]
> The Eclipse Foundation is the home of both the MicroProfile and Jakarta EE working groups. These working groups are responsible for defining enterprise Java and microservices standards, respectively. Eclipse also hosts the Adoptium community build of OpenJDK.

Figure 8-1 describes the standards covered in MicroProfile 6.1 and demonstrates the key aspects you must consider when building applications in cloud native environments. As trends change to different patterns for building microservices-based architectures, Jakarta EE and MicroProfile will adapt and likely add new standards.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//cc9991af-10ee-45eb-a93f-6db0abe5000e/markdown_3/imgs/img_in_image_box_149_224_860_530.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A07Z%2F-1%2F%2F10f74515ceb2c01092e80e8374ed1701299ccb05b5c6809216eb3fc5dda6a1b6" alt="Image" width="70%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 8-1. Structure of the MicroProfile standard</div> </div>

Standards in Java are useful, but we also need to find a strategy to address vendor neutrality and portability in the platforms we target. Open source software has a long tradition of using open foundations to address these aspects of the software landscape.

---

## Cloud Native Computing Foundation

The **Cloud Native Computing Foundation (CNCF)** is a vendor-neutral open source software foundation dedicated to making cloud native computing universal.

> **CNCF Charter**
> Cloud native technologies allow organizations to build and run scalable applications in modern, dynamic environments such as public, private, and hybrid clouds. Containers, service meshes, microservices, immutable infrastructure, and declarative APIs show this approach.

As vendor neutrality and portability are significant architectural concerns, it is not a surprise that several CNCF projects are extremely important in the delivery of cloud native applications.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//cc9991af-10ee-45eb-a93f-6db0abe5000e/markdown_3/imgs/img_in_image_box_176_1077_253_1177.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A07Z%2F-1%2F%2F4ee9036a04174c9c26a2186ae05dbcb0cb8f188f9d10f30312bbbee1e7c4b2a0" alt="Image" width="7%" /></div>

> [!NOTE]
> Compute platforms are not tied to a specific language stack, so advice given in the remainder of this chapter will expand beyond the scope of Java.

When building systems composed of multiple services, it is likely that you will need to revisit where and how certain components are deployed to meet evolving nonfunctional requirements. This is where CNCF is critical, hosting key projects with different benefits to help meet business and nonfunctional requirements.

Figuring out which of the many projects to apply to your specific use case is tough. The **CNCF Landscape** is an interactive map that attempts to categorize most of the projects and product offerings in the cloud native space. The CNCF Landscape is organized into multiple categories covering a range of concerns. Five of the key categories are:
- **Application definition and deployment**
- **Orchestration and management**
- **Runtime**
- **Provisioning**
- **Observability and analysis**

Within each of these categories in the CNCF Landscape, you will find individual CNCF projects, the statistics of the project, and where the ownership of each project resides.

Note that the formats and standards for container images themselves are not part of the CNCF and are maintained by a separate standards initiative, the **Open Container Initiative (OCI)**. Although vendor neutral, projects on the CNCF Landscape include “for profit” projects. CNCF open source projects have different levels of maturity, which helps developers and architects in considering various technologies in their cloud native deployments:

- **Sandbox**: Early innovative projects at an early stage of development that may not yet be at production standard.
- **Incubating**: The project is ready for production and has demonstrated active adoption. The project has adequate governance, community, security, and ecosystem, meeting the criteria of the incubating template.
- **Graduated**: The project has a proven track record of production usage in multiple industries and projects, meeting the graduation criteria.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//1f600227-b54a-4cfd-b4f0-9395e68bc0be/markdown_0/imgs/img_in_image_box_176_106_253_207.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A20Z%2F-1%2F%2F6ac22a5dc8e5e60dd352773c3dd8b9a1f40b6aa42503cade16dc30db7361951a" alt="Image" width="7%" /></div>

> [!NOTE]
> Architects frequently use the CNCF landscape as a way to identify technologies in a specific problem area, discover the merits of a project, and focus proof of concepts and spikes of functionality.

Three CNCF projects are critically important to cloud native Java developers and performance engineers:

### Kubernetes
**Kubernetes** (often shortened to **K8s**) is an open source container-orchestration system. It uses a cluster of compute nodes (hosts) to enable system operators and DevOps teams to deploy, scale, and coordinate distributed applications across the cluster. Kubernetes became a graduated project in CNCF in 2018. In Chapter 9, you will learn about deploying Java applications using containers and Kubernetes.

### Prometheus
**Prometheus** is a metrics format and time series database used to store metrics data. It was accepted to the CNCF in May 2016 as an incubating project and achieved graduated status in August 2018. It is widely deployed among Kubernetes applications and has benefited from a significant first-mover advantage, although the metrics landscape is evolving rapidly. You will learn more about Prometheus in Chapters 10 and 11.

### OpenTelemetry
**OpenTelemetry (OTel)** is a set of standards, formats, and libraries that handles the collection, aggregation, and transport of observability data from applications into an observability system. OTel is a CNCF project, and the technical development of the project takes place on GitHub. 

OTel is explicitly a cross-platform technology and is not Java-specific, although Java is a mature implementation of the standards. OTel is currently an incubating project at CNCF, but it is seeing explosive growth and is already being used in production by many organizations. We will revisit OTel in depth in Chapter 11.

Underpinning these technologies is the model for how things are deployed, so let's look at the importance of virtualization in the cloud native stack.

---

## Virtualization

Before we can address the topic of virtualization, we first need to address the broader question: *what is cloud?* You will often hear the common joke, “Cloud is just someone else’s computer,” but there is more to it than that. The following helps provide a working definition:

> The simplest definition of cloud is a data centre that's full of identical hardware that no-one ever touches except to unpack it on day one and throw it away when it fails; in between, every deployment, update, investigation, and management process is automated.
> — *Mary Branscombe*

When your infrastructure is in the cloud, your capacity is turned into a utility and ready to run, available across a series of diverse application use cases. Access is not typically provided directly to the infrastructure and hardware. Instead, there needs to be control, management, and clear division of the customer's runtime from both the infrastructure and potentially other customers.

For Java developers and performance engineers, this is our first tradeoff related to the move to cloud.

Access to the underlying operating system and hardware is available only at significant cost; typically you will have only limited insight into the physical platform, if at all. Perhaps surprisingly, virtualization techniques were originally developed in IBM mainframe environments as early as the 1970s. However, it was not until recently that x86 architectures were capable of supporting "true" virtualization.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//1f600227-b54a-4cfd-b4f0-9395e68bc0be/markdown_1/imgs/img_in_image_box_167_830_253_944.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A24Z%2F-1%2F%2Fa01d85b9cb61ad1dde129c9a78d309dc357a4fbd2c83dd41512b96d6c451614b" alt="Image" width="8%" /></div>

> [!NOTE]
> The traditional sysadmin techniques of “SSH into a box and have a look around” are not normally available in cloud environments—instead, remote management techniques have become the standard approach.

Virtualization is typically defined by the following three conditions:
1. **Equivalence**: Programs running on a virtualized OS should run almost the same as on bare metal. <sup>2</sup>
2. **Control**: A component, known as a **hypervisor**, must mediate all access to hardware resources.
3. **Efficiency**: The overhead of the virtualization must be as small as possible and not a significant fraction of execution time.

In a traditional, unvirtualized system, the OS kernel runs in a special, privileged mode (hence the need to switch into kernel mode). This gives the OS direct access to hardware—this is the situation when working locally on your developer laptop, for example.

However, in a virtualized system, direct access to hardware by a guest OS is forbidden. Figure 8-2 outlines the structure, with the host operating system of the commoditized cloud infrastructure forming the base layer of the infrastructure. The Feline and Mustelid components are typical REST microservices that we will introduce later in the chapter.

The next layer is the hypervisor, which acts as a layer of indirection between the host operating system and the guest operating system. As a developer, you can deploy freely to the guest operating system, potentially using containers.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//1f600227-b54a-4cfd-b4f0-9395e68bc0be/markdown_2/imgs/img_in_image_box_141_604_864_894.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A27Z%2F-1%2F%2F639d5fc49372b4e008f241bffbc0126bcfbdcef230bfddaf16e6aa2c343aad1d" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 8-2. Virtualization stack</div> </div>

The hypervisor is at the core of virtualization. The extensive use of virtual machines and hypervisors in the cloud has driven significant research and improvement to the overhead of hypervisors.

When moving to public cloud, your target platform will typically be a virtual machine packaged with the hypervisor. This will have an overall impact on performance that is, at least partly, out of your control—although public cloud providers do offer different options for the virtual machines available to you.

Let's explore some of the virtual machines offered by cloud providers and what decisions you have as an architect and developer.

### Choosing the Right Virtual Machines

Public cloud providers offer different types of virtual machines designed to suit different types of workload profiles. For example, Amazon EC2 has a huge number of options for VM configuration:

- **General purpose**: The starting point for applications, offering a wide range of compute options. For example, in the M7g series, you can choose from a medium VM with a single vCPU and 4 GB of memory to the `m7gd.metal`, a bare metal machine with 64 CPUs and 256 GB of memory.
- **Compute optimized**: Designed for workloads with high CPU loads.
- **Memory optimized**: Tailored for workloads with large datasets with significant in-memory read and write profiles, such as databases, in-memory caching, and data analytics.
- **Accelerated computing**: Uses hardware acceleration and is geared toward graphics, intense calculations, and generative AI applications.
- **Storage optimized**: Designed for high read and write operations on local storage, focused on transactional databases and Apache Spark-style workloads.
- **High-performance computing (HPC)**: Focused on complex simulations and deep learning workloads.

Azure provides a similar range of options, from **D-series** (general-purpose compute) to **L-series** (storage-optimized virtual machines). Google Cloud also offers a similar set, including workloads focused on general purpose, ultra-high memory, compute-intensive, and demanding GPU workloads.

As part of designing your applications on cloud, generally the best approach is to start with general-purpose VMs and build from there. Instance types are often sized in powers of 2, so moving to bigger VMs is a cost tradeoff. Instance families provide a consistent ratio of CPU, memory, network throughput, and storage across the instance sizes in that family, which is a helpful starting point.

Remember the lessons from earlier in the book: take small steps and measure whether adjusting VMs provides the type of performance benefit versus cost tradeoff that you are looking for.

In Chapter 9, you will explore how to mix and match VMs within your application deployments. Orchestration platforms like Kubernetes provide the ability to mix and match VMs, so you can run one specialized pool of nodes for specific tasks while other nodes focus on general-purpose use cases.

### Virtualization Considerations

When designing cloud applications, optimize for cost, reliability, and scalability by choosing the right VM for your use case. For example, in situations where you are (or expect to be) CPU-intensive, this impact should be measured and confirmed as part of a performance test conducted in a production-like environment.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//1f600227-b54a-4cfd-b4f0-9395e68bc0be/markdown_4/imgs/img_in_image_box_176_681_253_780.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A33Z%2F-1%2F%2Ff53a3b4c01ba92f43ea5d916a34d21043ff5bc70df8d21a545fc2c2d2aad82d3" alt="Image" width="7%" /></div>

> [!NOTE]
> One additional benefit of running in the cloud is that creating ephemeral environments for testing is simpler. We will revisit this concept in Chapter 9.

Another option is to run a “best of both worlds” platform. In this model, some processes run on public cloud and some processes on bare metal. This provides the possibility of optimizing certain workloads that need burst scale and reliability, but also allows for performance and consideration of mechanical sympathy on core processing. Red Hat’s OpenShift (“hybrid cloud”) technology is a good example of this approach.

---

## Images and Containers

When Java arrived in the late 90s, it promised a great future of portability with its slogan of “Write once, run everywhere,” meaning any operating system and machine capable of running a Java virtual machine can run your code. This was a very bold goal, and the abstraction was not always perfect, especially in the early days.

Nevertheless, as with so many other aspects of modern software, Java served as the way by which advanced ideas truly entered the mainstream.

> Big ideas such as virtual machines, dynamic self-management, JIT compilation and garbage collection are now part of the general landscape of programming languages.
> — *Benjamin J. Evans, “Java is a '90s Kid” in 97 Things Every Java Programmer Should Know*

The technology landscape continues to shift, and there has been an explosion in programming languages and platforms targeted at big data, artificial intelligence, cloud native routing, and network-level products. To support this array of complex technologies, the industry has had to react to deploying software on various operating systems, environments, and with a more diverse set of dependencies.

Portability is a design goal of cloud native applications, although it has appeared not in the portability of Java bytecode but at a slightly higher level—the **container image**. A container image (or just image) is an archive file that can be used to create an application process running under the control of an orchestration or container management system.

### Image Structure

Just as in traditional Unix environments the executable file on disk is the “frozen” representation of the program, the image can be thought of as the frozen (and portable) representation of the application component, which will be converted into an active component via scheduling and orchestration.

With this greater diversity and complexity of components, standardization is once again the weapon of choice. A good example is the **Open Container Image (OCI)** standard, established in 2015 by Docker.

Images are becoming the industry's preferred unit of packaging applications, including Java applications, even if the target platform is bare metal. The image is bundled with everything required to run the application, which includes the userspace components (such as a subset of operating system components) and the JVM. OCI is responsible for defining the format of images, how images run as containers, and how images are distributed.

### Building Images

One way to create an image as part of the software build process is to define the image instructions in a `Dockerfile`. Each line in the `Dockerfile` represents a new layer. A layer is an immutable change to the filesystem, which will be represented within the container and is stored in the build cache. Each existing layer in the build cache can be reused as a building block for new images.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//e7b48db1-404b-486b-b1d7-bd47cdd8f435/markdown_1/imgs/img_in_image_box_176_505_252_605.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A10%3A57Z%2F-1%2F%2Fff1e5d83ce4cbc0a69f9f33f5db8a32b85940093caeebc2c1b67dfeaf3e78c0f" alt="Image" width="7%" /></div>

> [!NOTE]
> Docker is often confused between its use as a technology and the commercial entity/registry provider. In this chapter, we refer to Docker as the actual standard format supported in open source and by excellent tooling.

In the following example, we can see the keyword `FROM`, which uses another image layer as a basis for adding our Java application `animals-demo-1.0-SNAPSHOT.jar`. The `USER`, `RUN`, `COPY`, and `WORKDIR` commands set up the app folder and move the built JAR to the `/app` folder, ready to be executed by the container entrypoint command `CMD`:

```dockerfile
FROM registry.access.redhat.com/ubi8/openjdk-17:1.13-1
USER root
RUN mkdir /app
COPY target/animals-demo-1.0-SNAPSHOT.jar /app
WORKDIR /app
CMD ["java", "-jar", "animals-demo-1.0-SNAPSHOT.jar", \
    "io.opentelemetry.examples.animal.AnimalApplication"]
```

Other tools have been developed as alternatives to the `Dockerfile` approach, having more information available to make build and layer optimization decisions.

**Jib** runs as part of a Java build system (e.g., Maven or Gradle) to create the image. It has the advantage of having detailed information about the structure of your Java application and its dependencies. It organizes the image into distinct layers, including dependencies, resources, and classes. Jib only modifies the layers that have changed. 

The theory is that Java library dependencies and resources change infrequently compared to the classes in your application code. By splitting layers out in this way, the immutable layers do not experience as much churn, decreasing the time of builds and startup during development.

Using Jib has the added benefit of keeping all dependencies fresh with each build of your application. Using the `Dockerfile` approach works too, but it is necessary to ensure that base images are updated as patches and newer versions are released. Jib has potential benefits for security patching and performance by helping to keep dependencies fresh.

It is also possible to run **multistage builds** in Docker by using it to both build the JAR and then use the JAR in a second stage to construct the final image. The layers used as part of the first build stage are discarded, and only the target JAR is copied across into the final image, ensuring a standardized, containerized build environment. The following example `Dockerfile` demonstrates this multistage approach:

```dockerfile
# This first stage acts as a builder using a maven base image to create the jar
FROM maven:3.9-openjdk-17 AS builder
COPY src /usr/src/app/src
COPY pom.xml /usr/src/app
RUN mvn -f /usr/src/app/pom.xml package

# This second stage builds the target runtime image
FROM registry.access.redhat.com/ubi8/openjdk-17:1.13-1
USER root
RUN mkdir /app
# Copy the jar created by the first stage
COPY --from=builder /usr/src/app/target/animals-demo-1.0-SNAPSHOT.jar /app
WORKDIR /app
CMD ["java", "-jar", "animals-demo-1.0-SNAPSHOT.jar"]
```

A typical image stack for a Java application includes OS dependencies, the JVM, configuration, and a JAR. A minimal base image is the **Universal Base Image (UBI) Minimal** from Red Hat, which is only 37.1 MB in compressed size. Layering OpenJDK on the AMD64 architecture results in a base image of 147.8 MB in compressed size. The final layer depends on the build size of your application. Images can get quite sizable; for example, a Windows AMD64 Eclipse Temurin image is 2.27 GB.

In Chapter 9, we will consider how the size of an image has the potential to impact scheduling.

### Running Containers

Containers provide a way for running applications in an isolated environment. They are controlled using two Linux kernel constructs:
- **namespaces**: Control access and visibility to resources on the host machine.
- **cgroups**: Enforce limits to machine resources—especially CPU utilization and memory.

One aim of container abstraction is to provide process isolation between different containers. The major conceptual difference from VMs is that containers do not use a hypervisor. Instead, applications in containers execute directly on the host operating system and access the host's kernel without hypervisor indirection. This makes containers lightweight and quick to start, forming the basis of the orchestration systems we will discuss in Chapter 9.

---

## Networking

Containers and orchestration systems use ephemeral compute, so developers should expect workloads to not reliably remain in the same physical or virtual host. Ephemeral compute enables dynamic scaling, optimizing infrastructure costs.

Scaling can occur within a given footprint, or by dynamically adding to the footprint (e.g., adding more nodes into a cluster). This can take advantage of **spot computing**, using unused cloud resources at a reduced cost. Spot instances are not reserved; when demand for those resources occurs, the spot instances will be terminated without advance notice.

From a networking perspective, things will not be as stable as fixed on-premises data centers, and components will not always have a dedicated IP address or continuously available compute. As a result, it is often best to think about the abstraction of traffic, generalized into two categories:

- **North $\rightarrow$ South**: Traffic that is not part of your system, originating from either somewhere else on the cloud or from the internet. North $\rightarrow$ South traffic needs to have a fixed IP address and is often referred to as an **ingress**.
- **East $\rightarrow$ West**: Service-to-service calls within the orchestration tier, using the internal service discovery provided by the orchestration platform to scale up and down. Within an orchestration system like Kubernetes, we can use a **service** to create a lightweight and local DNS entry, available to other services within the cluster.

One option for ingress is to use a highly available load balancer supplied by the cloud provider, with individual applications setting up the corresponding routing into the cluster. This allows for a fixed IP address for external calls while still providing the ability to scale up and add more workloads behind the scenes.

---

## Introducing the Fighting Animals Example

In this book, we provide complete and working examples that go beyond “Hello World” but are still simple enough to be understood and used as a starting point for real systems. This is because newcomers to the cloud stack frequently struggle to progress beyond initial, semi-trivial, sample projects.

When observability is layered onto the example, the situation gets more complex, as overly simple examples do not always generalize easily to an actual implementation that can form the basis of a production observability system. There is also an unavoidable complexity involved in implementing an observability system, with many variables and options.

Therefore, we introduce the **“Fighting Animals”** example application here. In Chapters 10 and 11, you will discover the observability considerations in more detail.

Fighting Animals is a simple Java application with a microservice architecture, available on GitHub. The main version is written as a Spring Boot application, with an alternative version based on Quarkus (we will stick to the Spring Boot version in the text).

The application runs as a collection of Docker containers (e.g., via Docker Compose) and exposes a REST endpoint on port 8080. Accessing the endpoint returns a simple JSON representation of two animals from several different biological clades that will battle each other. <sup>3</sup>

Call `GET /battle` to get a battle that looks like this:

```json
{
    "good": "<animal1>",
    "evil": "<animal2>"
}
```

There are several branches that we will explore further in upcoming chapters:
- `main`: No observability.
- `micrometer_only`: Micrometer metrics only.
- `micrometer_with_prom`: Micrometer metrics with Prometheus.
- `manual_tracing`: OpenTelemetry tracing using manual spans.
- `auto_otel`: Use of the OpenTelemetry Java agent to trace automatically.
- `k8s-with-argo`: An example using Kubernetes and rolling out changes using deployment strategies.
- `logging_only`: SLF4J logging exported to OpenTelemetry.
- `micrometer_with_otel`: Micrometer with OpenTelemetry metrics.
- `otel_metrics_raw_api`: OpenTelemetry metrics using the raw API.
- `distributed_systems`: Enhancing Fighting Animals with Kafka.
- `with_infinispan`: Enhancing Fighting Animals with Kafka and Infinispan.

In Figure 8-3, we can see the simple structure and API invocations of the Fighting Animals system.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//5fb4241e-d5b9-4b6c-b0ce-d6984eea27c8/markdown_1/imgs/img_in_image_box_142_235_864_477.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A18Z%2F-1%2F%2F03878de9640af74bf6eca7c8be3315010a03a0f7525fcce288644bad5ce7d34a" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 8-3. Fighting Animals microservices</div> </div>

The initial call results in further downstream calls to other microservices to fulfill the incoming request.

---

## A Word About Version Numbers

In all the Fighting Animals examples, we are using pinned versions of our dependencies and containers. This is to ensure the examples are reproducible and do not change over time. In a system that uses floating versions (like `latest`), the versions will change over time. This can make it very difficult to understand what has changed and why—and this problem only gets worse as the system gets more complex. We do use `latest` for our own application containers, but that's because they are under our control and we can ensure that they are always up to date.

---

## Summary

In this chapter, you have learned about how cloud platforms and components challenge our traditional model of optimization and performance.

MicroProfile is an excellent standard for building applications that are both cloud native and microservice-based architecture ready. Beyond considering Java standards in isolation, CNCF provides a guide for platform considerations and projects that should be considered for a cloud native architectural approach.

Virtualization is an important aspect of the cloud native stack and the principal building block for compute. Although there are low-level details in virtualization, the bigger benefits are gained from looking at the right VM configuration for the task. It is possible to mix bare metal and virtualization in a clustered deployment.

Images and containers are the standard unit of deployment in a cloud native environment. There are different approaches to creating and layering images for Java and some common gotchas that need to be considered. Networking is an important aspect of the cloud native stack, and with that, the concerns of service discovery and traffic routing. We introduced the Fighting Animals project, which we will use throughout the upcoming chapters to describe more complexities in the cloud stack.

In the next chapter, we will look at running cloud native Java processes in more detail. We will start by looking at running containers locally and then how to schedule and deploy on cloud native infrastructure.
