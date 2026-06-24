# Module 06: Compression Profiles

---

## 1. Why This Module Exists

Individual optimization techniques — downsampling images, re-compressing Flate streams, converting color to grayscale — are powerful tools, but each requires a numeric parameter: a target DPI, a quality factor, a Deflater compression level. Hardcoding these values into a single function produces a brittle system with no reconfigurable behavior. When a customer asks, "can you preserve full print quality?" or "can you make this file as small as possible for email?", a hardcoded optimizer has no answer.

**Compression profiles** solve this problem by separating two concerns that are often incorrectly merged:
*   **What to optimize** (image streams, text streams, font programs, metadata).
*   **How aggressively to optimize** (quality settings, DPI targets, filter choices).

A profile is an immutable configuration object that bundles all quality-related parameters into a named, reusable unit. The optimization engine reads the profile and dispatches accordingly — it never decides quality on its own.

This architecture also enables the **Open/Closed Principle**: adding a new profile requires only creating a new configuration object, with zero modifications to the optimizer classes.

---

## 2. Learning Objectives

By the end of this module, you will be able to:
*   **Design** a `CompressionProfile` using Java enums and records.
*   **Implement** three profiles: Low, Recommended, and Extreme — with precise parameter sets.
*   **Build** a profile-aware stream router that dispatches each stream type to the correct optimizer with the correct settings.
*   **Apply** the Strategy behavioral pattern to decouple profile logic from optimization logic.
*   **Evaluate** the trade-offs of each profile across file size, visual quality, processing time, and compatibility dimensions.
*   **Extend** the system with a new profile without modifying any existing optimizer class.

---

## 3. Conceptual Foundations

### The Strategy Pattern
The Strategy pattern defines a family of algorithms, encapsulates each one, and makes them interchangeable. The optimizer (the **context**) delegates behavior to a profile object (the **strategy**), rather than embedding conditional logic internally.

```
┌──────────────────────────────────────────────────────────────────┐
│   PdfCompressionOrchestrator (Context)                           │
│                                                                  │
│   - profile: CompressionProfile (Strategy interface)            │
│   - imageOptimizer: ImageOptimizationPipeline                   │
│   - flateOptimizer: FlateStreamAnalyzer                         │
│                                                                  │
│   process(streamType, data):                                     │
│     profile.getImageDpi()    → pass to imageOptimizer           │
│     profile.getJpegQuality() → pass to imageOptimizer           │
│     profile.getDeflateLevel()→ pass to flateOptimizer           │
└──────────────────────────────────────────────────────────────────┘

Profile Implementations:
 ┌────────────────────┐  ┌────────────────────┐  ┌────────────────────┐
 │  LowCompression    │  │ RecommendedProfile │  │ ExtremeCompression │
 │  DPI: 300          │  │ DPI: 150           │  │ DPI: 96            │
 │  JPEG: 0.87        │  │ JPEG: 0.75         │  │ JPEG: 0.45         │
 │  Deflate: 1        │  │ Deflate: 6         │  │ Deflate: 9         │
 │  Grayscale: NO     │  │ Grayscale: NO      │  │ Grayscale: YES     │
 └────────────────────┘  └────────────────────┘  └────────────────────┘
```

### Profile as Immutable Configuration
A profile is a **value object** — it holds no mutable state and carries no behavioral logic beyond exposing its parameters. This is the key distinction: the profile does not know how to compress anything. It only knows what numbers to use. The optimizer classes know how to compress, and they ask the profile for parameters.

### Stream Classification
The orchestrator must classify each PDF stream before routing it, because different stream types require different optimization strategies:

```
Stream Object
     │
     ▼
[ Stream Classifier ]
     │
     ├──► Image Stream (DCTDecode, JPXDecode, FlateDecode + image color space)
     │         └──► ImageOptimizationPipeline
     │
     ├──► Text/Drawing Stream (FlateDecode + content operators)
     │         └──► FlateReEncoder
     │
     ├──► Font Stream (/FontFile, /FontFile2, /FontFile3)
     │         └──► FontPreservationRule (preserve or subset)
     │
     └──► Metadata/XMP Stream
               └──► Discard or preserve based on profile
```

---

## 4. Technical Topics

### 4.1 CompressionProfile Interface and Implementations

A `sealed interface` in Java 17+ cleanly constrains the set of valid profiles while allowing pattern matching:

```java
public sealed interface CompressionProfile
        permits LowCompression, RecommendedCompression, ExtremeCompression {

    /** Target DPI for image downsampling. */
    int getTargetDpi();

    /** JPEG quality for re-encoded image streams (0.0–1.0). */
    float getJpegQuality();

    /** java.util.zip.Deflater level for Flate stream re-compression (1–9). */
    int getDeflateLevel();

    /** Whether to convert color images to grayscale. */
    boolean isGrayscaleEnabled();

    /** Whether to strip XMP/document metadata streams. */
    boolean isMetadataStrippingEnabled();

    /** Human-readable name for logging and reporting. */
    String displayName();
}
```

### 4.2 Low Compression Profile

**Intent**: Maximize visual quality. Use when the document will be printed, shared with legal significance, or viewed at high zoom.

| Parameter | Value | Rationale |
| :--- | :--- | :--- |
| Target DPI | 300 | Full print quality; no visible degradation on paper |
| JPEG Quality | 0.87 | Excellent fidelity; minor size reduction from metadata stripping |
| Deflate Level | 1 (BEST_SPEED) | Re-compress Flate streams quickly; prioritize speed over ratio |
| Grayscale | No | Color must be preserved |
| Metadata Strip | No | Legal documents require XMP authorship metadata |

**Expected size reduction**: 10–25% (primarily from structural optimization and Flate re-encoding, not image downsampling).

### 4.3 Recommended Compression Profile

**Intent**: Balanced trade-off between quality and storage. Use for general business distribution — email attachments, shared reports, presentations.

| Parameter | Value | Rationale |
| :--- | :--- | :--- |
| Target DPI | 150 | Excellent screen readability; degradation only visible at 200%+ zoom |
| JPEG Quality | 0.75 | Strong compression; subtle softening imperceptible at normal reading |
| Deflate Level | 6 (DEFAULT) | Standard compression ratio with reasonable CPU cost |
| Grayscale | No | Color preserved; conversion only in Extreme profile |
| Metadata Strip | Optional | Strip non-essential metadata; preserve title and author |

**Expected size reduction**: 40–70%.

### 4.4 Extreme Compression Profile

**Intent**: Minimize file size at the cost of visual quality. Use for archival storage, large batch processing, mobile delivery with severe bandwidth constraints.

| Parameter | Value | Rationale |
| :--- | :--- | :--- |
| Target DPI | 96 | Screen-only viewing; blur visible at any zoom |
| JPEG Quality | 0.45 | Significant artifacts visible; acceptable for plain-text scan archiving |
| Deflate Level | 9 (BEST_COMPRESSION) | Maximum ratio; slower but run once for archival |
| Grayscale | Yes | 3× decoded memory reduction; 2–3× additional JPEG savings for color images |
| Metadata Strip | Yes | Remove all non-essential XMP streams |

**Expected size reduction**: 75–92%.

### 4.5 Per-Stream Routing Rules

| Stream Type | Low | Recommended | Extreme |
| :--- | :--- | :--- | :--- |
| JPEG image | Re-encode at 0.87, 300 DPI | Re-encode at 0.75, 150 DPI | Re-encode at 0.45, 96 DPI, grayscale |
| PNG/Flate image | Flate re-compress level 1 | Re-encode JPEG 0.75 or Flate 6 | Re-encode JPEG 0.45, 96 DPI, grayscale |
| Content stream | Flate level 1 | Flate level 6 | Flate level 9 |
| Font (subset) | Preserve | Preserve | Preserve |
| Font (full embed) | Preserve | Subset if possible | Subset aggressively |
| XMP Metadata | Preserve | Strip non-essential | Strip all |

---

## 5. Internal Mechanisms

### Profile Dispatch Pipeline

```
PdfCompressionOrchestrator.optimize(pdfPath, profile)
│
├── 1. Parse XRef table (RandomAccessFile, XRefResolver from Module 2)
│
├── 2. Enumerate all stream objects
│
├── 3. For each stream:
│   │
│   ├── 3a. Read /Filter, /ColorSpace, /BitsPerComponent dictionary entries
│   │
│   ├── 3b. Classify stream (StreamClassifier.classify(dict) → StreamType enum)
│   │
│   ├── 3c. Decompress using ChainedFilterDecoder (Module 4)
│   │
│   ├── 3d. Route to optimizer:
│   │       JPEG_IMAGE  → ImageOptimizationPipeline(profile.getDpi(), profile.getQuality())
│   │       FLATE_TEXT  → FlateReEncoder(profile.getDeflateLevel())
│   │       FONT        → FontPreservationRule.apply(fontStream, profile)
│   │       METADATA    → if profile.isMetadataStrippingEnabled() → drop else preserve
│   │
│   └── 3e. Write optimized bytes to output buffer
│
└── 4. Serialize output PDF with updated stream lengths and XRef table
```

### Cost Estimation Before Execution
Before processing begins, the orchestrator can produce a **cost estimate** — a prediction of how much each stream will shrink — without actually re-encoding anything. This is useful for:
*   Progress reporting (`"Estimated savings: 45 MB"`).
*   Skipping streams where savings would be negligible (< 1%).
*   Warning users about Extreme profile quality degradation before it happens.

The estimator uses empirical compression ratios derived from stream size and detected content type:
```java
long estimatedOutputSize = switch (streamType) {
    case JPEG_IMAGE  -> (long)(stream.compressedLength * dpiRatioSquared * qualityRatio);
    case FLATE_TEXT  -> (long)(stream.compressedLength * 0.90); // ~10% Flate improvement
    case FONT        -> stream.compressedLength; // Preserved
    case METADATA    -> profile.isMetadataStrippingEnabled() ? 0L : stream.compressedLength;
};
```

---

## 6. Trade-Off Analysis

### Complete Profile Comparison

| Dimension | Low Compression | Recommended | Extreme Compression |
| :--- | :--- | :--- | :--- |
| **Image DPI** | 300 | 150 | 96 |
| **JPEG Quality** | 0.87 | 0.75 | 0.45 |
| **Color Mode** | Color | Color | Grayscale |
| **Deflate Level** | 1 | 6 | 9 |
| **Expected Size Reduction** | 10–25% | 40–70% | 75–92% |
| **Visual Quality** | Near-lossless | Good | Acceptable for text |
| **Processing Speed** | Fastest | Moderate | Slowest |
| **Print-Friendly** | ✅ Yes | ⚠️ Limited | ❌ No |
| **Screen Readable** | ✅ Yes | ✅ Yes | ✅ Basic |
| **PDF/A Compatible** | ✅ Yes | ⚠️ Depends | ❌ Usually not |
| **Best Use Cases** | Legal, publishing | Business, email | Archival, storage |

---

## 7. Hands-On Exercises

### A. Beginner: Implement `CompressionProfile` as a Sealed Interface
*   Create the `CompressionProfile` sealed interface and three `record` implementations: `LowCompression`, `RecommendedCompression`, `ExtremeCompression`.
*   Each record should expose the five profile parameters as accessor methods.
*   Add a `static CompressionProfile fromName(String name)` factory method that resolves a profile by string (e.g., `"extreme"` → `ExtremeCompression`).

### B. Intermediate: Profile-Aware Stream Router
*   Implement `StreamRouter` with method `byte[] route(StreamType type, byte[] data, CompressionProfile profile)`.
*   For `JPEG_IMAGE`, delegate to `ImageOptimizationPipeline`.
*   For `FLATE_TEXT`, delegate to `FlateStreamAnalyzer.deflate(data, profile.getDeflateLevel())`.
*   For `FONT`, return `data` unchanged.
*   Write unit tests covering all three profile × stream-type combinations (9 test cases).

### C. Advanced: Pre-Execution Cost Estimator
*   Implement `CompressionEstimator.estimate(List<StreamDescriptor> streams, CompressionProfile profile)` that returns an `EstimationReport` containing:
    *   Total estimated bytes before and after.
    *   Per-stream type breakdown.
    *   Warning flags for any image that would be visually degraded below a quality threshold.

---

## 8. Mini Project: PdfCompressionOrchestrator

### Objective
Build a command-line tool that accepts a PDF path and a profile name, runs the full optimization pipeline, and reports a before/after comparison.

### Expected Output
```text
══════════════════════════════════════════════════════════════════
  PDF Compression Orchestrator
  File   : contract_scanned.pdf
  Profile: RECOMMENDED (150 DPI | JPEG 0.75 | Deflate 6)
══════════════════════════════════════════════════════════════════

  Analyzing streams...
  ┌──────────────────┬────────┬──────────────┬───────────────┐
  │ Stream Type      │ Count  │ Before       │ After         │
  ├──────────────────┼────────┼──────────────┼───────────────┤
  │ JPEG Images      │    23  │  98.4 MB     │  14.2 MB      │
  │ Text/Drawing     │    48  │   1.2 MB     │   1.0 MB      │
  │ Font Streams     │     6  │   0.8 MB     │   0.8 MB      │
  │ Metadata/XMP     │     2  │  12 KB       │   4 KB        │
  └──────────────────┴────────┴──────────────┴───────────────┘
  Total Before : 100.4 MB
  Total After  :  16.0 MB
  Reduction    :  84.4 MB (84.1%)
  Duration     :  12.4 seconds

══════════════════════════════════════════════════════════════════
```

### Java Implementation Code
Write to `c:\Users\Admin\Desktop\projects\learning-repo\courses\java\java-pdf-optimization-engine\src\main\java\com\example\pdf\orchestrator\PdfCompressionOrchestrator.java`:

```java
package com.example.pdf.orchestrator;

import com.example.pdf.image.ImageOptimizationPipeline;
import com.example.pdf.image.ImageOptimizationPipeline.GrayscaleMode;
import com.example.pdf.filters.FlateStreamAnalyzer;

import java.io.IOException;
import java.util.zip.Deflater;

/**
 * Profile-driven PDF compression orchestrator.
 *
 * Wires together stream classification, per-type optimization dispatch,
 * and reporting. In this scaffold, optimization is simulated — wire in
 * real PDFBox or OpenPDF stream access in Module 7 and 8.
 */
public class PdfCompressionOrchestrator {

    // ─── Profile Definition ───────────────────────────────────────────────────

    public sealed interface CompressionProfile
            permits LowCompression, RecommendedCompression, ExtremeCompression {
        int   getTargetDpi();
        float getJpegQuality();
        int   getDeflateLevel();
        boolean isGrayscaleEnabled();
        boolean isMetadataStrippingEnabled();
        String displayName();
    }

    public record LowCompression() implements CompressionProfile {
        public int   getTargetDpi()               { return 300; }
        public float getJpegQuality()             { return 0.87f; }
        public int   getDeflateLevel()            { return Deflater.BEST_SPEED; }
        public boolean isGrayscaleEnabled()       { return false; }
        public boolean isMetadataStrippingEnabled(){ return false; }
        public String displayName()               { return "LOW (300 DPI | JPEG 0.87 | Deflate 1)"; }
    }

    public record RecommendedCompression() implements CompressionProfile {
        public int   getTargetDpi()               { return 150; }
        public float getJpegQuality()             { return 0.75f; }
        public int   getDeflateLevel()            { return Deflater.DEFAULT_COMPRESSION; }
        public boolean isGrayscaleEnabled()       { return false; }
        public boolean isMetadataStrippingEnabled(){ return true; }
        public String displayName()               { return "RECOMMENDED (150 DPI | JPEG 0.75 | Deflate 6)"; }
    }

    public record ExtremeCompression() implements CompressionProfile {
        public int   getTargetDpi()               { return 96; }
        public float getJpegQuality()             { return 0.45f; }
        public int   getDeflateLevel()            { return Deflater.BEST_COMPRESSION; }
        public boolean isGrayscaleEnabled()       { return true; }
        public boolean isMetadataStrippingEnabled(){ return true; }
        public String displayName()               { return "EXTREME (96 DPI | JPEG 0.45 | Deflate 9 | Grayscale)"; }
    }

    // ─── Stream Type Enum ─────────────────────────────────────────────────────

    public enum StreamType { JPEG_IMAGE, PNG_IMAGE, FLATE_TEXT, FONT, METADATA, UNKNOWN }

    // ─── Optimization Report ──────────────────────────────────────────────────

    public record StreamResult(StreamType type, long beforeBytes, long afterBytes) {}

    // ─── Core Optimization Method ─────────────────────────────────────────────

    /**
     * Optimize a single stream based on its type and the active profile.
     *
     * @param type    Detected stream type
     * @param data    Raw (decompressed) stream bytes
     * @param originalDpi DPI of source image (for image streams)
     * @param profile Active compression profile
     * @return        Optimized compressed bytes
     */
    public byte[] optimizeStream(StreamType type, byte[] data,
                                 int originalDpi, CompressionProfile profile)
            throws IOException {
        return switch (type) {
            case JPEG_IMAGE, PNG_IMAGE -> {
                GrayscaleMode gm = profile.isGrayscaleEnabled()
                        ? GrayscaleMode.CONVERT_GRAYSCALE
                        : GrayscaleMode.KEEP_COLOR;
                ImageOptimizationPipeline pipeline = new ImageOptimizationPipeline(
                        originalDpi, profile.getTargetDpi(), profile.getJpegQuality(), gm);
                yield pipeline.process(data);
            }
            case FLATE_TEXT -> FlateStreamAnalyzer.deflate(data, profile.getDeflateLevel());
            case FONT       -> data; // Preserve font streams
            case METADATA   -> profile.isMetadataStrippingEnabled() ? new byte[0] : data;
            case UNKNOWN    -> data;
        };
    }

    // ─── Profile Factory ──────────────────────────────────────────────────────

    public static CompressionProfile fromName(String name) {
        return switch (name.trim().toLowerCase()) {
            case "low"     -> new LowCompression();
            case "extreme" -> new ExtremeCompression();
            default        -> new RecommendedCompression();
        };
    }

    // ─── Reporting Utility ────────────────────────────────────────────────────

    public static void printReport(String filename, CompressionProfile profile,
                                   java.util.List<StreamResult> results, long durationMs) {
        long totalBefore = results.stream().mapToLong(StreamResult::beforeBytes).sum();
        long totalAfter  = results.stream().mapToLong(StreamResult::afterBytes).sum();
        double reduction = totalBefore == 0 ? 0 : (double)(totalBefore - totalAfter) / totalBefore * 100;

        System.out.println("\n══════════════════════════════════════════════════════════════════");
        System.out.println("  PDF Compression Orchestrator");
        System.out.printf( "  File   : %s%n", filename);
        System.out.printf( "  Profile: %s%n", profile.displayName());
        System.out.println("══════════════════════════════════════════════════════════════════");
        System.out.println("\n  Analyzing streams...");
        System.out.println("  ┌──────────────────┬────────┬──────────────┬───────────────┐");
        System.out.println("  │ Stream Type      │ Count  │ Before       │ After         │");
        System.out.println("  ├──────────────────┼────────┼──────────────┼───────────────┤");

        for (StreamType t : StreamType.values()) {
            long before = results.stream().filter(r -> r.type() == t).mapToLong(StreamResult::beforeBytes).sum();
            long after  = results.stream().filter(r -> r.type() == t).mapToLong(StreamResult::afterBytes).sum();
            long count  = results.stream().filter(r -> r.type() == t).count();
            if (count == 0) continue;
            System.out.printf("  │ %-16s │ %6d │ %12s │ %13s │%n",
                    t.name(), count,
                    humanBytes(before), humanBytes(after));
        }

        System.out.println("  └──────────────────┴────────┴──────────────┴───────────────┘");
        System.out.printf( "  Total Before : %s%n", humanBytes(totalBefore));
        System.out.printf( "  Total After  : %s%n", humanBytes(totalAfter));
        System.out.printf( "  Reduction    : %s (%.1f%%)%n", humanBytes(totalBefore - totalAfter), reduction);
        System.out.printf( "  Duration     : %.1f seconds%n", durationMs / 1000.0);
        System.out.println("\n══════════════════════════════════════════════════════════════════\n");
    }

    private static String humanBytes(long bytes) {
        if (bytes >= 1_048_576) return String.format("%.1f MB", bytes / 1_048_576.0);
        if (bytes >= 1024)      return String.format("%.1f KB", bytes / 1024.0);
        return bytes + " B";
    }

    // ─── Entry Point ──────────────────────────────────────────────────────────

    public static void main(String[] args) {
        if (args.length < 2) {
            System.out.println("Usage: PdfCompressionOrchestrator <pdf-path> <profile: low|recommended|extreme>");
            return;
        }
        CompressionProfile profile = fromName(args[1]);
        System.out.println("\nLoaded profile: " + profile.displayName());
        System.out.println("→ Wire PDFBox stream extraction (Module 7) to complete the pipeline.");
    }
}
```

---

## 9. Common Mistakes

### 1. Hardcoding Quality Values Instead of Using Profiles
*   *Symptom*: Every optimization call has `0.75f` and `150` scattered across the codebase. Changing the "recommended" quality requires a multi-file grep.
*   *Prevention*: All quality parameters must flow through a `CompressionProfile`. The optimizer classes must never contain a numeric quality literal.

### 2. Applying Image Optimization to Font Streams
*   *Symptom*: The output PDF renders with garbage characters or missing glyphs.
*   *Cause*: The stream classifier incorrectly identifies a `/FontFile2` (TrueType font program) stream as a binary image due to its high byte entropy and routes it through `ImageOptimizationPipeline`.
*   *Prevention*: Check the parent dictionary's `/Type` and `/Subtype` before classification. A stream with a parent `/FontDescriptor` dictionary must always be routed to `FONT`, regardless of its byte content.

### 3. Stripping PDF/A Metadata Under Extreme Profile
*   *Symptom*: Legal clients reject the optimized PDF because it no longer passes PDF/A validation.
*   *Cause*: The Extreme profile's `isMetadataStrippingEnabled() = true` removes the XMP stream containing the `pdfaid:conformance` and `pdfaid:part` metadata fields required for PDF/A compliance.
*   *Prevention*: Before stripping metadata, detect PDF/A conformance by checking for the `/OutputIntents` dictionary in the document catalog and the `pdfaid:` namespace in the XMP stream. If detected, disable metadata stripping regardless of profile.

---

## 10. Assessment

### Quiz
1.  **Which design pattern does the `CompressionProfile` interface implement?**
    *   A. Observer
    *   B. Strategy
    *   C. Decorator
    *   D. Factory Method

2.  **You add a `UltraHighFidelity` profile to the system. Which existing classes must you modify?**
    *   A. `ImageOptimizationPipeline`, `FlateStreamAnalyzer`, and `PdfCompressionOrchestrator`
    *   B. Only `PdfCompressionOrchestrator`
    *   C. Only the `CompressionProfile` sealed interface (add a new `permits` entry) and the new profile record itself
    *   D. Only the stream router's `switch` statement

3.  **A font stream is erroneously routed to the JPEG image optimizer. What is the most likely observable symptom?**
    *   A. The font renders slightly smaller.
    *   B. The PDF file size increases.
    *   C. The output PDF displays garbled characters or missing glyphs.
    *   D. The PDF fails to open with an XRef error.

### Design Question
A new requirement arrives: images smaller than 50 KB should never be downsampled, regardless of profile, because the CPU overhead is not justified. Design the change. Where in the architecture does this rule live — in the profile, the router, or the `ImageOptimizationPipeline`? Justify your answer using the Single Responsibility Principle.

---

## 11. Interview Perspective

### Common Interview Question
> "How would you design a PDF optimization library so that adding a new compression profile requires zero changes to existing optimizer classes?"

### Expected Reasoning
*   Define a `CompressionProfile` interface (or sealed interface) that all optimizer classes accept as a parameter.
*   Each optimizer reads parameters exclusively from the profile — no internal defaults.
*   New profiles implement the interface and provide their own parameter values.
*   Existing optimizer code is never touched. This is the Open/Closed Principle.

### Sample Answers

#### Strong Answer
> "I would define a `CompressionProfile` sealed interface with accessor methods like `getTargetDpi()`, `getJpegQuality()`, and `getDeflateLevel()`. The optimizer classes accept a `CompressionProfile` parameter and call these methods — they never contain numeric literals.
> To add a new profile, I create a new `record` implementing the interface. Zero existing code changes.
> If I want to validate that all sealed subtypes are handled at compile time, I can use a `switch` expression with pattern matching — the Java compiler will reject exhaustiveness if I add a new subtype without updating the switch, giving me a compile-time safety net."

#### Weak Answer
> "I would add an `if-else` chain in the optimizer that checks the profile name string. For each new profile, I'd add another branch. Eventually I'd refactor the chain into a map."
