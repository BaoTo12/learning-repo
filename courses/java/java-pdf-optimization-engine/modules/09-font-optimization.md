# Module 09: Font Optimization

---

## 1. Why This Module Exists

Font data is frequently overlooked during PDF optimization, yet it is a significant contributor to file size. A PDF generated from a word processor or design application often embeds complete font programs — the full set of glyph outlines for every character in a language's character repertoire. An Arabic, Chinese, Japanese, or Korean font can embed 15,000–65,000 glyph definitions, even when a document uses only 30 of them.

Consider a realistic example:
*   A 10-page business proposal uses Noto Sans CJK as its body font.
*   The document contains approximately 200 unique Chinese characters.
*   The full Noto Sans CJK Regular font program is ~22 MB.
*   Only the glyph outlines for those 200 characters are needed — approximately 400 KB.

An unoptimized PDF embeds the full 22 MB. An optimized PDF with font subsetting embeds only 400 KB — a 98% reduction in font data alone.

This module teaches you how to identify, inspect, classify, and optimize embedded fonts in Java PDF applications.

---

## 2. Learning Objectives

By the end of this module, you will be able to:
*   **Identify** the five PDF font types and explain the structure of a font dictionary.
*   **Determine** whether a font is fully embedded, subsetted, or referenced externally.
*   **Recognize** the Standard 14 (Base 14) fonts and explain why they require no embedding.
*   **Calculate** the byte contribution of font streams to total PDF file size.
*   **Implement** a `FontStreamInspector` tool using PDFBox to enumerate all fonts in a document.
*   **Evaluate** the compatibility and semantic risks of font removal and substitution.
*   **Design** font optimization rules appropriate for each compression profile from Module 6.

---

## 3. Conceptual Foundations

### Why Fonts Are Embedded
PDF's design goal is **device-independent rendering**: a document opened on any device, operating system, or PDF reader must look identical to how the author intended. This requires that the exact glyph shapes be embedded in the file itself.

Without embedding, a PDF reader must rely on fonts installed on the local machine. If the required font is absent, the reader substitutes a similar font — which may have different character widths, leading, and glyph shapes, causing text reflow and layout differences. For legal documents, contracts, and branded materials, this is unacceptable.

### Full Embedding vs. Font Subsetting

```
Full Font Embedding                   Font Subsetting
────────────────────                  ─────────────────
Font file contains all 65,536         Font file contains ONLY the
possible glyph definitions.           glyphs actually used in the document.

Example: "a", "b", ..., all CJK,      Example: glyphs for "Hello World"
all Greek, all Cyrillic...            → H, e, l, o, W, r, d (7 glyphs only)

Size: 5–22 MB per font                Size: 5–50 KB per font
```

### Subset Prefix Notation
The PDF specification requires that subsetted fonts be identifiable. A subset font's `/BaseFont` name is prefixed with a **6-character uppercase random tag** followed by a plus sign:

```
/BaseFont /ABCDEF+NotoSansCJK-Regular
           ──────
           6-char random prefix — this font is a subset
```

If no prefix is present, the font is either fully embedded or externally referenced. This naming convention is your primary signal for detecting subset status.

---

## 4. Technical Topics

### 4.1 PDF Font Types

| Type | Dictionary `/Subtype` | Glyph Format | Typical Source |
| :--- | :--- | :--- | :--- |
| **Type 1** | `/Type1` | PostScript Type 1 outlines | Adobe legacy fonts (Times, Helvetica) |
| **TrueType** | `/TrueType` | TrueType glyph tables (`glyf` table) | Windows/Mac system fonts |
| **CIDFont Type 0** | `/CIDFontType0` | CFF/Type 2 CID-keyed | OpenType CFF, CJK fonts |
| **CIDFont Type 2** | `/CIDFontType2` | TrueType CID-keyed | OpenType TrueType, CJK fonts |
| **Type 3** | `/Type3` | Inline PDF content streams | Custom glyphs, bitmaps, special symbols |

**Type 0 (Composite Font)**: A wrapper font that references one of the CIDFont types above. Used for multi-byte character encodings (required for CJK text). Its dictionary has a `/DescendantFonts` array pointing to the actual CIDFont.

**Type 3**: Unique because glyphs are defined as PDF content streams (using the same drawing operators as page content). They are never embedded as a font program — the glyph shapes are part of the PDF document body itself.

### 4.2 Font Descriptor Dictionary

The `/FontDescriptor` dictionary is where the actual font program binary is stored. It contains:

```
<< /Type /FontDescriptor
   /FontName /ABCDEF+ArialMT
   /Flags 32
   /FontBBox [-664 -210 2000 728]
   /ItalicAngle 0
   /Ascent 1854
   /Descent -434
   /CapHeight 716
   /StemV 80
   /FontFile2 14 0 R          ← TrueType font binary (indirect reference)
>>
```

| Dictionary Key | Content |
| :--- | :--- |
| `/FontFile` | Type 1 font binary (PFB) |
| `/FontFile2` | TrueType font binary (TTF) |
| `/FontFile3` | OpenType font binary (OTF/CFF, compressed) |

### 4.3 The Standard 14 (Base 14) Fonts
These fourteen fonts are guaranteed to be available in every PDF reader that conforms to the PDF specification. They **never need to be embedded**:

| Font Name | Family | Style |
| :--- | :--- | :--- |
| Helvetica | Sans-serif | Regular |
| Helvetica-Bold | Sans-serif | Bold |
| Helvetica-Oblique | Sans-serif | Italic |
| Helvetica-BoldOblique | Sans-serif | Bold Italic |
| Times-Roman | Serif | Regular |
| Times-Bold | Serif | Bold |
| Times-Italic | Serif | Italic |
| Times-BoldItalic | Serif | Bold Italic |
| Courier | Monospace | Regular |
| Courier-Bold | Monospace | Bold |
| Courier-Oblique | Monospace | Italic |
| Courier-BoldOblique | Monospace | Bold Italic |
| Symbol | Symbol | — |
| ZapfDingbats | Dingbats | — |

**Optimization opportunity**: If a document embeds a full copy of Helvetica (approximately 200 KB), but Helvetica is a Standard 14 font, the embedded program is 100% redundant and can be removed — saving 200 KB with zero rendering impact.

### 4.4 Glyph-to-Character Mapping: `/ToUnicode` CMap
The `/ToUnicode` stream in a font dictionary maps glyph IDs back to Unicode code points. This mapping is used by PDF readers for:
*   **Text search**: Finding text content in the document.
*   **Copy-paste**: Correctly extracting text when a user copies from the PDF.
*   **Accessibility**: Screen reader text extraction.

When subsetting a font, the `/ToUnicode` CMap must be preserved or regenerated to cover exactly the glyphs in the subset. **Stripping `/ToUnicode` breaks text searchability and copy-paste** — even if the visual rendering is unchanged.

### 4.5 CJK Font Considerations

CJK (Chinese, Japanese, Korean) fonts present unique challenges:

| Property | Typical Latin Font | Typical CJK Font |
| :--- | :--- | :--- |
| Total glyphs | 200–1,000 | 6,000–65,000 |
| Full embed size | 50–300 KB | 10–25 MB |
| Subset size for 200 chars | 5–20 KB | 150–500 KB |
| Subsetting savings | 90–95% | 97–99% |

CJK font subsetting is therefore one of the highest-ROI optimization steps for documents containing any CJK text. PDFBox supports CJK font loading and subset embedding via `PDType0Font.load(doc, fontStream, true)` (the `true` flag enables subsetting).

---

## 5. Internal Mechanisms

### How a PDF Reader Resolves Font Glyphs

```
Text rendering request: "Draw character U+4E2D (中) at position (x, y)"
│
├── Look up the active font object in the current graphics state
│
├── Locate the font's /Widths or /W (CIDFont widths) array
│   → Determine how far to advance the cursor after this character
│
├── Locate the font's glyph data:
│   ├── /FontFile2 → parse TrueType glyph table → get glyph outline
│   └── /FontFile3 → decompress CFF data → get Type 2 charstring
│
├── Scale glyph outline to current font size
│
└── Rasterize scaled outline to screen/printer pixels
```

If the font program is absent (not embedded) and the font is not a Standard 14 font, the reader performs **font substitution** — selecting the closest available system font, which may have different metrics.

### Font Stream Compression Chain

A font's binary program is typically stored as a compressed stream:
```
/FontFile2 14 0 R
  ↓
Object 14:
<< /Length 48231 /Filter /FlateDecode /Length1 125440 >>
stream
[ FlateDecode-compressed TrueType binary ]
endstream
```

`/Length1` is the uncompressed size of the TrueType binary. The `/Length` is the compressed size stored in the file. To inspect the font binary, you must first apply `Inflater` to the stream bytes.

### Subset Prefix Generation
When PDFBox subsets a font, it generates the 6-character random prefix by selecting random uppercase letters. The prefix is appended to `/BaseFont` and also embedded in the font's internal `name` table (the TrueType `name` table at ID 4: Full Font Name). This ensures that two different subsets of the same base font have distinct names and do not share glyph caches in a PDF reader.

---

## 6. Trade-Off Analysis

### Font Embedding Strategies

| Strategy | Size Impact | Rendering Fidelity | Text Searchability | Compatibility |
| :--- | :--- | :--- | :--- | :--- |
| **Full Embedding** | Largest (100%) | ✅ Exact | ✅ Full | ✅ All readers |
| **Font Subsetting** | 60–99% reduction | ✅ Exact (for used chars) | ✅ Full | ✅ All readers (PDF 1.2+) |
| **Standard 14 Reference** | Zero (no embed) | ⚠️ Metric differences on non-Adobe | ✅ Full | ✅ All conformant readers |
| **No Font Data** | Zero | ❌ Reader substitutes | ❌ May break | ❌ Breaks on missing fonts |

### When Standard 14 Substitution Is Safe

**Safe**:
*   The document was designed using Helvetica, Times, Courier, Symbol, or ZapfDingbats.
*   The author embedded a full copy of one of these fonts despite not needing to.
*   The document is a simple form or report with no custom glyph metrics.

**Unsafe**:
*   The font has the same name as a Standard 14 font but has customized kerning, ligatures, or OpenType features.
*   The font contains custom glyphs (logos, symbols) mapped to Standard 14 name characters.
*   The document is a legal contract where the exact text reflow must be preserved.

### When Font Subsetting Is Safe

**Safe**:
*   The document is read-only (not intended for further editing in a PDF editor).
*   The character set used in the document is stable and will not change.
*   Copy-paste and text search must work (preserve `/ToUnicode`).

**Unsafe**:
*   The document is a fillable form or is intended to receive additional text (future characters may not be in the subset).
*   The subset corrupts the `/ToUnicode` CMap (this is a library bug to watch for).

---

## 7. Hands-On Exercises

### A. Beginner: List All Fonts in a PDF
*   Load a PDF with PDFBox.
*   Iterate all pages and all fonts in each page's resource dictionary (`resources.getFontNames()`, `resources.getFont(name)`).
*   Print: font name, `/Subtype`, `/BaseFont`, and whether a subset prefix is present.

### B. Intermediate: Identify Fully Embedded vs. Subsetted vs. Standard 14
*   Extend exercise A to inspect each font's `/FontDescriptor` for `/FontFile`, `/FontFile2`, or `/FontFile3`.
*   Classify as: `FULL_EMBED`, `SUBSET`, `STANDARD_14`, or `NOT_EMBEDDED`.
*   Print the compressed stream size for each embedded font.

### C. Advanced: Calculate Total Font Byte Contribution
*   For each embedded font (full or subset), read the `/FontFile*` stream length.
*   Sum total font bytes across the document.
*   Calculate what percentage of the total file size is attributable to fonts.
*   Flag any fonts that could be Standard 14 substitutions (matching `/BaseFont` against the Standard 14 list).

---

## 8. Mini Project: FontStreamInspector

### Objective
Build a tool that produces a comprehensive font analysis report for any PDF, classifying every font by type, embedding status, byte size, and optimization opportunity.

### Expected Output
```text
══════════════════════════════════════════════════════════════════════
 FONT ANALYSIS REPORT: proposal_final.pdf  (Total size: 24.8 MB)
══════════════════════════════════════════════════════════════════════
 #   Base Font Name           Type       Status       Compressed Size
─────────────────────────────────────────────────────────────────────
 1   ABCDEF+NotoSansCJK-Reg   CIDFont2   SUBSET         0.4 MB  ✓
 2   NotoSansCJK-Regular      CIDFont2   FULL_EMBED    21.8 MB  ⚠ 98% reclaimable
 3   GHIJKL+Arial-Bold        TrueType   SUBSET         0.02 MB ✓
 4   Helvetica                Type1      FULL_EMBED     0.2 MB  ⚠ Standard 14 (removable)
 5   Times-Roman              Type1      NOT_EMBEDDED   —       ✓
═════════════════════════════════════════════════════════════════════
 Total font bytes:   22.4 MB (90.3% of file)
 Reclaimable:        22.0 MB (removing full embeds + Standard 14 copies)
══════════════════════════════════════════════════════════════════════
```

### Java Implementation Code
Write to `src/main/java/com/example/pdf/font/FontStreamInspector.java`:

```java
package com.example.pdf.font;

import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.font.PDFont;
import org.apache.pdfbox.pdmodel.font.PDFontDescriptor;
import org.apache.pdfbox.io.MemoryUsageSetting;

import java.io.File;
import java.io.IOException;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Set;

public class FontStreamInspector {

    // The Standard 14 font names — never need to be embedded
    private static final Set<String> STANDARD_14 = Set.of(
            "Helvetica", "Helvetica-Bold", "Helvetica-Oblique", "Helvetica-BoldOblique",
            "Times-Roman", "Times-Bold", "Times-Italic", "Times-BoldItalic",
            "Courier", "Courier-Bold", "Courier-Oblique", "Courier-BoldOblique",
            "Symbol", "ZapfDingbats"
    );

    public enum EmbedStatus {
        SUBSET,        // Subset prefix present; only used glyphs embedded
        FULL_EMBED,    // Full font program embedded; no subset prefix
        STANDARD_14,   // Standard 14 font; no embedding needed but program present
        NOT_EMBEDDED   // No font program in this PDF (externally referenced or Standard 14)
    }

    public record FontInfo(
            String baseFontName,
            String subtype,
            EmbedStatus status,
            long compressedBytes
    ) {}

    public static void inspect(File pdfFile) throws IOException {
        long fileSize = pdfFile.length();
        Map<String, FontInfo> fontMap = new LinkedHashMap<>();

        try (PDDocument doc = PDDocument.load(pdfFile,
                MemoryUsageSetting.setupMixed(50 * 1024 * 1024))) {

            for (int i = 0; i < doc.getNumberOfPages(); i++) {
                PDPage page = doc.getPage(i);
                PDResources resources = page.getResources();
                if (resources == null) continue;

                for (COSName fontName : resources.getFontNames()) {
                    PDFont font = resources.getFont(fontName);
                    if (font == null) continue;

                    String baseName = font.getName();
                    if (fontMap.containsKey(baseName)) continue; // Already analyzed

                    String subtype = font.getCOSObject()
                            .getNameAsString(COSName.SUBTYPE);

                    FontInfo info = classifyFont(font, baseName, subtype);
                    fontMap.put(baseName, info);
                }
            }
        }

        printReport(pdfFile.getName(), fileSize, fontMap);
    }

    private static FontInfo classifyFont(PDFont font, String baseName, String subtype)
            throws IOException {
        PDFontDescriptor descriptor = font.getFontDescriptor();

        if (descriptor == null) {
            // No font descriptor: Standard 14 or not embedded
            String stripped = stripSubsetPrefix(baseName);
            if (STANDARD_14.contains(stripped)) {
                return new FontInfo(baseName, subtype, EmbedStatus.STANDARD_14, 0L);
            }
            return new FontInfo(baseName, subtype, EmbedStatus.NOT_EMBEDDED, 0L);
        }

        COSStream fontStream = getFontStream(descriptor);
        if (fontStream == null) {
            return new FontInfo(baseName, subtype, EmbedStatus.NOT_EMBEDDED, 0L);
        }

        long streamBytes = fontStream.getInt(COSName.LENGTH, 0);
        boolean hasSubsetPrefix = hasSubsetPrefix(baseName);
        String stripped = stripSubsetPrefix(baseName);

        EmbedStatus status;
        if (hasSubsetPrefix) {
            status = EmbedStatus.SUBSET;
        } else if (STANDARD_14.contains(stripped)) {
            status = EmbedStatus.STANDARD_14;
        } else {
            status = EmbedStatus.FULL_EMBED;
        }

        return new FontInfo(baseName, subtype, status, streamBytes);
    }

    private static COSStream getFontStream(PDFontDescriptor descriptor) {
        COSDictionary dict = descriptor.getCOSObject();
        for (COSName key : new COSName[]{
                COSName.FONT_FILE, COSName.FONT_FILE2, COSName.FONT_FILE3}) {
            COSBase val = dict.getDictionaryObject(key);
            if (val instanceof COSStream s) return s;
        }
        return null;
    }

    private static boolean hasSubsetPrefix(String baseFontName) {
        // Subset prefix: exactly 6 uppercase letters followed by '+'
        return baseFontName.length() > 7
                && baseFontName.charAt(6) == '+'
                && baseFontName.substring(0, 6).matches("[A-Z]{6}");
    }

    private static String stripSubsetPrefix(String name) {
        if (hasSubsetPrefix(name)) return name.substring(7);
        return name;
    }

    private static void printReport(String filename, long fileSize,
                                    Map<String, FontInfo> fontMap) {
        System.out.println("\n══════════════════════════════════════════════════════════════════════");
        System.out.printf( " FONT ANALYSIS REPORT: %-30s (Total: %s)%n",
                filename, humanBytes(fileSize));
        System.out.println("══════════════════════════════════════════════════════════════════════");
        System.out.printf(" %-3s  %-36s %-12s %-14s %s%n",
                "#", "Base Font Name", "Type", "Status", "Compressed Size");
        System.out.println("─────────────────────────────────────────────────────────────────────");

        long totalFontBytes = 0;
        long reclaimable = 0;
        int idx = 1;

        for (FontInfo info : fontMap.values()) {
            String name = info.baseFontName().length() > 36
                    ? info.baseFontName().substring(0, 33) + "..."
                    : info.baseFontName();
            String sizeStr = info.compressedBytes() > 0
                    ? humanBytes(info.compressedBytes())
                    : "—";
            String flag = switch (info.status()) {
                case FULL_EMBED  -> "⚠ fully embedded";
                case STANDARD_14 -> "⚠ Standard 14 (removable)";
                case SUBSET      -> "✓";
                case NOT_EMBEDDED-> "✓";
            };
            System.out.printf(" %-3d  %-36s %-12s %-14s %8s  %s%n",
                    idx++, name, info.subtype(), info.status().name(),
                    sizeStr, flag);

            totalFontBytes += info.compressedBytes();
            if (info.status() == EmbedStatus.FULL_EMBED
                    || info.status() == EmbedStatus.STANDARD_14) {
                reclaimable += info.compressedBytes();
            }
        }

        double pctOfFile = fileSize == 0 ? 0
                : (double) totalFontBytes / fileSize * 100;

        System.out.println("═════════════════════════════════════════════════════════════════════");
        System.out.printf( " Total font bytes:   %s (%.1f%% of file)%n",
                humanBytes(totalFontBytes), pctOfFile);
        System.out.printf( " Reclaimable:        %s (removing full embeds + Standard 14 copies)%n",
                humanBytes(reclaimable));
        System.out.println("══════════════════════════════════════════════════════════════════════\n");
    }

    private static String humanBytes(long b) {
        if (b >= 1_048_576) return String.format("%.1f MB", b / 1_048_576.0);
        if (b >= 1024)      return String.format("%.1f KB", b / 1024.0);
        return b + " B";
    }

    public static void main(String[] args) throws IOException {
        if (args.length < 1) {
            System.out.println("Usage: FontStreamInspector <pdf-path>");
            return;
        }
        inspect(new File(args[0]));
    }
}
```

### Extension Ideas
1.  **Subset Validator**: For each SUBSET font, decode the `/ToUnicode` CMap stream and verify it covers all character code points present in the page's content streams.
2.  **Standard 14 Remover**: For any font classified as `STANDARD_14` (embedded but unnecessary), remove the `/FontFile*` stream from the font descriptor, update the `/FontDescriptor` dictionary, and save the PDF.
3.  **CJK Subset Reporter**: For fonts whose name suggests a CJK family (NotoSansCJK, MicrosoftYaHei, etc.), calculate the theoretical maximum subset size based on actual character usage.

---

## 9. Common Mistakes

### 1. Removing Fonts That Have No Standard 14 Equivalent
*   *Symptom*: The output PDF renders with a visibly different typeface — typically substituted with a sans-serif or monospace fallback.
*   *Cause*: The engineer matched a font by visual appearance (e.g., it "looks like Helvetica") rather than by checking the `/BaseFont` name against the exact Standard 14 list.
*   *Prevention*: Only apply Standard 14 removal when the `/BaseFont` name exactly matches one of the 14 standard names (after stripping any subset prefix). Never infer by visual similarity.

### 2. Stripping `/ToUnicode` CMap Streams
*   *Symptom*: Text in the optimized PDF cannot be selected, searched, or copied. Screen readers report the document as inaccessible.
*   *Cause*: A font optimization pass that compresses font dictionaries also removes the `/ToUnicode` entry, treating it as redundant metadata.
*   *Prevention*: The `/ToUnicode` entry is never redundant for non-Standard-14 fonts. Add an explicit exclusion rule: never remove or modify a `/ToUnicode` entry.

### 3. Assuming All TrueType Fonts Are Subsets
*   *Symptom*: A report claims 95% of fonts are subsets, but the PDF file size reduction from "subsetting" is minimal.
*   *Cause*: The detection logic checks for any font with `/Subtype /TrueType` and assumes it is subsetted, without checking the `/BaseFont` name for the 6-character prefix.
*   *Prevention*: Subset detection must check the `/BaseFont` name for the `XXXXXX+` pattern, not the font type. Only fonts with that prefix are guaranteed to be subsets.

### 4. Subsetting a Font in an Editable Form PDF
*   *Symptom*: When a form is filled in and a new character is typed, that character renders as a blank square or question mark.
*   *Cause*: The font was subsetted to contain only the glyphs present at optimization time. Any new character not in the subset has no glyph definition.
*   *Prevention*: Before subsetting any font, check whether the document contains interactive form fields (`doc.getDocumentCatalog().getAcroForm() != null`). If it does, do not subset fonts used in form fields.

---

## 10. Assessment

### Quiz
1.  **You see a font with `/BaseFont /XYZABC+TimesNewRomanPSMT` in a PDF. What does the prefix `XYZABC+` indicate?**
    *   A. The font was encrypted using a six-byte XOR key.
    *   B. This is a font subset — only the glyphs actually used in the document are embedded.
    *   C. The font was licensed and the prefix is a DRM identifier.
    *   D. The font was embedded using the Standard 14 replacement protocol.

2.  **Which of the following fonts does NOT need to be embedded in a conformant PDF?**
    *   A. Noto Sans Regular
    *   B. Courier-Bold
    *   C. OpenSans-Light
    *   D. FreeSans

3.  **What is the consequence of stripping a font's `/ToUnicode` entry during optimization?**
    *   A. The document's visual rendering changes because glyph shapes are stored in `/ToUnicode`.
    *   B. The PDF file size increases because `/ToUnicode` is a required compression marker.
    *   C. Text selection, copy-paste, and search functionality break because the glyph-to-Unicode mapping is lost.
    *   D. The font reverts to Standard 14 substitution for all characters.

4.  **A 20-page PDF uses NotoSansCJK with 180 unique characters. The full font program is 22 MB. Approximately how large will the subsetted font stream be?**
    *   A. 22 MB (subsetting does not reduce CJK fonts)
    *   B. 11 MB (50% reduction)
    *   C. 350 KB (approximately 180 glyphs × ~2 KB each)
    *   D. 12 KB (only the character codes are stored, not outlines)

5.  **Why is it unsafe to subset a font embedded in an interactive form PDF?**
    *   A. PDF readers cannot display subsetted fonts in form fields.
    *   B. When a user types a character not present in the subset, the PDF has no glyph definition for it and renders a blank or fallback glyph.
    *   C. Interactive form fields require the Standard 14 Helvetica font exclusively.
    *   D. The `/AcroForm` dictionary stores a full copy of all fonts, making subsetting ineffective.

<details>
<summary><b>Click to reveal answers</b></summary>

1. **B** — The 6-char uppercase prefix followed by `+` is the PDF specification's required marker for font subsets.
2. **B** — Courier-Bold is one of the Standard 14 fonts guaranteed to be available in all conformant PDF readers.
3. **C** — `/ToUnicode` maps glyph IDs to Unicode code points. Without it, viewers cannot extract text. Visual rendering is unaffected.
4. **C** — A typical CJK glyph outline is 1–3 KB when subsetted. 180 glyphs × ~2 KB = ~360 KB. This is in the right order of magnitude.
5. **B** — Subsetting is permanent: only glyphs used at optimization time are included. Future characters typed into a form field have no glyph definition.
</details>

### Design Question
You are building the font optimization module for the Extreme compression profile. Write the decision rules (as pseudocode or a flowchart) for whether to:
(a) Remove an embedded font program entirely (Standard 14 safe substitution).
(b) Subset the font.
(c) Preserve the font program unchanged.

Include the conditions under which each rule applies. Make sure your rules handle CJK fonts, form PDFs, and PDF/A compliance requirements correctly.

---

## 11. Interview Perspective

### Common Interview Question
> "A PDF contains an embedded 22 MB CJK font. Only 80 Chinese characters are actually used in the document. How do you safely reduce its font footprint?"

### Expected Reasoning
*   The document uses a CJK font with a huge glyph set, but only a tiny fraction is needed.
*   The correct approach is **font subsetting**: rebuild the font program to include only the 80 glyphs' outlines and their corresponding `/ToUnicode` CMap entries.
*   Safety checks: verify the document is not an editable form (which would prevent future character additions), and preserve the `/ToUnicode` CMap so text search and copy-paste continue to work.
*   PDFBox approach: use `PDType0Font.load(document, inputStream, true)` with the embed-subset flag, re-embed from the original font file, then re-flow the text through PDFBox's text engine to regenerate the subset with exactly the required glyphs.

### Sample Answers

#### Strong Answer
> "First I'd confirm the font is NOT a subset already — I'd check the `/BaseFont` name for the `XXXXXX+` prefix. If it's a full embed (`NotoSansCJK-Regular` with no prefix), the 22 MB is fully reclaimable down to roughly 200–400 KB for 80 characters.
>
> I'd use PDFBox's `PDType0Font.load()` with `embedSubset=true`. This requires the original `.ttf` or `.otf` font file, which I either provide or locate from the system font directory. PDFBox's text content engine tracks which glyph IDs appear in each page's content stream and builds a minimal subset.
>
> Before doing this, I'd check: (1) no interactive form fields use this font — if they do, I preserve the full embed; (2) the document is not PDF/A — if it is, subsetting rules change under PDF/A-1b vs. PDF/A-2b; (3) the `/ToUnicode` CMap is regenerated correctly for the subset — I'd verify by extracting text from the output PDF and checking it matches the original."

#### Weak Answer
> "I'd delete the font stream from the PDF and tell the viewer to substitute with a system font. That would save all 22 MB. The text will still display because the viewer will find a similar font."
