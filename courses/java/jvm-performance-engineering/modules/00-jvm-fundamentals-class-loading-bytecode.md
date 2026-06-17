# Module 00: JVM Fundamentals — Class Loading, Bytecode, Sizing, and Tooling

Welcome, students. In this foundational module, we establish the baseline concepts of the Java Virtual Machine (JVM). 

Before we study advanced topics like garbage collection barrier mechanics, tiered JIT compiler assembly generation, or lock contention, we must master the execution lifecycle of Java applications. We will trace how Java source code becomes native hardware instructions, explore the inner workings of the **Class Loading Subsystem**, contrast **Stack vs. Heap** allocations, analyze essential JVM memory sizing flags, and master the standard JDK command-line diagnostics tools.

---

## 1. Academic Lecture: The JVM Execution Lifecycle

The JVM is a virtualization engine. Unlike languages like C or C++ which compile directly to native machine code for a specific CPU architecture (x86_64, ARM), Java code compiles to an intermediate representation called **Bytecode**.

### The JDK vs. JRE vs. JVM
*   **JDK (Java Development Kit)**: The complete developer toolkit. It contains the compiler (`javac`), packaging tools (`jar`), and diagnostic tools (`jdb`, `jcmd`, `jstat`, `jmap`).
*   **JRE (Java Runtime Environment)**: The runtime bundle containing the JVM and core libraries. (Note: Deprecated as a separate standalone download since Java 9, replaced by modular runtimes generated via `jlink`).
*   **JVM (Java Virtual Machine)**: The execution engine itself, which reads bytecode and runs it on host operating systems.

```
+-------------------------------------------------------------+
|                     JDK (Development Kit)                   |
|  [ javac ]  [ jlink ]  [ jcmd ]  [ jstat ]  [ jmap ]        |
|  +-------------------------------------------------------+  |
|  |                 JRE (Runtime Environment)             |  |
|  |  [ Core Runtime Classes (java.base, etc.) ]           |  |
|  |  +-------------------------------------------------+  |  |
|  |  |                 JVM (Virtual Machine)           |  |  |
|  |  |  [ ClassLoader ]  [ JIT Compiler ]  [ GC ]      |  |  |
|  |  +-------------------------------------------------+  |  |
|  +-------------------------------------------------------+  |
+-------------------------------------------------------------+
```

### The Compilation and Execution Flow
1.  **Source Code Compilation**: The developer writes `.java` source code. The `javac` compiler translates it into `.class` files containing JVM bytecode.
2.  **Class Loading**: When the application runs, the JVM loads the `.class` files into memory (Metaspace).
3.  **Bytecode Execution**: The JVM execution engine reads bytecode instructions. It initially executes them using an **Interpreter** (which translates bytecode line-by-line to machine code). When specific paths become hot, the **JIT (Just-in-Time) Compiler** translates them directly to native assembly.

```
[ Code.java ] ---> ( javac ) ---> [ Code.class ] 
                                        |
                                        v
                               ( Class Loader ) 
                                        |
                                        v
                              [ Execution Engine ]
                              /                  \
                             v                    v
                     [ Interpreter ] <---> [ JIT Compiler ]
                            \                      /
                             v                    v
                        [ Native Machine Instructions ]
```

---

## 2. Anatomy of a Class File and Bytecode Basics

A `.class` file is a structured binary stream starting with the magic number `0xCAFEBABE`. It contains:
*   **Magic Number & Version**: Identifies the file format and target JDK version compatibility.
*   **Constant Pool**: An index table of literals, class names, method signatures, and field descriptors referenced in the class.
*   **Fields and Methods**: Descriptions of fields and methods, including local variable tables and the actual bytecode instructions.

### Inspecting Bytecode using `javap`
To view the bytecode representation of a class, use the JDK disassembler:
```bash
javap -c -v com.example.MyClass
```

Let's look at a simple bytecode segment for a method adding two integers:
```
public int add(int a, int b);
  Code:
   0: iload_1         // Load parameter 'a' (local variable index 1) onto the operand stack
   1: iload_2         // Load parameter 'b' (local variable index 2) onto the operand stack
   2: iadd            // Pop both integers, add them, and push the result back onto the stack
   3: ireturn         // Return the integer at the top of the stack
```
The JVM is a **stack-based execution engine**. Unlike register-based processors, all calculations are performed by pushing and popping values on an **Operand Stack**.

---

## 3. The Class Loading Subsystem

The ClassLoader is responsible for loading `.class` binary streams, resolving structures, and allocating memory. The class loading process is divided into three distinct phases: **Loading**, **Linking**, and **Initialization**.

```
+---------------------------------------------------------------------------------+
|                            Class Loading Subsystem                              |
|                                                                                 |
|  +----------------+      +---------------------------------------------------+  |
|  |   1. Loading   | ---> |                     2. Linking                    |  |
|  |  (Read bytes,  |      |  +----------------+ +----------------+ +--------+ |  |
|  |  define Class) |      |  |  Verification  | |  Preparation   | |Resolve | |  |
|  +----------------+      |  | (Format check) | |(Static fields) | |(Links) | |  |
|                          |  +----------------+ +----------------+ +--------+ |  |
|                          +---------------------------------------------------+  |
|                                                                    |            |
|                                                                    v            |
|                                                          +-------------------+  |
|                                                          | 3. Initialization  |  |
|                                                          | (Run <clinit> ops)|  |
|                                                          +-------------------+  |
+---------------------------------------------------------------------------------+
```

### The Three Phases
1.  **Loading**: The JVM locates the binary stream of the class (on local disk, jar, network) and creates a `java.lang.Class` object in the Metaspace.
2.  **Linking**:
    *   *Verification*: Ensures the bytecode is safe, does not violate access rules, and conforms to JVM specifications.
    *   *Preparation*: Allocates memory for static fields and initializes them to their default primitive values (e.g., `0`, `null`, `false`).
    *   *Resolution*: Resolves symbolic references in the constant pool into direct memory references.
3.  **Initialization**: Executes static initializer blocks (`static { ... }`) and assigns static fields their defined initial values.

### The ClassLoader Hierarchy
Class loading follows the **Parent Delegation Model**. When a ClassLoader is requested to load a class, it delegates the request to its parent before attempting to locate it itself.

```
       [ Bootstrap ClassLoader ]          (Loads rt.jar, java.base core API)
                 ^
                 |
        [ Platform ClassLoader ]          (Loads extension/modular modules)
                 ^
                 |
       [ Application ClassLoader ]        (Loads classpath/modulepath app jars)
                 ^
                 |
          [ Custom ClassLoader ]          (Loads custom paths, encrypted classes)
```

1.  **Bootstrap ClassLoader**: Written in native C/C++. Loads core JDK library classes (e.g., `java.lang.Object`, `java.util.List`).
2.  **Platform ClassLoader** (formerly Extension ClassLoader): Loads non-core platform APIs and security extensions.
3.  **Application ClassLoader** (or System ClassLoader): Loads standard classes defined in your application classpath or modulepath.
4.  **Custom ClassLoaders**: Programmatically written loaders for custom behaviors (dynamic hot reloading, encrypted bytecode).

#### Parent Delegation Rule:
A class loader will query its parent first. If the parent cannot find the class, the child's `findClass` method is invoked. This prevents class conflicts—for example, it prevents an application from loading a malicious version of `java.lang.String`.

---

## 4. Stack vs. Heap Memory Allocation

Every Java developer must understand where data resides at runtime. The JVM splits memory allocations into two primary segments: **Thread Stacks** and the **Java Heap**.

```
+-----------------------------------+   +------------------------------------+
|           Thread Stack            |   |             Java Heap              |
|                                   |   |                                    |
|  [ Stack Frame: main() ]          |   |  [ Object A (Point) ]              |
|  - int x = 10                     |   |  - int x = 15                      |
|  - Point ref = ----------------------->  - int y = 20                      |
|                                   |   |                                    |
|  [ Stack Frame: process() ]       |   |  [ Object B (String) ]             |
|  - double score = 95.5            |   |  - byte[] value = [...]            |
+-----------------------------------+   +------------------------------------+
```

### Thread Stack
*   **Scope**: Local to each thread (thread-confined). Deleted when the thread exits.
*   **Contents**: **Stack Frames**. A new frame is pushed onto the stack every time a method is called, and popped off when the method returns.
*   **Data Types**: Primitive variables (`int`, `double`, `boolean`) and reference addresses (pointers) pointing to objects on the Heap.
*   **Access Speed**: Extremely fast (L1/L2 cache-friendly, simple stack pointer increments).

### Java Heap
*   **Scope**: Shared across all application threads.
*   **Contents**: Object instances (e.g., instances of custom classes, arrays) and their corresponding instance fields.
*   **Data Types**: All objects.
*   **Access Speed**: Slower than stack (requires dereferencing pointers, subject to CPU cache misses, managed by GC sweeps).

### Memory Allocation Step-by-Step Walkthrough
Let's analyze this code block:
```java
public class MemoryTrace {
    public static void main(String[] args) {
        int val = 10;
        Point p = new Point(5, 5);
    }
}
```

1.  The JVM launches a thread to execute `main`. A **Stack Frame** for `main()` is pushed onto the thread stack.
2.  The primitive integer `val` is allocated inside the `main()` stack frame as a local variable with value `10`.
3.  The JVM processes `new Point(5, 5)`:
    *   It allocates memory for a `Point` object on the **Heap**.
    *   The object initialization is executed. Its instance variables (`x` and `y`) are written inside the object's Heap space.
4.  The local reference variable `p` is allocated inside the `main()` stack frame. Its value is set to the **heap memory address** of the newly created `Point` object.

---

## 5. Essential JVM Memory Sizing Flags

When deploying a production Java application, you must configure the JVM memory boundaries manually. Failing to do so will cause the JVM to use dynamic defaults that may not match your host container resources.

| Flag | Meaning | Recommended Usage |
| :--- | :--- | :--- |
| `-Xms<size>` | **Initial Heap Size**. The starting memory allocated to the Heap on boot. | Set equal to `-Xmx` to prevent runtime Heap expansion delays. |
| `-Xmx<size>` | **Maximum Heap Size**. The upper boundary of Heap memory. | Typically set to 60-80% of container RAM, leaving buffer for off-heap allocations. |
| `-Xss<size>` | **Thread Stack Size**. The memory allocated to each individual thread stack. | Defaults to `1m` (1MB). Reduce to `256k` or `512k` if running thousands of platform threads. |
| `-XX:MetaspaceSize` | **Initial Metaspace Size**. Triggers a GC cleanup cycle once hit. | Set high (e.g., `128m` or `256m`) to prevent early boot-up garbage collections. |
| `-XX:MaxMetaspaceSize` | **Maximum Metaspace Size**. The absolute limit of class metadata space. | Bound this flag in containers to prevent Java processes from consuming host RAM. |

Example command to boot a production service with 2GB Heap and bounded stack sizes:
```bash
java -Xms2g -Xmx2g -Xss256k -XX:MetaspaceSize=256m -XX:MaxMetaspaceSize=512m -jar app.jar
```

---

## 6. Understanding JVM Errors: OutOfMemory and StackOverflow

If your code violates memory boundaries, the JVM halts execution with a runtime error.

### 1. `java.lang.OutOfMemoryError: Java heap space`
*   **Cause**: The application has allocated too many objects on the Heap, and the Garbage Collector cannot reclaim any more space (objects are still reachable from GC Roots).
*   **Symptom**: Memory leak (e.g., adding to a static Map without cleanups) or insufficient heap allocation configurations.

### 2. `java.lang.OutOfMemoryError: Metaspace`
*   **Cause**: The Metaspace has run out of memory. This space holds loaded class definitions, static constants, and JIT method compilation metadata.
*   **Symptom**: Dynamic class generation tools (like reflection frameworks or bytecode manipulators) loading infinite unique classes.

### 3. `java.lang.OutOfMemoryError: GC overhead limit exceeded`
*   **Cause**: The JVM has spent **more than 98%** of its CPU execution time running garbage collection sweeps while reclaiming **less than 2%** of the heap.
*   **Symptom**: The heap is completely full of live objects, and the GC is running continuously in a desperate attempt to free memory.

### 4. `java.lang.StackOverflowError`
*   **Cause**: A thread stack has run out of frame space.
*   **Symptom**: Unbounded recursive method calls or extremely deep call stacks that consume all frames allocated by the `-Xss` limit.

---

## 7. Command-line Diagnostic Utilities

The JDK includes several simple diagnostic command-line tools that performance engineers use to monitor running applications.

### 1. `jps` (Java Virtual Machine Process Status Tool)
Displays the Process ID (PID) of all running Java applications on the host.
```bash
jps -l
```

### 2. `jinfo` (Java Configuration Info)
Inspects or dynamically updates JVM flags for a running process.
```bash
# Print all flags
jinfo -flags <PID>

# Turn on Class GC Logging dynamically
jinfo -flag +UnlockDiagnosticVMOptions <PID>
```

### 3. `jstat` (JVM Statistics Monitoring Tool)
Displays performance statistics such as GC generations capacity, collection count, and cumulative pause time.
```bash
# Monitor GC statistics every 1000ms
jstat -gcutil <PID> 1000
```

### 4. `jstack` (Java Thread Stack Trace Utility)
Generates a complete thread dump of all active threads, showing stack traces, locks, and state.
```bash
jstack -l <PID> > threaddump.txt
```

### 5. `jmap` (Java Memory Map)
Inspects heap statistics or writes a binary heap dump file.
```bash
# Print heap summary details
jmap -heap <PID>

# Trigger binary heap dump
jmap -dump:format=b,file=dump.hprof <PID>
```

### 6. `jcmd` (JVM Diagnostic Command Tool)
The modern, recommended multi-tool. It replaces many separate CLI utilities.
```bash
# Get system properties
jcmd <PID> VM.system_properties

# Perform Heap Dump
jcmd <PID> GC.heap_dump /tmp/dump.hprof

# Print JVM uptime details
jcmd <PID> VM.uptime
```

---

## 8. Theory vs. Production Trade-offs

### Parent-Delegation Bypass: Why Web Containers Break the Rules
In standard Java applications, the Parent-Delegation model ensures class loading stability. However, servlet containers (like Apache Tomcat, Jetty, or WildFly) explicitly bypass this rule for web applications.

*   **The Problem**: A single Tomcat instance might host two separate web applications. Application A uses `log4j v1.2`, and Application B uses `log4j v2.x`. If Tomcat used standard parent-delegation (delegating up to the System ClassLoader), the two applications would share the same version of log4j loaded globally, leading to runtime incompatibilities.
*   **The Workaround**: Web application class loaders utilize a **Child-First (or Servlet-First)** policy. They search the local webapp directory (`WEB-INF/lib/` and `WEB-INF/classes/`) *first* before delegating up to the parent container class loader.
*   **Trade-off**: This isolates applications but introduces class loading complexity. It can lead to hard-to-debug `ClassCastException` issues if the same class name is loaded by both the child and parent class loaders, as they are treated as completely distinct types by the JVM.

---

## 9. How to Use: Writing a Custom ClassLoader in Java 21

Let's write a complete, compile-grade Java 21 class that implements a custom ClassLoader. This custom loader loads class definitions dynamically from an in-memory byte array or raw file source, bypassing standard classpath restrictions.

First, let's write our custom loader:

```java
package com.capstone.jvm.fundamentals;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.logging.Logger;

/**
 * A Custom ClassLoader that loads compiled classes from a target folder path,
 * bypassing classpath settings.
 */
public class DirectoryClassLoader extends ClassLoader {
    private static final Logger LOGGER = Logger.getLogger(DirectoryClassLoader.class.getName());
    private final Path directoryPath;

    public DirectoryClassLoader(Path directoryPath) {
        // Delegate parent constructor to set System ClassLoader as parent
        super(ClassLoader.getSystemClassLoader());
        this.directoryPath = directoryPath;
    }

    @Override
    protected Class<?> findClass(String name) throws ClassNotFoundException {
        LOGGER.info("Attempting to custom load class: " + name);
        try {
            byte[] classBytes = loadClassData(name);
            if (classBytes == null) {
                throw new ClassNotFoundException("Could not read bytes for " + name);
            }
            // defineClass is an final method in ClassLoader that converts a byte array
            // containing class bytecode into a Class object.
            return defineClass(name, classBytes, 0, classBytes.length);
        } catch (Exception e) {
            throw new ClassNotFoundException("Failed to load class: " + name, e);
        }
    }

    private byte[] loadClassData(String className) throws Exception {
        // Convert class name package separator (e.g. "com.example.Target") to path format
        String fileName = className.replace('.', '/') + ".class";
        Path targetFile = directoryPath.resolve(fileName);

        if (!Files.exists(targetFile)) {
            LOGGER.warning("Target class file not found: " + targetFile.toAbsolutePath());
            return null;
        }

        return Files.readAllBytes(targetFile);
    }
}
```

Now, let's write a driver class demonstrating this custom class loading lifecycle:

```java
package com.capstone.jvm.fundamentals;

import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.logging.Logger;

public class ClassLoaderDemo {
    private static final Logger LOGGER = Logger.getLogger(ClassLoaderDemo.class.getName());

    public static void main(String[] args) {
        LOGGER.info("Starting Custom ClassLoader demo...");

        // Define our target custom directory path
        Path customBinDir = Paths.get("./custom_bin");

        // Instantiate our custom class loader
        DirectoryClassLoader customLoader = new DirectoryClassLoader(customBinDir);

        try {
            // Load a dummy class (Ensure the class file exists in custom_bin/com/example/MyClass.class)
            // Class<?> loadedClass = customLoader.loadClass("com.example.MyClass");
            // Object instance = loadedClass.getDeclaredConstructor().newInstance();
            
            LOGGER.info("Demo loader initialized. Parent ClassLoader: " + customLoader.getParent().getClass().getName());
        } catch (Exception e) {
            LOGGER.severe("Error occurred: " + e.getMessage());
        }
    }
}
```

---

## 10. Common Errors & Pitfalls

### Pitfall 1: `NoClassDefFoundError` vs. `ClassNotFoundException`
*   **`ClassNotFoundException`**: An **Exception** thrown explicitly at runtime when the application tries to load a class dynamically using methods like `Class.forName("com.example.Missing")`, but the class is not on the classpath.
*   **`NoClassDefFoundError`**: A **Linkage Error** thrown when the JIT/JVM compiler successfully compiled a class referencing another class, but during execution, the JVM cannot find the class definition because it was deleted from the classpath or failed to load.
*   **Root Cause of NoClassDefFoundError**: Often caused by static initializer block failures. If a class `MyClass` fails during `<clinit>` (e.g. throws a static `NullPointerException`), the JVM marks `MyClass` as failed. Any subsequent attempts to access `MyClass` will throw `NoClassDefFoundError: Could not initialize class MyClass`.

### Pitfall 2: Memory leaks via ClassLoader references
When class loaders are garbage collected, all classes loaded by them are also eligible for collection. If a reference to a ClassLoader, a Class instance, or an object of that class is leaked (e.g., inside a thread pool static thread context), the entire ClassLoader can never be garbage collected. This leads to Metaspace leaks that eventually cause `OutOfMemoryError: Metaspace`.

---

## 11. Socratic Review Questions

### Question 1
If class `A` is loaded by the Bootstrap ClassLoader, and class `B` is loaded by the Application ClassLoader, can code inside class `A` instantiate class `B`? Why or why not?

#### Answer
No, code inside class `A` cannot instantiate class `B` directly. 
Class loaders operate within a visibility boundary. A ClassLoader can see classes loaded by its parents or by itself, but it cannot see classes loaded by its children. 
Because the Bootstrap ClassLoader sits at the top of the hierarchy, it has no visibility into the Application ClassLoader (which is a descendant). If class `A` references class `B` in its source code, the JVM will fail to resolve the link, throwing `NoClassDefFoundError` or `ClassNotFoundException`.

### Question 2
When compiling a Java program, what happens to local primitive variables (e.g., `int x = 5`) inside methods? Are they registered inside the `.class` file Constant Pool?

#### Answer
No. The Constant Pool of a `.class` file stores symbolic descriptions and shared literals (such as String constants, class names, method names, and constant values like final static fields). 
Local variables inside methods are not registered inside the Constant Pool. Instead, they are represented in the bytecode method structure as instructions writing to index numbers in the **Local Variable Table** (e.g., `istore_1` to store an integer at index 1 of the local method frame). The raw primitive values are processed dynamically on the thread operand stack during execution.

---

## 12. Hands-on Challenge: Dynamic Class Loader and Decryptor

### The Challenge
In many enterprise application architectures (such as plugin engines or license-key checkers), compiled bytecode is encrypted and stored in databases or remote servers. 

Your task is to complete a custom ClassLoader called `EncryptedClassLoader`. It must load classes from a directory, read the encrypted byte stream, perform a decryption pass, and register the class.

For simplicity, we use a simple **XOR Cipher** for decryption. The encryption key is a single byte (e.g. `0x5F`). To decrypt the class bytes, you must perform a bitwise XOR (`^`) operation on each byte of the encrypted byte array.

Complete the decryption and definition logic inside the class below:

```java
package com.capstone.jvm.fundamentals.challenge;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.logging.Logger;

public class EncryptedClassLoader extends ClassLoader {
    private static final Logger LOGGER = Logger.getLogger(EncryptedClassLoader.class.getName());
    private final Path classPathFolder;
    private final byte xorKey;

    /**
     * @param classPathFolder directory containing encrypted .class files (suffixed with .enc)
     * @param xorKey the decryption key byte
     */
    public EncryptedClassLoader(Path classPathFolder, byte xorKey) {
        super(ClassLoader.getSystemClassLoader());
        this.classPathFolder = classPathFolder;
        this.xorKey = xorKey;
    }

    @Override
    protected Class<?> findClass(String name) throws ClassNotFoundException {
        try {
            // 1. Resolve filename: replace package dots with path separators and append ".class.enc"
            String fileName = name.replace('.', '/') + ".class.enc";
            Path targetFile = classPathFolder.resolve(fileName);

            if (!Files.exists(targetFile)) {
                throw new ClassNotFoundException("Encrypted class file not found: " + targetFile.toAbsolutePath());
            }

            // 2. Read the encrypted bytes from the file
            byte[] encryptedBytes = Files.readAllBytes(targetFile);

            // 3. Decrypt the bytes using XOR key
            byte[] decryptedBytes = decrypt(encryptedBytes);

            // 4. Define the class using defineClass
            return defineClass(name, decryptedBytes, 0, decryptedBytes.length);
        } catch (IOException e) {
            throw new ClassNotFoundException("Error reading encrypted class bytes", e);
        }
    }

    /**
     * Decrypts the byte array using bitwise XOR with the configured key.
     * 
     * @param input encrypted byte array
     * @return decrypted byte array
     */
    public byte[] decrypt(byte[] input) {
        byte[] output = new byte[input.length];
        
        // TODO: Implement the decryption loop.
        // Loop through 'input', perform a bitwise XOR (input[i] ^ xorKey) and save to 'output[i]'.
        // Cast the result to byte.
        
        return output;
    }
}
```

Write your implementation and document the validation steps. Save your solution notes inside `modules/00-jvm-fundamentals-class-loading-bytecode.md`.
