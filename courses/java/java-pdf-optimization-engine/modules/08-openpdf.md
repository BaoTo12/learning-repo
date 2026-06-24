# Module 08: OpenPDF

---

## 1. Why This Module Exists

Apache PDFBox excels at traversing and modifying the semantic content of existing PDFs — fonts, images, text, page geometry. But its save mechanism does not expose fine-grained control over structural compression decisions: how many objects go into an object stream, whether to force specific XRef stream encodings, or how to re-pack a complex object graph for maximum structural compaction.

**OpenPDF** — the Apache-licensed fork of iText 2.1.7 — takes a different approach. Its **stamper model** treats an existing PDF as an immutable base and appends modifications as a delta layer. Its compression pipeline provides a `setFullCompression()` switch that, in a single call, enables object stream compression across the entire document at save time.

For a PDF optimizer engineer, this makes OpenPDF the preferred choice when:
*   The primary goal is **structural size reduction** (compressing object dictionaries, removing cross-reference table overhead).
*   You need direct access to a PDF's raw `PdfObject` tree without the abstraction of a `PD*` wrapper layer.
*   You are building a **two-pass pipeline**: PDFBox for image manipulation → OpenPDF for structural finalization.

This module teaches you the OpenPDF API surface, its internal save pipeline, and how to combine it with PDFBox in a hybrid architecture.

---

## 2. Learning Objectives

By the end of this module, you will be able to:
*   **Read** an existing PDF using `PdfReader` with memory-aware loading.
*   **Apply** modifications using `PdfStamper` and commit the result.
*   **Enable** full structural compression with `setFullCompression()`.
*   **Iterate** all PDF objects using `PdfReader.getXrefSize()` and type-dispatch on `PdfObject`.
*   **Understand** the two-pass save mechanism: object serialization → object stream compression.
*   **Compare** OpenPDF and PDFBox across all relevant engineering dimensions.
*   **Design** a hybrid pipeline that uses PDFBox for image optimization and OpenPDF for structural finalization.

---

## 3. Conceptual Foundations

### The Stamper Model
PDFBox uses a DOM-like approach: you load a document, mutate objects in place, then save. OpenPDF uses a **stamper model**: the `PdfReader` is treated as a read-only data source. The `PdfStamper` streams modifications on top of the original content and writes the combined result to an output stream.

```
                    PDFBox Model
                    ────────────
  [Original PDF] ──► PDDocument ──► Mutate in place ──► save()


                    OpenPDF Stamper Model
                    ─────────────────────
  [Original PDF] ──► PdfReader (immutable)
                          │
                          └──► PdfStamper ──► apply modifications ──► close() → output
```

This model has important implications:
*   **PdfReader** state is not to be modified. Modifying reader-owned objects directly can corrupt the output.
*   **PdfStamper.close()** is the commit operation — it triggers the write pipeline. Without it, the output stream is incomplete and the output file is corrupt.

### Object Stream Compression (PDF 1.5+)
Uncompressed PDF files store each object as a plain-text block:
```
4 0 obj
<< /Type /Page /MediaBox [0 0 595 842] /Parent 2 0 R >>
endobj
```

PDF 1.5 introduced **object streams** (`/ObjStm`): a mechanism to pack multiple small objects (typically dictionary objects) into a single compressed stream. OpenPDF's `setFullCompression()` activates this grouping at save time:

```
Before (uncompressed):
  Object 4: 68 bytes (plain text dictionary)
  Object 5: 72 bytes
  Object 6: 91 bytes
  Object 7: 55 bytes

After (setFullCompression):
  ObjStm stream: 112 bytes (all four objects, FlateDecode-compressed)
  Net overhead reduction: 68+72+91+55=286 bytes → 112 bytes (61% reduction for this group)
```

For text-heavy documents with thousands of small dictionaries, this can reduce file size by 15–30%.

---

## 4. Technical Topics

### 4.1 PdfReader

```java
// Load from file path
PdfReader reader = new PdfReader("input.pdf");

// Load with memory limits (prevents heap OOM on huge PDFs)
PdfReader reader = new PdfReader("input.pdf",
        new ReaderProperties().setMemoryLimitsAwareHandler(
                new MemoryLimitsAwareHandler()));

// Key reader methods:
int pages   = reader.getNumberOfPages();     // Total page count
int xrefSz  = reader.getXrefSize();          // Total object count
PdfDictionary pageDict = reader.getPageN(1); // Page dictionary (1-indexed!)
```

**Important**: OpenPDF page numbers are **1-indexed** (page 1 = first page). PDFBox uses **0-indexed** pages.

### 4.2 PdfStamper

```java
ByteArrayOutputStream baos = new ByteArrayOutputStream();
PdfStamper stamper = new PdfStamper(reader, baos);

// Enable structural compression
stamper.setFullCompression();

// Set compression level for all streams written by the stamper
stamper.getWriter().setCompressionLevel(PdfStream.BEST_COMPRESSION);

// Apply modifications here (annotations, form fields, etc.)

// Commit — this triggers the full write pipeline
stamper.close();
reader.close();

byte[] outputBytes = baos.toByteArray();
```

### 4.3 Object Enumeration via XRef

The XRef table in OpenPDF maps object numbers to file positions. `getXrefSize()` returns the total number of entries (including free objects):

```java
PdfReader reader = new PdfReader("input.pdf");
int xrefSize = reader.getXrefSize();

for (int objNum = 1; objNum < xrefSize; objNum++) {
    PdfObject obj = reader.getPdfObject(objNum);
    if (obj == null) continue; // Free or cross-reference entry

    System.out.printf("Object %d: type=%s%n", objNum, pdfTypeName(obj));

    if (obj.isStream()) {
        PRStream stream = (PRStream) obj;
        PdfObject filterObj = stream.get(PdfName.FILTER);
        System.out.printf("  Filter: %s, Length: %d%n",
                filterObj, PdfReader.getStreamBytesRaw(stream).length);
    }
}
```

### 4.4 PdfObject Type System

| `PdfObject` Type Constant | Class | Corresponds To (PDF Spec) |
| :--- | :--- | :--- |
| `PdfObject.STREAM` | `PRStream` | Stream object |
| `PdfObject.DICTIONARY` | `PdfDictionary` | Dictionary `<< ... >>` |
| `PdfObject.ARRAY` | `PdfArray` | Array `[ ... ]` |
| `PdfObject.STRING` | `PdfString` | String literal |
| `PdfObject.NAME` | `PdfName` | Name object `/Name` |
| `PdfObject.NUMBER` | `PdfNumber` | Integer or Real |
| `PdfObject.BOOLEAN` | `PdfBoolean` | `true` / `false` |
| `PdfObject.NULL` | `PdfNull` | `null` |

Type dispatch pattern:
```java
if (obj instanceof PRStream stream) {
    byte[] rawBytes = PdfReader.getStreamBytesRaw(stream);
    byte[] decoded  = PdfReader.getStreamBytes(stream);  // Auto-decompresses
}
```

### 4.5 Structural Optimization Pass

OpenPDF's most powerful structural optimization feature is enabling full compression at the writer level before stamping:

```java
public static byte[] structurallyOptimize(byte[] inputPdfBytes) throws IOException {
    PdfReader reader = new PdfReader(inputPdfBytes);
    ByteArrayOutputStream baos = new ByteArrayOutputStream();
    PdfStamper stamper = new PdfStamper(reader, baos);

    stamper.setFullCompression();
    stamper.getWriter().setCompressionLevel(PdfStream.BEST_COMPRESSION);

    stamper.close();
    reader.close();
    return baos.toByteArray();
}
```

This single method can reduce a structurally unoptimized PDF (e.g., one produced by an old desktop publisher that writes uncompressed cross-reference tables and object dictionaries) by 10–30%.

---

## 5. Internal Mechanisms

### OpenPDF Two-Pass Save Pipeline

```
PdfStamper.close()
│
├── Pass 1: Object Serialization
│   │
│   ├── Visit all objects in PdfReader's XRef table
│   ├── Apply any pending modifications (stamper overlay)
│   ├── Classify each object:
│   │   ├── Large stream (image, font, content) → write directly to output
│   │   └── Small dictionary / scalar → candidate for ObjStm grouping
│   └── Write large objects with running byte offset tracking
│
├── Pass 2: Object Stream Compression (only when setFullCompression() active)
│   │
│   ├── Group small objects into ObjStm blocks (default: 200 objects/block)
│   ├── FlateDecode-compress each ObjStm block
│   └── Write compressed ObjStm blocks to output
│
├── Write Cross-Reference Stream (compressed XRef for PDF 1.5+)
│   └── 3-column binary XRef: [type | offset | gen_num]
│
└── Write Trailer + startxref + %%EOF
```

### How `setFullCompression()` Affects the XRef Structure
Traditional PDFs use a plaintext cross-reference table:
```
xref
0 8
0000000000 65535 f
0000000015 00000 n
0000000068 00000 n
...
```

With `setFullCompression()`, the XRef is replaced by a **cross-reference stream** — itself a compressed object stream that packs the XRef data more densely. This can reduce XRef overhead from several KB to a few hundred bytes for large documents.

---

## 6. Trade-Off Analysis: OpenPDF vs. Apache PDFBox

| Dimension | Apache PDFBox 3.x | OpenPDF 1.3.x |
| :--- | :--- | :--- |
| **License** | Apache 2.0 | LGPL 2.1 / MPL 1.1 |
| **API Style** | High-level `PD*` objects + low-level COS | Stamper model + raw `PdfObject` tree |
| **Image Extraction** | ✅ First-class via `PDImageXObject.getImage()` | ⚠️ Manual via `PdfReader.getStreamBytes()` + `ImageIO` |
| **Object Stream Compression** | ✅ Via `CompressParameters.DEFAULT_COMPRESSION` | ✅ Via `setFullCompression()` (more configurable) |
| **XRef Stream Compression** | ✅ Automatic on save | ✅ Active with `setFullCompression()` |
| **Thread Safety** | ❌ Not thread-safe | ❌ Not thread-safe |
| **PDF/A Support** | ✅ Validator and creation support | ⚠️ Limited |
| **Incremental Save** | ✅ `saveIncremental()` | ✅ Default stamper behavior |
| **Memory Control** | ✅ `MemoryUsageSetting` with scratch file | ✅ `MemoryLimitsAwareHandler` |
| **Best For** | Content editing, image manipulation, rendering | Structural rewriting, compression, form-fill |
| **Production Maturity** | Very high — Apache top-level project | High — widely used in enterprise Java |

### Hybrid Pipeline Pattern

For maximum compression, combine both libraries:

```
Stage 1 (PDFBox):
  PDFBoxImageOptimizer → downsample + re-encode all image streams
  → Save to intermediate byte array

Stage 2 (OpenPDF):
  structurallyOptimize(intermediateBytes)
  → setFullCompression() → compress object dictionaries + XRef
  → Save final output

Result: best-of-both — image compression from PDFBox, structural compression from OpenPDF
```

---

## 7. Hands-On Exercises

### A. Beginner: Open PDF and Print Object Count
*   Create a `PdfReader` from a file path.
*   Print `getXrefSize()` (total XRef entries) and `getNumberOfPages()`.
*   List the `/Filter` value for each stream object found by iterating XRef entries.

### B. Intermediate: Enable Full Compression and Measure Delta
*   Load a PDF with `PdfReader`.
*   Stamp it with `setFullCompression()` and `PdfStream.BEST_COMPRESSION`.
*   Output the before/after file sizes in bytes.
*   Run on three different PDFs and report which document type benefits most.

### C. Advanced: Orphaned Object Removal
*   Re-implement the orphaned object removal logic from Module 3 (objects reachable from the document catalog vs. all objects in XRef).
*   Use OpenPDF's `PdfReader.getPdfObject(n)` to enumerate all objects.
*   Build a reachability set by following dictionary values and array elements recursively.
*   Report which object numbers are unreachable from the root.

---

## 8. Mini Project: OpenPdfStructuralOptimizer

### Objective
Build a structural optimization pass using OpenPDF that applies full compression and reports size metrics.

### Maven Dependency
```xml
<dependency>
    <groupId>com.github.librepdf</groupId>
    <artifactId>openpdf</artifactId>
    <version>1.3.35</version>
</dependency>
```

### Java Implementation Code
Write to `src/main/java/com/example/pdf/openpdf/OpenPdfStructuralOptimizer.java`:

```java
package com.example.pdf.openpdf;

import com.lowagie.text.pdf.PdfName;
import com.lowagie.text.pdf.PdfObject;
import com.lowagie.text.pdf.PdfReader;
import com.lowagie.text.pdf.PdfStamper;
import com.lowagie.text.pdf.PdfStream;
import com.lowagie.text.pdf.PRStream;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.IOException;
import java.nio.file.Files;

public class OpenPdfStructuralOptimizer {

    /**
     * Apply full structural compression to a PDF byte array.
     * This enables object stream compression (PDF 1.5+) and
     * cross-reference stream compression, replacing the plain-text
     * XRef table with a compact binary representation.
     *
     * @param inputBytes  Raw bytes of the input PDF
     * @return            Compressed output PDF bytes
     */
    public static byte[] structurallyOptimize(byte[] inputBytes) throws IOException {
        PdfReader reader = new PdfReader(inputBytes);
        ByteArrayOutputStream baos = new ByteArrayOutputStream();

        PdfStamper stamper = new PdfStamper(reader, baos);
        stamper.setFullCompression();
        stamper.getWriter().setCompressionLevel(PdfStream.BEST_COMPRESSION);

        // Close triggers the two-pass write pipeline
        stamper.close();
        reader.close();

        return baos.toByteArray();
    }

    /**
     * Enumerate all stream objects in a PDF and classify them by filter type.
     *
     * @param inputBytes  Raw bytes of the input PDF
     */
    public static void inspectStreams(byte[] inputBytes) throws IOException {
        PdfReader reader = new PdfReader(inputBytes);
        int xrefSize = reader.getXrefSize();

        System.out.println("\n══════════════════════════════════════════════════");
        System.out.printf( "  Stream Inspector: %d XRef entries%n", xrefSize);
        System.out.println("══════════════════════════════════════════════════");

        long totalCompressedBytes = 0;
        int streamCount = 0;

        for (int i = 1; i < xrefSize; i++) {
            PdfObject obj = reader.getPdfObject(i);
            if (obj == null || !obj.isStream()) continue;

            PRStream stream = (PRStream) obj;
            PdfObject filterObj = stream.get(PdfName.FILTER);
            byte[] rawBytes = PdfReader.getStreamBytesRaw(stream);
            long len = rawBytes != null ? rawBytes.length : 0;

            System.out.printf("  Object %4d | %-20s | %,8d bytes%n",
                    i, filterObj != null ? filterObj.toString() : "(none)", len);
            totalCompressedBytes += len;
            streamCount++;
        }

        System.out.println("──────────────────────────────────────────────────");
        System.out.printf( "  Total streams:        %d%n", streamCount);
        System.out.printf( "  Total compressed size: %,d bytes%n", totalCompressedBytes);
        System.out.println("══════════════════════════════════════════════════\n");

        reader.close();
    }

    public static void main(String[] args) throws IOException {
        if (args.length < 2) {
            System.out.println("Usage: OpenPdfStructuralOptimizer <input.pdf> <output.pdf>");
            return;
        }

        File input  = new File(args[0]);
        File output = new File(args[1]);

        byte[] inputBytes = Files.readAllBytes(input.toPath());
        System.out.printf("Input:  %s (%,d bytes)%n", input.getName(), inputBytes.length);

        // Optional: inspect streams before optimization
        inspectStreams(inputBytes);

        long start = System.currentTimeMillis();
        byte[] outputBytes = structurallyOptimize(inputBytes);
        long duration = System.currentTimeMillis() - start;

        Files.write(output.toPath(), outputBytes);

        long saved = inputBytes.length - outputBytes.length;
        double pct = (double) saved / inputBytes.length * 100;

        System.out.printf("Output: %s (%,d bytes)%n", output.getName(), outputBytes.length);
        System.out.printf("Saved:  %,d bytes (%.1f%%)%n", saved, pct);
        System.out.printf("Time:   %.2f seconds%n", duration / 1000.0);
    }
}
```

---

## 9. Common Mistakes

### 1. Forgetting to Call `PdfStamper.close()`
*   *Symptom*: The output file is present but corrupt — PDF readers report "invalid PDF structure" or "unexpected end of file."
*   *Cause*: `close()` is the commit operation. Without it, the XRef table, trailer, and `%%EOF` marker are never written. The output stream contains only a partial document body.
*   *Prevention*: Always use a `try-finally` block or ensure `close()` is in a `finally` clause, even on exception paths. `PdfStamper` does not implement `AutoCloseable` in older OpenPDF versions — do not assume `try-with-resources` works unless you verify the version.

### 2. Calling `setFullCompression()` on Documents with PDF Version < 1.5
*   *Symptom*: The method call appears to succeed with no error, but the output file is no smaller than the input.
*   *Cause*: Object streams and XRef streams are PDF 1.5+ features. If the reader/writer is operating in PDF 1.4 compatibility mode, `setFullCompression()` is silently ignored.
*   *Prevention*: Check the PDF version from the reader: `reader.getPdfVersion()`. If it returns '4' (PDF 1.4) or lower, either upgrade the document version or accept that full compression cannot be applied.

### 3. Mutating a `PdfReader`-Owned Object Directly
*   *Symptom*: The output PDF contains corrupted data, or certain pages fail to render.
*   *Cause*: `PdfReader` parses objects lazily and caches them. Modifying a cached `PdfDictionary` or `PRStream` directly alters the read-side cache, which the stamper will then serialize in an inconsistent state.
*   *Prevention*: Never modify `PdfReader`-owned objects in place. Always create new `PdfObject` instances for values you want to change and use the stamper API to overlay them.

---

## 10. Assessment

### Quiz
1.  **In OpenPDF, which method call triggers the actual write of the output PDF to the stream?**
    *   A. `PdfReader.close()`
    *   B. `PdfStamper.flush()`
    *   C. `PdfStamper.close()`
    *   D. `PdfWriter.commit()`

2.  **What is the primary mechanism by which `setFullCompression()` reduces PDF file size?**
    *   A. It downsamples all embedded JPEG images.
    *   B. It groups multiple small object dictionaries into compressed object stream blocks.
    *   C. It strips all metadata from the document information dictionary.
    *   D. It removes all incremental update sections and linearizes the document.

3.  **You have a PDF that must remain digitally signed and valid after optimization. Which approach is correct?**
    *   A. Use `PdfStamper` in append mode (incremental update), which preserves the original byte range of the existing signature.
    *   B. Use `setFullCompression()`, which automatically detects and preserves digital signatures.
    *   C. Remove the digital signature before optimization and re-sign after.
    *   D. Use `PDDocument.save()` in PDFBox which never modifies signature byte ranges.

### Design Question
You need to build a two-stage pipeline where Stage 1 (PDFBox) optimizes images and Stage 2 (OpenPDF) applies structural compression. Design the interface between the two stages. What data type flows from Stage 1 to Stage 2? Why is a `byte[]` preferred over a `File` for the intermediate representation?

---

## 11. Interview Perspective

### Common Interview Question
> "When would you choose OpenPDF over PDFBox for a high-volume server-side PDF optimizer?"

### Sample Answers

#### Strong Answer
> "I would choose OpenPDF when the primary optimization goal is structural — compressing object dictionaries and the XRef table using PDF 1.5 object streams. OpenPDF's `setFullCompression()` activates this in one call and is simpler to wire into a pipeline than PDFBox's `CompressParameters`.
>
> For image manipulation, PDFBox is the better choice because `PDImageXObject.getImage()` gives me a `BufferedImage` directly, while OpenPDF requires manual stream byte extraction and `ImageIO` decoding.
>
> In a high-volume server context, I would combine them: PDFBox for the image optimization pass, producing an intermediate byte array, then OpenPDF's structural optimizer running on that byte array to compact the object graph. Both libraries are not thread-safe, so I would use a bounded thread pool with one `PdfReader`/`PdfStamper` pair per worker thread, never sharing instances across threads."

#### Weak Answer
> "OpenPDF is older and smaller, so it uses less memory. I would pick it when memory is tight and just call `setFullCompression()` on everything."
