# Module 03: File Formats

With the basic mechanics of B-Trees covered, we are now ready to explore how B-Trees and other structures are implemented on disk.

We access the disk in a way that is different from how we access main memory:

- **Main Memory**: Accesses are mostly automatic. Because of **virtual memory**, we do not have to manage physical offsets manually.
- **Disk Storage**: Accessed using **system calls**. We must specify the exact offset inside the target file and then translate the on-disk representation into a format suitable for main memory.

This means that efficient on-disk structures must be designed with this difference in mind. To do that, we must create a file format that is easy to build, modify, and interpret. In this module, we discuss key principles and practices that help us design all sorts of on-disk structures, not just B-Trees.

> **Key Rule**: Understanding B-Tree operations like splits and merges is necessary, but not enough for a real-world implementation. On-disk B-Trees are best thought of as a **page management mechanism** where algorithms compose, navigate, and calculate offsets for physical pages.

Since most of the complexity in B-Trees comes from mutability, we focus on page layouts, splits, relocations, and other concepts for mutable data structures. Later, in **Module 07**, we will discuss **LSM Trees**, focusing on sorting and maintenance where most of their complexity lies.

---

## Motivation

Creating a file format is similar to creating data structures in languages with an **unmanaged memory model** (like C). We allocate a block of memory and slice it using fixed-size primitive types and structures. To reference a larger chunk of memory or a variable-sized structure, we use pointers.

However, there is a major difference:

- **In-Memory**: Languages with unmanaged memory allow us to allocate memory without worrying about whether a contiguous segment is available, how fragmented it is, or what happens after we free it.
- **On-Disk**: We must handle **garbage collection** and **fragmentation** ourselves. Data layout is much more critical on disk. To keep disk-resident structures efficient, we must design binary formats that allow quick access, consider physical media constraints, and deserialize data efficiently.

> ### 💡 Beginner's Corner: The Fragmentation Problem
>
> - **The Problem**: Imagine you write three user records sequentially on disk: Alice (100 bytes), Bob (100 bytes), and Charlie (100 bytes). Now, Bob updates his profile and adds a bio, so his record grows to 150 bytes.
>     - Since Charlie's record is right next to Bob's, Bob's updated record cannot fit in his original spot without overwriting Charlie!
>     - If Bob is deleted, we are left with a 100-byte "hole" of empty space. If we later want to insert David (120 bytes), he won't fit in that hole.
> - **Why this matters**: In RAM, the operating system's memory manager hides these details. On disk, the database must manage these "holes" (fragmentation) manually to avoid wasting disk space and causing slow, scattered reads.

Without helper libraries, low-level memory tracking is challenging because we can only operate with memory segments of predefined size, and we must track which segments are released and which ones are in use.

In main memory, most layout issues do not exist or are easily solved using standard libraries. For example, handling variable-length fields is straightforward because we can use pointers to arbitrary memory. While developers sometimes design custom memory layouts to optimize for CPU cache lines and prefetching, this is done purely for performance optimization. On disk, these details are critical to correctness and basic performance.

---

## Binary Encoding

To store data on disk efficiently, it must be encoded in a format that is compact and easy to read and write. Because we do not have direct memory commands like `alloc` or `free` on disk—only `read` and `write` system calls—we must think of accesses differently and prepare our data layout accordingly.

### Primitive Types

Keys and values are represented in their raw binary forms (serialized to and deserialized from disk). Most numeric data types are represented as fixed-size values. When working with multibyte numeric values, it is critical to use the same **byte-order (endianness)** for both encoding and decoding.

> **Definitions**:
>
> - **Big-Endian**: The byte order starts from the **Most-Significant Byte (MSB)** and ends at the **Least-Significant Byte (LSB)**. The MSB has the lowest memory address.
> - **Little-Endian**: The byte order starts from the **Least-Significant Byte (LSB)** and ends at the **Most-Significant Byte (MSB)**. The LSB has the lowest memory address.

Below is a visualization of the 32-bit hexadecimal integer `0xAABBCCDD` (where `AA` is the MSB) stored under both byte orders:

#### Big Endian

| Address `a` | Address `a+1` | Address `a+2` | Address `a+3` |
| :---------: | :-----------: | :-----------: | :-----------: |
| `AA` (MSB)  |     `BB`      |     `CC`      |     `DD`      |

#### Little Endian

| Address `a` | Address `a+1` | Address `a+2` | Address `a+3` |
| :---------: | :-----------: | :-----------: | :-----------: |
|    `DD`     |     `CC`      |     `BB`      |  `AA` (MSB)   |

_Figure 3-1. Big- and little-endian byte order. The most significant byte is shown in gray. Addresses, denoted by a, grow from left to right._

> **Example**: To reconstruct a 64-bit integer, engines like `RocksDB` check the target platform's byte order. If the platform's endianness does not match the value's endianness, it uses a transformation function to read and reverse the bytes.

#### Numeric Type Sizes:

- `byte`: 1 byte (8 bits)
- `short`: 2 bytes (16 bits)
- `int`: 4 bytes (32 bits)
- `long`: 8 bytes (64 bits)
- `float` / `double`: Floating-point numbers represented by their sign, fraction, and exponent according to the **IEEE 754** standard. A 32-bit `float` uses 1 bit for the sign, 8 bits for the exponent, and 23 bits for the fraction.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//1cad5583-838e-4e5e-9f31-668502937614/markdown_0/imgs/img_in_image_box_139_922_1048_1031.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A21%3A58Z%2F-1%2F%2F63bb83d10e8a4e4e38e32f190cfd47a4757ab5fca14e7632e3bac2b8efe57c0b" alt="Image" width="76%" /></div>
<div style="text-align: center;">Figure 3-2. Binary representation of single-precision float number</div>

### Strings and Variable-Size Data

Unlike fixed-size primitive numbers, strings and variable-sized arrays are serialized by writing their length first, followed by the actual data bytes. This layout is called a **Pascal String** or **UCSD String**:

```c
struct String {
    uint16_t size;
    char data[size];
};
```

- **Alternative**: **Null-terminated strings**, where the reader consumes bytes until hitting a null byte (`\0`).
- **Advantage of Pascal Strings**: Finding the length of a string is an $O(1)$ constant-time operation (no need to scan the entire string), and deserialization is fast because the reader can allocate a buffer of the exact size immediately.

### Bit-Packed Data: Booleans, Enums, and Flags

- **Booleans**: Instead of wasting a whole byte (8 bits) for a single true/false value, databases pack eight boolean values into a single byte. Each bit represents a boolean (1 for set/true, 0 for unset/false).
- **Enums**: Used to represent frequently repeated, low-cardinality values as small integers. For example, B-Tree node types:
    ```c
    enum NodeType {
        ROOT = 0x00,
        INTERNAL = 0x01,
        LEAF = 0x02
    };
    ```
- **Flags**: A combination of packed booleans and enums representing overlapping named parameters. Because each bit represents a flag, we use power-of-two masks:
    ```c
    int IS_LEAF_MASK = 0x01;         // Bit 0 (0001b)
    int VARIABLE_SIZE_VALUES = 0x02; // Bit 1 (0010b)
    int HAS_OVERFLOW_PAGES = 0x04;   // Bit 2 (0100b)
    ```

Flags are read and written using bitwise operators:

```c
// Set a flag (Bitwise OR)
flags |= HAS_OVERFLOW_PAGES;
flags |= (1 << 2);

// Unset a flag (Bitwise AND with negation)
flags &= ~HAS_OVERFLOW_PAGES;
flags &= ~(1 << 2);

// Test if a flag is set
bool is_set = (flags & HAS_OVERFLOW_PAGES) != 0;
bool is_set = (flags & (1 << 2)) != 0;
```

---

## General Principles

When designing a file format, the first step is deciding the page size. Most in-place update engines divide files into fixed-size **pages** (usually matching physical disk blocks) to simplify read/write offsets. Append-only engines also write data page-wise: records are collected in memory and flushed to disk once a page boundary is reached.

### File Organization

A typical database file consists of:

1.  **Header**: A fixed-size block at the start of the file storing magic numbers, version info, and offsets to other segments.
2.  **Pages**: The main body of the file, split into fixed-size segments.
3.  **Trailer**: An optional fixed-size block at the end of the file holding metadata or lookup tables.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//1cad5583-838e-4e5e-9f31-668502937614/markdown_4/imgs/img_in_image_box_141_730_1050_981.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A22%3A00Z%2F-1%2F%2F894dc4e9b834ea326790057c7d8a781268303c4d6ac1d2a5def207a010873e57" alt="Image" width="76%" /></div>
<div style="text-align: center;">Figure 3-3. File organization</div>

#### Schema Layout Optimization

If the database has a fixed schema, it stores fields by their **positional identifiers** rather than writing field names repeatedly, saving massive disk space.

- **Fixed-size fields** are grouped at the beginning of the record.
- **Variable-size fields** are placed at the end, preceded by their length and offset.

**Example Layout**:

- _Fixed-size area_:
    - `employee_id` (4 bytes)
    - `tax_number` (4 bytes)
    - `birth_date` (3 bytes)
    - `gender` (1 byte)
    - `first_name_length` (2 bytes)
    - `last_name_length` (2 bytes)
- _Variable-size area_:
    - `first_name` (variable bytes)
    - `last_name` (variable bytes)

To read `first_name`, the reader jumps directly to the end of the fixed-size area. To read `last_name`, it calculates the offset by adding `first_name_length` to the start of the variable-size area.

---

## Page Structure

Database files are partitioned into fixed-size **pages** (usually 4 to 16 Kb). In B-Trees, we distinguish between:

- **Leaf Pages**: Hold keys and actual data records.
- **Non-Leaf Pages**: Hold keys and pointers (page IDs) to child pages.

Each B-Tree node occupies one or more physical pages. The original B-Tree paper described a simple page layout where keys, values, and child pointers were written as concatenated triplets:

| $p_0$ | $k_1$ | $v_1$ | $p_1$ | $k_2$ | $v_2$ | ... | $k_n$ | $v_n$ | $p_n$ | (Unused) |
| :---: | :---: | :---: | :---: | :---: | :---: | :-: | :---: | :---: | :---: | :------: |

_Figure 3-4. Page organization for fixed-size records_

#### Drawbacks of Simple Triplet Layout:

- Inserting a key anywhere except at the end requires shifting all subsequent elements.
- It cannot handle variable-size records; it only works if all keys and values are fixed-size.

---

## Slotted Pages

To handle variable-size records without massive fragmentation, we cannot simply divide a page into fixed-size segments (which wastes space if records do not fit perfectly) or shift records on every update (which invalidates external file pointers).

> **Goal**: We need a page format that:
>
> 1.  Stores variable-size records with minimal overhead.
> 2.  Reclaims space when records are deleted.
> 3.  Allows referencing records inside a page without relying on their exact physical offsets.

To achieve this, databases use a **slotted page** or **slot directory** layout (used by engines like `PostgreSQL`):

- **Layout**: Pointers (offsets) and actual records (cells) grow from opposite sides of the page.
- **Indirection**: Outside references only use a **Slot ID**. The physical offset of the cell is kept internal to the page.

| Page Header | Slot Pointer 1 | Slot Pointer 2 | Slot Pointer 3 | ... (Free Space) ... | Cell 3 | Cell 2 | Cell 1 |
| :---------- | :------------: | :------------: | :------------: | :------------------: | :----: | :----: | :----: |

_Figure 3-5. Slotted page_

- **How it Solves the Goals**:
    - _Minimal Overhead_: Only requires a small pointer array at the start of the page.
    - _Defragmentation_: The page can be rewritten and cells compacted internally without changing the external **Slot IDs**.
    - _Indirection_: Pointers can be re-sorted or updated internally; the Slot ID remains unchanged.

> ### 💡 Beginner's Corner: The Slotted Page Design and Indirection
>
> - **The Problem (Variable-Size and Physical Shuffling)**: If database records are variable-sized, deleting or updating a record would normally require shifting all subsequent records to compact the space. However, if other indexes point directly to the physical file offsets of those records, shifting them would break all those external pointers, requiring a slow update of every index in the database.
> - **The Solution (Slotted Page Indirection)**: Instead of pointing directly to a record's physical offset inside a page, external references point to a stable **Slot ID** (a fixed-index entry in the page header). The page header contains an array of **Slot Pointers** (offsets) that point to the actual physical locations of the records (Cells) at the end of the page.
>     - When a record is updated or moved during defragmentation, the database only updates the internal Slot Pointer in the header. The external **Slot ID** remains completely unchanged, meaning external references never break.
> - **Jargon Buster**:
>     - **Indirection**: A design pattern where instead of referencing a resource directly, you reference a stable identifier that maps to the resource. This allows the resource to be moved or modified without updating the original reference.

---

## Cell Layout

Cells are divided into two types:

- **Key Cells** (Non-leaf): Store a separator key and a child `page_id`.
- **Key-Value Cells** (Leaf): Store a key and its associated data record.

For efficiency, we assume all cells in a page are uniform (either all keys or all key-value pairs; either all fixed-size or all variable-size). This allows us to store cell metadata once in the page header rather than duplicating it in every cell.

### Key Cell Layout (Variable-Size)

- Fixed-size fields are grouped at the beginning, followed by the variable key bytes:

| `key_size` (4 bytes) | `page_id` (4 bytes) | `key` bytes (variable) |
| :------------------- | :------------------ | :--------------------- |

### Key-Value Cell Layout (Variable-Size)

- Uses a flags byte, followed by sizes, and then the variable key and record bytes:

| `flags` (1 byte) | `key_size` (4 bytes) | `value_size` (4 bytes) | `key` bytes (variable) | `data_record` bytes (variable) |
| :--------------- | :------------------- | :--------------------- | :--------------------- | :----------------------------- |

> **Page ID vs. File Offset**: Because pages are managed by a **Buffer Pool Manager**, cells store a logical `page_id` instead of a physical file offset. The buffer pool translates the `page_id` to a memory pointer. Cell offsets inside a page are stored relative to the page start, allowing the database to use smaller 2-byte integers for pointers.

---

## Combining Cells into Slotted Pages

Using the slotted page technique, cell pointer offsets are written starting from the left (after the header) growing rightward, while the actual cells are appended starting from the right end of the page growing leftward:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//cfefa220-4459-47d0-b4fc-4f7d1bf336cb/markdown_2/imgs/img_in_image_box_142_450_1047_655.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A21%3A59Z%2F-1%2F%2Faaf48babe65e619cb0259057cd28c80e3f13cedf66a8e7d644c6d03481a855be" alt="Image" width="75%" /></div>
<div style="text-align: center;">Figure 3-6. Offset and cell growth direction</div>

### Preserving Sorted Order

When keys are inserted out of order, the physical cells are simply appended to the free space without shifting existing cells. The logical sorted order is maintained by sorting the **offset pointers** at the left of the page:

1.  **Initial State**: Inserting "Tom", then "Leslie":
    - _Physical cells (appended)_: `[Tom]` (rightmost), then `[Leslie]` (to its left).
    - _Logical pointers (sorted)_: The pointer array points to `[Leslie]` first, then `[Tom]`.
2.  **Adding a New Key**: Inserting "Ron":
    - _Physical cell_: Appended to the remaining free space.
    - _Pointers re-sorted_: Pointers after the insertion point are shifted to make room for the new pointer in sorted order: `[Leslie]`, `[Ron]`, `[Tom]`.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//cfefa220-4459-47d0-b4fc-4f7d1bf336cb/markdown_2/imgs/img_in_image_box_138_1166_1047_1359.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A21%3A59Z%2F-1%2F%2Fefe08a70147afd7c252fc6055f4983125f7eeaed575e847e5a47bf986b0f7cf2" alt="Image" width="76%" /></div>
<div style="text-align: center;">Figure 3-7. Records appended in random order: Tom, Leslie</div>

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//cfefa220-4459-47d0-b4fc-4f7d1bf336cb/markdown_3/imgs/img_in_image_box_138_333_1047_525.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A22%3A00Z%2F-1%2F%2F37254ac1f5f0599a482f58b27addde8cad5cf3714b7b50ccee3d9d70922626a6" alt="Image" width="76%" /></div>
<div style="text-align: center;">Figure 3-8. Appending one more record: Ron</div>

---

## Managing Variable-Size Data

Deleting an item does not require shifting physical cells. Instead:

1.  The cell is marked as deleted (using a tombstone flag).
2.  An **availability list** (free list) is updated in memory, tracking the offset and size of the freed segment.
3.  When a new cell is inserted, the engine scans the availability list using one of two allocation strategies:
    - **First Fit**: Uses the first segment that is large enough. This can leave behind tiny, unusable remainders.
    - **Best Fit**: Scans the list to find the segment that leaves the smallest remainder.
4.  If no single segment is large enough but the sum of fragmented bytes is sufficient, the page is **defragmented** by reading the live cells and rewriting them contiguously.
5.  If the page is still full after defragmentation, the database writes the excess data to an **overflow page**.

> ### 💡 Beginner's Corner: Tombstones & Free Lists
>
> - **Jargon Buster**:
>     - **Tombstone**: A tiny flag/marker placed on a record indicating that it has been deleted. The physical bytes of the record are not immediately wiped or shifted (which would be slow); instead, the database just marks it as "dead." During subsequent reads, the database ignores it.
>     - **Availability List (Free List)**: A directory of the offset and size of all the "dead" holes in a page, allowing the database to reuse that space for future writes.
>
> ### 🚶‍♂️ Step-by-Step Breakdown: Page Defragmentation
>
> What happens when a page has plenty of total free space, but it's split into many tiny, unusable holes?
>
> 1. **Step 1: Detection (Page compaction triggered)**: The database tries to write a 150-byte record. The page has 200 bytes of total free space, but it is split into three separate holes of 60, 70, and 70 bytes. The record doesn't fit in any single hole.
> 2. **Step 2: Load & Scan**: The database reads the page into RAM. It scans the page to identify all "live" (non-tombstoned) cells and their slot pointers.
> 3. **Step 3: Compact in RAM**: The database copies all live cells to a temporary buffer in RAM, packing them tightly next to each other at the very end of the page. All "holes" and tombstones are wiped out.
> 4. **Step 4: Update Pointers**: The database updates the slot offsets at the beginning of the page to point to the new compacted locations of the cells.
> 5. **Step 5: Write Back**: The clean, compacted page (which now has one contiguous 200-byte free space block in the middle) is written back to disk. The 150-byte record can now be successfully inserted!

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//cfefa220-4459-47d0-b4fc-4f7d1bf336cb/markdown_4/imgs/img_in_image_box_139_607_1047_878.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A22%3A00Z%2F-1%2F%2Fd33583007ac770352323347211af8185d30a11eab111c5d92237d678ca406c01" alt="Image" width="76%" /></div>
<div style="text-align: center;">Figure 3-9. Fragmented page and availability list. Occupied pages are shown in gray. Dotted lines represent pointers to unoccupied memory regions from the availability list.</div>

> **Note**: In `SQLite`, unoccupied segments are called **freeblocks**. A pointer to the first freeblock is stored in the page header, along with the total number of free bytes in the page.
>
> **Optimization**: To improve search speed, some engines store keys and values separately. Keeping keys contiguous on the leaf level increases cache locality during search. Once the key is located, the engine follows an offset pointer to the corresponding value cell.

---

## Versioning

As database engines evolve, their binary file formats change. To maintain **backward compatibility**, storage engines must support older serialization formats. To do this, the engine must identify the file format version:

- **Filename Version Prefixes**: `Apache Cassandra` uses two-letter prefixes in filenames (e.g., `na-1-big-Data.db` for version 4.0, `ma-` for version 3.0). This allows identifying the format version without opening the file.
- **Separate Metadata Files**: `PostgreSQL` writes the format version to a separate text file named `PG_VERSION`.
- **Header Versioning**: The version is stored at a fixed offset in the file or index header. This part of the header must use a format that never changes across versions. Once the version is read, the engine instantiates a version-specific reader.

---

## Checksumming

Files on disk can be damaged by software bugs or hardware failures. To detect corruption early and prevent it from spreading, databases use **checksums** and **cyclic redundancy checks (CRCs)**.

> ### Checksums vs. CRCs vs. Cryptographic Hashes
>
> - **Checksums**: The weakest guarantee. Usually computed via XOR or summation. They cannot detect multi-bit corruption.
> - **Cyclic Redundancy Checks (CRCs)**: Highly effective at detecting burst errors (multiple consecutive corrupted bits, common in network and disk failures). They are computed using polynomial division and lookup tables.
> - **Cryptographic Hashes**: Strong, secure hashes (e.g., SHA-256) designed to detect malicious tampering. CRCs and checksums are not designed to resist intentional attacks.

#### Implementing Checksums:

- Before writing a page to disk, the engine calculates its checksum and writes it into the **page header**.
- When reading the page back, the checksum is recalculated and compared.
- A mismatch indicates physical corruption.
- By checksumming **page-by-page** rather than over the entire file, the database avoids reading the whole file to verify integrity, and corruption in one page does not require discarding the entire database file.

---

## Summary

- **Primitives and Structs**: Databases serialize primitive types (using uniform endianness) and group them into structures. Variable-sized fields like strings are serialized using Pascal-style string layouts (size followed by bytes).
- **Bit Packing**: Booleans, enums, and flags are packed into bits and read/written using bitwise operations to minimize storage overhead.
- **Slotted Page Layout**: Cells grow from the right, while offset pointers grow from the left. This allows inserting records out-of-order physically while maintaining a sorted logical order via pointer sorting.
- **Space Management**: Deleted records are marked with tombstones and added to an availability list. Fragmented pages are defragmented on-the-fly, or spilled into overflow pages.
- **Safety & Compatibility**: Files use header versioning for backward compatibility, and page-level checksumming (CRCs) to detect hardware corruption early.

---

### Footnotes

- $^1$ If the target platform's endianness does not match the value's endianness, the engine uses a transform function to read and reverse the bytes.
- $^2$ Primitive values are combined into structures, using fixed-size fields or pointers to other disk pages.
- $^3$ **Vectorized instructions**, or **Single Instruction Multiple Data (SIMD)**, describes a class of CPU instructions that perform the same operation on multiple data points.
- $^4$ The original post that has stirred up the discussion was controversial and one-sided, but you can refer to the presentation comparing MySQL and PostgreSQL index and storage formats, which references the original source as well.
