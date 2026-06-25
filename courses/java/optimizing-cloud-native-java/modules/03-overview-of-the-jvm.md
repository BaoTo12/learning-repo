# Overview of the JVM

Java is one of the largest technology platforms on the planet, with an estimated group of over 10 million developers.

The `JVM` is designed at a high level to hide low-level complexity from developers. Key tasks, such as **garbage collection** and **execution optimization**, are handled automatically by the `JVM` on behalf of the developer. Because Java aims at common developers, most programmers do not need to understand the platform's inner workings during daily work. They usually only meet these details when fixing a performance problem.

However, if you care about performance, understanding the `JVM` technology stack is necessary. It helps you write highly optimized software and gives the theoretical basis needed to find performance bottlenecks.

This chapter explains how the `JVM` executes Java, building a basis for later topics. Specifically, Chapter 6 gives an in-depth look at bytecode, which completes the material covered here. We recommend reading this chapter first, and then checking it a second time after you complete Chapter 6.

---

## Interpreting and Classloading

### Stack-Based Execution

The official Java Virtual Machine Specification — the VM Spec — describes the `JVM` as a **stack-based interpreted machine**. Unlike physical CPUs that use registers to store values, the `JVM` uses an **evaluation stack** — or execution stack — to store middle and part results, doing operations on the top values of the stack.

> **Mental Model: Switch inside a While Loop**
> If you are new to interpreters, think of the `JVM` interpreter's core execution loop as a `switch` statement placed inside a `while` loop. The interpreter processes each bytecode instruction — **opcode** — order, using the stack to hold math values.

While commercial engines like `HotSpot` are far more complex, this "switch-inside-while" stack interpreter acts as an excellent basic mental model.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//ddd38485-3a4f-4c88-a819-d5a0cb53161f/markdown_3/imgs/img_in_image_box_176_301_253_403.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A12Z%2F-1%2F%2Fb87bfe5459ceba60272d70029eb8a4c5e6c2bd3f3234c752b3626efc16827714" alt="Image" width="7%" /></div>

---

### Launching and Classloading

When you start an application with the command `java HelloWorld`:

1. The operating system starts the `java` compiled process.
2. This process starts the virtual runtime environment and starts the interpreter.
3. The interpreter seeks the application entry point: the `main()` method in `HelloWorld.class`.
4. Before running can begin, the `JVM` must load the class file using the **class loading** system.

Java uses a ranked chain of class loaders to load classes during startup:

- **Bootstrap Class Loader**: Formerly known as the "Primordial Class Loader," this loader is responsible for loading core Java runtime classes. Its main goal is to load a smallest, necessary set of boot classes — such as `java.lang.Object`, `java.lang.Class`, and `java.lang.ClassLoader` — so that later class loaders can start.
- **Platform Class Loader**: In Java 9+, this loader manages the rest of the base system classes — historically found in `rt.jar` —. It has the Bootstrap class loader as its parent. The legacy Extension class loader has been removed.
- **Application Class Loader**: Responsible for loading user classes from the set classpath. Although some texts call this the "System" class loader, that term is misleading because it does not load system classes. It has the Platform class loader as its parent.

#### Class Delegation and Resolution

- **Lazy Loading**: Java loads classes dynamically when they are first met during program running.
- **Delegation**: If a class loader cannot find a class, it hands the search upward to its parent. If the search reaches the Bootstrap class loader and still fails, the system throws a `ClassNotFoundException`.
- **Classpath Alignment**: Developers must guarantee that their compilation classpath exactly matches the production classpath to avoid runtime loading issues.
- **Single Loading Rule**: Usually, a class is loaded only once, creating a single `Class` object. However, if different class loaders load the same class, multiple separate class objects will exist. A class's being in the runtime is decided by both its **fully qualified class name** and the **specific class loader** that loaded it.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//b1c7788f-543d-42e3-8c24-0925d4f4746b/markdown_0/imgs/img_in_image_box_176_616_253_716.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A02Z%2F-1%2F%2Ff2761495fae28e3bbb77ceb232ba38723da44079e4ba1218136908b7affc4486" alt="Image" width="7%" /></div>

> **Insight: Multiple Class Loading in Application Servers**
> Application servers — such as Tomcat or JBoss EAP — use this behavior by using separate class loaders for different tenant applications. This allows tenants to run different versions of the same class libraries together.
> 
> Also, checking tools like Java agents dynamically reload and rewrite classes — bytecode weaving — to apply monitoring and observability.

---

### The Java Platform Module System (JPMS)

Introduced in Java 9, the **Java Platform Module System (JPMS)** deeply changed how Java applications start up:

- **Modular by Default**: All modern `JVM`s are modular; there is no "compatibility mode" that restores the monolithic Java 8 runtime.
- **Module Graph**: During startup, the `JVM` always builds a **module graph**—even for non-modular applications. This graph must be a **directed acyclic graph (DAG)**. If the module metadata contains any looped needs, startup fails instantly.
- **Startup Validation**: JPMS checks inter-module metadata at startup, guaranteeing that all required modules are there and that no clashing modules exist.
- **Efficiency**: The modular design guarantees that only the required modules are loaded, reducing startup time and memory sizes.
- **Main Module**: The entry point class lives in the main module. Non-modular applications will run their code in the `UNNAMED` module, using both the class-path and module-path.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//ddd38485-3a4f-4c88-a819-d5a0cb53161f/markdown_4/imgs/img_in_image_box_176_339_252_438.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A15Z%2F-1%2F%2F2065d2dac890d598c10a1f75633af1e443abe33af093a1e296fff1fa3b2142f4" alt="Image" width="7%" /></div>

> **Resource Note**: For a complete guide to JPMS, refer to *Java in a Nutshell* — 8th Edition — by Benjamin J. Evans, Jason Clark, and David Flanagan, or *Java 9 Modularity* by Sander Mak and Paul Bakker.

In modern Java, the Bootstrap loader only manages `java.base` and core modules — including java.security.sasl and java.datatransfer —, while the rest are handed to the Platform loader. Because class loaders are treated as objects, starting must skip normal checking to avoid looping issues. So, anything loaded by the Bootstrap loader gets full security rights, which is why the boot path is kept highly limited.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//ddd38485-3a4f-4c88-a819-d5a0cb53161f/markdown_4/imgs/img_in_image_box_176_792_252_892.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A15Z%2F-1%2F%2F755bca218bff0e6d7acd2a0c12577f9757a3a4ee9a88dcb839cb2841ab902f26" alt="Image" width="7%" /></div>

Legacy versions of Java up to and including 8 used a single runtime, and the Bootstrap class loader loaded the contents of `rt.jar`.

---

## Executing Bytecode

Java source code goes through a chain of changes before it is run:

1. **Compilation**: The Java compiler — javac — turns source code — .java — into middle class files — .class — containing bytecode.
2. **Simple Translation**: The compiler does a simple translation with least tuning, leaving the resulting bytecode highly readable and shaped closely to the original Java source — Figure 3-1 —.
3. **Runtime Execution**: The real power of the Java platform comes from how the `JVM` actively runs and tunes this bytecode at runtime.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//b1c7788f-543d-42e3-8c24-0925d4f4746b/markdown_1/imgs/img_in_image_box_142_198_864_525.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A03Z%2F-1%2F%2Ff89e32219fcd21f6e897ad8f9626489706af8fdbcbd61389d27e6435b0d95151" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 3-1. Java class file compilation</div> </div>

### Portability and Language Abstraction

Bytecode is an middle form that is free of any specific real hardware design.

- **Portability**: This separation allows compiled Java programs to run unchanged on any device or operating system that runs a matching `JVM`.
- **Language Independence**: The `JVM` executes bytecode, not Java itself. Any language that compiles to valid bytecode (such as Kotlin using `kotlinc`, Scala, or Groovy) can run on the `JVM`.

---

### Anatomy of a Class File

The structure of a compiled `.class` file is tightly defined by the VM Specification — Table 3-1 —:

| Component | Description |
| :--- | :--- |
| **Magic Number** | The special file signature: `0xCAFEBABE`. |
| **Version Number** | The major and minor version numbers used to compile the class. |
| **Constant Pool** | A table storing all constants, including class, interface, and method names. |
| **Access Flags** | Modifiers defining if the class is public, final, abstract, static, etc. |
| **This Class** | Index linking to the name of the current class in the constant pool. |
| **Superclass** | Index pointing to the name of the superclass. |
| **Interfaces** | List of indexes pointing to implemented interfaces. |
| **Fields** | Names and access flags for all fields in the class. |
| **Methods** | Signatures, access modifiers, and the bytecode — held in the `Code` attribute —. |
| **Attributes** | Extra metadata — such as the name of the source file or debug data —. |

#### 1. File Magic and Compatibility

Every class file must begin with the base-16 signature `0xCAFEBABE`. The next 4 bytes show the major and minor compiler versions.

- **Version Checks**: The class loader checks that the class file version does not pass the version allowed by the current `JVM`. If it does, a runtime `UnsupportedClassVersionError` is thrown.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//b1c7788f-543d-42e3-8c24-0925d4f4746b/markdown_2/imgs/img_in_image_box_176_554_253_655.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A04Z%2F-1%2F%2F9bcac0b50231d9f16949bb98ec7820a3a83169eb4e1c97c06d1416aa9ee8962d" alt="Image" width="7%" /></div>

> **Trivia Note**: Magic numbers help Unix-like operating systems find file types — unlike Windows, which depends on file extensions —. While the signature `0xCAFEBABE` is striking, it stays a lasting, strange part of the platform.

#### 2. The Constant Pool

The **constant pool** works as a main lookup table. Rather than hardcoding memory addresses or names directly into bytecode, instructions use indexes in the constant pool, making the bytecode highly small.

#### 3. Access Flags & Signatures

Access flags store flags showing if a class is public, final, abstract, an interface, an artificial class — compiler-generated —, an annotation, or an enum. Fields and methods are defined with similar signature blocks, and the `Code` attribute of a method holds the actual runnable bytecode.

> **Mnemonic for Class File Structure**:
> **M**y **V**ery **C**ute **A**nimal **T**urns **S**avage **I**n **F**ull **M**oon **A**reas
> **M**agic, **V**ersion, **C**onstant Pool, **A**ccess Flags, **T**his Class, **S**uperclass, **I**nterfaces, **F**ields, **M**ethods, **A**ttributes.

---

### Analyzing Bytecode with `javap`

Consider the following simple Java program:

```java
public class HelloWorld {
    public static void main(String[] args) {
        for (int i = 0; i < 10; i++) {
            System.out.println("Hello World");
        }
    }
}
```

We can unpack this class using the JDK's internal disassembler tool: `javap -c HelloWorld`. This gives the following bytecode:

```text
public class HelloWorld {
    public HelloWorld();
    Code:
        0: aload_0
        1: invokespecial #1 // Method java/lang/Object."<init>":()V
        4: return

    public static void main(java.lang.String[]);
    Code:
        0: iconst_0
        1: istore_1
        2: iload_1
        3: bipush 10
        5: if_icmpge 22
        8: getstatic #2 // Field java/lang/System.out:Ljava/io/PrintStream;
        11: ldc #3 // String Hello World
        13: invogetvirtual #4 // Method java/io/PrintStream.println:(Ljava/lang/String;)V
        16: iinc 1, 1
        19: goto 2
        22: return
}
```

#### Bytecode Analysis

- **Default Constructor**: Even though we did not define a constructor in the source code, `javac` automatically put the default constructor `public HelloWorld()`. It loads `this` using `aload_0` and calls the parent class constructor — Object::"<init>" — via `invokespecial`.
- **Loop Initialization**: In the `main` method, `iconst_0` pushes the integer 0 onto the stack, and `istore_1` stores it in the nearby variable at index 1 — which represents i —.
- **Loop Comparison**: On each round, `iload_1` loads the loop counter, and `bipush 10` pushes the end — 10 — onto the stack. The instruction `if_icmpge 22` — "if integer compare greater than or equal" — compares them, jumping to the end — offset 22 — once `i >= 10`.
- **Method Invocation**: If the comparison misses, `getstatic` gets the static link `System.out`, `ldc` loads the string "Hello World" from the constant pool, and `invokevirtual` calls the `println` method.
- **Increment & Loop**: Finally, `iinc` increases the loop variable `i` directly by 1, and `goto 2` jumps back to the comparison step.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//b1c7788f-543d-42e3-8c24-0925d4f4746b/markdown_4/imgs/img_in_image_box_177_482_252_582.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A06Z%2F-1%2F%2F264c2e748ebb9ec0c5c4362bf4da01fc5f4bb3fd19b9b9607cca26a6795ad3b8" alt="Image" width="7%" /></div>

> **Key Insight**: `JVM` opcodes are highly small, showing the target type, the operation, and the contact between local variables, the constant pool, and the execution stack.

---

## Introducing HotSpot

In April 1999, Sun Microsystems released **HotSpot**, bringing a huge lift to the Java world. The HotSpot virtual machine compiles and tunes code at runtime, reaching execution speeds similar to—and sometimes passing—normally compiled languages like C and C++ — Figure 3-3 —.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//c29e27d1-4f7e-4578-b240-0fede020da23/markdown_0/imgs/img_in_image_box_141_195_863_523.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A10%3A54Z%2F-1%2F%2F918c48dcc4bdce9242e376b04abe8eafa11f3027e56d97e9d5243f84c09d7df8" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 3-3. The HotSpot JVM</div> </div>

### The Design Trade-offs of Languages

Language designers face a basic choice between two ideas:

- **Zero-Cost Abstractions**: Languages like C++ try to stay as "close to the metal" as possible, giving developers low-level control.
- **Developer Productivity**: Languages like Java favor developer speed, abstraction, and ease of use over low-level control.

> "In general, C++ implementations obey the zero-overhead principle: What you don't use, you don't pay for. And further: What you do use, you couldn't hand code any better." $ ^{1} $
> — Bjarne Stroustrup

The zero-overhead model places a heavy mental load on developers, compelling them to manage memory and hardware interactions manually. It also requires compiling source code directly into platform-specific machine code at build time (known as ahead-of-time [AOT] compilation).

Java refuses this zero-overhead demand. Instead of compelling developers to write complex, low-level code, the HotSpot virtual machine actively watches the program's runtime behavior, naturally using smart tunings where they will give the greatest performance gains.

---

### Just-in-Time (JIT) Compilation

Java programs start running inside the bytecode interpreter. While the interpreter provides freedom, highest performance requires executing native machine instructions.

HotSpot solves this through **just-in-time — JIT — compilation**:

- **Runtime Analysis**: While the application runs in interpreted mode, HotSpot watches the running rate of methods and loops, collecting trace data.
- **Compilation Threshold**: Once a method or loop is run frequently enough to cross a specific limit, the JIT compiler translates it from bytecode into native machine code.
- **Native Execution**: Later calls to the method skip the interpreter fully, running directly on the physical CPU.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//c29e27d1-4f7e-4578-b240-0fede020da23/markdown_1/imgs/img_in_image_box_176_940_253_1040.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A10%3A54Z%2F-1%2F%2F5adcf3ffd742b53c581caa1a3cd7c05e7d45e5221e9f38543bf375f172e907e7" alt="Image" width="7%" /></div>

> **Insight: Dynamic Re-Optimization**
> Unlike fixed compilers, HotSpot's JIT compilers can actively re-compile and further tune code — re-JIT — if better optimization chances appear during runtime.

#### The Advantage of Profile-Guided Optimization (PGO)

Because JIT compilation occurs at runtime, it uses **profile-guided optimization — PGO —**:

- **Dynamic Inlining**: The compiler can inline hot method calls based on real-world runtime records.
- **Optimizing Virtual Calls**: HotSpot can tune away virtual method dispatch sending cost by watching the actual target types at runtime.
- **JVM Intrinsics**: At startup, HotSpot finds the exact CPU model it is running on. It can then replace standard bytecode orders with highly tuned, hardware-specific native instructions designed for that specific processor.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//c29e27d1-4f7e-4578-b240-0fede020da23/markdown_2/imgs/img_in_image_box_168_180_252_294.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A10%3A55Z%2F-1%2F%2F745f6244099868663c860f41ed87500daa1aef97d59123e90fa10afd25443865" alt="Image" width="8%" /></div>

> [!IMPORTANT]
> **Key Insight: Bytecode vs. Executed Native Code**
> Through the joining of compilation and active JIT tuning, the machine code actually running on the CPU looks totally different from the original Java source code. This is why simple mental models of Java running are often confusing when analyzing performance.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//c29e27d1-4f7e-4578-b240-0fede020da23/markdown_2/imgs/img_in_image_box_168_701_253_816.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A10%3A55Z%2F-1%2F%2F1d1092ee106c1a71959d7d48046200b178b57dd70a45358901e8a0a804a168a2" alt="Image" width="8%" /></div>

> **Terminology Note**: Using hardware-specific processor traits is known as **JVM intrinsics**. This is entirely separate from the *intrinsic locks* used by the `synchronized` keyword.

*Note: A full discussion of profile-guided optimization and JIT compiler mechanics can be found in Chapter 6.*

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//c29e27d1-4f7e-4578-b240-0fede020da23/markdown_2/imgs/img_in_image_box_176_1033_252_1133.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A10%3A55Z%2F-1%2F%2Ff9255b1255cc8ab65b9e744eb572e65a40c79c18e0f3cab1d13f06f0a5c3a7fa" alt="Image" width="7%" /></div>

> **Reminder**: Benchmarking small code pieces is highly focused and famously difficult. Developers should focus on top-down, application-wide performance instead.

---

### JVM Memory Management

In languages like C, C++, and Objective-C, developers must manually manage memory allocation and freeing.

- **The Benefit**: This provides predictable performance and ties resource spans directly to object lives.
- **The Drawback**: It brings a huge mental load on developers. Decades of industry experience show that manual memory watching is a common source of bugs, memory leaks, and crashes, wasting developer time on low-level accuracy rather than business value. Modern C++ and Objective-C ease this somewhat using smart pointers.

Java settled this by bringing automatic heap memory management through **garbage collection (GC)**.

- **The Process**: Garbage collection is an unpredictable process that automatically finds and takes memory that is no longer referenced when the `JVM` needs space for new allocations.
- **The Cost**: Historically, garbage collectors had to **stop the world (STW)**, stopping the application threads while taking memory. While these pauses are usually very short, they can grow under high workload pressure.
- **Modern Advances**: As of 2024, the `JVM`'s garbage collection is highly developed. Modern collectors do most of their work together alongside application threads, greatly reducing the frequency and length of STW pauses.
- **Correctness and Performance**: Giving memory management to the `JVM` improves application firmness and correctness, though GC tuning stays a vital part of system performance.

*Note: Garbage collection is a major performance topic; we cover its details in Chapters 4 and 5.*

---

### Threading and the Java Memory Model

Since its start, Java has provided built-in support for multithreaded programming.

```java
Thread t = new Thread(() -> {
    System.out.println("Hello World!");
});
t.start();
```

Because all production `JVM`s are multithreaded, every Java program is naturally multithreaded at runtime. While concurrency adds complexity for performance analysis, it allows Java applications to use all available CPU cores, giving massive performance benefits.

#### The Evolution of Java Threads

- **Green Threads (M:N)**: In the early days, Java application threads were shared onto a smaller group of operating system threads — for example, Solaris M:N or green threads —. This model had bad performance and added unnecessary complexity.
- **Platform Threads**: To resolve this, mainstream `JVM`s moved to a 1:1 mapping: each Java application thread maps to a special **platform thread** backed by a unique operating system thread.
- **Virtual Threads (Project Loom)**: Over the next 20 years, applications grew to require thousands of active connections, hitting a bottleneck because physical OS threads are resource-heavy. Java 21 introduced **virtual threads** — Project Loom —. Virtual threads are light execution contexts — similar to Go's goroutines — that allow applications to run millions of active threads efficiently, especially for network I/O tasks.

Platform threads remain the default, keeping the meaning of all existing Java applications. Developers must clearly choose to create virtual threads.

*Note: We cover virtual threads and concurrency in detail in Chapter 13.*

---

#### Memory Sharing and the Java Memory Model (JMM)

Java's concurrency model depends on three core rules:

1. All threads in a Java process share a single, common, garbage-collected **heap**.
2. Any object created by one thread can be reached by any other thread that holds a reference to it.
3. Objects are **mutable by default**. Field values can be changed at any time unless clearly marked as `final`.

Because threads share the same heap, the **Java Memory Model (JMM)** gives a strict set of rules defining how and when changes made to an object's fields by one thread become visible to other threads.

Without synchronization, thread scheduling by the operating system can cause threads to be kicked from CPU cores mid-operation, leaving objects in invalid or half-written states. To stop this, Java depends on **mutual exclusion locks (mutexes)**, though they can be complex to use correctly.

*Note: Concurrency, locks, and the JMM are covered extensively in Chapter 13.*

---

## Monitoring and Tooling for the JVM

The `JVM` is a highly mature platform that gives several powerful tools for tracing, monitoring, and observability:

- **Java Management Extensions (JMX)**: A general-purpose technology for monitoring and managing the `JVM` and its applications. It allows distant clients to ask values and call management methods — utilizing Remote Method Invocation — RMI — —.
- **Java Agents**: A powerful mechanism that uses the `java.lang.instrument` API to dynamically change method bytecode as classes are loaded.
- **JVM Tool Interface (JVMTI)**: A low-level native interface written in C or C++ that allows outside tools to monitor and control the internal state of the `JVM`.
- **Serviceability Agent (SA)**: A testing toolset that reads process memory and symbols from the outside, allowing debugging of live processes or crash dumps — core files — without running any code inside the chosen `JVM`.

---

#### 1. Java Agents and Bytecode Instrumentation

A **Java agent** allows you to put instrumentation logic — such as method timers or distributed tracing hooks — into an application without modifying its source code.

- **Installation**: Agents are wrapped as JAR files and loaded at startup using a specific command-line flag:
  ```bash
  -javaagent:<path-to-agent-jar>=<options>
  ```
- **Agent Entry Point**: The agent JAR's index file — META-INF/MANIFEST.MF — must include the `Premain-Class` attribute. This class must implement a `public static void premain(String agentArgs, Instrumentation inst)` method, which executes on the main thread before the application's `main()` method. The `premain` method must exit for the main application to start.
- **Class Transformation**: The agent records a bytecode transformer implementing `ClassFileTransformer` to catch and modify class byte arrays during loading. Because an agent is standard Java, it can start background threads to collect and export data to outside monitoring systems.

*Note: JMX and Java agents are covered in Chapter 11.*

---

#### 2. Native JVMTI Agents

When the Java-level instrumentation API is lacking, engineers use **JVMTI agents** written in native C/C++:

- **Installation**: Loaded via the command-line flags:
  ```bash
  -agentlib:<agent-lib-name>=<options>
  ```
  or
  ```bash
  -agentpath:<path-to-agent-path>=<options>
  ```
- **Trade-off**: Native agents are harder to write and debug. A programming error in a native agent can ruin process memory or crash the entire `JVM`. So, Java agents are favored unless low-level native access is absolutely necessary.

---

#### 3. VisualVM: Graphical Diagnostic Tooling

`VisualVM` is a complete desktop testing tool based on the NetBeans platform. It was historically packaged with Oracle JDK 6–8 and GraalVM 19–23.0, but is now kept as a separate download.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//cd5b113a-8cd0-4635-9a27-8583ef5a44b9/markdown_2/imgs/img_in_image_box_167_1039_253_1155.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A32Z%2F-1%2F%2Fac372f980606d213b497c522f60940e70c1190a735d3788373021b4075bcf80e" alt="Image" width="8%" /></div>

> **Compatibility Note**: `VisualVM` is a modern replacement for the outdated `jconsole` tool. To move, you can install a compatibility plug-in to run legacy `jconsole` plug-ins inside `VisualVM`.

#### Using VisualVM

- **Calibration**: When started, `VisualVM` measures the host machine. Ensure no other heavy workloads are running during this brief calibration stage.
- **Connection**: `VisualVM` connects to local JVMs automatically — using the JVM's attach mechanism —. For remote connections, the remote host must run a service daemon on port 1099, or the application server must support port-forwarded `JMX` and `RMI` traffic.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//cd5b113a-8cd0-4635-9a27-8583ef5a44b9/markdown_3/imgs/img_in_image_box_151_262_855_729.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A33Z%2F-1%2F%2F4fd3eff353d9236fef19a7bd875afb0e9a000b02d52a67f0835c8d2d0c9175df" alt="Image" width="69%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 3-4. VisualVM startup screen</div> </div>

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//cd5b113a-8cd0-4635-9a27-8583ef5a44b9/markdown_4/imgs/img_in_image_box_150_147_858_617.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A35Z%2F-1%2F%2F663de64df7014e72bba0cb014b0aa0da8cd48dbc10ab33fda8d9b51351a1f4c3" alt="Image" width="70%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 3-5. VisualVM default view</div> </div>

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//445ecdd2-f429-40a4-821c-6d9b843f7e3a/markdown_0/imgs/img_in_image_box_149_171_857_616.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A14Z%2F-1%2F%2F8374d0c0da7f3c1e2e0f79e1796d719b4581a696b3cfbfb273324b54b4186dd1" alt="Image" width="70%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 3-6. VisualVM Monitor screen</div> </div>

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//445ecdd2-f429-40a4-821c-6d9b843f7e3a/markdown_0/imgs/img_in_image_box_175_977_253_1078.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A15Z%2F-1%2F%2Fd0327aaa3e297c84739da96c7e5dcc74131bdfea8c9b83ebf58e4325ac45c4ee" alt="Image" width="7%" /></div>

By default, `VisualVM` provides four main tabs:

1. **Overview**: Displays an outline of the Java process, including startup flags, system properties, and the exact runtime version.
2. **Monitor**: Offers high-level data, including CPU load, heap use, class loading statistics, and active thread counts.
3. **Threads**: Maps all active application and VM threads on a timeline, showing their historical execution states and allowing the creation of thread dumps.
4. **Sampler and Profiler**: Provides lightweight sampling of CPU and memory usage (covered in Chapter 12).

*Note: The platform's plugin architecture allows you to add features easily, such as the JMX console or the popular garbage collection visualizer, `VisualGC`.*

---

## Java Implementations, Distributions, and Releases

> [!NOTE]
> The Java landscape changes frequently. This description is correct as of 2024. Over time, vendors may enter or exit the distribution market, and release cadences may shift.

Many developers are only aware of the Oracle JDK binary, but the modern Java ecosystem is made of multiple implementations and versions.

#### 1. Source Code Components

Every Java binary is built from two main source code stores:

- **Virtual Machine Source**: The engine that executes bytecode (predominantly `HotSpot`).
- **Class Library Source**: The core Java APIs (such as `java.lang`, `java.util`).

The **OpenJDK** project is the open-source, GPLv2+CE-licensed standard implementation of Java, led and supported primarily by Oracle.

> [!IMPORTANT]
> **OpenJDK is Source Code Only**
> The OpenJDK project does not distribute pre-built binaries. Instead, it provides the raw source code for both the HotSpot VM and class libraries. This source code makes the foundation of almost all modern Java distributions (including Oracle's private JDK). Other VMs, like Eclipse `OpenJ9` or `GraalVM`, can also be joined with OpenJDK class libraries to form a complete distribution.

---

#### 2. Choosing a Java Distribution

Since developers use pre-built binary distributions rather than raw source code, choosing the right seller is critical. Organizations judge vendors based on three main standards:

- **Licensing Cost**: Is the binary free to run in production?
- **Bug Support**: How are discovered bugs resolved?
- **Security Patches**: How quickly are security updates delivered?

- **Free Distributions**: Binaries built from OpenJDK source are free to use in production under the GPLv2+CE license. Examples include Eclipse Adoptium Temurin, Red Hat OpenJDK, Amazon Corretto, Microsoft OpenJDK, and BellSoft Liberica.
- **Resolving Bugs**: To fix a bug in OpenJDK, you can buy a commercial support agreement from a vendor, ask an OpenJDK author to file an issue, or write a patch and send it yourself.
- **Security Updates**: Fixes are committed to public OpenJDK repositories, and vendors build these fixes into their binary releases. To lessen trouble, most companies remain on **Long-Term Support (LTS)** versions.

---

#### 3. Major Java Distribution Vendors

- **Oracle JDK**: The most broadly known distribution. It is compiled from OpenJDK but relicensed under Oracle's proprietary terms with minor additions. Dual licensing is made possible because OpenJDK contributors sign an agreement allowing Oracle to use their code.
- **Eclipse Adoptium (Temurin)**: Formerly AdoptOpenJDK, this is a community-led project under the Eclipse group. Member companies (like Red Hat, Google, Microsoft, and Azul) provide build and test skill, compiling OpenJDK source into fully checked, free binaries across multiple platforms.
- **Red Hat**: A long-standing OpenJDK contributor (second only to Oracle). Red Hat makes, supports, and maintains OpenJDK builds for RHEL, Fedora, and Windows, and shares free container images.
- **Amazon Corretto**: Amazon's OpenJDK distribution, tuned for AWS cloud environments but also distributed for Windows, macOS, and Linux to guarantee developer consistency.
- **Microsoft Build of OpenJDK**: Microsoft's binaries, designed to provide a smooth setup experience on Azure cloud systems.
- **Azul Systems (Zulu)**: Offers free OpenJDK binaries (Zulu) with optional paid support, alongside a proprietary, high-performance VM called *Azul Platform Prime* (formerly Zing) featuring unique GC and JIT engines.
- **GraalVM**: Originally an Oracle Labs study project. GraalVM includes an OpenJDK runtime with a JIT compiler written in Java. Importantly, it supports **ahead-of-time (AOT) native compilation**, compiling Java directly into lightweight, independent native binaries.
- **Eclipse OpenJ9**: Originally IBM's proprietary J9 VM, open-sourced in 2017. It runs on the Eclipse OMR runtime and is matching with Java approval. It powers the zero-cost *IBM Semeru Runtimes*.
- **Android Runtime (ART)**: Android is sometimes thought of as being "based on Java." However, the picture is actually a little more complex. Android uses a cross compiler to convert class files to a different (.dex) file format. These .dex files are then run by the Android Runtime (ART), which is not a JVM. In fact, Google now suggests the Kotlin language over Java for developing Android apps. As this technology stack is so far from the other examples, we won't study Android any further in this book.

> **Performance Note: OpenJDK Consistency**
> All OpenJDK-derived distributions (Adoptium, Red Hat, Corretto, Microsoft, Zulu) are compiled from the same upstream source code and verified using the same TCK test suites. Therefore, **there are no systematic performance differences** between these distributions on an equal version and setup.
> 
> The only minor exception is that Oracle does not distribute the *Shenandoah* GC (developed by Red Hat and Amazon), choosing to push its own *ZGC* collector instead.

---

#### 4. The Java Release Cycle

Java features are developed in the open on GitHub. Pull requests are joined into the main OpenJDK branch, with larger features developed in project forks before joining.

- **Feature Releases (6-Month Cadence)**: Every six months (March and September), a new feature release is cut from the main branch. Features that are not ready must wait for the next train. Oracle only supports each feature release until the next one arrives.
- **Update/LTS Releases**: Major versions (8, 11, 17, 21, etc.) are marked as **Long-Term Support (LTS)** versions. When Oracle stops keeping a feature release, community members step in to maintain the LTS update streams (8u, 11u, 17u, 21u), delivering security patches and critical updates.
- **Industry Adoption**: The industry has mostly rejected upgrading JDKs every six months. Instead, groups remain on LTS versions, upgrading only from one LTS release to the next.

For detailed licensing and support analysis, check the *Java Is Still Free* document maintained by the Java Champions community.

---

## Summary

In this chapter, we explored the core anatomy of the `JVM`, including:

- Bytecode compilation and stack-based interpretation.
- Dynamic just-in-time (JIT) compilation and profile-guided optimization.
- Automatic memory management (garbage collection) and thread models.
- Diagnostic technologies (JMX, Java agents, JVMTI, SA) and the `VisualVM` tool.
- The OpenJDK ecosystem, binary distributions, and the six-month release cycle.

In Chapter 4, we begin our deep dive into garbage collection, starting with the fundamental concepts of mark-and-sweep and exploring how HotSpot implements GC.
