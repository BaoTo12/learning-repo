# Module 13: Testing and Validation

---

## 1. Why This Module Exists

A PDF optimizer that reduces a document by 90% is a failure if it silently corrupts the document structure, rendering the output unreadable, or degrades embedded diagrams to illegible blurs.

Testing a document optimization engine is uniquely challenging:
*   **Intended Changes**: We cannot use simple file-level byte assertions (like matching MD5 checksums) because our changes are lossy; the output bytes are *intended* to differ.
*   **Silent Corruption**: A PDF file might load without error in one reader but crash another. Structural corruption (e.g. invalid cross-reference offsets) can hide inside the binary trailer.
*   **Visual Degradation**: Downsampling algorithms can render small font details or signature marks illegible.

To ship code with confidence, we need a rigorous validation harness. We must verify both **structural compliance** (conformance to the PDF specification) and **perceptual quality** (the visual fidelity of optimized images).

This module teaches you how to implement automated regression testing, construct synthetic test inputs, calculate pixel-level image quality metrics (PSNR), and write JUnit 5 test suites.

---

## 2. Learning Objectives

By the end of this module, you will be able to:
*   **Construct** a testing pyramid tailored for document processing systems.
*   **Calculate** Peak Signal-to-Noise Ratio (PSNR) to programmatically measure image quality loss.
*   **Write** parameterized JUnit 5 regression tests using a golden corpus.
*   **Implement** programmatic validation of PDF output integrity.
*   **Generate** synthetic PDFs dynamically to stress-test pipeline components.
*   **Design** negative test assertions for malformed or corrupted inputs.

---

## 3. Conceptual Foundations

### The Document Testing Pyramid
A robust pipeline combines multiple testing tiers:

```
          /\
         /  \      System Acceptance: Check PDF/A, Acrobat Preflight
        /    \
       /      \    Compatibility Testing: Test rendering on multiple engines
      /────────\
     /          \  Regression Testing: Run Golden Corpus validation
    /────────────\
   /              \ Functional & Unit Testing: Test individual Passes & PSNR bounds
  /────────────────\
```

### Visual Quality Metrics: PSNR
To verify image compression is visually lossless, we compare the original image and the optimized image at the pixel level. The standard metric is the **Peak Signal-to-Noise Ratio (PSNR)**, measured in decibels (dB).

First, we calculate the **Mean Squared Error (MSE)** between the original image $I$ and the compressed image $K$ of size $M \times N$:
$$\text{MSE} = \frac{1}{3 M N} \sum_{i=0}^{M-1} \sum_{j=0}^{N-1} \left[ (I_{r,i,j} - K_{r,i,j})^2 + (I_{g,i,j} - K_{g,i,j})^2 + (I_{b,i,j} - K_{b,i,j})^2 \right]$$
Then, the PSNR is:
$$\text{PSNR} = 20 \cdot \log_{10} \left( \frac{\text{MAX}_I}{\sqrt{\text{MSE}}} \right) = 20 \cdot \log_{10} \left( \frac{255}{\sqrt{\text{MSE}}} \right)$$
*   **PSNR > 40 dB**: Visually identical (excellent quality).
*   **30 dB to 40 dB**: Visually lossless for standard viewing (good quality).
*   **20 dB to 30 dB**: Visually degraded (noticeable artifacts).
*   **PSNR < 20 dB**: Unacceptable degradation.

### Round-Trip Parsing Correctness
The absolute baseline check for any optimized PDF is **parse safety**.
If you optimize a document, write it to disk, and attempt to reload it:
```java
try (PDDocument doc = PDDocument.load(new File("output.pdf"))) {
    // If this throws an IOException, the file structure is corrupted
}
```
We can also execute a **render round-trip** using PDFBox’s `PDFRenderer` to render every page of the optimized file to a `BufferedImage` in memory. If the renderer completes without throwing drawing exceptions, we have high confidence that the page content streams are structurally sound.

---

## 4. Technical Topics

### 4.1 JUnit 5 Parameterized Tests
Rather than writing separate tests for every test file, we use `@ParameterizedTest` and `@MethodSource` to feed a collection of PDF fixtures (our golden corpus) into a single test execution pipeline.

```java
@ParameterizedTest
@MethodSource("provideGoldenCorpus")
void testCompressionAndVibe(File fixture) {
    // Run optimizer, verify size decrease, verify PSNR
}
```

### 4.2 Handling Temporary Directories
PDF optimization creates many disk files during processing. In tests, we must avoid polluting the file system. JUnit 5’s `@TempDir` annotation automatically manages temp directories, creating them before tests and cleaning them up afterward:

```java
@TempDir
Path tempDir;
```

### 4.3 Programmatic Synthetic PDF Generation
Relying on external files for unit tests can make tests brittle if files are missing or modified.
For unit testing individual passes, we can write helper methods to programmatically build simple, valid PDFs containing text and synthetic images using PDFBox, creating independent, self-contained test scenarios.

---

## 5. Internal Mechanisms

### Computing PSNR in Java
To calculate PSNR in Java, we read RGB values from `BufferedImage` objects. We must ensure both images have identical pixel dimensions. If their sizes differ due to downsampling, we must upscale the optimized image back to the original dimensions using bilinear interpolation before calculating pixel differences.

```
[ Original Image (800x600) ]            [ Optimized Image (400x300) ]
            │                                         │
            │                                         ▼  (Upscale)
            │                           [ Upscaled Image (800x600) ]
            │                                         │
            └───────────────► [ Compare ] ◄───────────┘
                                    │
                                    ▼
                             Calculate MSE
                                    │
                                    ▼
                             Calculate PSNR
```

---

## 6. Trade-Off Analysis

### Pixel-Exact Assertions vs. Metric Thresholds

| Metric | Pixel-Exact Check | PSNR Threshold Check |
| :--- | :--- | :--- |
| **Applicability** | Lossless transformations only | Lossy transformations (image re-encoding) |
| **Brittleness** | Very High (library updates break hashes) | Low (tolerates minor numeric color shifts) |
| **Implementation Cost** | Low (direct comparison of digests) | Moderate (calculating pixel values) |
| **Fidelity Representation** | Poor (flags visual matches as fails) | Excellent (reflects human visual system) |

### Golden Corpus Sizing
*   **Large Corpus (1,000+ files)**: Excellent coverage of real-world anomalies.
    *   *Trade-off*: Slow execution time (takes hours to complete in CI pipelines).
*   **Pruned Corpus (10–20 files)**: Curated to cover distinct PDF variants (forms, scanned images, complex font subsets, linear PDFs).
    *   *Trade-off*: Fast execution (< 1 minute), ideal for pre-commit checks.

---

## 7. Hands-On Exercises

### A. Beginner: Verify PDF Page Count
Write a JUnit 5 test that takes an input file, runs a metadata strip pass, saves it to a temporary path, and asserts that the optimized page count matches the original file's page count.

### B. Intermediate: Write a PSNR Assertor
Write a helper method `assertVisualQuality(File original, File optimized, double minPsnrDb)`. The method must locate images inside the PDFs, extract them, calculate their PSNR, and throw an `AssertionError` if quality falls below the target.

### C. Advanced: Programmatic PDF Corruption Tester
Write a negative test that passes truncated or corrupt PDF files to your parsing engine. Assert that the engine handles structural exceptions gracefully (throwing `IOException` or custom parser errors) instead of crashing with an unhandled NullPointerException.

---

## 8. Mini Project: PdfOptimizerTestSuite

### Objective
Create a complete, self-contained test suite using JUnit 5. The project must include:
1.  `SyntheticPdfGenerator`: A utility that programmatically generates standard PDF documents containing dummy text and image patterns for testing.
2.  `PsnrCalculator`: A helper that calculates the Peak Signal-to-Noise Ratio between two `BufferedImage` objects.
3.  `PdfOptimizerTestSuite`: The JUnit 5 test class running tests for:
    *   **Round-trip parsing validity**.
    *   **File size reduction verification**.
    *   **Visual quality conservation (asserting PSNR > 30 dB)**.

### Java Implementation

Save the following classes in your testing directory (e.g. `src/test/java/com/example/pdf/test/`):

#### 1. PsnrCalculator.java
```java
package com.example.pdf.test;

import java.awt.image.BufferedImage;

public class PsnrCalculator {

    /**
     * Calculates the Peak Signal-to-Noise Ratio (PSNR) between two images.
     */
    public static double calculatePSNR(BufferedImage img1, BufferedImage img2) {
        if (img1.getWidth() != img2.getWidth() || img1.getHeight() != img2.getHeight()) {
            throw new IllegalArgumentException("Images must have identical dimensions for PSNR calculation.");
        }

        int width = img1.getWidth();
        int height = img2.getHeight();
        double sumSquaredError = 0;

        for (int y = 0; y < height; y++) {
            for (int x = 0; x < width; x++) {
                int rgb1 = img1.getRGB(x, y);
                int rgb2 = img2.getRGB(x, y);

                int r1 = (rgb1 >> 16) & 0xff;
                int g1 = (rgb1 >> 8) & 0xff;
                int b1 = rgb1 & 0xff;

                int r2 = (rgb2 >> 16) & 0xff;
                int g2 = (rgb2 >> 8) & 0xff;
                int b2 = rgb2 & 0xff;

                sumSquaredError += Math.pow(r1 - r2, 2);
                sumSquaredError += Math.pow(g1 - g2, 2);
                sumSquaredError += Math.pow(b1 - b2, 2);
            }
        }

        // Divide by 3 because of three color channels (RGB)
        double mse = sumSquaredError / (double) (width * height * 3);
        if (mse == 0) {
            return Double.POSITIVE_INFINITY; // Identical images
        }

        return 20.0 * Math.log10(255.0 / Math.sqrt(mse));
    }
}
```

#### 2. SyntheticPdfGenerator.java
```java
package com.example.pdf.test;

import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDPageContentStream;
import org.apache.pdfbox.pdmodel.font.PDType1Font;
import org.apache.pdfbox.pdmodel.font.Standard14Fonts;
import org.apache.pdfbox.pdmodel.graphics.image.JPEGFactory;
import org.apache.pdfbox.pdmodel.graphics.image.PDImageXObject;

import java.awt.Color;
import java.awt.Graphics2D;
import java.awt.image.BufferedImage;
import java.io.File;
import java.io.IOException;

public class SyntheticPdfGenerator {

    /**
     * Generates a valid test PDF file containing a high-resolution gradient image and text.
     */
    public static void generateTestPdf(File outputFile) throws IOException {
        try (PDDocument doc = new PDDocument()) {
            PDPage page = new PDPage();
            doc.addPage(page);

            // 1. Create a high-res synthetic test image (gradient)
            BufferedImage bufferedImage = new BufferedImage(800, 600, BufferedImage.TYPE_INT_RGB);
            Graphics2D g = bufferedImage.createGraphics();
            for (int i = 0; i < 800; i++) {
                for (int j = 0; j < 600; j++) {
                    bufferedImage.setRGB(i, j, new Color(i % 256, j % 256, (i + j) % 256).getRGB());
                }
            }
            g.dispose();

            // Convert image to PDFBox XObject (using high quality, uncompressed setup initially)
            PDImageXObject pdImage = JPEGFactory.createFromImage(doc, bufferedImage, 1.0f);

            // 2. Draw text and image onto the page content stream
            try (PDPageContentStream contentStream = new PDPageContentStream(doc, page)) {
                contentStream.drawImage(pdImage, 50, 200, 500, 375);

                // Add standard text
                contentStream.beginText();
                contentStream.setFont(new PDType1Font(Standard14Fonts.FontName.HELVETICA_BOLD), 18);
                contentStream.newLineAtOffset(50, 100);
                contentStream.showText("PDF Engine Compression Testing Ground");
                contentStream.endText();
            }

            doc.save(outputFile);
        }
    }
}
```

#### 3. PdfOptimizerTestSuite.java
```java
package com.example.pdf.test;

import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.graphics.image.PDImageXObject;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.awt.image.BufferedImage;
import java.io.File;
import java.io.IOException;
import java.nio.file.Path;

import static org.junit.jupiter.api.Assertions.*;

public class PdfOptimizerTestSuite {

    @TempDir
    Path tempDir;

    private File originalFile;
    private File optimizedFile;

    @BeforeEach
    void setUp() throws IOException {
        originalFile = tempDir.resolve("original.pdf").toFile();
        optimizedFile = tempDir.resolve("optimized.pdf").toFile();

        // Generate the synthetic target file
        SyntheticPdfGenerator.generateTestPdf(originalFile);
    }

    @Test
    void testFileCompilesAndCompresses() throws IOException {
        assertTrue(originalFile.exists(), "Original test file must exist");

        // Simulate our optimization pipeline logic
        runDummyCompression(originalFile, optimizedFile);

        assertTrue(optimizedFile.exists(), "Optimized output file must be created");
        assertTrue(optimizedFile.length() < originalFile.length(),
                String.format("Output size (%d bytes) must be smaller than input size (%d bytes)",
                        optimizedFile.length(), originalFile.length()));
    }

    @Test
    void testOutputIsLoadableAndValid() throws IOException {
        runDummyCompression(originalFile, optimizedFile);

        // Round-trip load verification
        assertDoesNotThrow(() -> {
            try (PDDocument doc = PDDocument.load(optimizedFile)) {
                assertEquals(1, doc.getNumberOfPages(), "Page count must remain identical");
            }
        }, "Optimized PDF must be parseable without throwing exceptions");
    }

    @Test
    void testVisualQualityCheckViaPSNR() throws IOException {
        runDummyCompression(originalFile, optimizedFile);

        BufferedImage origImg = extractFirstImage(originalFile);
        BufferedImage optImg = extractFirstImage(optimizedFile);

        assertNotNull(origImg, "Must extract image from original document");
        assertNotNull(optImg, "Must extract image from optimized document");

        // Compute the Peak Signal-to-Noise Ratio (PSNR)
        double psnr = PsnrCalculator.calculatePSNR(origImg, optImg);
        System.out.println("Computed PSNR for image: " + psnr + " dB");

        // Verify the visual fidelity remains high (above 30 dB is considered good quality)
        assertTrue(psnr > 30.0, "Visual quality degrades below acceptable threshold (30.0 dB). Found: " + psnr);
    }

    private void runDummyCompression(File input, File output) throws IOException {
        try (PDDocument doc = PDDocument.load(input)) {
            // Traverse elements and run a dummy compression (re-encoding images at lower JPEG quality)
            for (PDPage page : doc.getPages()) {
                var resources = page.getResources();
                for (COSName name : resources.getXObjectNames()) {
                    if (resources.isImageXObject(name)) {
                        PDImageXObject origImage = (PDImageXObject) resources.getXObject(name);
                        BufferedImage img = origImage.getImage();

                        // Compress and replace image stream
                        PDImageXObject newImage = JPEGFactory.createFromImage(doc, img, 0.40f); // 40% JPEG quality
                        resources.put(name, newImage);
                    }
                }
            }
            doc.save(output);
        }
    }

    private BufferedImage extractFirstImage(File pdfFile) throws IOException {
        try (PDDocument doc = PDDocument.load(pdfFile)) {
            for (PDPage page : doc.getPages()) {
                var resources = page.getResources();
                for (COSName name : resources.getXObjectNames()) {
                    if (resources.isImageXObject(name)) {
                        PDImageXObject img = (PDImageXObject) resources.getXObject(name);
                        return img.getImage();
                    }
                }
            }
        }
        return null;
    }
}
```

---

## 9. Common Mistakes

### 1. Using File Hashes to Assert Quality Correctness
*   *Symptom*: Valid image optimizations fail the test pipeline whenever libraries (PDFBox, Java ImageIO) are updated.
*   *Cause*: Asserting that `md5(optimized.pdf)` matches a hardcoded string. Compressed byte layouts change with encoder versions.
*   *Prevention*: Assert sizes (`optimizedSize < originalSize`) and visual quality thresholds (`psnr > 30.0`), never exact byte matches.

### 2. Not Cleaning Up Temporary Directories
*   *Symptom*: Continuous integration (CI) runners run out of disk space.
*   *Cause*: Writing test PDFs to hardcoded directories (e.g. `C:\temp\`) without manual cleanup hooks.
*   *Prevention*: Always use JUnit 5’s `@TempDir` to manage target directories, which cleans up files automatically.

### 3. Neglecting Dimension Mismatch Warnings in PSNR
*   *Symptom*: `IllegalArgumentException` thrown during image comparisons in the visual validation phase.
*   *Cause*: Downsampling tests change image resolution from $800 \times 600$ to $400 \times 300$, and the PSNR comparison logic attempts to read out-of-bounds indices.
*   *Prevention*: Ensure your verification script upscales the downsampled image back to the original size before calculating PSNR.

---

## 10. Assessment

### Quiz

1.  **Which metric mathematically represents pixel-level visual distortion, where values above 30 dB are considered visually lossless?**
    *   A. Compression Ratio
    *   B. Mean Squared Error (MSE)
    *   C. Peak Signal-to-Noise Ratio (PSNR)
    *   D. Structural Similarity Index (SSIM)

2.  **Why should test runners avoid using MD5 checksum validation on optimized PDFs?**
    *   A. MD5 is insecure for hashing PDF passwords.
    *   B. PDFBox updates, operating system color profiles, or Java ImageIO changes can modify output bytes without changing visual formatting.
    *   C. Checking MD5 hashes requires loading files into memory.
    *   D. The PDF standard forbids embedding files with MD5 signatures.

3.  **What does JUnit 5's `@TempDir` annotation guarantee?**
    *   A. It creates temporary files that are kept forever.
    *   B. It automatically cleans up allocated directory paths after test execution completes.
    *   C. It increases processing speed by running tests in RAM.
    *   D. It encrypts testing documents on disk.

4.  **You write a round-trip test that renders every page of the optimized PDF to a `BufferedImage`. What does this help detect?**
    *   A. Incomplete file uploads.
    *   B. Font file license validation.
    *   C. Low-level content stream parsing syntax corruptions.
    *   D. PDF password changes.

5.  **If the Mean Squared Error (MSE) between two images is calculated as 0, what is the PSNR value?**
    *   A. 0 dB
    *   B. 255 dB
    *   C. Double.POSITIVE_INFINITY
    *   D. Double.NEGATIVE_INFINITY

<details>
<summary><b>Click to reveal answers</b></summary>

1. **C** — PSNR measures the ratio between maximum possible signal power and corrupting noise power, expressed on a logarithmic scale.
2. **B** — Binary representation changes when encoder algorithms compile details differently, making exact hash comparisons brittle.
3. **B** — `@TempDir` manages lifecycle boundaries for local workspace temp directories.
4. **C** — Rendering page vectors checks if draw operators can compile, catching parsing defects in page content.
5. **C** — An MSE of 0 indicates zero pixel differences, resulting in division by zero in the log math, which yields infinity.
</details>

---

## 11. Interview Perspective

### Common Interview Question
> "How do you test a lossy PDF optimizer for correctness when the output is intentionally different from the input?"

### Expected Reasoning
The interviewer wants to see that you understand the difference between validating deterministic transformations and validating lossy, heuristic optimizations. A complete answer covers:
1.  **Structural Validity (Syntactic Round-trip)**: Verify the output remains a valid PDF structure using parser load tests and rendering checks.
2.  **Size Assertions (Deterministic Target)**: Verify output size is strictly smaller than the input.
3.  **Perceptual Quality (Statistical Validation)**: Explain how visual metrics like PSNR or SSIM are calculated on extracted images to prevent quality drops below thresholds.
4.  **Golden Corpus (Regression Safeguards)**: Discuss maintaining a curated set of test PDFs to prevent regressions on complex layouts.

### Sample Answers

#### Strong Answer
> "Testing a lossy PDF optimizer requires three distinct validation layers: structural validity, size metrics, and perceptual fidelity.
>
> For structural validity, I implement round-trip validation. The pipeline must load the optimized PDF using a parser like PDFBox and render each page to a memory buffer using `PDFRenderer`. If this step throws no exceptions, the output structure is verified as compliant.
>
> For compression metrics, I check that the output size is strictly smaller than the input size.
>
> For perceptual visual quality, I use Peak Signal-to-Noise Ratio (PSNR). I extract matching images from the before and after files, upscale the downsampled versions to align dimensions, and compute pixel error differences. The test asserts that the PSNR remains above 30 dB.
>
> Finally, I run these assertions against a golden corpus of 20 test documents that cover edge-case PDF features like font subsets, form dictionaries, and vector graphics to prevent regression in production releases."

#### Weak Answer
> "I open a few files in Acrobat Reader and check them myself to make sure they look okay. If they do, I commit the code. If we need automated tests, I check the output file hash matches the original file hash."
