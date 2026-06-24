# Module 05: Image Processing in Java for PDF Optimization

---

## 1. Why This Module Exists

In most real-world PDF documents, embedded images account for 70–95% of total file size. A PDF optimizer that only strips metadata or re-compresses text streams achieves minimal savings because the dominant payloads are binary image blobs.

| PDF Type | Typical Image Contribution |
| :--- | :--- |
| Text-only reports | 5–20% |
| Slides with screenshots | 40–70% |
| Scanned documents | 80–95% |
| Magazine/catalog PDFs | 70–90% |

Without understanding image processing, you cannot build meaningful compression profiles. This module bridges the gap between PDF stream extraction (Module 4) and practical pixel manipulation — translating compressed image bytes into `BufferedImage` objects, applying spatial transformations, and re-encoding at controlled quality levels.

The connection chain is:
```
Module 4 (Stream Filters) ──► Module 5 (Image Processing) ──► Module 6 (Profiles)
Extract compressed bytes       Decode, transform, re-encode       Bundle into strategy
```

---

## 2. Learning Objectives

By the end of this module, you will be able to:
*   **Explain** why images dominate PDF file sizes using quantitative DPI math.
*   **Decode** image streams extracted from PDF files into Java `BufferedImage` representations.
*   **Implement** image downsampling using `Graphics2D` with bicubic interpolation.
*   **Calculate** appropriate target pixel dimensions from DPI targets and original image metadata.
*   **Compare** Nearest Neighbor, Bilinear, Bicubic, and Lanczos algorithms across quality and performance dimensions.
*   **Configure** JPEG compression quality using `JPEGImageWriteParam` and explain its relationship to the DCT quantization matrix.
*   **Apply** YCbCr chroma subsampling at different ratios (4:4:4, 4:2:2, 4:2:0) and measure their impact on image size.
*   **Convert** color images to grayscale using the luminance formula and evaluate when this is appropriate.
*   **Design** a composable `ImageOptimizationPipeline` class driven by configurable compression parameters.

---

## 3. Conceptual Foundations

### The BufferedImage Pixel Matrix
A `BufferedImage` is an in-memory two-dimensional matrix of pixel values. Each pixel contains one or more channel values (e.g., Red, Green, Blue for a `TYPE_INT_RGB` image). Unlike a compressed JPEG file (which is a compact, high-entropy byte sequence), a `BufferedImage` stores every pixel at full precision — an uncompressed raw representation.

```
                    Compressed JPEG (e.g., 50 KB DCTDecode stream)
                                     │
                             ImageIO.read(stream)
                                     │
                                     ▼
    ┌──────────────────────────────────────────────────────┐
    │           BufferedImage (e.g., 1920 × 1080)          │
    │                                                      │
    │  [R:255 G:120 B:40] [R:254 G:119 B:41] ...          │  ← Row 0
    │  [R:100 G:200 B:90] [R:101 G:200 B:91] ...          │  ← Row 1
    │  ...                                                 │
    └──────────────────────────────────────────────────────┘
    Memory usage: 1920 × 1080 × 3 bytes = 6,220,800 bytes (~5.9 MiB)
```

**Critical insight**: A 50 KB JPEG file expands to ~6 MB in RAM when decoded. When processing batches of high-resolution images, heap exhaustion is the primary engineering risk.

### The Decode–Process–Encode Lifecycle
Every image optimization operation follows this four-phase lifecycle:

```
Phase 1: Extract   ──► Phase 2: Decode    ──► Phase 3: Transform ──► Phase 4: Encode
Raw PDF bytes           BufferedImage           Resize / convert        New compressed
from stream object      (uncompressed pixels)   / color convert         bytes → PDF
```

You must fully decompress the image before any transformation. There is no way to resize or change quality settings on a JPEG-compressed byte array without decoding it to pixels first.

### DPI: Density vs. Dimension
DPI (Dots Per Inch) describes how densely pixels are packed in a print context. It does not directly change the pixel count — it is metadata that tells a printer how large the image should appear on paper.

For PDF optimization purposes, we care about the **physical DPI at which the image was originally scanned or produced**, and the **target DPI appropriate for the intended use case**. Reducing DPI means proportionally reducing pixel dimensions:

```
Target Width  = Original Width  × (Target DPI ÷ Original DPI)
Target Height = Original Height × (Target DPI ÷ Original DPI)
```

A 600 DPI scan of an A4 page has these dimensions:
```
Width:  8.27 inches × 600 DPI = 4,962 pixels
Height: 11.69 inches × 600 DPI = 7,014 pixels
Memory: 4962 × 7014 × 3 bytes = ~104 MB per page
```

Downsampling to 150 DPI yields:
```
Width:  4,962 × (150/600) = 1,240 pixels
Height: 7,014 × (150/600) = 1,753 pixels
Memory: 1240 × 1753 × 3 bytes = ~6.5 MB (16× reduction)
```

---

## 4. Technical Topics

### 4.1 BufferedImage Types and Color Models

| `BufferedImage` Type Constant | Channels | Bytes/Pixel | Use Case |
| :--- | :--- | :--- | :--- |
| `TYPE_INT_RGB` | 3 (R, G, B) | 4 (packed int) | Standard color photos |
| `TYPE_INT_ARGB` | 4 (R, G, B, A) | 4 (packed int) | Images with transparency |
| `TYPE_BYTE_GRAY` | 1 (luminance) | 1 | Grayscale scans |
| `TYPE_3BYTE_BGR` | 3 (B, G, R) | 3 | JPEG I/O default |
| `TYPE_BYTE_BINARY` | 1 (1-bit) | 1/8 | Monochrome fax images |

**Raster Data Storage**: Pixels are stored in a `DataBuffer` backing the `WritableRaster`. For `TYPE_INT_RGB`, each pixel is packed into a 32-bit integer as `0x00RRGGBB`. Direct pixel access via `getRGB(x, y)` performs bounds checking and unpacking on every call — expensive in loops. For performance-critical code, access the `DataBuffer` directly via `raster.getDataElements()`.

### 4.2 Resampling Algorithms

When you reduce an image's pixel dimensions, you must decide how to compute the value of each new pixel from the surrounding original pixels. This is **interpolation**.

#### Nearest Neighbor
Assigns each new pixel the value of the single closest original pixel. Extremely fast, but produces hard edges and a "pixelated" or "blocky" appearance.
```
New pixel at (x', y') = Original pixel at (round(x' × scaleX), round(y' × scaleY))
```

#### Bilinear Interpolation
Computes a weighted average of the 4 surrounding pixels (2×2 grid). Weights are proportional to the fractional distance from each neighbor.
```
P = (1-dx)(1-dy)·P00 + dx(1-dy)·P10 + (1-dx)dy·P01 + dx·dy·P11
```
Produces smooth results but can slightly blur fine details.

#### Bicubic Interpolation
Computes a weighted average across a 4×4 grid (16 surrounding pixels) using cubic polynomial weighting kernels. The cubic kernel `W(x)` assigns higher weight to nearby pixels and negative weight to pixels at distance > 1 (which sharpens edges slightly):
```
W(x) = (a+2)|x|³ − (a+3)|x|² + 1    for |x| ≤ 1
W(x) = a|x|³ − 5a|x|² + 8a|x| − 4a  for 1 < |x| < 2
(where a is typically −0.5 or −0.75)
```
The sharpness-enhancing negative lobe is what distinguishes bicubic from bilinear. This makes it the standard choice for general PDF optimization.

#### Lanczos (Windowed Sinc)
Uses a sinc function windowed by another sinc (Lanczos window) over a support radius of 2–3 pixels:
```
L(x) = sinc(x) · sinc(x/a)    for |x| < a, else 0
sinc(x) = sin(πx) / (πx)
```
Produces the sharpest, highest-quality downsample results with minimal aliasing. However, it is computationally expensive — 3–5× slower than bicubic — and can produce mild ringing artifacts near sharp edges.

### 4.3 JPEG Quality and DCT Quantization
JPEG compression divides the image into 8×8 pixel blocks and applies the Discrete Cosine Transform to each, producing 64 frequency coefficients per block. These coefficients are then divided element-wise by a **quantization matrix** and rounded to integers.

```
Quantized[u][v] = round( DCT_Coefficient[u][v] / Q[u][v] )
```

The quality factor (0–100) scales the quantization matrix: **lower quality → larger divisors → more rounding → more data loss → smaller file**. The relationship is nonlinear: going from quality 90 to 80 reduces file size by ~50%, while going from 50 to 40 reduces it by a much smaller margin.

### 4.4 Chroma Subsampling
The human eye is more sensitive to luminance (brightness) than chrominance (color). JPEG exploits this by converting images from RGB to YCbCr (Y = luminance, Cb/Cr = color difference), then storing the color channels at reduced resolution.

| Subsampling Ratio | Y Resolution | Cb/Cr Resolution | File Size Impact |
| :--- | :--- | :--- | :--- |
| 4:4:4 | Full | Full | Largest (no subsampling) |
| 4:2:2 | Full | Half horizontal | ~33% smaller than 4:4:4 |
| 4:2:0 | Full | Half both dimensions | ~50% smaller than 4:4:4 |

Most JPEG encoders default to 4:2:0. `JPEGImageWriteParam` does not expose chroma subsampling directly in standard Java; it can be controlled via vendor-specific parameters or through explicit YCbCr plane manipulation.

### 4.5 Grayscale Conversion
Converting a color image to grayscale reduces its channel count from 3 to 1, reducing decoded memory by 3×. The standard luminance-weighted formula preserves perceived brightness:
```
Y = 0.299 × R + 0.587 × G + 0.114 × B
```
The green channel carries the most perceptual weight. A simple average `(R+G+B)/3` produces a visibly different (often lighter) result and should not be used.

**When to apply grayscale conversion**: Legal documents, contracts, scanned text pages, forms, and invoices. Not suitable for product photography, branding materials, or any document where color carries meaningful information.

---

## 5. Internal Mechanisms

### Graphics2D Rendering Pipeline

```java
BufferedImage target = new BufferedImage(targetWidth, targetHeight, source.getType());
Graphics2D g2d = target.createGraphics();
g2d.setRenderingHint(RenderingHints.KEY_INTERPOLATION,
                     RenderingHints.VALUE_INTERPOLATION_BICUBIC);
g2d.setRenderingHint(RenderingHints.KEY_RENDERING,
                     RenderingHints.VALUE_RENDER_QUALITY);
g2d.setRenderingHint(RenderingHints.KEY_ANTIALIASING,
                     RenderingHints.VALUE_ANTIALIAS_ON);
g2d.drawImage(source, 0, 0, targetWidth, targetHeight, null);
g2d.dispose();
```

Internally, `drawImage` with bicubic hint triggers the Java2D pipeline to:
1. Select the `BicubicInterpolator` kernel.
2. Map each destination pixel `(x', y')` back to source space using the affine transform.
3. Evaluate the 4×4 kernel neighborhood in source space.
4. Write the weighted sum to the destination `DataBuffer`.

The rendering is single-threaded in standard Java2D. For very large images, consider splitting into horizontal strips processed by a `ForkJoinPool`.

### Memory Peak During Image Replacement
When processing a single image stream, the heap holds:
```
Peak Heap = Original decoded pixels + Target decoded pixels + Re-encoded bytes buffer
           ≈ (W₁ × H₁ × Ch × B) + (W₂ × H₂ × Ch × B) + compressed_output
```
For a 4962×7014 color image downsampled to 1240×1753:
```
Peak ≈ 104 MB (original) + 6.5 MB (target) + ~0.5 MB (JPEG output)
     ≈ 111 MB peak per image
```
Processing images sequentially and allowing GC to collect the original `BufferedImage` before loading the next is essential for memory-safe batch processing.

---

## 6. Trade-Off Analysis

### Interpolation Algorithm Comparison

| Algorithm | Speed | Visual Quality | Artifacts | Best For |
| :--- | :--- | :--- | :--- | :--- |
| Nearest Neighbor | ★★★★★ | ★☆☆☆☆ | Severe aliasing | Debug/preview only |
| Bilinear | ★★★★☆ | ★★★☆☆ | Mild blur | Thumbnails |
| Bicubic | ★★★☆☆ | ★★★★☆ | Very mild ringing | PDF optimization (recommended) |
| Lanczos | ★★☆☆☆ | ★★★★★ | Mild ringing | High-end publishing |

### JPEG Quality Trade-Off Ladder

| Quality | Visual Fidelity | File Size (relative) | Recommended Use |
| :--- | :--- | :--- | :--- |
| 0.90 | Excellent — nearly lossless | ~100% | Print, professional publishing |
| 0.85 | Very good | ~70% | Low-compression profile |
| 0.75 | Good — slight softening | ~45% | Recommended profile |
| 0.60 | Acceptable | ~30% | Web delivery |
| 0.50 | Noticeable artifacts | ~22% | Extreme profile |
| 0.30 | Poor — clear block artifacts | ~12% | Rarely used |

### Grayscale Conversion

| Dimension | Outcome |
| :--- | :--- |
| **Benefit** | 3× decoded memory reduction; 2–3× JPEG file size reduction |
| **Drawback** | Permanent loss of color information |
| **When to Use** | Contracts, invoices, scanned text, any document where color carries no semantic meaning |
| **When NOT to Use** | Marketing materials, product catalogs, diagrams using color to encode data |

---

## 7. Hands-On Exercises

### A. Beginner: Image Stream Loader
*   **Objective**: Write `BufferedImage loadImage(byte[] data)` that decodes a compressed image byte array using `ImageIO.read(new ByteArrayInputStream(data))`.
*   **Output**: Print the image's width, height, `getType()` constant, and calculated uncompressed memory footprint in MB.
*   **Test**: Use a small JPEG or PNG file read via `Files.readAllBytes()`.

### B. Intermediate: Bicubic Downsampler
*   **Objective**: Implement `BufferedImage resize(BufferedImage src, int targetWidth, int targetHeight)` using `Graphics2D` with bicubic `RenderingHints`.
*   **Challenge**: After resizing, measure execution time using `System.nanoTime()` and print the result alongside input/output dimension comparison.

### C. Advanced: Entropy-Based Auto Quality Selector
*   **Objective**: Implement `float selectJpegQuality(BufferedImage image)` that samples the image's pixel value distribution and estimates its entropy:
    - Compute a 256-bin histogram of luminance values.
    - Compute Shannon entropy: `H = -Σ(p_i × log₂(p_i))` over all bins.
    - Map entropy to quality: high entropy (natural photos) → 0.75; low entropy (solid regions, charts) → 0.55.
*   **Rationale**: Low-entropy images (large uniform areas) compress far more aggressively with JPEG than high-entropy natural photographs for the same quality setting.

---

## 8. Mini Project: ImageOptimizationPipeline

### Objective
Build a composable `ImageOptimizationPipeline` class that accepts a compressed image byte array, a target DPI, an original DPI, and a quality setting — and returns an optimized compressed JPEG byte array.

### Requirements
*   Decode input using `ImageIO.read()`.
*   Calculate target dimensions from DPI ratio.
*   Skip downsampling if target dimensions are >= original (no upscaling).
*   Apply bicubic interpolation downsampling via `Graphics2D`.
*   Optionally convert to grayscale using the luminance formula.
*   Re-encode as JPEG using `JPEGImageWriteParam` at the configured quality.
*   Return the compressed output bytes.

### Java Implementation Code
Write to `c:\Users\Admin\Desktop\projects\learning-repo\courses\java\java-pdf-optimization-engine\src\main\java\com\example\pdf\image\ImageOptimizationPipeline.java`:

```java
package com.example.pdf.image;

import javax.imageio.IIOImage;
import javax.imageio.ImageIO;
import javax.imageio.ImageWriteParam;
import javax.imageio.ImageWriter;
import javax.imageio.plugins.jpeg.JPEGImageWriteParam;
import javax.imageio.stream.ImageOutputStream;
import java.awt.Graphics2D;
import java.awt.RenderingHints;
import java.awt.image.BufferedImage;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.util.Iterator;
import java.util.Locale;

public class ImageOptimizationPipeline {

    public enum GrayscaleMode { KEEP_COLOR, CONVERT_GRAYSCALE }

    private final int targetDpi;
    private final int originalDpi;
    private final float jpegQuality;
    private final GrayscaleMode grayscaleMode;

    public ImageOptimizationPipeline(int originalDpi, int targetDpi,
                                     float jpegQuality, GrayscaleMode grayscaleMode) {
        this.originalDpi = originalDpi;
        this.targetDpi = targetDpi;
        this.jpegQuality = jpegQuality;
        this.grayscaleMode = grayscaleMode;
    }

    /**
     * Optimize an image stream.
     *
     * @param inputBytes  Compressed image bytes (JPEG, PNG, etc.)
     * @return            Optimized JPEG-compressed bytes
     * @throws IOException if decoding or encoding fails
     */
    public byte[] process(byte[] inputBytes) throws IOException {
        // Phase 1: Decode
        BufferedImage original = decode(inputBytes);
        int originalWidth  = original.getWidth();
        int originalHeight = original.getHeight();

        // Phase 2: Calculate target dimensions
        int targetWidth  = (int)(originalWidth  * ((double) targetDpi / originalDpi));
        int targetHeight = (int)(originalHeight * ((double) targetDpi / originalDpi));

        // Phase 3: Downsample (skip if target >= original)
        BufferedImage processed;
        if (targetWidth < originalWidth && targetHeight < originalHeight) {
            processed = downsample(original, targetWidth, targetHeight);
        } else {
            processed = original;
        }

        // Phase 4: Optional grayscale conversion
        if (grayscaleMode == GrayscaleMode.CONVERT_GRAYSCALE) {
            processed = toGrayscale(processed);
        }

        // Phase 5: Encode
        byte[] output = encodeJpeg(processed, jpegQuality);

        // Log summary
        System.out.printf("  [Pipeline] %dx%d → %dx%d | Original: %,d bytes | Optimized: %,d bytes | Ratio: %.1f%%\n",
                originalWidth, originalHeight, processed.getWidth(), processed.getHeight(),
                inputBytes.length, output.length,
                (double) output.length / inputBytes.length * 100);

        return output;
    }

    private BufferedImage decode(byte[] bytes) throws IOException {
        try (ByteArrayInputStream bais = new ByteArrayInputStream(bytes)) {
            BufferedImage img = ImageIO.read(bais);
            if (img == null) {
                throw new IOException("ImageIO could not decode image stream (unsupported format or corrupt data)");
            }
            return img;
        }
    }

    private BufferedImage downsample(BufferedImage src, int targetWidth, int targetHeight) {
        int imageType = (src.getType() == BufferedImage.TYPE_CUSTOM || src.getType() == 0)
                ? BufferedImage.TYPE_INT_RGB
                : src.getType();

        BufferedImage target = new BufferedImage(targetWidth, targetHeight, imageType);
        Graphics2D g2d = target.createGraphics();
        try {
            g2d.setRenderingHint(RenderingHints.KEY_INTERPOLATION,
                                 RenderingHints.VALUE_INTERPOLATION_BICUBIC);
            g2d.setRenderingHint(RenderingHints.KEY_RENDERING,
                                 RenderingHints.VALUE_RENDER_QUALITY);
            g2d.setRenderingHint(RenderingHints.KEY_ANTIALIASING,
                                 RenderingHints.VALUE_ANTIALIAS_ON);
            g2d.drawImage(src, 0, 0, targetWidth, targetHeight, null);
        } finally {
            g2d.dispose();
        }
        return target;
    }

    /**
     * Converts a color image to grayscale using the ITU-R BT.601 luminance formula:
     * Y = 0.299R + 0.587G + 0.114B
     */
    private BufferedImage toGrayscale(BufferedImage src) {
        int w = src.getWidth();
        int h = src.getHeight();
        BufferedImage gray = new BufferedImage(w, h, BufferedImage.TYPE_BYTE_GRAY);
        Graphics2D g2d = gray.createGraphics();
        try {
            g2d.drawImage(src, 0, 0, null);
        } finally {
            g2d.dispose();
        }
        return gray;
    }

    private byte[] encodeJpeg(BufferedImage image, float quality) throws IOException {
        // Ensure image is in a JPEG-compatible color model
        BufferedImage encodeTarget = image;
        if (image.getType() == BufferedImage.TYPE_BYTE_GRAY) {
            // Grayscale images encode directly as JPEG
            encodeTarget = image;
        } else if (image.getColorModel().hasAlpha()) {
            // JPEG does not support alpha channel: flatten onto white background
            BufferedImage flattened = new BufferedImage(
                    image.getWidth(), image.getHeight(), BufferedImage.TYPE_INT_RGB);
            Graphics2D g2d = flattened.createGraphics();
            try {
                g2d.setColor(java.awt.Color.WHITE);
                g2d.fillRect(0, 0, image.getWidth(), image.getHeight());
                g2d.drawImage(image, 0, 0, null);
            } finally {
                g2d.dispose();
            }
            encodeTarget = flattened;
        }

        Iterator<ImageWriter> writers = ImageIO.getImageWritersByFormatName("jpeg");
        if (!writers.hasNext()) {
            throw new IOException("No JPEG ImageWriter available in this JVM environment.");
        }
        ImageWriter writer = writers.next();
        JPEGImageWriteParam params = new JPEGImageWriteParam(Locale.getDefault());
        params.setCompressionMode(ImageWriteParam.MODE_EXPLICIT);
        params.setCompressionQuality(quality);

        try (ByteArrayOutputStream baos = new ByteArrayOutputStream();
             ImageOutputStream ios = ImageIO.createImageOutputStream(baos)) {
            writer.setOutput(ios);
            writer.write(null, new IIOImage(encodeTarget, null, null), params);
            writer.dispose();
            return baos.toByteArray();
        }
    }

    // ─── Standalone Test Driver ───────────────────────────────────────────────

    public static void main(String[] args) throws IOException {
        if (args.length < 2) {
            System.out.println("Usage: ImageOptimizationPipeline <image-file> <target-dpi>");
            return;
        }
        byte[] inputBytes = java.nio.file.Files.readAllBytes(java.nio.file.Paths.get(args[0]));
        int targetDpi = Integer.parseInt(args[1]);

        // Profile: Recommended (150 DPI, quality 0.75, color preserved)
        ImageOptimizationPipeline pipeline = new ImageOptimizationPipeline(
                300, targetDpi, 0.75f, GrayscaleMode.KEEP_COLOR);

        byte[] result = pipeline.process(inputBytes);
        java.nio.file.Files.write(java.nio.file.Paths.get("optimized_output.jpg"), result);
        System.out.println("Written to: optimized_output.jpg");
    }
}
```

### Extension Ideas
1.  **Lanczos Filter**: Replace the bicubic `RenderingHints` with a custom Lanczos kernel implementation using `ConvolveOp` and `Kernel` for publishing-grade quality.
2.  **Entropy Analyzer**: Before encoding, compute Shannon entropy of pixel luminance and auto-adjust `jpegQuality` downward for low-entropy images (solid backgrounds, charts).
3.  **Progressive Strip Processing**: Split large images into horizontal strips, process each strip independently, and concatenate — keeping peak heap usage proportional to strip height rather than total image height.

---

## 9. Common Mistakes

### 1. Loading All Images Into Heap Simultaneously
*   *Symptom*: `java.lang.OutOfMemoryError: Java heap space` when processing PDFs with many large images.
*   *Cause*: Processing images in parallel threads, each holding a decoded `BufferedImage` in memory at the same time.
*   *Prevention*: Process images sequentially. Explicitly null the reference to the original `BufferedImage` after encoding, then call `System.gc()` as a hint before loading the next image.

### 2. Using `getScaledInstance()` for Downsampling
*   *Symptom*: Downsampled images appear blurry with poor edge definition.
*   *Cause*: `BufferedImage.getScaledInstance(w, h, Image.SCALE_SMOOTH)` uses a deprecated multi-pass area-averaging algorithm that produces lower quality than `Graphics2D` with bicubic hints.
*   *Prevention*: Always use the `Graphics2D.drawImage()` approach with explicit `RenderingHints` as shown in the mini project.

### 3. Double-JPEG Re-encoding Artifacts
*   *Symptom*: Each optimization pass introduces new blocking and ringing artifacts. After 2–3 passes, text becomes unreadable.
*   *Cause*: Decoding an already-lossy JPEG image and re-encoding it at a lower quality applies DCT quantization errors on top of existing quantization errors. These errors accumulate multiplicatively.
*   *Prevention*: An optimization pipeline should re-encode an image **at most once**. Track whether a stream was already processed and skip it in subsequent passes.

### 4. Ignoring Alpha Channel Before JPEG Encoding
*   *Symptom*: `javax.imageio.IIOException: JPEG codec does not support ARGB images`.
*   *Cause*: JPEG does not support transparency. Attempting to encode a `TYPE_INT_ARGB` `BufferedImage` directly throws an exception.
*   *Prevention*: Before encoding, check `image.getColorModel().hasAlpha()`. If true, composite the image onto a solid white background as shown in the `encodeJpeg()` method above.

---

## 10. Assessment

### Quiz

1.  **A scanned document image is 4,962 × 7,014 pixels (600 DPI). You target 150 DPI. What are the output dimensions?**
    *   A. 1,240 × 1,753 pixels
    *   B. 2,481 × 3,507 pixels
    *   C. 3,721 × 5,260 pixels
    *   D. 4,962 × 7,014 pixels (unchanged)

2.  **Which resampling algorithm evaluates a 4×4 pixel neighborhood and applies a cubic kernel that includes a sharpness-enhancing negative lobe?**
    *   A. Nearest Neighbor
    *   B. Bilinear
    *   C. Bicubic
    *   D. Lanczos

3.  **The luminance-weighted grayscale formula assigns which channel the highest weight?**
    *   A. Red (0.299)
    *   B. Green (0.587)
    *   C. Blue (0.114)
    *   D. All channels equally (0.333)

4.  **What is the consequence of re-encoding an already-JPEG-compressed image at a lower quality setting?**
    *   A. No quality loss — JPEG is a lossless format.
    *   B. The second quantization pass multiplies the quantization error from the first pass, producing visibly worse artifacts than a single-pass encode at that quality.
    *   C. The output becomes slightly sharper because two rounds of edge-reinforcement occur.
    *   D. The file size increases because the second pass cannot compress the error terms.

5.  **Why should you flatten an ARGB image onto a white background before JPEG encoding?**
    *   A. JPEG stores pixels in YCbCr color space, which cannot represent alpha-premultiplied RGB values.
    *   B. The JPEG format specification does not support a transparency (alpha) channel. The encoder will throw an exception unless the alpha channel is resolved first.
    *   C. Transparent pixels cause integer overflow in the DCT transform block calculation.
    *   D. The `ImageWriter` API requires exactly 3 channels; 4-channel inputs are automatically rejected by the `JPEGImageWriteParam` parameter block.

<details>
<summary><b>Click to reveal answers</b></summary>

1. **A** — `4962 × (150/600) = 1240`, `7014 × (150/600) = 1753`.
2. **C** — Bicubic uses a 4×4 neighborhood and a cubic kernel with negative lobes that provide mild edge enhancement.
3. **B** — Green carries 58.7% of perceived luminance because human cone cells are most sensitive to mid-spectrum wavelengths.
4. **B** — JPEG is lossy; each encode introduces quantization error. Re-encoding multiplies this error, visible as increasingly severe blocking.
5. **B** — JPEG does not support transparency. Standard `ImageWriter` implementations throw an exception for ARGB inputs.
</details>

### Implementation Challenge
Extend `ImageOptimizationPipeline` to support a **strip-based processing mode** that splits a large `BufferedImage` into horizontal strips of configurable height, processes each strip independently, and assembles the results. Verify that peak heap usage stays under `2 × stripHeight × imageWidth × 3 bytes`.

---

## 11. Interview Perspective

### Common Interview Question
> "Walk me through how you would reduce a 120 MB scanned 50-page PDF — originally scanned at 600 DPI with JPEG quality 95% — down to under 10 MB, without visible quality loss for screen reading."

### Expected Reasoning
A strong candidate must:
*   Identify 150 DPI as an appropriate screen-reading target (16× pixel reduction from 600 DPI → 150 DPI).
*   Explain the decode → downsample → re-encode lifecycle.
*   Choose JPEG quality 0.72–0.75 for the recommended profile.
*   Address memory: sequential processing, not parallel loading.
*   Mention double-encoding risk: since the original is already JPEG, one re-encode pass is acceptable but must not happen again.

### Sample Answers

#### Strong Answer
> "First, I'd extract each image stream from the PDF using the XRef object map. Since the original scan is at 600 DPI and the target is screen reading, I'd downsample to 150 DPI — that's a 4× linear reduction in each dimension, meaning 16× fewer pixels. I'd use `Graphics2D` with bicubic `RenderingHints` to minimize aliasing during the resize.
> After resizing, I'd re-encode as JPEG at quality 0.75. For a document this size, the images are probably 80–90% of the total bytes, so this pass alone should reduce the file to 10–15% of its original size.
> Memory-wise, I'd process one image at a time sequentially and null the decoded `BufferedImage` reference before moving to the next, allowing GC to collect it. Peak heap per image would be roughly 6.5 MB (decoded target) + 104 MB (decoded original) — so about 112 MB per image, which is manageable. I'd set the JVM `-Xmx256m` and monitor for pressure."

#### Weak Answer
> "I would loop through all the images, resize them using `getScaledInstance()` with `SCALE_FAST`, then save them as JPEG. For a 120 MB file, the output should be around 10 MB since JPEG is very good at compression. I'd run this in a thread pool to make it faster."
