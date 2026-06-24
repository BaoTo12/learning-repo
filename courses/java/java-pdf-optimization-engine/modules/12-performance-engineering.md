# Module 12: Performance Engineering

---

## 1. Why This Module Exists

A PDF optimization engine that runs perfectly in local JUnit tests can quickly bring a production server to its knees. PDF processing is extremely resource-intensive, pushing both CPU (for image resampling and Flate compression) and memory (for holding heavy decoded image buffers and large PDF object graphs) to their limits.

For example, processing a 500 MB PDF containing 1,000 scanned pages on a standard server configuration without optimization will trigger massive garbage collection (GC) pauses, disk thrashing, and out-of-memory (OOM) errors.

If your optimizer takes 45 seconds to compress a single document, it cannot support real-time user uploads or batch-processing of millions of archived records. Performance engineering is not an afterthought; it is a core structural requirement.

This module teaches you how to identify memory, CPU, and I/O bottlenecks in Java, profile applications with Java Flight Recorder (JFR), write microbenchmarks with JMH, and build a high-throughput, thread-safe batch optimizer.

---

## 2. Learning Objectives

By the end of this module, you will be able to:
*   **Audit** Java heap pressure and GC pause behavior during PDF stream processing.
*   **Locate** bottlenecks using Java Flight Recorder (JFR) and Flame Graphs.
*   **Implement** memory-mapped file I/O via Java NIO to bypass heap constraints.
*   **Design** a high-throughput parallel batch optimizer using a bounded thread pool.
*   **Write** reliable JVM microbenchmarks using the Java Microbenchmark Harness (JMH).
*   **Explain** the performance trade-offs of heap buffers, disk caching, and off-heap allocations.

---

## 3. Conceptual Foundations

### CPU-Bound vs. I/O-Bound Workloads
PDF optimization involves a mix of both processing types:
*   **I/O-Bound**: Parsing the PDF Cross-Reference (XRef) table and reading/writing large streams.
*   **CPU-Bound**: Running the `Inflater` and `Deflater` algorithms (FlateDecode) and performing bicubic image interpolation (resampling).

Understanding the dominant bottleneck determines how we scale. Adding threads to an I/O-bound pipeline on a system with standard magnetic disks will increase head-seeking latency and *slow down* processing. Adding threads to a CPU-bound image pipeline on a multi-core CPU, however, scales throughput linearly up to the core limit.

### JVM Heap Pressure and GC Behavior
When a PDF reader decodes a compressed image (e.g. 10 MB JPEG on disk), it must decompress it into a raw pixel layout in memory (`BufferedImage`).
An $8000 \times 6000$ pixel scan at 24-bit color depth requires:
$$\text{Memory} = 8000 \times 6000 \times 3 \text{ bytes} = 144 \text{ MB of raw pixels}$$
These arrays are short-lived. If the optimizer processes images sequentially, it allocates and discards hundreds of these 144 MB arrays. This creates massive **GC allocation pressure**, forcing the JVM to run frequent Young Generation (Eden) collections, which eventually escalate to stop-the-world Full GCs that freeze the application.

### Memory-Mapped I/O (mmap)
Traditional Java file I/O reads data from the operating system page cache into a JVM heap buffer. This creates a duplicate copy of the data.
By using memory-mapped I/O (`FileChannel.map()`), the OS maps the file bytes directly into the process's virtual memory space. The Java application reads bytes directly from virtual memory via off-heap memory addresses. This reduces copying overhead and allows random-access XRef parsing without loading the file into heap memory.

### Amdahl's Law
Amdahl's Law defines the theoretical limit of speedup in parallel execution:
$$\text{Speedup} = \frac{1}{(1 - P) + \frac{P}{N}}$$
Where $P$ is the parallelizable portion of the application and $N$ is the number of processor cores.
If parsing and serializing (serial steps) take 20% of the runtime, and image processing takes 80%, the maximum theoretical speedup on an 8-core server is:
$$\text{Speedup} = \frac{1}{(1 - 0.80) + \frac{0.80}{8}} = \frac{1}{0.20 + 0.10} = 3.33x$$
No matter how many cores are added, the speedup can never exceed $5x$ due to the 20% serial bottleneck.

---

## 4. Technical Topics

### 4.1 Java Flight Recorder (JFR)
JFR is a profiling tool built into the JVM. It records detailed JVM events (CPU execution, thread states, GC pauses, memory allocations) with less than 1% overhead.
To launch JFR from the command line:
```bash
java -XX:StartFlightRecording=duration=60s,filename=pdf_profile.jfr -jar app.jar
```
You can view the resulting `.jfr` file in **JDK Mission Control (JMC)** or export it to generate Flame Graphs, which visually highlight hot execution paths.

### 4.2 Bounded Thread Pools
Parallelizing PDF processing must be done with caution. If you process 50 large PDFs in parallel on a system with 4 cores, the 50 threads will attempt to allocate raw image buffers concurrently, causing an immediate `OutOfMemoryError`.
A robust production optimizer must use a **bounded queue** and a **rejection execution policy** (like `CallerRunsPolicy`) to keep queue sizes stable and block incoming uploads when the system is saturated.

```java
ThreadPoolExecutor executor = new ThreadPoolExecutor(
    cores, cores, 60L, TimeUnit.SECONDS,
    new LinkedBlockingQueue<>(queueCapacity),
    new ThreadPoolExecutor.CallerRunsPolicy()
);
```

### 4.3 Off-Heap Buffers vs. Temporary Files
When caching large binary chunks:
*   `ByteBuffer.allocateDirect()` allocates memory outside the JVM garbage-collected heap.
    *   *Pros*: Eliminates GC pauses; ideal for passing data to OS channels.
    *   *Cons*: Allocation and deallocation are slow; risks OS memory leaks if reference cleanup fails.
*   **Scratch Files**: PDFBox can spill memory to disk when parsing using `MemoryUsageSetting.setupTempFileOnly()`.
    *   *Pros*: Processes gigabyte-scale documents with less than 16 MB of JVM heap.
    *   *Cons*: Introduces disk write/read latency.

---

## 5. Internal Mechanisms

### GC Allocations during Image Processing
When decoding compressed streams, PDFBox creates a `COSStream` object and buffers its input. During image optimization, the pipeline looks like this:

```
[ PDF File on Disk ] 
      │  (Memory-Mapped Read)
      ▼
[ Off-Heap OS Page Cache ]
      │  (Read bytes into JVM heap)
      ▼
[ compressed byte[] ] ────► Deflater/Inflater ────► [ decompressed byte[] ]
                                                           │
                                                           ▼
[ BufferedImage ] ◄─────── 2D Raster Graphics ◄─────── Color Space Transform
      │
      ▼ (JPEG Compression Encoder)
[ output byte[] ]
```

Every transition generates heap arrays. If GC pauses are too high, we can reduce allocation rates by reusing byte arrays via a pool mechanism (e.g. standard `ThreadLocal` byte buffers).

### RandomAccessFile vs Memory-Mapped File Channel
A traditional `RandomAccessFile` makes system calls (`seek` and `read`) every time PDFBox traverses the XRef list. Each system call forces a CPU context switch from user space to kernel space. A memory-mapped file (`FileChannel.map`) turns those file offsets into virtual memory address lookups, eliminating system calls and accelerating traversal times.

---

## 6. Trade-Off Analysis

### Throughput Tuning Configurations

| Parameter | Heap Buffers (`setupMainMemory`) | Scratch Files (`setupTempFileOnly`) | Memory-Mapped I/O |
| :--- | :--- | :--- | :--- |
| **Max Document Size** | Limited by JVM heap (e.g. 2 GB) | Unlimited (limited by disk space) | Unlimited (limited by OS virtual address space) |
| **Speed (I/O)** | Fastest | Slowest (disk bottlenecks) | Very Fast |
| **GC Overhead** | High (large arrays on heap) | Low (objects stream to disk) | Low |
| **Failure Mode** | JVM `OutOfMemoryError` | Disk full / I/O Exception | OS paging swap storm |

### Batch Sizing Strategy
Running too many parallel tasks degrades throughput because threads compete for memory bandwidth and CPU cache space. The optimal thread count is:
*   $\text{Threads} = \text{Available Cores}$ for purely CPU-bound tasks (image compression).
*   $\text{Threads} = 2 \times \text{Available Cores}$ for mixed I/O and CPU workloads.

---

## 7. Hands-On Exercises

### A. Beginner: JFR Thread Profiling
Run the pipeline from Module 11 on a loop. Take a 10-second JFR recording. Open JDK Mission Control, locate the **Thread Allocation** screen, and list the top three Java classes allocating the most memory.

### B. Intermediate: Write a JMH Benchmark
Write a JMH benchmark class that measures the throughput of your image downsampling algorithm from Module 5. Set 3 warmup iterations, 3 measurement iterations, and 1 execution fork.

### C. Advanced: CPU Thread Pool Saturation Test
Create a parallel testing harness that launches 10 concurrent threads to compress a high-resolution PDF. Track memory consumption and processing times, then compare the results to a single-threaded queue to identify lock contention points.

---

## 8. Mini Project: BatchPdfOptimizer

### Objective
Create a command-line tool `BatchPdfOptimizer` that processes a directory containing hundreds of PDF files in parallel. It must use a bounded thread pool to control memory consumption and report:
1.  Individual file compression ratios.
2.  Aggregate throughput measured in Megabytes processed per second (MB/s).
3.  Total GC compilation and execution metrics.

### Java Implementation

Save this code to `src/main/java/com/example/pdf/perf/BatchPdfOptimizer.java`:

```java
package com.example.pdf.perf;

import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.io.MemoryUsageSetting;

import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.*;
import java.util.concurrent.atomic.LongAdder;

public class BatchPdfOptimizer {

    // Record to hold processing metrics for an individual PDF file
    public record FileResult(
            String fileName,
            long originalBytes,
            long optimizedBytes,
            long durationMs,
            boolean success,
            String errorMsg
    ) {}

    // Main task class that executes optimization on a single file
    public static class OptimizationTask implements Callable<FileResult> {
        private final Path inputPath;
        private final Path outputPath;

        public OptimizationTask(Path inputPath, Path outputPath) {
            this.inputPath = inputPath;
            this.outputPath = outputPath;
        }

        @Override
        public FileResult call() {
            String name = inputPath.getFileName().toString();
            long originalSize = 0;
            long startTime = System.currentTimeMillis();

            try {
                originalSize = Files.size(inputPath);
                // Perform structural optimization (using PDFBox low-overhead loading)
                optimizeSingleFile(inputPath.toFile(), outputPath.toFile());
                long optimizedSize = Files.size(outputPath);
                long duration = System.currentTimeMillis() - startTime;
                return new FileResult(name, originalSize, optimizedSize, duration, true, null);
            } catch (Exception e) {
                long duration = System.currentTimeMillis() - startTime;
                return new FileResult(name, originalSize, 0L, duration, false, e.getMessage());
            }
        }

        private void optimizeSingleFile(File input, File output) throws IOException {
            // Memory-mapped temporary file storage strategy to protect the heap
            MemoryUsageSetting memorySetting = MemoryUsageSetting.setupTempFileOnly();
            try (PDDocument doc = PDDocument.load(input, memorySetting)) {
                // Apply a simple structural cleanup (such as stripping metadata) to simulate work
                doc.getDocumentCatalog().getCOSObject().removeItem(org.apache.pdfbox.cos.COSName.METADATA);
                // Save document with structural compression enabled
                doc.save(output);
            }
        }
    }

    public static void runBatch(Path inputDir, Path outputDir, int threadCount) throws Exception {
        if (!Files.exists(inputDir) || !Files.isDirectory(inputDir)) {
            throw new IllegalArgumentException("Input directory does not exist or is not a directory");
        }
        Files.createDirectories(outputDir);

        List<Path> pdfFiles = new ArrayList<>();
        try (var stream = Files.list(inputDir)) {
            stream.filter(p -> p.toString().toLowerCase().endsWith(".pdf"))
                  .forEach(pdfFiles::add);
        }

        if (pdfFiles.isEmpty()) {
            System.out.println("No PDF files found in " + inputDir);
            return;
        }

        System.out.printf("Starting batch optimization of %d PDFs on %d threads...%n", pdfFiles.size(), threadCount);

        // Bounded thread pool with a capacity queue matching core counts
        int queueCapacity = threadCount * 2;
        BlockingQueue<Runnable> queue = new LinkedBlockingQueue<>(queueCapacity);
        ThreadPoolExecutor executor = new ThreadPoolExecutor(
                threadCount,
                threadCount,
                30, TimeUnit.SECONDS,
                queue,
                new ThreadPoolExecutor.CallerRunsPolicy() // Block incoming threads when pipeline is saturated
        );

        List<Future<FileResult>> futures = new ArrayList<>();
        long batchStart = System.currentTimeMillis();

        for (Path file : pdfFiles) {
            Path outputFilePath = outputDir.resolve(file.getFileName());
            OptimizationTask task = new OptimizationTask(file, outputFilePath);
            futures.add(executor.submit(task));
        }

        executor.shutdown();
        if (!executor.awaitTermination(1, TimeUnit.HOURS)) {
            System.err.println("Batch execution timed out after 1 hour.");
        }

        long batchDurationMs = System.currentTimeMillis() - batchStart;

        // Collect reports
        List<FileResult> results = new ArrayList<>();
        long totalOriginalBytes = 0;
        long totalOptimizedBytes = 0;
        int successCount = 0;
        int failCount = 0;

        for (Future<FileResult> future : futures) {
            try {
                FileResult result = future.get();
                results.add(result);
                if (result.success()) {
                    totalOriginalBytes += result.originalBytes();
                    totalOptimizedBytes += result.optimizedBytes();
                    successCount++;
                } else {
                    failCount++;
                }
            } catch (InterruptedException | ExecutionException e) {
                failCount++;
            }
        }

        // Print final reports
        printReport(results, totalOriginalBytes, totalOptimizedBytes, successCount, failCount, batchDurationMs);
    }

    private static void printReport(List<FileResult> results, long origBytes, long optBytes,
                                     int success, int fails, long durationMs) {
        double totalOrigMB = origBytes / 1_048_576.0;
        double totalOptMB = optBytes / 1_048_576.0;
        double savedMB = totalOrigMB - totalOptMB;
        double compressionRatio = origBytes == 0 ? 0.0 : (double) (origBytes - optBytes) / origBytes * 100;
        double durationSec = durationMs / 1000.0;
        double throughputMBs = durationSec == 0.0 ? 0.0 : totalOrigMB / durationSec;

        System.out.println("\n======================================================================");
        System.out.println("                    BATCH PDF OPTIMIZATION SUMMARY                    ");
        System.out.println("======================================================================");
        System.out.printf(" Successful Executions:   %d%n", success);
        System.out.printf(" Failed Executions:       %d%n", fails);
        System.out.printf(" Total Running Time:       %.2f seconds%n", durationSec);
        System.out.printf(" Total Original Size:     %.2f MB%n", totalOrigMB);
        System.out.printf(" Total Optimized Size:    %.2f MB%n", totalOptMB);
        System.out.printf(" Net Bytes Reclaimed:     %.2f MB (%.2f%%)%n", savedMB, compressionRatio);
        System.out.printf(" Aggregate Throughput:    %.2f MB/second%n", throughputMBs);
        System.out.println("======================================================================");
        System.out.printf(" %-30s | %-12s | %-12s | %s%n", "File Name", "Orig Size", "Opt Size", "Time (ms)");
        System.out.println("----------------------------------------------------------------------");
        for (FileResult res : results) {
            if (res.success()) {
                System.out.printf(" %-30s | %-12s | %-12s | %d%n",
                        truncate(res.fileName(), 30),
                        formatBytes(res.originalBytes()),
                        formatBytes(res.optimizedBytes()),
                        res.durationMs());
            } else {
                System.out.printf(" %-30s | FAILED: %s%n",
                        truncate(res.fileName(), 30),
                        res.errorMsg() != null ? truncate(res.errorMsg(), 35) : "Unknown");
            }
        }
        System.out.println("======================================================================\n");
    }

    private static String formatBytes(long b) {
        if (b >= 1_048_576) return String.format("%.2f MB", b / 1_048_576.0);
        if (b >= 1024) return String.format("%.2f KB", b / 1024.0);
        return b + " B";
    }

    private static String truncate(String s, int len) {
        if (s == null) return "";
        if (s.length() <= len) return s;
        return s.substring(0, len - 3) + "...";
    }

    public static void main(String[] args) throws Exception {
        if (args.length < 2) {
            System.out.println("Usage: java BatchPdfOptimizer <input-directory> <output-directory> [threads]");
            return;
        }

        Path input = Path.of(args[0]);
        Path output = Path.of(args[1]);
        int threads = Runtime.getRuntime().availableProcessors();
        if (args.length >= 3) {
            threads = Integer.parseInt(args[2]);
        }

        runBatch(input, output, threads);
    }
}
```

---

## 9. Common Mistakes

### 1. Sharing `PDDocument` Instances Across Tasks
*   *Symptom*: Random data corruption, cross-page rendering errors, or concurrency exceptions.
*   *Cause*: Passing a single `PDDocument` instance reference to multiple concurrent tasks in the execution pool. **PDFBox documents are not thread-safe**.
*   *Prevention*: Each thread task must load, modify, and save its own independent document instance using thread-local references.

### 2. Using Unbounded Linked Blocking Queues
*   *Symptom*: Sudden crash of the JVM with `java.lang.OutOfMemoryError: Java heap space` when submitting a large batch of directories.
*   *Cause*: Using `new LinkedBlockingQueue<>()` without specifying a capacity. The pipeline accepts millions of files, schedules tasks, and overflows heap memory with pending `Future` objects and path strings.
*   *Prevention*: Always enforce task limits by instantiating queues with a fixed maximum capacity (e.g. `100`), and configure a `CallerRunsPolicy` to slow down queue submissions.

### 3. Disregarding Garbage Collector Selection
*   *Symptom*: High CPU usage but very low document optimization throughput.
*   *Cause*: Running the JVM with the default Serial GC configuration on multi-core systems, causing threads to stop and wait during garbage collections.
*   *Prevention*: In production settings, start the JVM using the G1 garbage collector: `-XX:+UseG1GC`, which is optimized for managing large short-lived objects.

---

## 10. Assessment

### Quiz

1.  **Which JVM configuration option changes the garbage collection model to G1GC, which is optimal for parallel PDF pipelines?**
    *   A. `-XX:+UseParallelGC`
    *   B. `-XX:+UseG1GC`
    *   C. `-Xmx1024m`
    *   D. `-XX:+StartFlightRecording`

2.  **You configure a thread pool with a `CallerRunsPolicy`. What happens when the work queue fills up?**
    *   A. The pipeline discards extra tasks without notifying the user.
    *   B. The execution engine throws a `RejectedExecutionException` and aborts.
    *   C. The thread that submitted the task executes it itself, naturally blocking and slowing down submissions.
    *   D. The JVM starts another thread pool in the background.

3.  **Why does memory-mapped file I/O (`FileChannel.map`) perform faster than standard `RandomAccessFile` during structural PDF analysis?**
    *   A. It compresses the PDF contents on-the-fly.
    *   B. It bypasses JVM heap allocation copy cycles and translates offsets directly to virtual memory without context switches.
    *   C. It runs the garbage collector in parallel.
    *   D. It automatically encrypts stream arrays.

4.  **According to Amdahl's Law, if 40% of your PDF optimization pipeline must be run sequentially, what is the maximum speedup you can achieve, even with an infinite number of CPU cores?**
    *   A. $2.5x$
    *   B. $5.0x$
    *   C. $10.0x$
    *   D. $1.5x$

5.  **Which tool should be used to record JVM CPU execution profiles and heap allocations with less than 1% runtime overhead?**
    *   A. VisualVM
    *   B. Java Flight Recorder (JFR)
    *   C. JMH Benchmarking Harness
    *   D. JUnit 5 Assertions

<details>
<summary><b>Click to reveal answers</b></summary>

1. **B** — The G1 garbage collector is activated via `-XX:+UseG1GC` and manages memory segments dynamically to reduce pauses.
2. **C** — The `CallerRunsPolicy` forces the submitter thread (often the main thread) to run the task, preventing queue overload.
3. **B** — Memory-mapping exposes the file contents directly to user virtual address space, eliminating copying costs.
4. **A** — $\text{Speedup Limit} = \frac{1}{\text{Serial Fraction}} = \frac{1}{0.40} = 2.5x$.
5. **B** — JFR is embedded into JVM engines directly, providing accurate recording without introducing performance overhead.
</details>

---

## 11. Interview Perspective

### Common Interview Question
> "Your PDF optimizer processes 1 file per second on a single thread. You have an 8-core server. What is the maximum theoretical throughput improvement, and what engineering constraints prevent achieving it in practice?"

### Expected Reasoning
The candidate should answer using performance theory and hardware mechanics:
1.  **Amdahl's Law Limit**: Quantify the maximum speedup based on serial bottlenecks (e.g. disk write time, catalog serialization).
2.  **Resource Contention**: Focus on Shared I/O bandwidth. 8 cores reading/writing to the same disk channel will bottleneck on disk controllers.
3.  **Memory Constraints**: Focus on JVM memory constraints. Running 8 parallel threads processing huge image raster buffers concurrently can exhaust the heap, triggering GC cycles that decrease throughput.
4.  **Lock Contention**: Thread coordination bottlenecks (such as database logging or shared buffer queues).

### Sample Answers

#### Strong Answer
> "If 100% of the optimization pipeline were parallelizable, the maximum speedup on an 8-core machine would be $8x$, translating to 8 files/second.
>
> However, in practice, we won't reach this limit due to Amdahl's Law and system hardware bottlenecks.
>
> First, parsing files and serializing updates are serial steps. If these take 10% of the processing time, the maximum theoretical speedup is capped at $5.26x$.
>
> Second, I/O bottlenecks will occur. If we process documents concurrently, they will saturate disk read/write bandwidth.
>
> Third, GC pressure will limit throughput. PDF processing generates large, short-lived byte arrays for decoded images. Running 8 tasks in parallel increases garbage collection overhead. GC pause cycles (Stop-The-World) will degrade our CPU utilization.
>
> To maximize efficiency, we must use memory-mapped I/O, apply disk caching rules (`MemoryUsageSetting.setupTempFileOnly()`), use a bounded thread pool, and configure the G1 GC to manage the heap."

#### Weak Answer
> "We would get exactly $8x$ improvement because we have 8 cores. We just create 8 threads using a loop. It's an easy change."
