# Module 10: Metadata and Cleanup

---

## 1. Why This Module Exists

When we think of PDF optimization, our attention naturally shifts to heavy assets like images and fonts. However, non-visual and structural elements—such as XML metadata (XMP), document information dictionaries, embedded file attachments, page thumbnails, and duplicated resource streams—can account for a surprising 5% to 30% of a PDF’s total size.

For example:
*   A scanned legal contract might contain embedded high-resolution page thumbnails (`/Thumb`) created by scanner software, adding 150 KB per page. For a 100-page document, this is 15 MB of visual bloat that modern PDF readers generate on-the-fly anyway.
*   A document created by merging several smaller PDFs can contain duplicate copies of the same company logo or font streams, each written as a separate indirect object.
*   Archived reports often contain multi-megabyte CAD drawing files or spreadsheets embedded as attachments (`/EmbeddedFiles`).

Cleaning up these non-visual components is a **"free lunch"** optimization: it costs absolutely nothing in rendering quality, introduces zero visual artifacts, and can be applied universally as a preprocessing hygiene pass. This module teaches you how to systematically identify and strip this structural bloat using Java.

---

## 2. Learning Objectives

By the end of this module, you will be able to:
*   **Analyze** the structure of a PDF's Document Catalog to locate metadata, attachments, and thumbnails.
*   **Differentiate** between the traditional Document Information dictionary (`/Info`) and modern XMP metadata (`/Metadata`).
*   **Implement** an automated mark-and-sweep reachability algorithm to locate orphaned objects in a PDF graph.
*   **Detect and deduplicate** duplicate PDF streams using cryptographic hashing (SHA-256).
*   **Design** a selective cleanup pipeline that prunes non-visual data without breaking standards compliance (like PDF/A).

---

## 3. Conceptual Foundations

### The Document Catalog as the Root of the Object Graph
A PDF is not a flat sequence of bytes; it is a directed object graph. The root of this graph is the **Document Catalog**, represented by the `/Root` entry in the PDF trailer. All visible pages, fonts, outlines, interactive forms, attachments, and metadata streams must be reachable by traversing references starting from this `/Root` dictionary.

```
                  [ Trailer ]
                       │
                       ▼
                 [ /Root (Catalog) ]
                 /     │     \
     ┌──────────/      │      \──────────┐
     ▼                 ▼                 ▼
[ /Pages ]       [ /Metadata ]     [ /Names ]
     │           (XMP XML Stream)        │
     ▼                                   ▼
[ /Page ]                         [ /EmbeddedFiles ]
     │                                   │
     ▼                                   ▼
[ /Thumb ] (Thumbnail)            [ /EmbeddedFile Stream ]
```

Any object in the file that cannot be reached by traversing references starting from the Document Catalog is considered an **orphan**. Orphaned objects still occupy bytes in the file and are listed in the Cross-Reference (XRef) table, but they are dead weight.

### Document Info Dictionary (`/Info`) vs. XMP Metadata (`/Metadata`)
PDF documents carry metadata in two distinct locations:
1.  **Document Info Dictionary (`/Info`)**: A simple key-value dictionary containing basic document metadata strings such as `/Title`, `/Author`, `/Subject`, `/Keywords`, `/Creator`, `/Producer`, `/CreationDate`, and `/ModDate`. This dictionary is referenced directly from the trailer.
2.  **Metadata Stream (`/Metadata`)**: Introduced in PDF 1.4, this is a stream containing XML formatted according to the **Extensible Metadata Platform (XMP)** standard. XMP uses W3C Resource Description Framework (RDF) syntax to represent metadata in namespaces like Dublin Core (`dc:`), PDF Basic (`pdf:`), and XMP Basic (`xmp:`). The Metadata stream is referenced from the `/Root` dictionary (and can also be attached to individual pages, fonts, or images).

### Mark-and-Sweep Reachability Analysis
To identify and delete orphaned objects, we employ a classic **mark-and-sweep garbage collection** algorithm adapted for the PDF object model:
*   **Mark Phase**: Traverse the object graph starting from `/Root` (and `/Info`), following all indirect object references (`COSObject`). Add all traversed object numbers to a `Set<Long>` of reachable objects.
*   **Sweep Phase**: Iterate through the PDF's Cross-Reference table (XRef). Any object number not present in the reachable set is garbage. We remove these objects from the document structure and mark their XRef entries as free.

### Duplicate Stream Deduplication
PDF creation tools often embed multiple identical copies of resources (such as logos, watermarks, or font fragments). To identify and eliminate them:
1.  Compute a **cryptographic hash (SHA-256)** of the raw bytes of every stream object in the PDF.
2.  Maintain a map of `Hash -> ObjectReference`.
3.  When a duplicate stream is detected, update all dictionaries referencing the duplicate object so they point to the first instance of the stream instead.
4.  The duplicate object becomes an orphan, which is subsequently reclaimed during the sweep phase or when saving the file.

---

## 4. Technical Topics

### 4.1 XMP Metadata Structure
An XMP metadata stream typically looks like this:
```xml
<?xpacket begin="" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about="" xmlns:dc="http://purl.org/dc/elements/1.1/">
   <dc:format>application/pdf</dc:format>
   <dc:title><rdf:Alt><rdf:li xml:lang="x-default">Financial Report</rdf:li></rdf:Alt></dc:title>
  </rdf:Description>
  <rdf:Description rdf:about="" xmlns:pdf="http://ns.adobe.com/pdf/1.3/">
   <pdf:Producer>Acrobat Distiller 11.0</pdf:Producer>
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>
```
To optimize this, we can either:
*   **Strip the stream completely** (remove `/Metadata` from the `/Root` dictionary).
*   **Prune the stream** using standard XML DOM parsing in Java, removing bloated metadata tags (like Photoshop history, editing sessions, or printer settings) while retaining required tags (like Dublin Core title and author).

### 4.2 Document Info Dictionary
The `/Info` dictionary is located in the trailer:
```
trailer
<< /Size 45
   /Root 12 0 R
   /Info 13 0 R >>
```
Object `13 0 R` contains:
```
13 0 obj
<< /Author (Jane Doe)
   /Creator (Microsoft Word)
   /Producer (Mac OS X 10.15 Quartz PDFContext)
   /CreationDate (D:20260620110418Z) >>
endobj
```
Unlike the XMP `/Metadata` stream, the `/Info` dictionary is a simple key-value structure. We can clear its fields by replacing values with empty strings or removing the entries entirely from the dictionary, except for key system metadata if needed (e.g. `/Producer`).

### 4.3 Page Thumbnails (`/Thumb`)
Some applications write pre-rendered JPEG thumbnail images for every page into the `/Thumb` entry of the page dictionaries:
```
3 0 obj
<< /Type /Page
   /Parent 2 0 R
   /Resources 4 0 R
   /Contents 5 0 R
   /Thumb 8 0 R >>  <-- Page thumbnail
endobj
```
Removing the `/Thumb` key from all page dictionaries deletes the link, turning the thumbnail image stream (object 8) into an orphan that will be swept away. Modern readers dynamically render thumbnails instantly in memory, making `/Thumb` streams obsolete size bloat.

### 4.4 File Attachments (`/EmbeddedFiles`)
Embedded file attachments are stored in a name tree pointed to by the `/Names` dictionary in the Document Catalog:
```
12 0 obj
<< /Type /Catalog
   /Pages 2 0 R
   /Names << /EmbeddedFiles 15 0 R >> >>
endobj
```
To strip all file attachments, we simply remove the `/Names` entry or specifically prune `/EmbeddedFiles` from the `/Names` dictionary.

---

## 5. Internal Mechanisms

### Traversal and Sweep
When using Apache PDFBox, we traverse the low-level object model using the `COS` API. Since circular references are common in PDF graphs (e.g., page parents pointing back to root, or annotations referencing their target pages), we must track visited objects during mark-and-sweep to prevent infinite loops.

```
Start traversal at Document Catalog (/Root)
  │
  ▼
 Add object to visited set
  │
  ▼
 Iterate through dictionary keys
  │
  ├── Is value a Direct Object?
  │     └─ Recursively inspect it
  │
  └── Is value a Reference (COSObject)?
        ├─ Has referenced object been visited?
        │    ├─ Yes: Stop recursion branch
        │    └─ No:  Recursively inspect referenced object
```

### Hash-Based Stream Deduplication
Stream deduplication requires reading the raw bytes of streams. In PDFBox, stream streams are represented by `COSStream`. When we compute a SHA-256 hash of a stream, we must read the *decoded* (filtered) stream bytes rather than the encoded ones, as different compressors might yield different compressed bytes for identical uncompressed inputs.

Once a duplicate stream is identified, we locate the reference containing the duplicate and update it. PDFBox maintains a cache of indirect objects (`COSObject`). By modifying the underlying `COSBase` reference inside the `COSObject` wrapper, we redirect all pointers to the single source object.

---

## 6. Trade-Off Analysis

### Metadata Strip Profiles
When building a production compression pipeline, we must match the metadata cleanup strategy to the target Profile:

| Profile | Strategy | Size Savings | Risks |
| :--- | :--- | :--- | :--- |
| **Visually Lossless** | Prune non-standard XMP; retain `/Info` | Minor (10–100 KB) | Safe; preserves document title, author, and creation dates. |
| **Balanced** | Strip XMP completely; retain basic `/Info` | Moderate (50–500 KB) | Breaks PDF/A validation, which strictly requires matching XMP and `/Info`. |
| **Aggressive Size Reduction** | Strip XMP and `/Info` entirely | High (up to 1–5 MB on bloated files) | Loss of all authorship, dates, and indexing keywords; search engine optimization (SEO) indexing is degraded. |

### PDF/A and Accessibility Compliance
*   **PDF/A Compliance**: The ISO standard for long-term archiving (PDF/A) requires a valid XMP `/Metadata` stream. Stripping `/Metadata` invalidates PDF/A compliance immediately.
*   **Tagged PDFs (Accessibility)**: Screen readers rely on a structural hierarchy tree under `/StructTreeRoot` inside the Document Catalog. Stripping `/StructTreeRoot` or its referenced objects destroys accessibility compliance (Section 508 / PDF/UA). **We must never sweep `/StructTreeRoot` paths**.

---

## 7. Hands-On Exercises

### A. Beginner: Extract and Print XMP Metadata
Write a program that loads a PDF using PDFBox, accesses the `/Metadata` stream from the Document Catalog, reads it as an input stream, and prints the raw XML content to the console. If no metadata exists, print a message.

### B. Intermediate: Attachment Auditor
Write a utility that traverses the `/Names` dictionary of a PDF, inspects the `/EmbeddedFiles` name tree, prints the name and size of every embedded file, and calculates the total percentage of the PDF file size consumed by attachments.

### C. Advanced: Page Thumbnail Inspector
Write a program that iterates through all pages in a PDF, checks for the presence of the `/Thumb` dictionary entry, and prints the width, height, and compressed size of the thumbnail image streams found.

---

## 8. Mini Project: PdfCleanupEngine

### Objective
Create a command-line tool `PdfCleanupEngine` that performs four structural hygiene passes:
1.  **Metadata Pruning**: Removes the `/Metadata` (XMP) stream and strips non-essential metadata from the `/Info` dictionary.
2.  **Attachment Stripping**: Strips the `/EmbeddedFiles` tree from the Document Catalog.
3.  **Thumbnail Stripping**: Removes `/Thumb` references from all pages.
4.  **Resource Deduplication**: Uses SHA-256 hashing to identify duplicate stream objects and merges them.

The program must compile using Java 21+ and Apache PDFBox 3.0.2. It must track and output statistics showing how many bytes were saved by each pass.

### Java Implementation

Save this code to `src/main/java/com/example/pdf/cleanup/PdfCleanupEngine.java`:

```java
package com.example.pdf.cleanup;

import org.apache.pdfbox.cos.*;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.io.MemoryUsageSetting;

import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.*;

public class PdfCleanupEngine {

    public record CleanupReport(
            long initialSize,
            long finalSize,
            int thumbnailsRemoved,
            int attachmentsRemoved,
            int duplicateStreamsMerged,
            long metadataBytesSaved
    ) {
        public void printReport() {
            System.out.println("══════════════════════════════════════════════════════════════════════");
            System.out.println("                     PDF CLEANUP ENGINE REPORT                        ");
            System.out.println("══════════════════════════════════════════════════════════════════════");
            System.out.printf(" Initial File Size:         %s%n", formatSize(initialSize));
            System.out.printf(" Final File Size:           %s%n", formatSize(finalSize));
            System.out.printf(" Thumbnails Removed:        %d%n", thumbnailsRemoved);
            System.out.printf(" Attachments Removed:       %d%n", attachmentsRemoved);
            System.out.printf(" Duplicate Streams Merged:   %d%n", duplicateStreamsMerged);
            System.out.printf(" Metadata Bytes Reclaimed:  %s%n", formatSize(metadataBytesSaved));
            long totalSaved = initialSize - finalSize;
            double percentage = initialSize == 0 ? 0.0 : (double) totalSaved / initialSize * 100;
            System.out.printf(" Total Reclaimed:           %s (%.2f%%)%n", formatSize(totalSaved), percentage);
            System.out.println("══════════════════════════════════════════════════════════════════════");
        }

        private String formatSize(long bytes) {
            if (bytes >= 1_048_576) return String.format("%.2f MB", bytes / 1_048_576.0);
            if (bytes >= 1024) return String.format("%.2f KB", bytes / 1024.0);
            return bytes + " B";
        }
    }

    public static CleanupReport clean(File inputFile, File outputFile) throws IOException {
        long initialSize = inputFile.length();
        int thumbnailsRemoved = 0;
        int attachmentsRemoved = 0;
        int duplicateStreamsMerged = 0;
        long metadataBytesSaved = 0;

        // Configure PDFBox to load the document using a memory-mapped temporary file
        try (PDDocument doc = PDDocument.load(inputFile, MemoryUsageSetting.setupTempFileOnly())) {
            COSDictionary catalog = doc.getDocumentCatalog().getCOSObject();

            // 1. Strip Metadata stream
            if (catalog.containsKey(COSName.METADATA)) {
                COSBase metadataBase = catalog.getDictionaryObject(COSName.METADATA);
                if (metadataBase instanceof COSStream metadataStream) {
                    metadataBytesSaved += metadataStream.getInt(COSName.LENGTH, 0);
                }
                catalog.removeItem(COSName.METADATA);
            }

            // 2. Strip non-essential fields from Info Dictionary
            COSDictionary info = doc.getDocumentInformation().getCOSObject();
            if (info != null) {
                // Keep only critical creator information
                Set<COSName> keysToKeep = Set.of(COSName.PRODUCER, COSName.CREATOR);
                List<COSName> currentKeys = new ArrayList<>(info.keySet());
                for (COSName key : currentKeys) {
                    if (!keysToKeep.contains(key)) {
                        info.removeItem(key);
                    }
                }
            }

            // 3. Strip Page Thumbnails
            for (PDPage page : doc.getPages()) {
                COSDictionary pageDict = page.getCOSObject();
                if (pageDict.containsKey(COSName.THUMB)) {
                    pageDict.removeItem(COSName.THUMB);
                    thumbnailsRemoved++;
                }
            }

            // 4. Strip Embedded File Attachments
            if (catalog.containsKey(COSName.NAMES)) {
                COSBase namesBase = catalog.getDictionaryObject(COSName.NAMES);
                if (namesBase instanceof COSDictionary namesDict) {
                    if (namesDict.containsKey(COSName.EMBEDDED_FILES)) {
                        namesDict.removeItem(COSName.EMBEDDED_FILES);
                        attachmentsRemoved++;
                    }
                    if (namesDict.isEmpty()) {
                        catalog.removeItem(COSName.NAMES);
                    }
                }
            }

            // 5. Deduplicate identical streams
            duplicateStreamsMerged = deduplicateStreams(doc);

            // Save the document. PDFBox will automatically write only the referenced objects.
            doc.save(outputFile);
        }

        long finalSize = outputFile.length();
        return new CleanupReport(
                initialSize,
                finalSize,
                thumbnailsRemoved,
                attachmentsRemoved,
                duplicateStreamsMerged,
                metadataBytesSaved
        );
    }

    private static int deduplicateStreams(PDDocument doc) throws IOException {
        int mergedCount = 0;
        MessageDigest digest;
        try {
            digest = MessageDigest.getInstance("SHA-256");
        } catch (NoSuchAlgorithmException e) {
            throw new RuntimeException("SHA-256 digest unavailable", e);
        }

        // Map containing Hash -> Indirect reference of the first unique COSStream
        Map<String, COSObject> hashToUniqueStream = new HashMap<>();

        // Locate all COSObject entries that contain COSStream instances
        List<COSObject> allObjects = new ArrayList<>(doc.getDocument().getObjects());

        for (COSObject cosObject : allObjects) {
            COSBase dereferenced = cosObject.getObject();
            if (dereferenced instanceof COSStream stream) {
                // Compute the hash of the uncompressed stream data
                String streamHash = computeStreamHash(stream, digest);
                if (streamHash == null) continue;

                if (hashToUniqueStream.containsKey(streamHash)) {
                    COSObject originalObject = hashToUniqueStream.get(streamHash);
                    // Redirect the duplicate to point to the original base object
                    cosObject.setObject(originalObject.getObject());
                    mergedCount++;
                } else {
                    hashToUniqueStream.put(streamHash, cosObject);
                }
            }
        }
        return mergedCount;
    }

    private static String computeStreamHash(COSStream stream, MessageDigest digest) {
        digest.reset();
        byte[] buffer = new byte[8192];
        int read;
        try (InputStream in = stream.createInputStream()) {
            while ((read = in.read(buffer)) != -1) {
                digest.update(buffer, 0, read);
            }
        } catch (IOException e) {
            // Unparseable stream or decryption failure, skip optimization
            return null;
        }
        byte[] hashBytes = digest.digest();
        StringBuilder hexString = new StringBuilder();
        for (byte b : hashBytes) {
            String hex = Integer.toHexString(0xff & b);
            if (hex.length() == 1) hexString.append('0');
            hexString.append(hex);
        }
        return hexString.toString();
    }

    public static void main(String[] args) {
        if (args.length < 2) {
            System.out.println("Usage: java PdfCleanupEngine <input-pdf> <output-pdf>");
            return;
        }

        File input = new File(args[0]);
        File output = new File(args[1]);

        try {
            CleanupReport report = clean(input, output);
            report.printReport();
        } catch (IOException e) {
            System.err.println("Cleanup failed with error:");
            e.printStackTrace();
        }
    }
}
```

---

## 9. Common Mistakes

### 1. Stripping Metadata from PDF/A (Archival) Documents
*   *Symptom*: Output PDF passes standard viewers but fails long-term preservation checks (Verapdf, Acrobat Preflight).
*   *Cause*: The cleanup engine stripped `/Metadata` from a PDF/A compliant document. PDF/A strictly mandates embedded metadata in XMP format.
*   *Prevention*: Inspect the Document Catalog for `/GTS_PDFA14` or `/OutputIntents` containing PDF/A identifier dictionaries. If present, bypass XMP stripping.

### 2. Modifying Metadata in Digitally Signed PDFs
*   *Symptom*: Opening the optimized PDF displays a warning: "Document has been altered since signature was applied."
*   *Cause*: Modifying keys in `/Info` or stripping `/Metadata` changes the document byte structure, invalidating the byte ranges protected by digital signatures.
*   *Prevention*: (See Module 14) Detect the presence of signatures (`/Sig` annotations or `/V` entries in form dictionaries) and immediately abort any cleanup optimization passes.

### 3. Deduplicating Streams of Different Subtypes
*   *Symptom*: Images display incorrectly, or fonts render as garbled symbols.
*   *Cause*: The deduplication hash was calculated only on the uncompressed stream bytes, but the dictionary metadata (e.g., width, height, decoding parameters) differed between the references.
*   *Prevention*: When deduplicating streams, confirm that structural dictionary metadata matches or that you are only replacing the stream object content, not the metadata dictionaries that reference them.

---

## 10. Assessment

### Quiz

1.  **Why does stripping the XMP `/Metadata` stream invalidate PDF/A compliance?**
    *   A. PDF/A requires the file extension to be `.xml`.
    *   B. The PDF/A specification mandates that metadata must be embedded as an XML stream conformant to the XMP standard.
    *   C. Stripping metadata corrupts the cross-reference table formatting.
    *   D. PDF/A documents are encrypted, making metadata removal impossible.

2.  **Which directory path starting from `/Root` points to embedded file attachments?**
    *   A. `/Root` -> `/Pages` -> `/Thumb`
    *   B. `/Root` -> `/Names` -> `/EmbeddedFiles`
    *   C. `/Root` -> `/Outlines` -> `/Attachments`
    *   D. `/Root` -> `/Metadata` -> `/Attachments`

3.  **What is the consequence of deleting the `/Thumb` entry from a Page dictionary?**
    *   A. The page can no longer be rendered by PDF viewers.
    *   B. Page previews are deleted and modern PDF readers will render previews on-the-fly, reclaiming size without losing usability.
    *   C. The page orientation changes from landscape to portrait.
    *   D. PDF text-searching ceases to function.

4.  **When deduplicating streams with SHA-256, why must we hash the *decoded* (uncompressed) stream data rather than the raw bytes in the file?**
    *   A. The PDF specification forbids hashing compressed bytes.
    *   B. Identical content might be compressed with different algorithms or settings (e.g. Flate vs. LZW, or different compression levels), producing distinct file-level bytes for identical raw data.
    *   C. The Java `MessageDigest` library does not support compressed arrays.
    *   D. Decoded bytes are always smaller than compressed bytes.

5.  **What is the "Mark" phase of a PDF mark-and-sweep algorithm?**
    *   A. Drawing watermark stamps onto each page stream.
    *   B. Generating SHA-256 hashes for all dictionary keys.
    *   C. Recursively traversing the document starting from `/Root` and marking all reachable indirect object numbers as active.
    *   D. Inserting warning tags inside corrupt PDF trailers.

<details>
<summary><b>Click to reveal answers</b></summary>

1. **B** — PDF/A is an ISO standard requiring all metadata to be structured as XMP XML. Stripping it violates the validation schema.
2. **B** — Attachments are stored within the `/Names` dictionary inside the `/EmbeddedFiles` name tree.
3. **B** — Removing `/Thumb` deletes the pre-rendered preview streams. Modern readers construct thumbnails instantly in memory.
4. **B** — Two identical streams might have been compressed with different tools, resulting in different raw file bytes. Hashing decoded streams ensures content identity.
5. **C** — Traversal from `/Root` maps the reachability graph; any unmarked objects in the document catalog structure are candidates for deletion.
</details>

---

## 11. Interview Perspective

### Common Interview Question
> "A 50-page PDF is 85 MB. Image sizes only account for 40 MB. Walk me through identifying and eliminating the remaining 45 MB."

### Expected Reasoning
The candidate should demonstrate a structured approach to analyzing PDF size composition:
1.  **Inventory & Measurement**: Use a tool (like our `COS` inspector or a structural parser) to list all objects and determine what object types consume the 45 MB.
2.  **Hypothesis Generation**:
    *   Could there be embedded files (attachments)?
    *   Are there duplicate image or font streams stored under separate object numbers?
    *   Do pages contain large embedded JPEG thumbnails (`/Thumb`)?
    *   Is there a giant XML metadata block (`/Metadata`) containing Photoshop history or printing configuration?
3.  **Remediation Plan**:
    *   **Attachments**: Prune `/EmbeddedFiles` from the `/Names` tree.
    *   **Thumbnails**: Drop `/Thumb` from all page dictionaries.
    *   **Duplicates**: Run a cryptographic hash deduplication step.
    *   **Orphans**: Perform a mark-and-sweep graph traversal to purge unreferenced objects.

### Sample Answers

#### Strong Answer
> "To resolve the 45 MB discrepancy, I would first run a structural audit to classify object types by byte size.
>
> First, I would check for embedded attachments. Large CAD diagrams or data spreadsheets can hide in the `/Names` tree under `/EmbeddedFiles`. Removing this reference disconnects them.
>
> Second, I'd check for duplicate stream objects. If the document was merged, it might contain 50 copies of the same company logo or font stream. I'd calculate SHA-256 hashes of the uncompressed stream contents and rewrite references to point to a single instance.
>
> Third, I would check if scanner software embedded pre-rendered page thumbnails under `/Thumb` in the page dictionaries. Removing these keys forces viewers to render thumbnails dynamically, which saves considerable space.
>
> Lastly, I would execute a mark-and-sweep reachability traversal from the `/Root` catalog. This ensures that when the file is rewritten, any unreferenced orphan objects are completely removed, reclaiming the 45 MB without impacting page content."

#### Weak Answer
> "I would compress the PDF again using a standard zip program or re-convert the whole PDF into a set of images, then compress those images. That would make it smaller, but it might ruin the resolution."
