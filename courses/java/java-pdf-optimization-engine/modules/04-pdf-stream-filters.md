# Module 04: PDF Stream Filters

---

## 1. Why This Module Exists

A PDF stream filter is the compression or encoding algorithm applied to the binary data inside a stream object. Every large payload in a PDF — whether it is a photographic image, a page of vector drawing commands, a font program, or a metadata block — is wrapped in a stream dictionary that declares which filter algorithm was used to encode its bytes.

You cannot optimize a PDF's compression without first understanding which filters are already applied, why they were chosen, and what rules govern when you can safely re-encode them. This module bridges the theoretical compression concepts from Module 1 with the practical object model from Module 3.

By the end of this module, you will be able to:
*   Identify every filter type used inside a PDF by its dictionary key.
*   Understand the algorithm behind each filter, why it was designed, and what content type it targets.
*   Safely decompress and re-compress streams as part of an optimization pipeline.
*   Evaluate the critical trade-off between lossless and lossy compression at each decision point in your engine.

This knowledge is the direct prerequisite for all downstream optimization work: you cannot re-encode a JPEG image without knowing how to detect `/DCTDecode`, decompress its stream using JPEG decoding, downsample the pixel buffer, and write it back with a new `/DCTDecode` filter. Every image optimization step depends entirely on understanding these filters first.

---

## 2. Learning Objectives

By the end of this module, you will be able to:
*   **Identify** all seven PDF stream filter types from their dictionary keys and explain the algorithm they represent.
*   **Implement** lossless Flate stream decompression and compression in Java using `java.util.zip.Inflater` and `Deflater`.
*   **Implement** PNG row predictor encoding and decoding (Sub, Up, Average, Paeth) as a pre-processing stage for FlateDecode.
*   **Compare** lossless and lossy filter classes across all dimensions: compression ratio, quality loss, reversibility, and target payload type.
*   **Design** a filter detection and routing engine in Java that reads a stream's `/Filter` dictionary and dispatches to the correct decompressor.
*   **Evaluate** which filters should be preserved, re-encoded, or converted during an optimization pass.

---

## 3. Conceptual Foundations

### What Is a Stream Filter?
In the PDF specification, a **filter** is a transformation applied to a stream's raw binary data before it is written to the file. When a reader loads the stream, it applies the **inverse** transformation to recover the original data.

```
                  Encoding (Write Time)
                  ──────────────────────
Raw Data ───────► [ Filter Algorithm ] ───────► Compressed Bytes in PDF File
                  
                  Decoding (Read Time)
                  ──────────────────────
Compressed Bytes in PDF ───► [ Inverse Algorithm ] ───► Recovered Raw Data
```

A stream dictionary declares its filter using the `/Filter` key. Multiple chained filters are allowed, listed in application order as an array:
```
<< /Filter [/ASCII85Decode /FlateDecode] /Length 4120 >>
stream
... binary bytes ...
endstream
```

Here, the raw bytes were first compressed by Flate, then encoded as ASCII85. A decoder must reverse this chain in the opposite order: first ASCII85Decode, then FlateDecode.

### Lossless vs. Lossy: The Fundamental Divide
Every filter belongs to exactly one of two classes:

```
┌─────────────────────────────────────────────────────────────────────┐
│                       FILTER CLASSIFICATION                         │
├───────────────────────────────────┬─────────────────────────────────┤
│         LOSSLESS                  │          LOSSY                  │
│ Exact byte-perfect reconstruction │ Irreversible data loss          │
│ Lower compression ratio           │ Very high compression ratio     │
├───────────────────────────────────┼─────────────────────────────────┤
│ FlateDecode (zlib/deflate)        │ DCTDecode (JPEG)                │
│ LZWDecode                         │ JPXDecode (JPEG 2000)           │
│ RunLengthDecode                   │                                 │
│ CCITTFaxDecode                    │                                 │
│ JBIG2Decode (mostly lossless)     │                                 │
└───────────────────────────────────┴─────────────────────────────────┘
```

The optimization engine's core decision at every image stream is: **can this content tolerate quality loss?** Photographs can. Text, line art, signatures, and QR codes typically cannot.

---

## 4. Technical Topics

### 4.1 FlateDecode
**Algorithm**: DEFLATE (LZ77 sliding-window dictionary + Huffman entropy coding), wrapped in the zlib framing format (2-byte header + Adler-32 checksum).

**In the PDF dictionary**:
```
<< /Filter /FlateDecode /Length 8421 >>
```

**What it compresses**:
*   Page content streams (text positioning commands, line drawing operators like `m`, `l`, `B`, `f`).
*   Font programs (CFF/Type1 glyph outlines).
*   Object streams (PDF 1.5+ feature to compress many object dictionaries into a single Flate block).
*   XRef streams (the Cross-Reference table itself, as of PDF 1.5).
*   Any image data that must be preserved exactly (lossless graphics, diagrams, screenshots of text).

**Predictor Sub-parameter** (`/DecodeParms`):
Flate-compressed image data often uses **PNG row predictors** as a pre-processing step to maximize entropy reduction before deflating. The predictor sub-parameter specifies which row-delta algorithm was applied:

| Predictor Value | Algorithm | Description |
| :--- | :--- | :--- |
| 1 | None | Raw bytes, no pre-filtering. |
| 10 | PNG None | Row stored as-is. |
| 11 | PNG Sub | Each byte encodes the difference from the byte one pixel to the left. |
| 12 | PNG Up | Each byte encodes the difference from the byte directly above. |
| 13 | PNG Average | Each byte encodes the difference from the average of left and above. |
| 14 | PNG Paeth | Each byte encodes the difference using the Paeth nonlinear predictor. |
| 15 | PNG Optimal | Encoder selected the best algorithm row-by-row. Decoder must read the per-row filter byte. |

**Java APIs**: `java.util.zip.Inflater` (decompress), `java.util.zip.Deflater` (compress).

---

### 4.2 DCTDecode
**Algorithm**: Discrete Cosine Transform (DCT), the core mathematical operation behind JPEG compression.

**How DCT works** (conceptual):
1.  The pixel buffer is divided into 8×8 blocks.
2.  Each block's pixels are transformed from spatial domain (pixel values) to frequency domain (a matrix of 64 cosine coefficients).
3.  Low-frequency coefficients (representing broad color areas) are preserved at full precision.
4.  High-frequency coefficients (representing fine detail and sharp edges) are divided by a **quantization matrix** and rounded, discarding subtle detail.
5.  The quantized coefficients are compressed using lossless Huffman coding.

**Quality Factor**: Controls the aggressiveness of the quantization matrix. Higher quality (90–100%) discards less detail. Lower quality (20–50%) discards more, producing smaller files with visible block artifacts.

**In the PDF dictionary**:
```
<< /Filter /DCTDecode /ColorSpace /DeviceRGB /Width 1920 /Height 1080 /BitsPerComponent 8 /Length 245000 >>
```

**What it compresses**: Photographic images, continuous-tone color artwork.

**What it should NOT compress**: Binary line art, text screenshots, technical diagrams, signatures (produces ringing artifacts around high-contrast edges).

**Java APIs**: `javax.imageio.ImageIO` with JPEG format writers and `JPEGImageWriteParam` for quality tuning.

---

### 4.3 LZWDecode
**Algorithm**: Lempel-Ziv-Welch, a dictionary-based compression algorithm derived from LZ78. Historically significant as the primary compression method in PDF 1.0 and TIFF files.

**Why it matters for optimization**: LZW is patent-encumbered (the patent expired in the mid-2000s) and produces lower compression ratios than FlateDecode's DEFLATE algorithm for similar input types. When your optimizer encounters an `/LZWDecode` stream, the canonical optimization is to **re-encode it as `/FlateDecode`** (typically yielding 10–30% smaller output with no quality loss).

**Java APIs**: LZW is not in the standard JDK. You must implement the algorithm manually or use the Apache Commons Compress library.

---

### 4.4 RunLengthDecode
**Algorithm**: Run-Length Encoding (RLE). A trivially simple lossless compression that replaces consecutive sequences of identical bytes with a count + value pair (e.g., 50 identical white pixels encoded as `49, 255` instead of 50 bytes of `255`).

**When it appears**: Only efficient for highly repetitive data. Primarily used for early TIFF images, raw bitmaps of monochrome scans, or as an intermediate encoding layer chained before another filter.

**Optimization rule**: RLE streams should always be re-encoded using FlateDecode, which will achieve significantly better compression on the same data due to LZ77 sliding-window capabilities.

---

### 4.5 CCITTFaxDecode
**Algorithm**: CCITT Group 3 and Group 4 fax compression, standardized by the ITU Telecommunication Standardization Sector for transmitting black-and-white (1-bit per pixel) images over telephone lines.

**CCITT Group 3**: Encodes each row of pixels using modified Huffman coding, also storing row-level synchronization markers. Less efficient but tolerant of transmission errors.

**CCITT Group 4**: Uses two-dimensional run-length coding, comparing each row with the row above. Extremely efficient for monochrome text pages, producing compression ratios of 5:1 to 15:1 on typical scanned documents.

**When it appears**: Black-and-white scanned documents, fax archives, legal contracts, and older enterprise document management systems.

**Optimization rule**: For monochrome images, CCITT Group 4 is typically near-optimal. The alternative is JBIG2, which offers even better compression. Converting color photographs stored under CCITTFax to JPEG or JBIG2 is usually unnecessary; these are already efficiently compressed for their color depth.

---

### 4.6 JBIG2Decode
**Algorithm**: JBIG2 (Joint Bi-level Image Experts Group, version 2), a highly advanced compression standard specifically designed for binary (1-bit per pixel) image data.

**Key innovation — Symbol Library**: JBIG2 analyzes all glyphs (letters and symbols) in a scanned page, extracts unique symbols into a shared dictionary, and then encodes each occurrence on the page as a reference to that dictionary entry. This is extremely effective for scanned text pages where the same letters appear hundreds of times.

**Two modes**:
*   **Lossless**: Exact pixel-level reproduction. File size is typically 5–7× smaller than CCITT Group 4.
*   **Lossy**: Similar symbols are merged into a single dictionary entry (e.g., two slightly different scans of the letter "a" are normalized to one), introducing barely-visible differences but achieving even higher compression (up to 10× smaller than CCITT Group 4).

**When it appears**: High-volume scanned document archives, court records systems, large-scale digitization projects.

---

### 4.7 JPXDecode (JPEG 2000)
**Algorithm**: JPEG 2000, a wavelet-based image compression standard designed to supersede JPEG with both lossless and lossy modes in a single format.

**How it differs from JPEG**:

| Property | JPEG (DCTDecode) | JPEG 2000 (JPXDecode) |
| :--- | :--- | :--- |
| Transform | 8×8 DCT blocks | Wavelet transform (full image) |
| Block artifacts | Yes (at low quality) | No (graceful degradation) |
| Lossless mode | No | Yes |
| Region of interest | No | Yes (selective quality areas) |
| Progressive rendering | Limited | Excellent |
| Compression ratio | High | Higher (especially lossless) |

**When it appears**: Medical imaging (DICOM), high-fidelity archival systems, geospatial imagery, digital cinema (DCI).

**Optimization rule**: If a PDF already uses JPXDecode, it is likely already at near-optimal compression for its content type. Re-encoding JPEG 2000 to standard JPEG achieves slightly worse quality and may actually increase file size for lossless-mode JPX streams.

---

## 5. Internal Mechanisms

### FlateDecode: The Deflate Algorithm in Detail

```
Raw Input Bytes
      │
      ▼
[ LZ77 Sliding Window (32KB lookback) ]
  ─ Scans for duplicate substrings
  ─ Emits (offset, length) back-references for matches
  ─ Emits raw literals for unmatched bytes
      │
      ▼
[ Huffman Tree Encoder ]
  ─ Counts symbol frequencies
  ─ Assigns shorter bit codes to frequent symbols
  ─ Writes compressed bit stream
      │
      ▼
[ Zlib Frame Wrapper ]
  ─ Prepends 2-byte CMF/FLG header
  ─ Appends 4-byte Adler-32 checksum
      │
      ▼
Compressed Output (stored in PDF stream)
```

### PNG Row Predictor Lifecycle
When the `/DecodeParms` dictionary specifies `Predictor 15` (PNG Optimal), each row of pixel data in the raw stream is prefixed by a single **filter byte** (0–4) indicating which algorithm was used for that row. The decoder must:
1.  Read the filter byte.
2.  Apply the inverse predictor function to the remaining bytes of the row.
3.  Reconstruct the original pixel values.

```
Row bytes (with filter byte prefix):
[ 0x02 | E1 05 F2 11 02 08 ... ]
   │
   │ Filter byte 0x02 = PNG Up predictor
   ▼
Each decoded byte = encoded_byte + byte_directly_above
```

### DCTDecode Memory Lifecycle
When a Java optimizer loads a JPEG-compressed PDF image for downsampling:
1.  The compressed stream bytes are passed to a JPEG decoder (`ImageIO.read()`).
2.  The decoder allocates a full uncompressed `BufferedImage` in heap memory: `width × height × channels × bytesPerChannel`.
3.  The image processing engine (downsample, color convert) is applied to the `BufferedImage`.
4.  The modified image is re-encoded by a JPEG writer (`ImageIO.write()`) producing a new compressed stream.
5.  The new compressed bytes replace the old stream in the output PDF.

Memory peak: `(original_image_pixels × 3 bytes) + (downsampled_pixels × 3 bytes)` must both fit in JVM heap simultaneously during the transformation.

---

## 6. Trade-Off Analysis

### Strategy: Re-encoding FlateDecode with Maximum Compression Level

```java
Deflater deflater = new Deflater(Deflater.BEST_COMPRESSION); // Level 9
```

| Dimension | Deflate Level 1 (Fast) | Deflate Level 6 (Default) | Deflate Level 9 (Max) |
| :--- | :--- | :--- | :--- |
| **CPU Time** | Very Fast (~2×) | Moderate | Slow (~8×) |
| **Output Size** | Slightly Larger | Balanced | Smallest |
| **Reversibility** | Lossless | Lossless | Lossless |
| **When to Use** | Real-time server pipelines | General batch optimization | Archival storage compression |
| **When Not to Use** | Storage-cost-sensitive archive | — | High-throughput API responses |

---

### Strategy: Converting LZW → Flate vs. Keeping LZW

| Dimension | Keep LZW | Convert to Flate |
| :--- | :--- | :--- |
| **Quality** | Identical (lossless) | Identical (lossless) |
| **File Size** | Larger | 10–30% smaller |
| **Compatibility** | PDF 1.0+ (all readers) | PDF 1.2+ (all modern readers) |
| **CPU Cost** | None (no re-encoding) | Low (re-encode once) |
| **Recommendation** | Keep if the file must support PDF 1.0 legacy readers | Always convert for modern documents |

---

## 7. Hands-On Exercises

### A. Beginner: Flate Decompressor
*   **Objective**: Write a Java method `byte[] flateDecode(byte[] compressed)` that uses `java.util.zip.Inflater` to decompress raw FlateDecode stream bytes (including the 2-byte zlib header).
*   **Test**: Hardcode a small zlib-compressed byte array, call your method, and verify the output matches the original text string using `new String(result, StandardCharsets.UTF_8)`.

### B. Intermediate: Filter Dictionary Router
*   **Objective**: Write a `StreamFilterRouter` class with a method `byte[] decode(String filterName, byte[] data)` that routes to the appropriate decompression implementation:
    *   `/FlateDecode` → Java `Inflater`
    *   `/RunLengthDecode` → Custom RLE decoder
    *   Unknown → Throw `UnsupportedFilterException`
*   **Challenge**: Handle the case where `/Filter` is a single Name object vs. an Array of filter names (chained filters).

### C. Advanced: PNG Row Predictor Decoder
*   **Objective**: Implement a `PngPredictorDecoder` class that decodes a raw image byte stream encoded with `Predictor 15`. The decoder must read the per-row filter byte (0–4) and apply the corresponding inverse predictor function.
*   **Challenge**: Implement all five predictor functions (None, Sub, Up, Average, Paeth) and verify output against a known PNG pixel buffer.

---

## 8. Mini Project: FlateDecode Stream Compressor and Inspector

### Objective
Create a command-line Java utility that reads a PDF file, locates all streams using FlateDecode, decompresses each stream, reports its raw content type (text/binary/image-data), and optionally re-compresses it at a higher Deflater compression level.

### Requirements
*   Use only standard JDK 21+ (`java.util.zip.Inflater`, `Deflater`, `RandomAccessFile`).
*   Locate the `/Length` key in each stream's dictionary to read exactly the correct number of bytes.
*   Decompress using `Inflater`.
*   Classify the raw content:
    *   **Text/Operator**: If decompressed bytes contain printable ASCII PDF operators (e.g., `BT`, `Tf`, `Tj`).
    *   **Binary Image Data**: If byte values are widely distributed (high entropy).
    *   **Structured Data**: If it starts with PDF object syntax (for object streams).
*   Re-compress at `Deflater.BEST_COMPRESSION` and report the size difference.

### Expected Output
```text
======================================================
FLATE STREAM ANALYZER: report.pdf
======================================================
Stream 1: [Object 4 0] Length: 8,421 bytes
  Filter:           FlateDecode
  Decompressed:     42,100 bytes
  Content Type:     Text/Operator (PDF drawing commands)
  Re-compressed:    7,890 bytes (-6.3% size improvement)

Stream 2: [Object 17 0] Length: 245,100 bytes
  Filter:           FlateDecode
  Decompressed:     1,024,000 bytes
  Content Type:     Binary Image Data (high entropy)
  Re-compressed:    245,095 bytes (-0.002% - already well compressed)
------------------------------------------------------
Total streams analyzed:  18
Total size saved:        12,450 bytes
======================================================
```

### Java Implementation Code
Write this to `c:\Users\Admin\Desktop\projects\learning-repo\courses\java\java-pdf-optimization-engine\src\main\java\com\example\pdf\filters\FlateStreamAnalyzer.java`:

```java
package com.example.pdf.filters;

import java.io.File;
import java.io.IOException;
import java.io.RandomAccessFile;
import java.nio.charset.StandardCharsets;
import java.util.zip.DataFormatException;
import java.util.zip.Deflater;
import java.util.zip.Inflater;

public class FlateStreamAnalyzer {

    public static void main(String[] args) {
        if (args.length < 1) {
            System.out.println("Usage: java com.example.pdf.filters.FlateStreamAnalyzer <pdf-path>");
            return;
        }
        File file = new File(args[0]);
        if (!file.exists() || !file.isFile()) {
            System.err.println("Invalid file: " + file.getAbsolutePath());
            return;
        }
        try (RandomAccessFile raf = new RandomAccessFile(file, "r")) {
            analyzeFile(raf, file.getName());
        } catch (IOException e) {
            System.err.println("Error reading PDF: " + e.getMessage());
            e.printStackTrace();
        }
    }

    private static void analyzeFile(RandomAccessFile raf, String name) throws IOException {
        System.out.println("\n======================================================");
        System.out.println("FLATE STREAM ANALYZER: " + name);
        System.out.println("======================================================");

        long fileLen = raf.length();
        long pos = 0;
        int streamIndex = 0;
        long totalSaved = 0;

        // Read entire file into byte array for token scanning
        // Note: for large files, use a sliding window approach
        byte[] fileBytes = new byte[(int) Math.min(fileLen, 200_000_000L)];
        raf.seek(0);
        raf.readFully(fileBytes);

        String content = new String(fileBytes, StandardCharsets.ISO_8859_1);
        int searchStart = 0;

        while (true) {
            // Locate next /FlateDecode marker
            int flateIdx = content.indexOf("/FlateDecode", searchStart);
            if (flateIdx == -1) break;

            // Locate stream start after this filter declaration
            int streamKeyword = content.indexOf("\nstream", flateIdx);
            if (streamKeyword == -1) {
                searchStart = flateIdx + 12;
                continue;
            }

            // Extract object number from the nearest "obj" token before the filter
            int objDecl = content.lastIndexOf(" obj", flateIdx);
            String objId = "?";
            if (objDecl > 0) {
                int lineStart = content.lastIndexOf('\n', objDecl) + 1;
                String objLine = content.substring(lineStart, objDecl + 4).trim();
                String[] parts = objLine.split("\\s+");
                if (parts.length >= 2) {
                    objId = parts[0] + " " + parts[1];
                }
            }

            // Find /Length value in the dictionary
            long streamLength = extractLengthValue(content, flateIdx);
            if (streamLength <= 0) {
                searchStart = streamKeyword + 7;
                continue;
            }

            // Stream data starts after "\nstream\n"
            int dataStart = streamKeyword + 7; // skip "\nstream"
            if (dataStart < content.length() && content.charAt(dataStart) == '\r') dataStart++;
            if (dataStart < content.length() && content.charAt(dataStart) == '\n') dataStart++;

            long safeLength = Math.min(streamLength, fileBytes.length - dataStart);
            if (safeLength <= 0) {
                searchStart = dataStart;
                continue;
            }

            byte[] compressedData = new byte[(int) safeLength];
            System.arraycopy(fileBytes, dataStart, compressedData, 0, (int) safeLength);

            streamIndex++;
            System.out.printf("\nStream %d: [Object %s] Length: %,d bytes\n", streamIndex, objId, safeLength);
            System.out.println("  Filter:           FlateDecode");

            // Attempt decompression
            byte[] decompressed = inflate(compressedData);
            if (decompressed == null) {
                System.out.println("  Status:           Could not decompress (possibly chained filters)");
                searchStart = dataStart;
                continue;
            }
            System.out.printf("  Decompressed:     %,d bytes\n", decompressed.length);

            // Classify content
            String contentType = classifyContent(decompressed);
            System.out.println("  Content Type:     " + contentType);

            // Re-compress at maximum level
            byte[] recompressed = deflate(decompressed, Deflater.BEST_COMPRESSION);
            long sizeDelta = safeLength - recompressed.length;
            double pctSaved = (double) sizeDelta / safeLength * 100.0;
            System.out.printf("  Re-compressed:    %,d bytes (%+.1f%% size improvement)\n", recompressed.length, -pctSaved);
            totalSaved += sizeDelta;

            searchStart = dataStart;
        }

        System.out.println("\n------------------------------------------------------");
        System.out.printf("Total streams analyzed:  %d\n", streamIndex);
        System.out.printf("Total size saved:        %,d bytes\n", totalSaved);
        System.out.println("======================================================\n");
    }

    private static long extractLengthValue(String content, int fromIndex) {
        int lengthIndex = content.lastIndexOf("/Length", fromIndex);
        if (lengthIndex == -1) return -1;
        String sub = content.substring(lengthIndex + 7).trim();
        String[] tokens = sub.split("\\s+");
        for (String token : tokens) {
            String clean = token.replaceAll("[^0-9]", "");
            if (!clean.isEmpty()) {
                try {
                    return Long.parseLong(clean);
                } catch (NumberFormatException ignored) {}
            }
        }
        return -1;
    }

    public static byte[] inflate(byte[] compressed) {
        Inflater inflater = new Inflater();
        try {
            inflater.setInput(compressed);
            byte[] buffer = new byte[8192];
            java.io.ByteArrayOutputStream baos = new java.io.ByteArrayOutputStream();
            while (!inflater.finished()) {
                try {
                    int count = inflater.inflate(buffer);
                    if (count == 0 && inflater.needsInput()) break;
                    baos.write(buffer, 0, count);
                } catch (DataFormatException e) {
                    return null;
                }
            }
            return baos.toByteArray();
        } finally {
            inflater.end();
        }
    }

    public static byte[] deflate(byte[] input, int level) {
        Deflater deflater = new Deflater(level);
        try {
            deflater.setInput(input);
            deflater.finish();
            byte[] buffer = new byte[8192];
            java.io.ByteArrayOutputStream baos = new java.io.ByteArrayOutputStream();
            while (!deflater.finished()) {
                int count = deflater.deflate(buffer);
                baos.write(buffer, 0, count);
            }
            return baos.toByteArray();
        } finally {
            deflater.end();
        }
    }

    private static String classifyContent(byte[] data) {
        if (data.length == 0) return "Empty";

        // Count printable ASCII characters
        int printable = 0;
        int pdfOperators = 0;
        for (int i = 0; i < Math.min(data.length, 512); i++) {
            int b = data[i] & 0xFF;
            if (b >= 32 && b <= 126) printable++;
        }

        String preview = new String(data, 0, Math.min(data.length, 256), StandardCharsets.US_ASCII);
        if (preview.contains("BT") && preview.contains("ET")) pdfOperators++;
        if (preview.contains(" Tf") || preview.contains(" Tj") || preview.contains(" TJ")) pdfOperators++;
        if (preview.contains(" m\n") || preview.contains(" l\n") || preview.contains(" re ")) pdfOperators++;

        double printableRatio = (double) printable / Math.min(data.length, 512);
        if (pdfOperators >= 2) return "Text/Operator (PDF drawing commands)";
        if (printableRatio > 0.85 && data[0] == '<' && data[1] == '<') return "Structured Data (Object stream)";
        if (printableRatio < 0.3) return "Binary Image Data (high entropy)";
        return "Mixed Content";
    }
}
```

### Extension Ideas
1.  **Compression Level Profiler**: Run re-compression at all 9 Deflater levels (1–9) for each stream and output a CSV report to find the optimal level for each stream type.
2.  **PNG Predictor Auto-Select**: Before deflating raw image data, test all five PNG predictor algorithms, select the one yielding the most compressible output, and apply it automatically.

---

## 9. Common Mistakes

### 1. Re-compressing Pre-Compressed JPEG Streams
*   *Symptom*: Output images have heavy visible block artifacts, and file sizes paradoxically increase.
*   *Cause*: The optimizer wraps a `/DCTDecode` JPEG stream in an additional `/FlateDecode` filter without decompressing it first. JPEG data is high-entropy binary; applying Flate does nothing useful. Worse, the optimizer then decodes and re-encodes the already-lossy JPEG image, applying JPEG quantization a second time and multiplying the quality loss.
*   *Prevention*: Always inspect the `/Filter` key before processing. Never apply Flate over DCT. If you want to re-encode JPEG data at a different quality, you must: (1) detect `/DCTDecode`, (2) fully decompress to a raw pixel buffer using `ImageIO.read()`, (3) downsample if needed, (4) re-compress fresh with `ImageIO.write()` using the new quality setting.

### 2. Ignoring the Zlib Header in FlateDecode Streams
*   *Symptom*: `java.util.zip.DataFormatException: incorrect header check` thrown by `Inflater.inflate()`.
*   *Cause*: The developer initialized `Inflater` with `new Inflater(true)`, which activates raw DEFLATE mode. But PDF FlateDecode streams use the **zlib framing format**, which includes a 2-byte CMF/FLG header. The raw DEFLATE inflater cannot parse this header.
*   *Prevention*: Initialize `Inflater` with the default constructor `new Inflater()` (which expects zlib-framed data), not `new Inflater(true)` (which expects raw DEFLATE).

### 3. Chained Filter Order Inversion
*   *Symptom*: All decompression attempts throw errors or produce garbage output.
*   *Cause*: A stream dictionary specifies multiple filters in an array: `[/ASCII85Decode /FlateDecode]`. The developer decodes left-to-right (ASCII85 first), but the array represents **encoding** order. Decoding must reverse the chain: first Flate, then ASCII85.
*   *Prevention*: Always reverse the `/Filter` array order when decoding. Encoding order is left-to-right (as listed); decoding order is right-to-left.

---

## 10. Assessment

### Quiz
1.  **Which PDF filter is based on the Discrete Cosine Transform and applies lossy compression to photographic images?**
    *   A. `/FlateDecode`
    *   B. `/LZWDecode`
    *   C. `/DCTDecode`
    *   D. `/CCITTFaxDecode`

2.  **What is the purpose of the `/DecodeParms` dictionary entry accompanying a `/FlateDecode` filter with `Predictor 15`?**
    *   A. It specifies the zlib compression level (1–9) used when writing the stream.
    *   B. It indicates that each row of pixel data is prefixed with a filter byte specifying which PNG predictor was applied to that row.
    *   C. It declares the number of color channels in the embedded image.
    *   D. It provides a cryptographic checksum to verify stream integrity after decompression.

3.  **When should you NOT re-encode a `/CCITTFaxDecode` stream using `/DCTDecode`?**
    *   A. When the image dimensions exceed 4000×4000 pixels.
    *   B. When the image is 1-bit per pixel monochrome (black and white). DCT is designed for continuous-tone color images and would be invalid for 1-bit depth.
    *   C. When the document was originally created using Adobe Acrobat.
    *   D. When the stream `/Length` value exceeds 1 MiB.

4.  **In what order must a decoder process a stream with `/Filter [/ASCII85Decode /FlateDecode]`?**
    *   A. ASCII85Decode first, then FlateDecode.
    *   B. FlateDecode first, then ASCII85Decode.
    *   C. Both filters simultaneously using two parallel Inflater instances.
    *   D. The order is reader-defined and may be applied in any sequence.

5.  **Why does JBIG2Decode achieve better compression ratios than CCITTFaxDecode on scanned text documents?**
    *   A. JBIG2 uses a higher-bit quantization matrix to group similar pixels.
    *   B. JBIG2 builds a shared symbol dictionary from recurring glyphs and encodes each character occurrence as a dictionary reference, eliminating redundant pixel data for repeated characters.
    *   C. JBIG2 applies DCT transforms to each 8×8 block of monochrome pixels.
    *   D. JBIG2 uses wavelet decomposition across the entire page, similar to JPEG 2000.

<details>
<summary><b>Click to reveal answers & explanations</b></summary>

1. **Answer: C — `/DCTDecode`**
   * DCT (Discrete Cosine Transform) is the algorithm underlying JPEG compression, which is the format for DCTDecode streams.

2. **Answer: B**
   * `Predictor 15` means PNG Optimal: each row has a leading filter byte indicating the sub-predictor used. The decoder must read this byte for every row.

3. **Answer: B**
   * CCITT encodes 1-bit black-and-white images. DCTDecode operates on multi-component continuous-tone color data. Applying it to 1-bit data would first require a color space conversion and would produce meaningless and much-larger output.

4. **Answer: B**
   * The `/Filter` array lists filters in **encoding** order. Decoding is performed in **reverse** order. So Flate was applied second (outermost), and must be decoded first; ASCII85 was applied first (innermost) and decoded last.

5. **Answer: B**
   * JBIG2's symbol dictionary is its key innovation: it extracts recurring glyph shapes, stores them once, and references them by index for every occurrence on the page, which is far more efficient than row-based encoding for text-heavy documents.
</details>

### Implementation Challenge
Implement a `ChainedFilterDecoder` class in Java that:
1.  Accepts a `/Filter` value that can be either a single Name or an array.
2.  Reverses the filter order for decoding.
3.  Dispatches each step to the appropriate decoder (Flate for now, extensible to others).
4.  Returns the fully decoded raw byte array.

---

## 11. Interview Perspective

### Common Interview Question
*   **Question**: "You're building a PDF optimizer. You detect a stream with `/Filter [/ASCII85Decode /FlateDecode]`. What steps do you take to decode it and re-compress it at a higher compression level?"

### Expected Reasoning
The candidate must demonstrate:
*   Understanding that the filter array represents encoding order, not decoding order.
*   Correct reversal: decode FlateDecode first (zlib `Inflater`), then ASCII85Decode.
*   Re-compression: apply `Deflater` at a higher level, then optionally re-apply ASCII85 or drop it (since ASCII85 is only needed for PostScript compatibility).
*   Final step: update the `/Filter` key and `/Length` value in the stream dictionary.

### Sample Answers

#### Strong Answer
> "The `/Filter` array is applied in encoding order: first FlateDecode was applied, then ASCII85Decode was applied on top. To decode, I must reverse this: first run ASCII85Decode to recover the raw Flate-compressed bytes, then run FlateDecode using a zlib `Inflater` (not a raw DEFLATE inflater, since FlateDecode uses zlib framing) to recover the final raw stream content.
> To re-optimize, I would then re-compress the raw content using `Deflater.BEST_COMPRESSION` and write it back. I'd also drop the ASCII85 encoding layer since modern PDF readers support binary streams directly — this eliminates an unnecessary encoding step, saving both space and decode time. Finally, I'd update the stream dictionary's `/Filter` entry to just `/FlateDecode` and recalculate the `/Length` value to match the new compressed byte count."

#### Weak Answer
> "I would call `decompress()` on both filters at the same time in parallel threads, then pass the output to a ZIP library to compress it again. Since ZIP and FlateDecode are basically the same thing, the output should just work."
