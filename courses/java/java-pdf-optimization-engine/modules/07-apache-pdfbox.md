# Module 07: Apache PDFBox Deep Dive

---

## 1. Why This Module Exists

Modules 1–6 built a strong theoretical foundation: you understand the PDF object model, stream filters, image processing algorithms, and compression profile design. But all the code examples so far operate on raw bytes — you wrote a `RandomAccessFile`-based XRef parser and a `Inflater`-based stream decoder from scratch.

In production engineering, you do not reimplement PDF parsing for every project. You stand on the shoulders of **Apache PDFBox**, the most widely deployed open-source Java PDF library. PDFBox provides:
*   A safe, high-level API (`PDDocument`, `PDPage`, `PDImageXObject`) that abstracts byte-level parsing.
*   A low-level COS (Carousel Object System) API that exposes every raw PDF object for direct manipulation.
*   Memory management through `MemoryUsageSetting`, preventing heap exhaustion on large files.
*   Saving strategies including full rewrite, incremental save, and linearization.

This module teaches you not just the API surface, but **why each API works the way it does** — what happens inside PDFBox when you call `PDDocument.load()`, how lazy loading is implemented, where the COS layer maps to the PDF object model from Module 3, and what happens at the byte level when you call `save()`.

---

## 2. Learning Objectives

By the end of this module, you will be able to:
*   **Load** PDF documents safely using `MemoryUsageSetting` with appropriate memory configuration.
*   **Navigate** the two-layer model: high-level `PD*` classes vs. low-level `COS*` objects.
*   **Traverse** the resource graph from `PDDocument` → `PDPage` → `PDResources` → `PDImageXObject`.
*   **Extract** image data from PDF image XObjects as `BufferedImage` instances.
*   **Replace** stream contents in a `COSStream` with new optimized bytes.
*   **Configure** object stream compression using `CompressParameters` on save.
*   **Choose** between `save()`, `saveIncremental()`, based on use case requirements.
*   **Avoid** resource leaks from unclosed `PDDocument` instances and scratch files.

---

## 3. Conceptual Foundations

### PDFBox's Two-Layer Model
PDFBox exposes two distinct API layers that reflect the PDF specification's own separation between semantic content and raw objects:

```
┌────────────────────────────────────────────────────────────────┐
│                    HIGH-LEVEL PD* LAYER                        │
│                                                                │
│  PDDocument ─► PDPage ─► PDResources ─► PDImageXObject        │
│  PDFont     ─► PDType0Font, PDType1Font, PDTrueTypeFont        │
│  PDAnnotation, PDFormXObject, PDColorSpace...                  │
│                                                                │
│  Provides: type safety, semantic meaning, convenience methods  │
│  Example:  pdfImage.getImage() → BufferedImage                 │
├────────────────────────────────────────────────────────────────┤
│                    LOW-LEVEL COS* LAYER                        │
│                                                                │
│  COSDocument ─► COSObject ─► COSDictionary / COSStream         │
│  COSName, COSString, COSArray, COSInteger, COSFloat, COSNull   │
│                                                                │
│  Provides: direct access to raw PDF objects and streams        │
│  Example:  cosStream.createOutputStream() → write raw bytes    │
└────────────────────────────────────────────────────────────────┘
```

Every `PD*` object wraps a corresponding `COS*` object. You can always escape to the low level via `.getCOSObject()`.

### Lazy Loading
PDFBox does **not** load the entire PDF into memory on `PDDocument.load()`. Instead, it:
1.  Reads the trailer and XRef table/stream at startup to build an in-memory offset map.
2.  Deserializes individual objects **on demand** — only when your code first accesses them via `getPage()`, `getResources()`, etc.
3.  Caches deserialized objects in the `COSDocument` object pool after first access.

This means calling `PDDocument.load()` on a 500 MB PDF is fast and uses modest memory — until you actually iterate all its images.

### Scratch File Mechanics
When `MemoryUsageSetting.setupMixed(heapBytes)` is used, PDFBox creates a **temporary file** on disk to hold stream data that overflows the heap budget. The scratch file path defaults to the system temp directory. When `PDDocument.close()` is called, the scratch file is deleted.

**If you forget to call `close()`**, the scratch file is orphaned — the JVM process holds a file handle, but the file descriptor is never released, and the temp storage is never reclaimed.

---

## 4. Technical Topics

### 4.1 MemoryUsageSetting

PDFBox offers three memory strategies:

| Setting | Heap Usage | Disk Usage | Best For |
| :--- | :--- | :--- | :--- |
| `setupMainMemoryOnly()` | All in heap | None | Small PDFs (< 50 MB), unit testing |
| `setupTempFileOnly()` | Minimal | All to temp file | Very large PDFs on low-memory servers |
| `setupMixed(maxHeapBytes)` | Up to limit | Overflow to disk | General production use |

```java
// Recommended production setting: up to 50 MB in heap, overflow to scratch file
MemoryUsageSetting memSetting = MemoryUsageSetting.setupMixed(50 * 1024 * 1024);
PDDocument doc = PDDocument.load(new File("large.pdf"), memSetting);
```

### 4.2 Document and Page Navigation

```java
PDDocument doc = PDDocument.load(file, memSetting);
try {
    int pageCount = doc.getNumberOfPages();
    for (int i = 0; i < pageCount; i++) {
        PDPage page = doc.getPage(i);
        PDResources resources = page.getResources();
        // Iterate image XObjects
        for (COSName xObjectName : resources.getXObjectNames()) {
            PDXObject xobj = resources.getXObject(xObjectName);
            if (xobj instanceof PDImageXObject pdfImage) {
                processImage(pdfImage, page, i);
            }
        }
    }
} finally {
    doc.close(); // ALWAYS in finally or try-with-resources
}
```

### 4.3 Image Extraction and Replacement

**Extracting** a `BufferedImage` from an image XObject:
```java
BufferedImage rawPixels = pdfImage.getImage();
// rawPixels is now a fully decoded in-memory pixel matrix
```

**Replacing** the stream contents for optimization. The COS-level approach gives full control:
```java
COSStream cosStream = pdfImage.getCOSObject();

// Clear existing filters and write new compressed bytes
try (OutputStream out = cosStream.createRawOutputStream()) {
    out.write(optimizedJpegBytes);
}

// Update the stream dictionary to reflect the new encoding
cosStream.setItem(COSName.FILTER, COSName.DCT_DECODE);
cosStream.setInt(COSName.LENGTH, optimizedJpegBytes.length);
// Update colorspace if converted to grayscale
if (convertedToGrayscale) {
    cosStream.setItem(COSName.COLORSPACE, COSName.DEVICEGRAY);
    cosStream.setInt(COSName.BITS_PER_COMPONENT, 8);
}
```

**Important**: After stream replacement, the `/Width` and `/Height` keys in the image dictionary must also be updated if the image was downsampled:
```java
cosStream.setInt(COSName.WIDTH, newWidth);
cosStream.setInt(COSName.HEIGHT, newHeight);
```

### 4.4 Saving Strategies

| Method | Behavior | When to Use |
| :--- | :--- | :--- |
| `doc.save(outputStream)` | Full rewrite: serializes all objects, generates a new XRef table, produces a clean output PDF | Optimization (always produces the smallest output) |
| `doc.saveIncremental(outputStream)` | Appends only modified objects as an incremental update, preserves original bytes | Signing workflows, preserving digital signatures |

**Object stream compression on save**:
```java
// Compress object dictionaries into object streams (PDF 1.5+)
// This can reduce file size by 10–20% for text-heavy documents
doc.save(outputFile, CompressParameters.DEFAULT_COMPRESSION);
```

### 4.5 COS API Direct Object Access
For operations beyond the `PD*` API — for example, accessing embedded file attachments, modifying the document catalog, or removing orphaned objects — use the `COSDocument`:

```java
COSDocument cosDoc = doc.getDocument();
// Iterate all objects in the document
for (COSObject cosObj : cosDoc.getObjects()) {
    COSBase base = cosObj.getObject();
    if (base instanceof COSStream cosStream) {
        // Inspect or modify the stream
    }
}
```

---

## 5. Internal Mechanisms

### Document Load Sequence

```
PDDocument.load(file, memSetting)
│
├── 1. Open file via RandomAccessRead (FileInputStream or memory-mapped)
│
├── 2. Locate last %%EOF marker and read startxref offset
│
├── 3. Parse XRef table or cross-reference stream at that offset
│       → Build COSDocument.objectPool (offset map: objNum → fileOffset)
│
├── 4. Parse Trailer dictionary
│       → Follow /Prev chain for incremental updates (same as our XRefResolver)
│
├── 5. Resolve /Root (document catalog) and /Info (metadata)
│       → These are deserialized eagerly; all other objects remain lazy
│
└── 6. Return PDDocument wrapping the COSDocument
    At this point, no page content or image data has been decoded yet.
```

### Save Sequence

```
PDDocument.save(outputFile, CompressParameters.DEFAULT_COMPRESSION)
│
├── 1. COSWriter visits every object in COSDocument.objectPool
│
├── 2. Objects eligible for object streams (non-stream dictionaries, scalars)
│    are grouped into COSObjectStream blocks and FlateDecode-compressed
│
├── 3. Each object (or object stream) is written to output sequentially
│    with a byte offset tracked in the new XRef structure
│
├── 4. A new XRef stream (compressed, FlateDecode) or XRef table is written
│
├── 5. A new Trailer dictionary points to the Root and Info objects
│
└── 6. Startxref + %%EOF is appended
    Result: a clean, fully rewritten PDF with no orphaned or duplicate objects.
```

### Heap Usage Timeline During Image Processing

```
Time →    T0          T1           T2          T3          T4
          Load      Decode      Downsample   Re-encode    Next image
          PDF       image[i]    image[i]     image[i]
          ──────────────────────────────────────────────────────────
Heap:     [XRef]  [XRef+BIG]  [XRef+BIG+  [XRef+small  [XRef]
                               small]       ]
                  ↑ Peak here: original BufferedImage + target BufferedImage
```

Between T3 and T4, the original `BufferedImage` must be released (set to `null`) and GC must run before loading the next large image.

---

## 6. Trade-Off Analysis

### MemoryUsageSetting Selection

| Scenario | Recommended Setting | Reason |
| :--- | :--- | :--- |
| Unit testing with small PDFs | `setupMainMemoryOnly()` | No disk I/O, simpler cleanup |
| Batch processing on a server with 4 GB RAM | `setupMixed(100 * 1024 * 1024)` | 100 MB heap budget, overflow to disk |
| Processing 1 GB+ PDFs on a 512 MB container | `setupTempFileOnly()` | All stream data goes to disk; heap for metadata only |
| Interactive PDF signing (small file) | `setupMainMemoryOnly()` | Speed matters; no disk I/O latency |

### save() vs. saveIncremental()

| Dimension | `save()` | `saveIncremental()` |
| :--- | :--- | :--- |
| **Output Size** | Smallest — no orphaned objects | Larger — original bytes preserved |
| **Digital Signatures** | ❌ Breaks existing signatures | ✅ Preserves signature byte range |
| **Use Case** | Optimization, archival | Annotation, form-fill, counter-signing |
| **XRef Format** | Clean new XRef | Appended incremental XRef |

---

## 7. Hands-On Exercises

### A. Beginner: Load PDF and Print Page Count
*   Load a PDF using `PDDocument.load()` with `setupMixed(50 MB)`.
*   Print the page count, PDF version, and document title from `PDDocumentInformation`.
*   Close the document inside a `try-with-resources` block.

### B. Intermediate: List All Image Resources
*   Iterate all pages, all XObject resources per page.
*   For each `PDImageXObject`, print its name, width, height, color space, bits per component, and current filter.
*   Identify which images are above a size threshold (e.g., 500 KB decoded) as candidates for optimization.

### C. Advanced: Replace Images Above Threshold
*   Combine exercise B with `ImageOptimizationPipeline` (Module 5).
*   For each image whose decoded size exceeds a configurable threshold, run the pipeline.
*   Write optimized bytes back to the `COSStream`.
*   Update the `/Width`, `/Height`, `/Filter`, and `/ColorSpace` dictionary entries.
*   Save the output using `CompressParameters.DEFAULT_COMPRESSION`.

---

## 8. Mini Project: PDFBoxImageOptimizer

### Objective
Build a complete PDF image optimization tool using PDFBox. The tool iterates all image XObjects in a PDF, applies the `ImageOptimizationPipeline` using a configurable `CompressionProfile`, writes the result back, and saves a new optimized PDF.

### Maven Dependency
Add to `pom.xml`:
```xml
<dependency>
    <groupId>org.apache.pdfbox</groupId>
    <artifactId>pdfbox</artifactId>
    <version>3.0.2</version>
</dependency>
```

### Java Implementation Code
Write to `src/main/java/com/example/pdf/pdfbox/PDFBoxImageOptimizer.java`:

```java
package com.example.pdf.pdfbox;

import com.example.pdf.image.ImageOptimizationPipeline;
import com.example.pdf.image.ImageOptimizationPipeline.GrayscaleMode;
import com.example.pdf.orchestrator.PdfCompressionOrchestrator.CompressionProfile;
import com.example.pdf.orchestrator.PdfCompressionOrchestrator.RecommendedCompression;

import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.graphics.PDXObject;
import org.apache.pdfbox.pdmodel.graphics.image.PDImageXObject;
import org.apache.pdfbox.io.MemoryUsageSetting;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSObject;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.IOException;
import java.io.OutputStream;
import java.util.HashSet;
import java.util.Set;

public class PDFBoxImageOptimizer {

    private final CompressionProfile profile;
    private final int originalDpi;

    public PDFBoxImageOptimizer(CompressionProfile profile, int originalDpi) {
        this.profile = profile;
        this.originalDpi = originalDpi;
    }

    public void optimize(File inputFile, File outputFile) throws IOException {
        long startTime = System.currentTimeMillis();
        long totalBefore = 0, totalAfter = 0;
        int imagesProcessed = 0;

        MemoryUsageSetting memSetting = MemoryUsageSetting.setupMixed(50 * 1024 * 1024);

        // Track processed COSStreams to avoid double-processing shared resources
        Set<Integer> processedObjectNumbers = new HashSet<>();

        try (PDDocument doc = PDDocument.load(inputFile, memSetting)) {
            System.out.printf("\nProcessing: %s [%d pages]%n",
                    inputFile.getName(), doc.getNumberOfPages());
            System.out.printf("Profile:    %s%n%n", profile.displayName());

            for (int pageIndex = 0; pageIndex < doc.getNumberOfPages(); pageIndex++) {
                PDPage page = doc.getPage(pageIndex);
                PDResources resources = page.getResources();
                if (resources == null) continue;

                for (COSName xObjectName : resources.getXObjectNames()) {
                    PDXObject xobj = resources.getXObject(xObjectName);
                    if (!(xobj instanceof PDImageXObject pdfImage)) continue;

                    COSStream cosStream = pdfImage.getCOSObject();
                    int objNumber = System.identityHashCode(cosStream); // Use identity as proxy
                    if (!processedObjectNumbers.add(objNumber)) continue; // Skip shared resources

                    // Read existing compressed bytes
                    byte[] originalBytes = readCompressedStream(cosStream);
                    long beforeSize = originalBytes.length;
                    totalBefore += beforeSize;

                    // Run optimization pipeline
                    GrayscaleMode gm = profile.isGrayscaleEnabled()
                            ? GrayscaleMode.CONVERT_GRAYSCALE
                            : GrayscaleMode.KEEP_COLOR;

                    ImageOptimizationPipeline pipeline = new ImageOptimizationPipeline(
                            originalDpi, profile.getTargetDpi(), profile.getJpegQuality(), gm);

                    byte[] optimizedBytes;
                    try {
                        optimizedBytes = pipeline.process(originalBytes);
                    } catch (IOException e) {
                        System.err.printf("  [SKIP] Page %d image '%s': %s%n",
                                pageIndex + 1, xObjectName.getName(), e.getMessage());
                        totalAfter += beforeSize;
                        continue;
                    }

                    // Write optimized bytes back to COSStream
                    writeOptimizedStream(cosStream, optimizedBytes,
                            profile.getTargetDpi(), profile.getTargetDpi(),
                            pdfImage.getWidth(), pdfImage.getHeight(),
                            profile.isGrayscaleEnabled());

                    totalAfter += optimizedBytes.length;
                    imagesProcessed++;

                    System.out.printf("  [Page %2d] %-20s %,8d → %,8d bytes (%.1f%%)%n",
                            pageIndex + 1, xObjectName.getName(),
                            beforeSize, optimizedBytes.length,
                            (double) optimizedBytes.length / beforeSize * 100);
                }
            }

            // Save with object stream compression
            doc.save(outputFile);
            long duration = System.currentTimeMillis() - startTime;

            System.out.println("\n─────────────────────────────────────────────");
            System.out.printf("Images optimized : %d%n", imagesProcessed);
            System.out.printf("Total before     : %s%n", humanBytes(totalBefore));
            System.out.printf("Total after      : %s%n", humanBytes(totalAfter));
            System.out.printf("Saved            : %s (%.1f%%)%n",
                    humanBytes(totalBefore - totalAfter),
                    (double)(totalBefore - totalAfter) / Math.max(totalBefore, 1) * 100);
            System.out.printf("Duration         : %.1f seconds%n", duration / 1000.0);
            System.out.printf("Output           : %s%n", outputFile.getAbsolutePath());
        }
    }

    private byte[] readCompressedStream(COSStream stream) throws IOException {
        try (var rawInput = stream.createRawInputStream();
             ByteArrayOutputStream baos = new ByteArrayOutputStream()) {
            rawInput.transferTo(baos);
            return baos.toByteArray();
        }
    }

    private void writeOptimizedStream(COSStream stream, byte[] optimizedBytes,
                                      int newWidth, int newHeight,
                                      int originalWidth, int originalHeight,
                                      boolean convertedToGrayscale) throws IOException {
        try (OutputStream out = stream.createRawOutputStream()) {
            out.write(optimizedBytes);
        }
        stream.setItem(COSName.FILTER, COSName.DCT_DECODE);
        stream.setInt(COSName.LENGTH, optimizedBytes.length);

        // Update dimensions if downsampled
        int targetW = (int)(originalWidth  * ((double) profile.getTargetDpi() / originalDpi));
        int targetH = (int)(originalHeight * ((double) profile.getTargetDpi() / originalDpi));
        if (targetW < originalWidth) {
            stream.setInt(COSName.WIDTH,  targetW);
            stream.setInt(COSName.HEIGHT, targetH);
        }

        if (convertedToGrayscale) {
            stream.setItem(COSName.COLORSPACE, COSName.DEVICEGRAY);
        }
    }

    private static String humanBytes(long b) {
        if (b >= 1_048_576) return String.format("%.1f MB", b / 1_048_576.0);
        if (b >= 1024)      return String.format("%.1f KB", b / 1024.0);
        return b + " B";
    }

    public static void main(String[] args) throws IOException {
        if (args.length < 3) {
            System.out.println("Usage: PDFBoxImageOptimizer <input.pdf> <output.pdf> <profile> [originalDpi]");
            System.out.println("  profile: low | recommended | extreme");
            return;
        }
        CompressionProfile profile = com.example.pdf.orchestrator
                .PdfCompressionOrchestrator.fromName(args[2]);
        int dpi = args.length > 3 ? Integer.parseInt(args[3]) : 300;

        PDFBoxImageOptimizer optimizer = new PDFBoxImageOptimizer(profile, dpi);
        optimizer.optimize(new File(args[0]), new File(args[1]));
    }
}
```

---

## 9. Common Mistakes

### 1. Forgetting to Call `PDDocument.close()`
*   *Symptom*: Temp files accumulate in the system's `%TEMP%` directory; long-running servers run out of disk space.
*   *Cause*: `setupMixed()` creates a scratch file that is only deleted when `close()` is called. If the code path throws an exception before `close()`, the scratch file leaks.
*   *Prevention*: Always use `try-with-resources` (`try (PDDocument doc = ...)`). `PDDocument` implements `Closeable` in PDFBox 3.x.

### 2. Using `setupMainMemoryOnly()` on Large Files in Production
*   *Symptom*: `java.lang.OutOfMemoryError: Java heap space` when processing 200 MB+ PDFs.
*   *Cause*: All stream content is kept in heap. A single 200 MB PDF with its decoded images can require 2–4× its compressed size in RAM.
*   *Prevention*: Use `setupMixed(heapBudget)`. Set the heap budget to 30–50% of available JVM heap.

### 3. Not Updating `/Width`, `/Height` After Downsampling
*   *Symptom*: The output PDF renders the optimized image stretched or squashed across its original bounding box area.
*   *Cause*: The image stream contains 1240×1753 pixels, but the dictionary still declares `/Width 4962 /Height 7014`. PDF viewers use the dictionary values to determine the pixel matrix layout.
*   *Prevention*: Always update `/Width` and `/Height` in the `COSStream` dictionary to match the actual dimensions of the new pixel data written to the stream.

### 4. Not Setting `CompressParameters` on Save
*   *Symptom*: The output PDF is larger than expected despite successful image optimization.
*   *Cause*: Object dictionaries are written as uncompressed objects. For a document with many small objects, uncompressed object serialization can add 15–25% overhead.
*   *Prevention*: Always call `doc.save(outputFile, CompressParameters.DEFAULT_COMPRESSION)` unless the output must be compatible with PDF 1.4 or older readers.

---

## 10. Assessment

### Quiz
1.  **What does `MemoryUsageSetting.setupMixed(maxBytes)` do when the memory limit is exceeded?**
    *   A. Throws `OutOfMemoryError`.
    *   B. Silently drops the data that does not fit.
    *   C. Writes the overflow data to a temporary scratch file on disk.
    *   D. Switches to `setupMainMemoryOnly()` mode and doubles the heap allocation.

2.  **Why must you update `/Width` and `/Height` in the image dictionary after downsampling?**
    *   A. PDF readers use these values to interpret the raw byte layout of the pixel matrix.
    *   B. The JPEG encoder cannot determine dimensions automatically.
    *   C. The XRef table uses `/Width` and `/Height` to calculate stream byte offsets.
    *   D. PDFBox throws an exception if these values are stale.

3.  **When should you use `saveIncremental()` instead of `save()`?**
    *   A. When the output file must be smaller than the input file.
    *   B. When you need to preserve existing digital signatures in the document.
    *   C. When the PDF contains more than 100 pages.
    *   D. When the document was originally created with Adobe Acrobat.

### Debugging Task
The following code silently produces incorrect output — the optimized images appear at the wrong size in the output PDF. Identify and fix the bug:

```java
private void writeOptimizedStream(COSStream stream, byte[] bytes) throws IOException {
    try (OutputStream out = stream.createRawOutputStream()) {
        out.write(bytes);
    }
    stream.setItem(COSName.FILTER, COSName.DCT_DECODE);
    stream.setInt(COSName.LENGTH, bytes.length);
    // --- No other updates ---
}
```

---

## 11. Interview Perspective

### Common Interview Question
> "How does PDFBox's `MemoryUsageSetting` work under the hood, and when would you choose `setupTempFileOnly()` over `setupMixed()`?"

### Sample Answers

#### Strong Answer
> "`MemoryUsageSetting` controls how PDFBox's `ScratchFile` allocates storage for raw stream bytes. In `setupMixed(maxBytes)` mode, up to `maxBytes` of stream data is stored directly in a heap byte buffer. Once that limit is reached, additional stream data is written to a temporary file on disk — effectively a disk-backed buffer pool.
> In `setupTempFileOnly()` mode, all stream data goes directly to disk from the start. Heap usage is minimized to just the object metadata (dictionary keys and scalar values), typically a few MB even for very large PDFs.
> I would choose `setupTempFileOnly()` when running inside a container with severely constrained heap (e.g., 256 MB JVM limit) processing multi-hundred-MB PDFs. The disk I/O overhead is worth it to avoid OOM errors. For typical server-side processing with 2–4 GB available heap, `setupMixed(100MB)` gives good performance with disk fallback safety."

#### Weak Answer
> "I would just use `setupMainMemoryOnly()` and set the JVM `-Xmx` flag high enough. Memory is cheap."
