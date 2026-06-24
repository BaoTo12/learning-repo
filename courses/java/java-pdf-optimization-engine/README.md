# PDF Compression and Optimization Engine in Java

Welcome to the **PDF Compression and Optimization Engine in Java** course. This syllabus is designed for senior Java developers, system architects, and document pipeline engineers who need to build high-performance, memory-efficient PDF processing engines capable of safely and aggressively optimizing files for production environments.

In this course, you will dive below the abstraction layers of high-level PDF libraries and study the low-level PDF specification, indirect object structures, stream filters, font embedding methodologies, and image downsampling algorithms.

---

## 🎯 Course Objectives

By the end of this course, you will be able to:
1. **Understand PDF Architecture**: Trace the four major file sections (Header, Body, XRef Table, Trailer) and navigate the indirect object graph.
2. **Profile PDF Bloat**: Inspect PDF documents programmatically to identify and isolate primary sources of file size (e.g., redundant fonts, uncompressed streams, high-resolution images).
3. **Recompress and Downsample Images**: Implement intelligent downsampling of raster images and convert legacy image compression formats to modern, highly compressed equivalents.
4. **Compress Content Streams**: Use stream filters (such as `FlateDecode`) to compress raw text and vector coordinate instructions.
5. **Optimize Fonts & Metadata**: Clean up duplicate resources, prune excess XML metadata blocks, and optimize font sub-setting.
6. **Design Memory-Efficient Handlers**: Build streaming and random-access PDF parsers that process multi-gigabyte PDF files under tight JVM heap constraints.

---

## 📚 Structured Syllabus & Modules

This curriculum is structured into consecutive learning phases. This initial setup covers the core problem domain and structural fundamentals:

| Module | Topic | File Link |
| :--- | :--- | :--- |
| **01** | Why PDF Compression Is Difficult & Problem Domain | [01-why-pdf-compression-is-difficult.md](./modules/01-why-pdf-compression-is-difficult.md) |
| **02** | Core PDF Knowledge: File Structure & Navigation | [02-pdf-file-structure.md](./modules/02-pdf-file-structure.md) |
| **03** | Core PDF Knowledge: PDF Object Model | [03-pdf-object-model.md](./modules/03-pdf-object-model.md) |
| **04** | Core PDF Knowledge: Stream Filters | [04-pdf-stream-filters.md](./modules/04-pdf-stream-filters.md) |
| **05** | Image Processing in Java for PDF Optimization | [05-image-processing-fundamentals.md](./modules/05-image-processing-fundamentals.md) |
| **06** | Compression Profiles & Strategy Design | [06-compression-profiles.md](./modules/06-compression-profiles.md) |
| **07** | Apache PDFBox Deep Dive | [07-apache-pdfbox.md](./modules/07-apache-pdfbox.md) |
| **08** | OpenPDF: Structural Optimization & Library Comparison | [08-openpdf.md](./modules/08-openpdf.md) |
| **09** | Font Optimization | [09-font-optimization.md](./modules/09-font-optimization.md) |
| **10** | Metadata and Cleanup | [10-metadata-and-cleanup.md](./modules/10-metadata-and-cleanup.md) |
| **11** | Compression Engine Architecture | [11-compression-engine-architecture.md](./modules/11-compression-engine-architecture.md) |
| **12** | Performance Engineering | [12-performance-engineering.md](./modules/12-performance-engineering.md) |
| **13** | Testing and Validation | [13-testing-and-validation.md](./modules/13-testing-and-validation.md) |
| **14** | Production Concerns | [14-production-concerns.md](./modules/14-production-concerns.md) |

---

---

## 📦 External Library Dependencies

Modules 1–6 use **JDK 21+ standard APIs only** (`java.util.zip`, `javax.imageio`).
Modules 7–14 use the following dependencies:

```xml
<!-- Apache PDFBox (Modules 7, 9, 10, 11, 12, 13, 14) -->
<dependency>
    <groupId>org.apache.pdfbox</groupId>
    <artifactId>pdfbox</artifactId>
    <version>3.0.2</version>
</dependency>

<!-- OpenPDF (Module 8, 11, 14) -->
<dependency>
    <groupId>com.github.librepdf</groupId>
    <artifactId>openpdf</artifactId>
    <version>1.3.35</version>
</dependency>

<!-- JUnit Jupiter API (Module 13 Testing) -->
<dependency>
    <groupId>org.junit.jupiter</groupId>
    <artifactId>junit-jupiter-api</artifactId>
    <version>5.10.2</version>
    <scope>test</scope>
</dependency>
<dependency>
    <groupId>org.junit.jupiter</groupId>
    <artifactId>junit-jupiter-engine</artifactId>
    <version>5.10.2</version>
    <scope>test</scope>
</dependency>
```

---

## 🛠️ Prerequisites & Local Execution Setup

To compile the labs and execute the programmatic analysis tools in this course, you will need:
* **Java Development Kit (JDK) 21 or later** (LTS).
* A standard Java development environment or IDE (such as IntelliJ IDEA, Eclipse, or VS Code).
* Raw terminal access or command-line compiler utilities (`javac`, `java`).

Verify your JDK environment configuration:
```bash
java --version
# Should output openjdk 21 or later
```

---

## 📈 Graduation & System Assessment Rubrics

Your progress and final projects will be assessed across four core dimensions:

### 1. PDF Structural Analysis Precision (25% Weight)
* **Blob Categorization**: Accurately distinguishing between content streams, image streams, font files, and metadata dictionary structures.
* **Size Attribution**: Writing tools that report size distributions without relying on heavy external dependencies.

### 2. Compression Logic & Profile Alignment (25% Weight)
* **Configurable Profiles**: Implementing lossless, balanced, and aggressive profiles that cleanly align with target quality limits.
* **Object Deduplication**: Safely identifying identical resources (e.g., duplicate image assets across pages) and rewriting the object table to share references.

### 3. Stream & Image Re-encoding (25% Weight)
* **Re-encoding Filters**: Compressing raw uncompressed data streams via FlateDecode.
* **Downsampling Precision**: Downsampling raster images to target DPI metrics (e.g., 72, 150, 300) while maintaining color-space integrity.

### 4. Integrity Preservation & Compliance (25% Weight)
* **XRef Alignment**: Ensuring XRef table offsets are calculated to the exact byte after rewrite.
* **Incremental Preservation**: Supporting modern PDF conventions including hybrid XRef tables, object streams, and incremental update chains.
