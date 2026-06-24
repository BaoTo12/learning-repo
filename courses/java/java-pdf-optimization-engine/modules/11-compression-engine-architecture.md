# Module 11: Compression Engine Architecture

---

## 1. Why This Module Exists

In the early stages of building a PDF optimizer, it is tempting to write a single, monolithic script that handles image extraction, metadata stripping, and stream compression in one large loop. While this works for simple scripts, it quickly falls apart in production.

As new compression techniques are added (such as JBIG2 image encoding, CJK font subsetting, or color space transformations), a monolithic codebase becomes impossible to maintain, test, or extend. It violates the **Single Responsibility Principle** and makes it extremely difficult to isolate bugs or write unit tests.

To build a production-grade library, we need a clean, modular architecture. We must separate:
1.  **Configuration**: What compression profile and settings should be used?
2.  **State Management**: What is the current state of the PDF during processing?
3.  **Optimization Strategies**: How is each individual optimization pass implemented?
4.  **Orchestration**: In what order do the passes execute, and how do they communicate?

This module teaches you how to design a pluggable, robust, and testable PDF compression engine in Java using industry-standard software design patterns.

---

## 2. Learning Objectives

By the end of this module, you will be able to:
*   **Apply** the Strategy, Pipeline, and Chain-of-Responsibility design patterns to document optimization.
*   **Design** thread-safe and immutable configuration models using Java `record` types.
*   **Implement** a modular execution pipeline that manages context and state across multiple independent passes.
*   **Use** Java's Service Provider Interface (`ServiceLoader` SPI) to allow runtime extensibility without code modifications.
*   **Build** dependency-injected components that are easily mockable and unit-testable.

---

## 3. Conceptual Foundations

### Strategy Pattern for Pluggable Compression Profiles
The **Strategy Pattern** defines a family of algorithms, encapsulates each one, and makes them interchangeable. In our engine:
*   The `CompressionProfile` from Module 6 defines the strategy configuration.
*   Each `OptimizationPass` represents an execution strategy. Different passes can run or bypass themselves based on the active configuration.

### Pipeline and Chain-of-Responsibility Patterns
An optimization engine runs passes sequentially. This is represented by the **Pipeline Pattern**. We feed a document into the pipeline, and it flows through a series of filters (passes).

To support control flow (such as short-circuiting the pipeline if a document is digitally signed or if a critical error occurs), we incorporate the **Chain-of-Responsibility Pattern**. Each pass inspects the document and decides whether to perform work, halt execution, or pass control to the next stage.

```
[ Input PDF ]
      │
      ▼
┌────────────────────────────────────────────────────────┐
│               PdfOptimizationPipeline                  │
│                                                        │
│  1. PreFlightPass   ──► (Abort if Encrypted/Signed?)   │
│         │                                              │
│         ▼                                              │
│  2. MetadataPass    ──► (Strips XMP / Info)            │
│         │                                              │
│         ▼                                              │
│  3. ImagePass       ──► (Resamples & Re-encodes JPEG)  │
│         │                                              │
│         ▼                                              │
│  4. StructuralPass  ──► (OpenPDF XRef Stream Compres)  │
└────────────────────────────────────────────────────────┘
      │
      ▼
[ Optimized PDF ]
```

### Open/Closed Principle
Our architecture conforms to the **Open/Closed Principle**: *software entities should be open for extension, but closed for modification*.
If a developer wants to add a new custom optimization pass (e.g., stripping vector graphics or flattening layers), they should not need to modify the core pipeline class. They should be able to implement an `OptimizationPass` interface and drop it into the classpath.

---

## 4. Technical Topics

### 4.1 The `OptimizationContext`
Optimization passes must share state (e.g., statistics, warnings, temp files, and access to the active document). A mutable context object carries this state through the pipeline.

```java
public class OptimizationContext {
    private final PDDocument document;
    private final EngineConfig config;
    private final Map<String, Long> metrics = new HashMap<>();
    private final List<String> warnings = new ArrayList<>();
    
    // Constructor, getters, and utility methods
}
```

### 4.2 Immutable Configuration with Java Records
Configuration should be read-only during pipeline execution to prevent side effects. Java `record` classes are perfect for this as they are shallowly immutable, clean, and thread-safe.

```java
public record EngineConfig(
    boolean stripMetadata,
    boolean stripAttachments,
    boolean optimizeImages,
    int jpegQuality,
    int maxImageDpi,
    boolean enableFullCompression
) {}
```

### 4.3 The Service Provider Interface (SPI)
Java's `ServiceLoader` is a facility for locating providers of a service at runtime. We define `OptimizationPass` as our service interface:
1.  Define the interface: `com.example.pdf.engine.OptimizationPass`.
2.  Implement the interface in multiple classes.
3.  Register the implementations by creating a provider configuration file in `META-INF/services/com.example.pdf.engine.OptimizationPass`.
4.  Load them dynamically using `ServiceLoader.load(OptimizationPass.class)`.

This decoupling allows developers to distribute custom optimization passes in separate JAR files that plug into the main engine transparently.

---

## 5. Internal Mechanisms

### Pipeline Execution Loop
The core engine loops through registered passes. To measure performance accurately, the orchestration engine wraps each pass execution with high-precision timing (`System.nanoTime()`) and records the file size differences if saving is required.

```
For each registered OptimizationPass:
  1. Check if pass is enabled in EngineConfig
  2. Record start time (System.nanoTime())
  3. Execute pass.apply(context)
  4. Record end time and calculate elapsed MS
  5. Add PassResult to the final report
  6. Check if context has requested abort/short-circuit
       └─ Yes: Break loop early
```

### Pass Order Constraints
The execution sequence of optimization passes is not arbitrary. Changing the order can break functionality or yield poorer compression:
1.  **Pre-Flight Passes**: Must run first to verify encryption, passwords, and digital signatures.
2.  **Structural Cleanup**: Removing attachments, metadata, and thumbnails should happen before heavy compression, as it simplifies the object graph.
3.  **Image and Font Processing**: Re-encoding images and subsetting fonts should happen next.
4.  **Final Compression**: Object stream serialization and XRef stream conversion (OpenPDF full compression) must happen *last*, as they pack the clean objects into stream bundles. If you run structural cleanup *after* pack compression, you will have to unpack the streams, edit, and repack them.

---

## 6. Trade-Off Analysis

### Pluggable SPI vs. Hardcoded Registration

| Metric | ServiceLoader (SPI) | Hardcoded Pipeline Array |
| :--- | :--- | :--- |
| **Coupling** | Loose (decoupled compile-time) | Tight (core depends on all passes) |
| **Extensibility** | High (drop JARs on classpath) | Low (must modify engine source) |
| **Ordering Control** | Harder (requires `@Order` metadata) | Simple (order defined in code array) |
| **Debuggability** | Complex (implicit discovery) | Straightforward (traceable code flow) |

### Stateful Context vs. Functional Pipeline
*   **Stateful Context**: Passes modify the document and record metrics inside a single shared `OptimizationContext` object.
    *   *Trade-off*: Fast, low-overhead, memory-efficient. However, thread-safety must be managed (cannot run the same context instance across multiple threads in parallel).
*   **Pure Functional**: Each pass returns a new copy of the document and a new context.
    *   *Trade-off*: High memory overhead. Creating copies of a 500 MB PDF object graph in memory for each pass causes severe GC thrashing. **A stateful context is required for PDF engines due to memory constraints.**

---

## 7. Hands-On Exercises

### A. Beginner: Define `OptimizationPass` and implement `NoOpPass`
Create the `OptimizationPass` interface. Implement a simple class `NoOpPass` that prints a message to standard output when run and returns a successful `PassResult`.

### B. Intermediate: Build a Static Pipeline
Write a class `StaticPipeline` that maintains an internal `List<OptimizationPass>`. Implement a method `addPass(OptimizationPass)` and `execute(OptimizationContext)` that executes the registered passes in order.

### C. Advanced: SPI Pass Discoverer
Write a utility that uses `ServiceLoader` to find all implementations of `OptimizationPass` on the classpath. Print their class names and sort them based on a custom priority method or annotation.

---

## 8. Mini Project: PdfOptimizationEngine

### Objective
Implement a production-ready, extensible `PdfOptimizationEngine`. The codebase consists of:
1.  `EngineConfig`: A configuration record.
2.  `OptimizationContext`: Tracks document state, metrics, and logs.
3.  `OptimizationPass`: The core interface.
4.  `PassResult`: The outcome of a pass execution.
5.  `PdfOptimizationPipeline`: The orchestrator that dynamically loads passes using SPI, sorts them, and executes them, producing an `OptimizationReport`.

### Java Implementation

Save the following classes in `src/main/java/com/example/pdf/engine/`:

#### 1. EngineConfig.java
```java
package com.example.pdf.engine;

public record EngineConfig(
        boolean stripMetadata,
        boolean stripAttachments,
        boolean optimizeImages,
        int jpegQuality,
        int maxImageDpi,
        boolean enableFullCompression
) {
    public static EngineConfig defaultSettings() {
        return new EngineConfig(true, true, true, 75, 150, true);
    }
}
```

#### 2. PassResult.java
```java
package com.example.pdf.engine;

public record PassResult(
        String passName,
        boolean success,
        long durationMs,
        String message,
        boolean modified
) {}
```

#### 3. OptimizationContext.java
```java
package com.example.pdf.engine;

import org.apache.pdfbox.pdmodel.PDDocument;
import java.util.*;

public class OptimizationContext {
    private final PDDocument document;
    private final EngineConfig config;
    private final Map<String, String> executionMetadata = new LinkedHashMap<>();
    private final List<String> warnings = new ArrayList<>();
    private boolean aborted = false;
    private String abortReason = "";

    public OptimizationContext(PDDocument document, EngineConfig config) {
        this.document = Objects.requireNonNull(document);
        this.config = Objects.requireNonNull(config);
    }

    public PDDocument getDocument() { return document; }
    public EngineConfig getConfig() { return config; }

    public void addMetadata(String key, String value) {
        executionMetadata.put(key, value);
    }

    public Map<String, String> getMetadata() {
        return Collections.unmodifiableMap(executionMetadata);
    }

    public void addWarning(String warning) {
        warnings.add(warning);
    }

    public List<String> getWarnings() {
        return Collections.unmodifiableList(warnings);
    }

    public boolean isAborted() { return aborted; }
    public String getAbortReason() { return abortReason; }

    public void abort(String reason) {
        this.aborted = true;
        this.abortReason = reason;
    }
}
```

#### 4. OptimizationPass.java
```java
package com.example.pdf.engine;

import java.io.IOException;

public interface OptimizationPass {
    /**
     * @return The unique identifier of the optimization pass.
     */
    String getName();

    /**
     * @return Lower values run first. Range: 0 (preflight) to 100 (packing).
     */
    int getPriority();

    /**
     * Executes the optimization strategy on the context.
     */
    PassResult apply(OptimizationContext context) throws IOException;
}
```

#### 5. PdfOptimizationPipeline.java
```java
package com.example.pdf.engine;

import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.io.MemoryUsageSetting;

import java.io.File;
import java.io.IOException;
import java.util.*;

public class PdfOptimizationPipeline {

    private final List<OptimizationPass> registeredPasses = new ArrayList<>();

    public PdfOptimizationPipeline() {
        // Empty constructor
    }

    public void registerPass(OptimizationPass pass) {
        registeredPasses.add(Objects.requireNonNull(pass));
    }

    /**
     * Discovers and registers passes on the classpath using ServiceLoader SPI.
     */
    public void discoverPasses() {
        ServiceLoader<OptimizationPass> loader = ServiceLoader.load(OptimizationPass.class);
        for (OptimizationPass pass : loader) {
            registerPass(pass);
        }
    }

    public OptimizationReport execute(File inputFile, File outputFile, EngineConfig config) throws IOException {
        long startTime = System.currentTimeMillis();
        long initialSize = inputFile.length();
        List<PassResult> results = new ArrayList<>();

        // Sort passes by priority: lowest runs first
        List<OptimizationPass> activePasses = new ArrayList<>(registeredPasses);
        activePasses.sort(Comparator.comparingInt(OptimizationPass::getPriority));

        // Load document safely
        try (PDDocument doc = PDDocument.load(inputFile, MemoryUsageSetting.setupTempFileOnly())) {
            OptimizationContext context = new OptimizationContext(doc, config);

            for (OptimizationPass pass : activePasses) {
                if (context.isAborted()) {
                    results.add(new PassResult(
                            pass.getName(),
                            false,
                            0L,
                            "Skipped due to pipeline abort: " + context.getAbortReason(),
                            false
                    ));
                    continue;
                }

                long passStart = System.nanoTime();
                try {
                    PassResult result = pass.apply(context);
                    long duration = (System.nanoTime() - passStart) / 1_000_000;
                    results.add(new PassResult(
                            pass.getName(),
                            result.success(),
                            duration,
                            result.message(),
                            result.modified()
                    ));
                } catch (Exception e) {
                    long duration = (System.nanoTime() - passStart) / 1_000_000;
                    results.add(new PassResult(
                            pass.getName(),
                            false,
                            duration,
                            "Error: " + e.getMessage(),
                            false
                    ));
                    context.addWarning("Pass '" + pass.getName() + "' threw exception: " + e.getMessage());
                }
            }

            if (!context.isAborted()) {
                doc.save(outputFile);
            } else {
                throw new IOException("Optimization pipeline aborted: " + context.getAbortReason());
            }
        }

        long finalSize = outputFile.length();
        long duration = System.currentTimeMillis() - startTime;

        return new OptimizationReport(
                inputFile.getName(),
                initialSize,
                finalSize,
                duration,
                results
        );
    }
}
```

#### 6. OptimizationReport.java
```java
package com.example.pdf.engine;

import java.util.List;

public record OptimizationReport(
        String fileName,
        long initialSizeBytes,
        long finalSizeBytes,
        long totalDurationMs,
        List<PassResult> passResults
) {
    public void printSummary() {
        System.out.println("======================================================================");
        System.out.printf(" PIPELINE EXECUTION SUMMARY: %s%n", fileName);
        System.out.println("======================================================================");
        System.out.printf(" Total Duration:  %d ms%n", totalDurationMs);
        System.out.printf(" Initial Size:    %,d bytes%n", initialSizeBytes);
        System.out.printf(" Final Size:      %,d bytes%n", finalSizeBytes);
        long saved = initialSizeBytes - finalSizeBytes;
        double savingsPct = initialSizeBytes == 0 ? 0 : (double) saved / initialSizeBytes * 100;
        System.out.printf(" Bytes Reclaimed: %,d bytes (%.2f%%)%n", saved, savingsPct);
        System.out.println("----------------------------------------------------------------------");
        System.out.printf(" %-24s | %-7s | %-9s | %s%n", "Pass Name", "Status", "Time (ms)", "Message");
        System.out.println("----------------------------------------------------------------------");
        for (PassResult res : passResults) {
            System.out.printf(" %-24s | %-7s | %-9d | %s%n",
                    res.passName(),
                    res.success() ? "SUCCESS" : "FAILED",
                    res.durationMs(),
                    res.message());
        }
        System.out.println("======================================================================");
    }
}
```

---

## 9. Common Mistakes

### 1. Shared Thread State in the Pipeline
*   *Symptom*: Random corruption or data mixing when optimizing multiple PDFs in parallel.
*   *Cause*: Registering a single instance of a stateful pass (e.g. a pass that retains a class-level variable `PDDocument doc`) across threads.
*   *Prevention*: Optimization passes must be stateless. All execution state must remain inside local variables inside the `apply(OptimizationContext)` scope.

### 2. Violating Pass Priority Constraints
*   *Symptom*: Metadata cleanup passes fail to reclaim bytes, or full-compression output sizes are larger than expected.
*   *Cause*: Running the OpenPDF full packing pass *before* structural metadata cleaning. The clean objects are never written to the packed stream.
*   *Prevention*: Define and enforce clean priority ranges: Pre-flight (0–10), Pruning (20–40), Processing (50–70), Serialization/Packing (80–100).

### 3. Masking Critical Pipeline Failures
*   *Symptom*: A pass fails, but the pipeline exits with a success report while producing a broken PDF file.
*   *Cause*: Swallowing all exceptions in the execution loop and proceeding to save without checks.
*   *Prevention*: Categorize exceptions. Minor parsing errors on XMP can raise a warning; XRef table structural errors must call `context.abort()` to halt execution immediately.

---

## 10. Assessment

### Quiz

1.  **Which design pattern is best suited for letting developers add new optimization actions (e.g. font-subsetting, image-resizing) to the engine without modifying the core pipeline code?**
    *   A. Observer Pattern
    *   B. Strategy Pattern
    *   C. Factory Pattern
    *   D. Decorator Pattern

2.  **In a multi-pass optimization engine, why should metadata pruning run before image resampling?**
    *   A. Metadata contains the sizing boundaries for images.
    *   B. Pruning resources simplifies the object graph, making image traversal faster and avoiding work on deleted assets.
    *   C. Resampling images removes the metadata entries from the trailer.
    *   D. The PDF specification requires metadata to occupy the lowest object numbers.

3.  **Why must the `OptimizationContext` be stateful, while the `OptimizationPass` implementations should be stateless?**
    *   A. Context objects contain the configuration settings, which change during execution.
    *   B. Passes need to share class-level mutable variables to communicate.
    *   C. Stateful context objects avoid copying heavy PDF memory structures, while stateless passes ensure thread safety when executing multiple files.
    *   D. Stateless passes are required by the Java compiler for SPI compatibility.

4.  **How is a short-circuit trigger implemented in the pipeline execution loop?**
    *   A. Calling `System.exit(0)`.
    *   B. Setting an abort flag inside the shared `OptimizationContext` which the loop checks before launching the next pass.
    *   C. Throwing a runtime exception that kills the JVM.
    *   D. Setting all configuration parameters to false.

5.  **Which file path registers service providers for the ServiceLoader framework in a JAR?**
    *   A. `/META-INF/services/`
    *   B. `/src/main/resources/`
    *   C. `/WEB-INF/classes/`
    *   D. `/java/util/spi/`

<details>
<summary><b>Click to reveal answers</b></summary>

1. **B** — The Strategy pattern enables encapsulating different algorithms (passes) and selecting or registering them dynamically.
2. **B** — Executing structural cleaning beforehand removes redundant assets (e.g., deleted images in metadata, thumbnails) so subsequent passes do not waste CPU processing them.
3. **C** — PDFs are heavy memory structures; copying them yields OOMs. A single stateful context avoids copies. Stateless passes allow multiple threads to run the pipeline concurrently.
4. **B** — The context stores an abort state. The pipeline loop checks `context.isAborted()` and exits the loop without invoking remaining passes.
5. **A** — Java's ServiceLoader framework searches the standard `/META-INF/services/` directory for configuration files named after the interface class.
</details>

---

## 11. Interview Perspective

### Common Interview Question
> "How would you design a PDF optimization library that third-party developers can extend with custom optimization passes without modifying your library's source code?"

### Expected Reasoning
The interviewer is looking for software design patterns, dependency injection, and modular runtime registration:
1.  **Define Abstraction Boundaries**: Establish an `OptimizationPass` interface defining a clean interface contract.
2.  **State Separation**: Explain that passes share a mutable state container (`OptimizationContext`) but must be stateless themselves.
3.  **Runtime Discovery**: Introduce Java's Service Provider Interface (SPI) `ServiceLoader` pattern. Explain how a third-party developer can bundle their pass, register it under `META-INF/services/com.example.pdf.engine.OptimizationPass`, and have the pipeline load it dynamically.
4.  **Ordering Concerns**: Explain how priority weights or annotations ensure custom passes execute in the correct order.

### Sample Answers

#### Strong Answer
> "I would design the library using a Pipeline pattern backed by the Service Provider Interface (SPI) pattern.
>
> First, I'd define a public interface `OptimizationPass` containing `getName()`, `getPriority()`, and `apply(OptimizationContext)`. The execution state of the PDF is managed by a shared context object to avoid expensive document cloning.
>
> To support extension without library modifications, the `PdfOptimizationPipeline` class will use Java’s `ServiceLoader` to dynamically locate passes on the classpath at runtime. A third-party developer simply implements the `OptimizationPass` interface, packages it inside their own JAR, and places a text file in `META-INF/services/` declaring their implementation.
>
> The pipeline will dynamically discover the pass, read its `getPriority()` weight to place it correctly in the sequence—for instance, ensuring a metadata pass runs before a packing pass—and run it transparently."

#### Weak Answer
> "I'd ask the developer to download the source code of my engine from GitHub, add their logic inside the main class, compile it themselves, and link that new JAR in their application."
