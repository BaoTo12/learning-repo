# Module 04: Implementing B-Trees

In the previous module, we discussed the general principles of building binary formats. We learned how to create cells, build hierarchies, and connect them to pages using pointers. These concepts apply to both **in-place update** and **append-only** storage structures.

In this module, we discuss concepts specific to **B-Trees**, divided into three main groups:

1.  **Organization**: Establishing relationships between keys and pointers, and implementing headers and links between pages.
2.  **Traversal Processes**: Performing binary search during root-to-leaf descends, and collecting breadcrumbs to track parent nodes during splits or merges.
3.  **Optimizations and Maintenance**: Tuning B-Tree performance via rebalancing, right-only appends, bulk loading, background maintenance, and garbage collection.

---

## Page Header

The **page header** holds metadata used for page navigation, maintenance, and optimization. It typically contains:

- **Flags** describing page contents and layout.
- **Cell Count**: The number of cells currently stored in the page.
- **Offsets**: Lower and upper offsets marking the boundaries of the free space (used to append cell pointers and data cells).
- **Metadata**: Implementation-specific values (e.g., `PostgreSQL` stores page size and layout version; `MySQL InnoDB` stores heap record counts and level; `SQLite` stores cell count and a rightmost pointer).

### Magic Numbers

> **Definition**: A **magic number** is a constant multibyte block written into the file or page header. It serves as a signature to validate the block type, version, or alignment.

- **Validation**: It is highly unlikely that a random byte sequence on disk would match the magic number by chance.
- **Example**: During writes, the database can place the hex magic number `50 41 47 45` (representing "PAGE") into the page header. During reads, the database compares the header bytes with this expected sequence. A mismatch immediately flags alignment or corruption errors.

### Sibling Links

Some B-Tree implementations store forward and backward pointers in the page header pointing directly to the left and right sibling pages on the same level.

- **Benefit**: Allows range scans to locate adjacent nodes immediately, without ascending back to parent nodes.
- **Drawback**: Adds complexity and locking overhead during splits and merges, as sibling pointers in adjacent pages must be updated too.

> ### 💡 Beginner's Corner: Sibling Links and Concurrency Trade-offs
>
> - **The Problem (Range Query Performance)**: A range query (e.g., retrieving all records where `age > 21` in sorted order) requires traversing Leaf Pages in sequence. In a standard B-Tree, once the database finishes reading Leaf Page A, it must ascend back up to the parent page, find the next child pointer, and descend to Leaf Page B. This constant up-and-down parent-traversal is slow and increases CPU overhead during range scans.
> - **The Solution (Sibling Pointers)**: By storing direct "next" and "previous" page identifiers (sibling links) in the page headers, Leaf Pages form a double-linked list on the leaf level. The database can perform range scans by traversing directly from one leaf page to the next, completely bypassing parent nodes.
> - **The Concurrency Challenge**: Sibling links introduce severe concurrency issues. When a leaf page splits, the database must acquire exclusive locks not only on the splitting page and its parent, but also on its left and right sibling pages to update their sibling pointers. If multiple writer threads are splitting adjacent pages and acquiring locks in opposite directions, it can easily lead to **thread deadlocks** (where threads block each other indefinitely). Therefore, B-Tree implementations must use highly complex latching protocols to prevent deadlocks.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//7a67897c-1f2d-48ee-aeaf-f06f0b5bbf06/markdown_4/imgs/img_in_image_box_145_137_1051_425.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A22%3A00Z%2F-1%2F%2Fea0decb0e22d6e2e8a1b8ae6003796ab503507e8ed701a4806f3cd23ec271b96" alt="Image" width="76%" /></div>
<div style="text-align: center;">Figure 4-1. Locating a sibling by following parent links (a) versus sibling links (b)</div>

### Rightmost Pointers

Because B-Tree separator keys divide the tree into subranges, there is always **one more child pointer than there are keys** (represented as $N+1$).

- **Implementation**: In many engines, each separator key is paired with a child pointer in a cell, while the final **rightmost pointer** is stored separately in the page header (e.g., `SQLite`).

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//2d78bc6e-d176-4f6f-9b56-5e097e3ec593/markdown_0/imgs/img_in_image_box_139_632_1047_928.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A21%3A58Z%2F-1%2F%2F89b1f38e886b94affd8a42948b8b0291f5d7f523bf695a5071d65e7d9cca62fe" alt="Image" width="76%" /></div>
<div style="text-align: center;">Figure 4-2. Rightmost pointer</div>

When a rightmost child page splits:

1.  The newly promoted key and a pointer to the left split-half are appended as a new cell in the parent node.
2.  The parent's rightmost pointer is reassigned to point to the newly created right split-half node.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//2d78bc6e-d176-4f6f-9b56-5e097e3ec593/markdown_1/imgs/img_in_image_box_219_162_973_396.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A21%3A59Z%2F-1%2F%2F45a47743bc251e3e3a5f0c825baa14f91b08bd246aeed63d250068e5db3494a8" alt="Image" width="63%" /></div>
<div style="text-align: center;">Figure 4-3. Rightmost pointer update during node split. The promoted key is shown in gray.</div>

### Node High Keys

An alternative design stores the rightmost pointer inside a normal cell paired with a **high key**.

> **Definition**: The **high key** represents the highest possible key value that can be stored in the subtree under the current node. This approach is used in **$B_{link}$-Trees** (e.g., `PostgreSQL`).

- **Standard B-Tree Node**: Has $N$ keys ($K_i$) and $N+1$ pointers ($P_i$). The lower bound $K_0 = -\infty$ is implicit. Subtree keys are bounded by $K_{i-1} \leq K_s < K_i$.
- **$B_{link}$-Tree Node**: Adds an explicit $K_{N+1}$ high key. It specifies the absolute upper bound for the subtree pointed to by $P_N$ (and thus the entire node).

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//2d78bc6e-d176-4f6f-9b56-5e097e3ec593/markdown_2/imgs/img_in_image_box_201_822_600_952.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A21%3A59Z%2F-1%2F%2F63990503cab667e05db52296e379f136a31f38ae851331718c090a3745559a9a" alt="Image" width="33%" /></div>
<div style="text-align: center;">a) Node without high key (goes to $+\infty$)</div>

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//2d78bc6e-d176-4f6f-9b56-5e097e3ec593/markdown_2/imgs/img_in_image_box_637_822_1047_950.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A21%3A59Z%2F-1%2F%2Fc990172b6e27bca9add597ffb2d8c5bd37c93c026e4d4ff1c40dfd4a157bc0ab" alt="Image" width="34%" /></div>
<div style="text-align: center;">Figure 4-4. B-Trees without (a) and with (b) a high key</div>

By storing high keys, all pointers are stored in pairs inside normal cells. This removes the need for special rightmost pointer edge-cases in code.

| Strategy                            | Node Layout                | Search Range Bound                   |
| :---------------------------------- | :------------------------- | :----------------------------------- |
| **No High Key (Virtual $+\infty$)** | $N$ keys, $N+1$ pointers   | Ranges extend up to $+\infty$        |
| **High Key ($B_{link}$-Tree)**      | $N+1$ keys, $N+1$ pointers | Ranges bounded strictly by $K_{N+1}$ |

### Overflow Pages

Because page sizes are fixed (e.g., 4 Kb), storing large variable-size records inside B-Tree nodes can saturate a page long before the node is logically "full" in terms of key count.

- **Problem**: Resizing a page dynamically is impractical as it requires copying data to a new contiguous disk region.
- **Solution**: Build nodes using **overflow pages** (linked extension pages).

> **Implementation**: The database sets a `max_payload_size` (node size divided by fanout). The primary page stores the keys and only a small portion of the value. The rest of the value payload is spilled to a chain of **overflow pages**.

- **Chaining**: When the first overflow page is allocated, its `page_id` is written into the primary page cell. If more space is needed, subsequent overflow pages are linked together in a chain, storing the next `page_id` in the header of the previous page.
- **Traversing**: The database only traverses the overflow chain when returning the full record payload to the user. Since keys remain in the primary page, search indexing is unaffected.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//675494f9-c82b-45e6-a345-b73d66f8b253/markdown_0/imgs/img_in_image_box_136_294_1043_1323.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A21%3A58Z%2F-1%2F%2F82629e7b487028b6f97f44901325af21d4a724499456120b9f16355c8141504d" alt="Image" width="76%" /></div>
<div style="text-align: center;">Figure 4-6. Overflow pages</div>

---

## Binary Search

Lookups within B-Tree pages use **binary search**, which requires sorted keys to function.

- **Successful Search**: Returns a positive number indicating the key's index position.
- **Unsuccessful Search**: Returns a negative number representing the **insertion point** (the index of the first element greater than the searched key).
- **Insertion**: The absolute value of the negative return is the target index. The database shifts elements to the right by one position starting from this index to make room for the new record.

### Binary Search with Indirection Pointers

In slotted pages, cells are stored in insertion order, and only their offset pointers are kept sorted. To run binary search:

1.  Find the midpoint in the sorted **offset pointer array**.
2.  Follow that pointer to locate the actual cell in the page.
3.  Compare the cell's key with the searched key.
4.  Decide whether to search left or right, and repeat the process recursively.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//675494f9-c82b-45e6-a345-b73d66f8b253/markdown_3/imgs/img_in_image_box_141_545_1047_941.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A21%3A59Z%2F-1%2F%2F69668775bb900d6f78f8610844ede2022f3655d6a31f24e4924a25905e37ddc5" alt="Image" width="76%" /></div>
<div style="text-align: center;">Figure 4-7. Binary search with indirection pointers. The searched element is shown in gray. Dotted arrows represent binary search through cell pointers. Solid lines represent accesses that follow the cell pointers, necessary to compare the cell value with a searched key.</div>

---

## Propagating Splits and Merges

Because B-Tree node splits and merges propagate upward, the database must trace the path from the modified leaf back up to the root.

- **Parent Pointers**: Nodes can store pointers to their parent pages. Since parent pages are already loaded when referencing child pages, this information does not need to be written to disk. However, parent pointers must be updated whenever a node's parent changes (during splits, merges, or rebalancing).
- **Parent Pointers for Traversal**: Some engines (e.g., `WiredTiger`) use parent pointers instead of sibling pointers to traverse leaves, avoiding thread deadlocks. To find a sibling, the engine ascends to the parent, follows the next child pointer, and descends. If it reaches the end of the parent, it ascends recursively toward the root.

### Breadcrumbs

Instead of maintaining parent pointers on disk, databases track the root-to-leaf path dynamically in memory using **breadcrumbs**.

> **Definition**: **Breadcrumbs** are in-memory references to all nodes traversed on the path from the root to the target leaf. They are stored in a **stack** (e.g., `PostgreSQL`'s `BTStack`).

- **Backtracking**: When a leaf node splits or merges, the engine pops the top item from the breadcrumb stack to find its immediate parent.
- **Propagation**: If the parent has space, the promoted key and child pointer are written to it. If the parent is full, it is split in turn, popping the next parent from the stack. This process propagates recursively until a parent with free space is found or the stack is empty (meaning the root split).

> ### 💡 Beginner's Corner: The Breadcrumb Mechanism and Why It Exists
>
> - **The Problem (Why We Don't Store Parent Pointers on Disk)**: When a leaf node splits or merges, the database must update its parent node to add or remove a separator key. To do this, the database needs to know which page is the parent of the current leaf. However, storing parent pointers inside B-Tree pages on disk is highly problematic:
>     1. **Space Overhead**: Every byte used for metadata like a parent pointer reduces the space available for keys and child pointers, lowering the node's **fanout** and increasing the tree's height.
>     2. **Cascading Disk Writes**: When a node splits, its children are distributed between two pages. If children stored parent pointers, the database would have to write updates to all those child pages on disk to update their parent pointers, causing massive write amplification.
> - **The Solution (In-Memory Breadcrumbs)**: Instead of storing parent pointers on disk, the database tracks the traversal path dynamically in RAM. When a query descends the B-Tree from the root to a leaf page, the database pushes the page ID of every visited node onto a temporary in-memory stack (called **Breadcrumbs** or a **Traversal Stack**).
> - **The Underlying Mechanism**:
>     1. **Descent**: During search, pages are traversed: `Root Page A` $\rightarrow$ `Internal Page B` $\rightarrow$ `Leaf Page C`. The stack becomes `[Root Page A, Internal Page B]`.
>     2. **Split Trigger**: Leaf Page C overflows. It splits into C and a new sibling page D.
>     3. **Backtracking**: The database pops the top page ID from the stack (`Internal Page B`). It now has direct, instant access to C's parent page in memory without doing any disk lookups or storing parent pointers.
>     4. **Promotion**: The database inserts the new separator key for page D into `Internal Page B`.
>     5. **Recursive Propagation**: If `Internal Page B` also overflows, it splits, and the database pops the next page ID from the stack (`Root Page A`) to update the level above, repeating the process up to the root if necessary.

> ### 🚶‍♂️ Step-by-Step Breakdown: Propagating a Split with Breadcrumbs
>
> Imagine we are inserting a key into Leaf Page E. Here is how the database uses a breadcrumb stack to handle overflows:
>
> 1. **Step 1: The Descent (Pushing Breadcrumbs)**: As the database searches from the root to Leaf Page E, it records its path in a temporary stack in RAM:
>     - `[Root Page A] -> [Internal Page B] -> [Internal Page C] -> [Leaf Page E]`
> 2. **Step 2: Overflow Detected**: The database attempts to write to Leaf Page E, but it is full. E splits into E and a new sibling page F.
> 3. **Step 3: Pop the Parent**: The database needs to insert the separator key for F into E's parent. It pops the top of the breadcrumb stack to instantly find its parent: `Internal Page C`.
> 4. **Step 4: Attempt Parent Insert**:
>     - _Scenario A (Parent has room)_: The database writes the separator key to Page C. The split is complete!
>     - _Scenario B (Parent is full)_: Page C overflows and must split into C and G.
> 5. **Step 5: Cascade Upward**: Since Page C split, we must insert a separator key into _its_ parent. The database pops the next page from the stack: `Internal Page B`. This process repeats.
> 6. **Step 6: Splitting the Root**: If the stack becomes completely empty and we still need to insert a separator, it means the root page split. The database allocates a brand new root page and points it to the split halves, increasing the tree's height by one.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//7f8eb8bb-060b-48b7-b6a6-af9e15ef26dd/markdown_1/imgs/img_in_image_box_141_144_1041_969.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A21%3A59Z%2F-1%2F%2F3f254cbb6166f2623dcd52055c3180b337e65093069ac068f1edfbc629d24497" alt="Image" width="75%" /></div>
<div style="text-align: center;">Figure 4-8. Breadcrumbs collected during lookup, containing traversed nodes and cell indices. Dotted lines represent logical links to visited nodes. Numbers in the breadcrumbs table represent indices of the followed child pointers.</div>

---

## Rebalancing

To avoid the high I/O cost of splits and merges, B-Trees can delay these operations by redistributing elements between adjacent sibling nodes on the same level.

- **Load Balancing (Insert)**: Instead of splitting a full node, the engine checks if a sibling has free space. If so, it transfers some elements to the sibling, making room in the current node.
- **Load Balancing (Delete)**: Instead of merging underflowed nodes immediately, the engine steals keys from a sibling to restore the node's occupancy to at least 50%.
- **B\*-Trees**: Delay splits by distributing elements between neighboring nodes until both siblings are full. When they finally overflow, two nodes are split into three nodes (each two-thirds full). This is used in `SQLite`.
- **Search Efficiency**: Higher node occupancy means a more compact tree with smaller height, requiring fewer page reads during search.

> ### 💡 Beginner's Corner: B-Tree Rebalancing (Redistribution) Mechanism
>
> - **Why It Exists (Avoiding Expensive Splits and Merges)**: In a disk-based database, allocating a new page, copying data, and updating parent/sibling pointers during splits and merges requires multiple random disk writes, which is highly expensive. To optimize performance, the database tries to delay these physical structural changes.
> - **The Underlying Mechanism (Key Rotation)**:
>     - **Handling Overflows (Insert)**: When a write operation finds that a leaf page is full, the database reads the headers of its adjacent sibling pages (using the sibling links). If a sibling page has free space, the database transfers a portion of the keys from the full page to the sibling page. The database then updates the separator key in the parent node to match the new boundary between the siblings. No new pages are allocated, and no recursive parent splits are triggered.
>     - **Handling Underflows (Delete)**: When a deletion causes a page's occupancy to fall below 50%, the database checks its siblings. If a sibling has extra keys, the database transfers some keys from the sibling to the underflowed page to balance their occupancy, updating the parent's separator key. A physical page merge is only performed if the combined keys of both siblings can fit entirely within a single page.
> - **Why It Optimizes Search Performance**: Delaying splits via rebalancing keeps B-Tree pages highly packed (high **node occupancy**). When pages are close to 100% full, the tree requires fewer total pages and levels to store the same amount of data. This keeps the tree height as low as possible, guaranteeing that lookups require the minimum number of disk reads.

> ### 🚶‍♂️ Step-by-Step Breakdown: Tracing a B-Tree Rebalancing (Redistribution)
>
> Imagine Leaf Page A (full, 3 keys: `[10, 12, 15]`) wants to insert **11**, but its neighbor Leaf Page B is nearly empty (1 key: `[25]`).
>
> 1. **Step 1: Check Siblings**: Instead of immediately splitting Leaf Page A into two pages, the database checks the occupancy of its sibling, Leaf Page B, by reading Page B's header.
> 2. **Step 2: Space Found**: The database sees that Page B has plenty of empty slots.
> 3. **Step 3: Transfer Keys (Rotate)**: The database moves the highest key of Page A (**15**) over to the beginning of Page B. Leaf Page B now holds `[15, 25]`.
> 4. **Step 4: Insert New Key**: Page A now has a free slot, so the database writes **11** into Page A. Page A now holds `[10, 11, 12]`.
> 5. **Step 5: Update Parent Separator**: Since the boundary between Page A and Page B has changed (it was 15, but now Page B starts with 15), the database updates the separator key in the parent node to reflect the new boundary. No pages had to be allocated or deleted!

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//7f8eb8bb-060b-48b7-b6a6-af9e15ef26dd/markdown_3/imgs/img_in_image_box_141_148_1047_493.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A21%3A59Z%2F-1%2F%2F3f3a5097c92618c34496c7b91986c6f744812a9c827733c51959bc834e181ba8" alt="Image" width="76%" /></div>
<div style="text-align: center;">Figure 4-9. B-Tree balancing: Distributing elements between the more occupied node and the less occupied one</div>

---

## Right-Only Appends

When primary keys are monotonically increasing (e.g., auto-incrementing IDs), all insertions happen at the far right end of the index (the rightmost leaf). This opens up significant optimization paths:

- **Fastpath (PostgreSQL)**: If the inserted key is larger than the first key in the rightmost page and the page has room, the key is written directly to the cached rightmost leaf page, skipping the entire root-to-leaf read path.
- **Quickbalance (SQLite)**: When the rightmost node is full, instead of performing a standard split (which leaves two half-empty pages), the engine allocates a new rightmost node and adds its pointer to the parent. The new page starts empty but is expected to fill up quickly due to sequential appends.

### Bulk Loading

If the data to be written is already sorted (e.g., rebuilding an index for defragmentation or importing a dataset), we can build the B-Tree from the bottom up:

1.  **Write leaf pages** sequentially one by one.
2.  Once a leaf page is full, **propagate** its first key to the parent page.
3.  Build the higher levels of the tree from these parent pointers.

- **Benefits**:
    - Avoids all splits and merges on disk.
    - Only parent nodes along the rightmost path must be kept in memory during building.
    - **Immutable B-Trees** built this way do not need to reserve empty space for future writes, allowing 100% page occupancy and maximum search performance.

---

## Compression

Compression saves disk space, but introduces a clear trade-off: higher compression ratios save storage and reduce disk read sizes, but require more CPU cycles and RAM to compress and decompress data.

- **File-Level Compression**: Impractical because updating a single record requires recompressing the entire file.
- **Page-Level Compression**: Fits B-Trees well. Pages are compressed and decompressed independently when loaded or flushed.
- **Row/Column Compression**: Decouples compression from page management by compressing individual rows or columns.

> ### WARNING: Compression and Block Padding
>
> Because compressed pages vary in size, a compressed page might only occupy a fraction of a physical disk block. Since disk transfers occur in fixed block sizes, reading a compressed page may force the system to read extra bytes from adjacent pages, or pad the blocks with empty space, creating alignment overhead.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//ffd9e9f7-151c-494a-9cce-8a58e5e3c40c/markdown_2/imgs/img_in_image_box_139_161_1051_496.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A22%3A00Z%2F-1%2F%2Fe0a91da003e304533987cad6674831e00e191053dd35d64a9c5562aac789e9eb" alt="Image" width="76%" /></div>
<div style="text-align: center;">Figure 4-10. Compression and block padding</div>

- **Compression Libraries**: Most engines support pluggable compression libraries like `Snappy`, `zLib`, or `lz4`. Selection depends on four metrics: memory overhead, compression speed, decompression speed, and compression ratio.

---

## Vacuum and Maintenance

To keep query paths fast, databases run background maintenance processes to clean up pages, reclaim space, and re-order cells.

- **Live (Addressable) Records**: Records that can be reached by following pointers down from the root node.
- **Garbage (Non-Addressable) Records**: Records that are no longer referenced by any pointer. They are logically deleted or overwritten.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//ffd9e9f7-151c-494a-9cce-8a58e5e3c40c/markdown_3/imgs/img_in_image_box_139_892_1049_1239.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A22%3A00Z%2F-1%2F%2Ff9369f1a6860bfb4eca394a6e949cae5d99ebc721fb97408247b588e1353a93d" alt="Image" width="76%" /></div>
<div style="text-align: center;">Figure 4-11. An example of a fragmented page</div>

### Fragmentation Caused by Updates and Deletes

- **Deletes**: Merely remove the cell's offset pointer from the page header. The physical cell bytes remain on the page but are no longer addressable.
- **Splits**: Trim cell offsets in the header. The cells whose offsets were truncated remain physically in the page but are non-addressable.
- **Updates**: On leaf pages, updates avoid immediate rewrites. If the new value fits, it overwrites the old one. If not, it is appended to the free space, and the old version's offset is discarded, leaving a non-addressable cell.

> **MVCC Note**: Some databases (e.g., `PostgreSQL`) leave old versions of updated or deleted cells in place as **ghost records** to support multiversion concurrency control. These remain readable for concurrent transactions and are collected only when no active transaction can see them.

### Page Defragmentation

Over time, deleting offsets without moving cells scatters free bytes across the page. This fragmentation means a new cell might not find a contiguous block of free bytes, even if the page has enough total free space.

- **Compaction (Vacuum)**: An asynchronous background process that:
    1.  Scans pages to locate non-addressable garbage cells.
    2.  Rewrites the page, packing live cells contiguously in logical key order.
    3.  May relocate pages to new physical positions in the file.
    4.  Returns freed pages to the page cache.
    5.  Adds the IDs of freed disk pages to a persistent **freelist** so they can be reused for future allocations.

---

## Summary

- **Page Header**: Stores flags, cell count, free space offsets, and **magic numbers** for page type and alignment validation.
- **Sibling & Parent Pointers**: Sibling links in headers speed up range scans. Parent pointers or in-memory **breadcrumbs** (stored in a stack) allow split and merge operations to propagate recursively back to the root.
- **Rightmost & High Keys**: Separator keys are paired with pointers. The extra pointer can be stored as a **rightmost pointer** in the header or paired with a **high key** in $B_{link}$-Trees.
- **Overflow Pages**: Link multiple pages together to store oversized payloads without page resizing.
- **Optimizations**:
    - **Rebalancing**: Redistributes keys between siblings to delay splits and merges.
    - **Right-Only Appends**: Optimizes sequential writes by skipping the read path.
    - **Bulk Loading**: Builds trees bottom-up from sorted data, achieving 100% occupancy.
    - **Garbage Collection**: Compacts fragmented pages, reclaiming non-addressable cell space and tracking freed pages via a **freelist**.

---

### Footnotes

- $^1$ Promoted keys and pointers to new siblings are appended to the parent, and the rightmost child pointer is reassigned to point to the new right sibling.
- $^2$ In PostgreSQL, breadcrumbs are stored in a stack internally named `BTStack` to backtrack during recursive splits and merges.
- $^3$ The **freelist** tracks the IDs of empty pages on disk that can be reused for new writes, persisting this data to survive node crashes.
