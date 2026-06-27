# Module 06: B-Tree Variants

**B-Tree variants** have several things in common:

- **Tree structure** for hierarchical organization.
- **Balancing** through node splits and merges.
- **Standard lookup and delete algorithms**.

Other details, such as concurrency control, on-disk page representation, links between sibling nodes, and background maintenance processes, can vary significantly between implementations.

In this module, we will discuss several techniques used to build efficient **B-Trees** and the structures that employ them:

- **Copy-on-Write (CoW) B-Trees**: These are structured like B-Trees, but their nodes are **immutable** and are never updated in place. Instead, pages are copied, updated, and written to new locations.
- **Lazy B-Trees**: These reduce the number of disk I/O requests from subsequent writes to the same node by **buffering updates** in memory.
- **FD-Trees (Flash Disk Trees)**: These buffer updates in a small, mutable B-Tree. When this tree fills up, its contents are written into an **immutable run**. Updates then propagate between levels of sorted runs in a cascading manner.
- **Bw-Trees**: These split B-Tree nodes into smaller parts that are written in an **append-only** manner. This reduces the cost of small writes by batching updates together.
- **Cache-Oblivious B-Trees**: These allow us to design on-disk data structures that perform optimally across multiple levels of the memory hierarchy without needing platform-specific tuning.

---

## Copy-on-Write

Some databases, instead of building complex latching mechanisms, use the **Copy-on-Write (CoW)** technique to guarantee data integrity during concurrent operations.

### How Copy-on-Write Works

1.  When a page is about to be modified, its contents are **copied** to a new location.
2.  The modification is applied to this new copy, leaving the original page untouched.
3.  A new parallel tree path (up to the root) is created to reference the new page, reusing untouched sibling pages where possible.
4.  Once the new page hierarchy is complete, the pointer to the root page is **atomically updated** to point to the new version.

> ### 💡 Beginner's Corner: Copy-on-Write Path Copying & Atomic Swaps
>
> - **What it is**: Copy-on-Write (CoW) is a memory and storage management technique where write operations do not overwrite existing data in place. Instead, modified pages are copied to a new physical location on disk, updated there, and all parent pages pointing to them are also copied up to the root.
> - **Why it exists & What problem it solves**: In traditional database engines, updating a page in place requires acquiring exclusive write locks (latches) to prevent concurrent readers from seeing half-written, corrupted states. These locks cause contention and block reads. CoW solves this by keeping the original pages completely unmodified, allowing readers to access them lock-free and with zero blockages.
> - **Underlying Mechanism**: When a leaf page is modified, its physical address changes. Because B-Trees are hierarchical, the parent node must be updated to point to the new physical address of this child. This in turn changes the parent's content, requiring a new copy of the parent page. This effect propagates recursively up to the root. The database maintains a pointer to the active root. Once the entire new path is written to disk, the root pointer is updated to the new root address using an atomic CPU instruction (like a single-word write). Concurrent readers that started before the switch continue traversing the old pages (which are still valid and unmodified), while new readers immediately see the new version.
> - **Common Misconception**: Beginners often assume CoW is highly efficient because it avoids lock contention. In reality, CoW introduces severe _write amplification_ and _space amplification_. Modifying even a single 1-byte value in a leaf node requires copying and writing the entire leaf page (e.g., 4KB or 8KB) plus every branch node on the path to the root.

> [!NOTE]
> Old tree versions remain fully accessible to readers running concurrently with the writer. Writers modifying pages must wait until previous write operations finish, but they do not block readers.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//97b96c84-8adb-47bf-82cc-9119e439c4e6/markdown_1/imgs/img_in_image_box_142_144_1048_460.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A22%3A00Z%2F-1%2F%2Fddf074a92fac0d6aabd1d61ea05dc38d275e34c9802887864ab8c8ffa8f8d144" alt="Image" width="76%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 6-1. Copy-on-write B-Trees</div> </div>

### Trade-offs of Copy-on-Write

| Advantages                                                                                                                                               | Disadvantages                                                                                                                |
| :------------------------------------------------------------------------------------------------------------------------------------------------------- | :--------------------------------------------------------------------------------------------------------------------------- |
| **No Reader Synchronization**: Written pages are immutable, so readers access them without latching or locking.                                          | **High Space Overhead**: Requires more disk space, as old versions must be kept until active readers finish.                 |
| **No Reader-Writer Blocking**: Readers and writers run concurrently without interfering with each other.                                                 | **High CPU & I/O Cost**: Entire page contents must be copied even for small, single-byte modifications.                      |
| **Crash Safety**: A system crash cannot leave pages in a corrupted state, as the root pointer is switched only after all page modifications are written. | **No Sibling Pointers**: Due to the append-only nature, sibling pointers are impractical. Scans must ascend to parent nodes. |

---

### Implementing Copy-on-Write: LMDB

The **Lightning Memory-Mapped Database (LMDB)** is a prominent storage engine that uses copy-on-write. It is a key-value store used by the OpenLDAP project.

- **Single-Level Store**: LMDB maps the database file directly into the application's address space using a memory map (`mmap`). Operations are satisfied directly from this map, removing the need for a page cache or application-level caching.
- **No WAL or Compaction**: Because of its copy-on-write design, LMDB does not require a write-ahead log (WAL), checkpointing, or compaction processes. $ ^{1} $
- **Path Copying**: During an update, every branch node on the path from the root to the target leaf is copied and modified. The rest of the tree remains unchanged, pointing to the original pages.
- **Double-Buffered Root**: LMDB keeps only two versions of the root node: the active version and the version where new changes are currently being written. Once a transaction commits, the root pointer is switched.
- **Space Reclamation**: Pages from old tree sections are reclaimed and reused as soon as the concurrent read transactions referencing them complete.

---

## Abstracting Node Updates

To write a page to disk, we must first update its in-memory representation. There are three primary ways to represent and update B-Tree nodes in memory:

1.  **Direct Binary Access (Unmanaged Memory)**:
    In languages with unmanaged memory (like C/C++), raw binary data in B-Tree nodes can be reinterpreted using structures and runtime pointer casts. The structures point directly to memory managed by the page cache or memory-mapped files.
2.  **In-Memory Materialization (Language-Native Objects)**:
    Nodes are read from disk and converted into native language objects (e.g., classes or structs). Inserts, updates, and deletes are performed on these objects. During a flush, these changes are serialized back into raw binary pages. This simplifies concurrent access but **doubles memory overhead** since both the raw binary page and the language-native object must coexist in memory.
3.  **Wrapper Objects**:
    Common in managed languages (like Java or C#), this approach uses wrapper objects that act as interfaces to the underlying byte buffers. Any modification made to the wrapper is immediately written directly into the backing binary buffer.

> [!TIP]
> Separating on-disk pages, cached pages, and in-memory representations allows them to have different lifecycles. We can buffer inserts, updates, and deletes in memory and reconcile them with the on-disk format only when needed.

---

## Lazy B-Trees

**Lazy B-Trees** $ ^{2} $ reduce the cost of updating B-Trees by using lightweight, concurrency-friendly in-memory structures to buffer updates and write them to disk with a delay.

### WiredTiger

**WiredTiger** (the default storage engine for MongoDB) uses different formats for in-memory and on-disk pages. Before in-memory pages are written to disk, they undergo a **reconciliation** process.

- **Clean Pages**: Consist of an index structure constructed directly from the on-disk page image.
- **Dirty Pages**: Contain the base page index plus an **update buffer** implemented as a **skiplist**. Skiplists offer search complexities similar to balanced trees but provide better concurrent write performance.

> ### 💡 Beginner's Corner: Skiplists & Reconciliation
>
> - **What it is**: A skiplist is a probabilistic data structure that consists of a base linked list of sorted elements, with multiple layers of parallel lists ("express lanes") built on top. Each higher layer skips over a number of elements below it, allowing search operations to jump forward quickly. Reconciliation is the process of merging an in-memory update buffer with a static base page and writing the unified result to disk.
> - **Why it exists & What problem it solves**: Modifying on-disk B-Tree pages for every single write is extremely slow because it requires random I/O. Buffering these writes in memory is necessary, but a standard balanced tree (like an AVL or Red-Black tree) requires complex pointer updates and rebalancing operations under concurrent writes, which leads to high lock contention. A skiplist solves this because it does not require rigid rebalancing; insertions only require local, probabilistic pointer updates, making it highly concurrent and fast for write-heavy workloads.
> - **Underlying Mechanism**: When a write occurs, instead of modifying the on-disk page or a complex in-memory page structure, the write is appended to an in-memory skiplist associated with that page. Searches must scan both the base page (which is read-only in memory) and the skiplist, merging the results to return the latest value. During background reconciliation, a worker thread reads the base page, walks the sorted skiplist, merges the operations (applying updates and deletes), serializes the combined data into a brand-new contiguous page, writes it to disk, and updates the in-memory page references.
> - **Common Misconception**: Beginners might think that skiplists are slow for reads because they require searching two structures. However, since the skiplist is kept relatively small and resides entirely in RAM, the search overhead is negligible compared to the massive disk I/O savings achieved by batching writes.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//e6bee445-4bd2-45cd-8423-382b55c7c403/markdown_0/imgs/img_in_image_box_142_767_1049_1055.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A22%3A00Z%2F-1%2F%2Fdee3a36f407ad14af9435d96225c9d8a0898c8342f0d60bf514e94b00c21fd23" alt="Image" width="76%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 6-2. WiredTiger: high-level overview</div> </div>

- **Reads**: The engine reads the base page and merges its contents with the active update buffer to return the most recent data.
- **Flushes (Reconciliation)**: The background thread reconciles the update buffer with the base page and writes the merged result to a new disk location. If the merged page exceeds the maximum page size, it is split into multiple new pages.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//e6bee445-4bd2-45cd-8423-382b55c7c403/markdown_2/imgs/img_in_image_box_141_138_1048_803.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A22%3A01Z%2F-1%2F%2F747d77c010470be24438308ef8017aa889728016ad41e2aac4cf3f2ba4d874d2" alt="Image" width="76%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 6-3. WiredTiger pages</div> </div>

> [!IMPORTANT]
> The primary advantage of WiredTiger's approach is that page updates and structural changes (splits and merges) are handled entirely by background threads. User read and write operations do not have to wait for disk I/O to complete.

---

### Lazy-Adaptive Tree

Instead of buffering updates for individual nodes, the **Lazy-Adaptive Tree (LA-Tree)** groups nodes into subtrees and attaches an **update buffer** to the top node of each subtree.

1.  **Insertion**: A new entry is first written to the update buffer of the subtree's root node.
2.  **Cascading Propagation**: When a buffer fills up, its elements are copied and propagated down to the buffers of the next lower subtree level.
3.  **Recursive Spilling**: This propagation continues recursively. When updates finally reach the leaf level, they are applied to the leaf pages in a single batch.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//e6bee445-4bd2-45cd-8423-382b55c7c403/markdown_4/imgs/img_in_image_box_144_145_1041_547.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A22%3A02Z%2F-1%2F%2Fbd1d4a6e67b38d24058f482fa775b6283df9fa407764d827bedd8a4c4584572d" alt="Image" width="75%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 6-4. LA-Tree</div> </div>

By batching modifications, the LA-Tree avoids performing many independent updates on individual pages. Instead, multiple updates to a page are performed together, reducing disk writes and localizing structural modifications like node splits and merges.

> ### 💡 Beginner's Corner: Subtree Buffers & Cascading Propagation
>
> - **What it is**: A Lazy-Adaptive Tree (LA-Tree) does not buffer writes for each individual node. Instead, it groups multiple levels of the B-Tree into subtrees and associates a single, shared memory buffer with the root of each subtree.
> - **Why it exists & What problem it solves**: In a write-heavy database, even if we buffer updates in memory, flushing them to disk still causes high write amplification if updates are scattered randomly across many leaf nodes. The LA-Tree solves this by batching updates at a coarser grain (the subtree level). This localizes write operations to specific regions of the tree and allows multiple updates destined for the same leaf pages to be flushed together in a single, sequential write.
> - **Underlying Mechanism**: When an insert occurs, it is appended to the buffer of the root node of the top-level subtree. When this buffer reaches its capacity limit, a background process flushes its entries down to the next level of subtree buffers. This is called _cascading propagation_. Because the updates are sorted, they can be distributed to the appropriate child subtree buffers in batch. This process repeats recursively down the levels of the tree. When the updates finally reach the leaf nodes, they are applied in bulk, meaning a leaf page is written to disk only once for many accumulated writes, drastically reducing physical I/O.

---

## FD-Trees

Random writes are historically slow on HDDs due to disk head movement. On SSDs, random writes do not require mechanical movement but cause write amplification and trigger frequent garbage collection.

To avoid random writes entirely, we can use append-only storage combined with merge processes. One implementation of this concept is the **Flash Disk Tree (FD-Tree)**.

An **FD-Tree** consists of:

- A small, mutable **head tree** (a standard B-Tree) that buffers incoming updates.
- Multiple **immutable sorted runs** (logarithmic runs) stored on disk, with sizes increasing by a factor of $ k $.

When the head tree fills up, its contents are written out as a new sorted run. As runs grow, they are merged with lower-level runs, gradually propagating data down the hierarchy, similar to LSM compaction.

### Fractional Cascading

To avoid performing a costly binary search on every single level during a lookup, FD-Trees use **fractional cascading**.

In standard multi-level arrays, searching requires $ O(\log n) $ steps per level. Fractional cascading builds **bridges** (or **fences**) between levels, allowing a search to locate an item on the first level and then follow direct pointers to its approximate location on subsequent levels.

#### Fractional Cascading Example

Assume we have three sorted arrays:

```
A1 = [12, 24, 32, 34, 39]
A2 = [22, 25, 28, 30, 35]
A3 = [11, 16, 24, 26, 30]
```

To bridge the gaps, we pull every $ N\text{-th} $ element (e.g., every second element, $ N=2 $) from the lower array to the higher array:

```
A1 = [12, 24, 25, 30, 32, 34, 39]  (pulled 25 and 30 from A2)
A2 = [16, 22, 25, 26, 28, 30, 35]  (pulled 16 and 26 from A3)
A3 = [11, 16, 24, 26, 30]
```

We then build physical pointers (bridges) from these pulled elements in the higher array directly to their corresponding positions in the lower array:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//70289cb2-e697-4a1b-9151-cb05b7f15b8b/markdown_2/imgs/img_in_image_box_140_301_1038_940.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A22%3A01Z%2F-1%2F%2F3e67382cb50937f52334f04b7ff81f964196f72ba0ff3114a66dc869d7b8d55b" alt="Image" width="75%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 6-5. Fractional cascading</div> </div>

> ### 💡 Beginner's Corner: Fractional Cascading & Fences
>
> - **What it is**: Fractional cascading is an algorithmic technique used to speed up searches across a collection of multiple sorted arrays. It works by copying a fraction of elements from lower-level arrays into higher-level arrays and adding physical pointers (bridges or fences) from these copied elements directly to their exact positions in the lower levels.
> - **Why it exists & What problem it solves**: In a multi-level storage structure (like an FD-Tree or LSM Tree), a lookup operation might have to search multiple sorted arrays (runs) to find a key. Doing a full binary search on each array of size $N$ takes $O(\log N)$ time per level, leading to an overall search complexity of $O(L \log N)$ for $L$ levels. Fractional cascading solves this by allowing the search to perform a binary search only once on the first array. The search then uses the pre-computed physical pointers (bridges) to jump directly to the exact region in the next array, reducing the search cost at each subsequent level to $O(1)$.
> - **Underlying Mechanism**: In the fractional cascading example, every $2\text{nd}$ element from array $A_2$ is promoted to $A_1$. Along with each promoted element in $A_1$, we store a pointer to its original index in $A_2$. When searching for a key, we perform a binary search on $A_1$. Once we find the closest element in $A_1$, we follow its associated bridge pointer directly to $A_2$. This places us either exactly on the target element in $A_2$ or immediately adjacent to it, requiring at most a single local comparison ($O(1)$) to find the key in $A_2$ instead of a full binary search. We then repeat this process to jump from $A_2$ to $A_3$.

---

### Logarithmic Runs in FD-Trees

In an FD-Tree, the highest-level run ($ L_1 $) is created when the head B-Tree fills up. Subsequent fills cause the head tree to merge with $ L_1 $, overwriting it. When $ L_1 $ exceeds its size threshold, it merges with $ L_2 $, and so on.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//70289cb2-e697-4a1b-9151-cb05b7f15b8b/markdown_3/imgs/img_in_image_box_144_872_1046_1056.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A22%3A01Z%2F-1%2F%2F8f02e15c31a15d3fe83daafe627d57f8d86f3dada97a1a70e52403ecad1b83ba" alt="Image" width="75%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 6-6. Schematic FD-Tree overview</div> </div>

- **Bridges**: Head elements from lower-level pages are propagated up to higher levels as pointers, ensuring that we can skip binary searches on lower levels.
- **Deletes and Tombstones**: Because pages are not updated in place, duplicate keys can exist across levels. Deletions are handled by inserting **tombstones** (or **filter entries**). A tombstone shadows any older version of the key on lower levels. Tombstones are discarded during merges once they reach the lowest level, as no older versions remain to be shadowed.

---

## Bw-Trees

Standard B-Trees suffer from three main performance limitations:

1.  **Write Amplification**: Small updates require rewriting entire disk-resident pages.
2.  **Space Amplification**: Extra space must be reserved in each page to accommodate future inserts.
3.  **Concurrency Bottlenecks**: Managing concurrent access requires complex latching mechanisms.

The **Buzzword-Tree (Bw-Tree)** solves these problems by combining **append-only storage**, **delta chains**, and a **lock-free in-memory mapping table**.

### Update Chains

Instead of modifying a page in place, a Bw-Tree writes the base page and its modifications separately.

- **Delta Nodes**: Each insert, update, or delete is prepended as a new **delta node** to an in-memory **update chain** that terminates at the original base page.
- **Immutability**: Neither the base page nor the delta nodes are modified after creation. This removes the need to reserve extra page space for future updates.
- **Read Overhead**: During a read, the engine must traverse the delta chain from the newest delta to the base page, applying the modifications to reconstruct the current logical state of the node.

> ### 💡 Beginner's Corner: Delta Chains & Memory Consolidation
>
> - **What it is**: A delta chain is a linked list of update records (delta nodes) prepended to a base page in memory. Each delta node represents a single logical mutation (an insertion, update, or deletion of a key-value pair) on that page.
> - **Why it exists & What problem it solves**: Traditional B-Trees perform in-place updates. If multiple threads write to the same page concurrently, they must coordinate using locks (latches), which blocks other threads and degrades performance on modern multi-core CPUs. Furthermore, writing a small change requires copying and writing the entire page to disk, causing high write amplification. Delta chains solve this by making pages immutable: updates are simply appended to the chain in memory, and eventually, the entire chain is consolidated and written sequentially, avoiding locks and reducing write overhead.
> - **Underlying Mechanism**: When a key is inserted, instead of modifying the binary layout of the base page, a small `delta` node is allocated in memory containing the new key-value pair and a pointer to the current head of the page's chain. When a thread reads the node, it starts at the newest delta node and traverses down the pointers to the base page, building a temporary view of the data. If the chain grows too long (e.g., more than 8-16 deltas), a background thread performs _consolidation_: it reads the base page, applies all the deltas in order, creates a brand-new consolidated base page in a new memory location, and updates the mapping table pointer.

---

### Taming Concurrency with Compare-and-Swap

To avoid updating parent pointers every time a child node prepends a delta, Bw-Trees use logical node identifiers and an in-memory **mapping table** that maps these logical IDs to physical memory offsets.

- **Latch-Free Updates**: The Bw-Tree uses atomic **Compare-and-Swap (CAS)** operations to update physical offsets in the mapping table, removing the need for page latches.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//09bbfb4a-fc8d-40c7-9ab8-c847922805dd/markdown_2/imgs/img_in_image_box_144_708_1044_894.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A22%3A01Z%2F-1%2F%2F97bbbce2dcd5608ab1abe3e1f4706a63e355d73cd681fa2ffa924a457d3f1f60" alt="Image" width="75%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 6-7. Bw-Tree. Dotted lines represent virtual links between the nodes, resolved using the mapping table. Solid lines represent actual data pointers between the nodes.</div> </div>

#### The Bw-Tree Update Workflow

1.  **Locate Node**: Traverse the tree from the root to the target leaf using logical IDs. Look up the physical offset of the latest delta (or base node) in the mapping table.
2.  **Create Delta**: Allocate a new delta node and set its next pointer to the address of the latest node found in step 1.
3.  **Atomic Swap**: Use a **Compare-and-Swap (CAS)** operation to update the mapping table entry from the old node address to the new delta node address.

> [!NOTE]
> If two threads attempt to install a delta node on the same logical node concurrently, only one CAS operation will succeed. The losing thread must read the new head of the chain and retry its operation.

> ### 💡 Beginner's Corner: Compare-and-Swap (CAS) & The Mapping Table
>
> - **What it is**: Compare-and-Swap (CAS) is an atomic CPU instruction that compares the contents of a memory location to a given expected value and, if they are equal, modifies the contents of that memory location to a new given value. The mapping table is an in-memory array that maps logical page IDs to physical memory addresses.
> - **Why it exists & What problem it solves**: In standard B-Trees, updating a node's location or pointer requires updating the parent node's pointer. If multiple threads are updating different parts of the tree, they must lock parent and sibling nodes, causing massive lock contention. The mapping table solves this by introducing a layer of indirection: parent nodes store logical page IDs instead of direct physical memory pointers. When a child node is modified (such as when a new delta node is prepended), its physical memory address changes, but its logical page ID remains identical. This means we only need to update a single entry in the mapping table, which can be done atomically using a CAS instruction without acquiring any locks.
> - **Underlying Mechanism**: At the hardware level, a CAS operation is executed as a single, uninterruptible instruction (e.g., `LOCK CMPXCHG` on x86 architectures). The thread reads the current physical address of a page from the mapping table (the _expected value_), constructs a new delta node pointing to this address, and then issues a CAS instruction to write the new delta node's address into the mapping table. The CPU guarantees that if another thread has updated the mapping table entry in the split second between the read and the write, the expected value will not match, the CAS will fail, and the thread will safely abort and retry the operation without causing data corruption.
>
> ### 🚶‍♂️ Step-by-Step Breakdown: Bw-Tree Write & CAS Installation
>
> 1. **Step 1 (Locate Logical ID)**: The writing thread traverses the tree to find the logical page ID of the target leaf node.
> 2. **Step 2 (Read Address & Allocate)**: The thread reads the current physical address of the node from the mapping table. It allocates a new delta node in memory and sets its `next` pointer to this physical address.
> 3. **Step 3 (Execute CAS)**: The thread issues a CAS instruction on the mapping table entry, passing the logical page ID, the expected physical address (read in Step 2), and the address of the new delta node.
> 4. **Step 4 (Resolution)**:
>     - **If the CAS succeeds**: The mapping table now points to the new delta node, exposing the write to all other threads. The write is complete.
>     - **If the CAS fails**: Another thread has modified the node concurrently. The writing thread discards the new delta node (or updates its pointer), reads the new physical address from the mapping table, and retries from Step 2.

---

### Structural Modification Operations (SMOs)

Like standard B-Trees, Bw-Tree nodes must split when they overflow and merge when they underflow. Since Bw-Trees are latch-free, these **Structural Modification Operations (SMOs)** are performed in a non-blocking, multi-step manner.

#### Split Workflow

1.  **Consolidation**: The splitting thread consolidates the target node by applying its delta chain to the base node and creating a new right sibling page containing the right half of the keys.
2.  **Split Delta**: A special **split delta node** is appended to the original (left) node. This delta contains the split key and a logical pointer to the new right sibling node. At this stage, the sibling is accessible via the split delta but is not yet linked from the parent.
3.  **Parent Update**: A parent boundary delta is appended to the parent node to add the link to the new right sibling, completing the split.

> [!IMPORTANT]
> Because Bw-Trees are latch-free, any thread that encounters an incomplete, half-completed SMO must help complete it before proceeding with its own operation.

> ### 🚶‍♂️ Step-by-Step Breakdown: Bw-Tree Node Split (SMO)
>
> 1. **Step 1 (Consolidation & Sibling Creation)**: A thread detects that a leaf node has overflowed. It consolidates the node's delta chain and base page, splits the keys in half, and allocates a new right sibling node in memory to hold the upper half of the keys. It registers a new logical ID for this sibling in the mapping table.
> 2. **Step 2 (Install Split Delta)**: The thread allocates a _split delta node_ containing the split key and the logical ID of the new right sibling. It attempts to install this split delta on the left node via a CAS operation. Once successful, the left node is logically split: any thread traversing the left node that looks for a key greater than the split key will follow the logical pointer in the split delta to the new right sibling.
> 3. **Step 3 (Propagate to Parent)**: The split is not yet complete because the parent node does not have a direct link to the new right sibling. The thread constructs a _boundary delta node_ containing the split key and the right sibling's logical ID, and attempts to install it on the parent node via a CAS operation.
> 4. **Step 4 (Cooperative Completion)**: If a concurrent thread accesses the left node and detects the split delta before the parent update is complete, it does not wait. Instead, it cooperatively attempts to perform Step 3 itself, ensuring that structural modifications cannot block progress or cause deadlocks.

#### Merge Workflow

1.  **Remove Sibling**: A **remove delta node** is appended to the right sibling, marking it as logically deleted.
2.  **Merge Delta**: A **merge delta node** is appended to the left sibling, pointing directly to the right sibling's contents and logically joining them.
3.  **Parent Update**: The link to the deleted right sibling is removed from the parent node.

To prevent concurrent conflicting splits and merges, Bw-Trees install an **abort delta node** on parent nodes during SMOs, which acts as a non-blocking write lock.

---

### Consolidation and Garbage Collection

As delta chains grow longer, reads become slower. To maintain good performance, Bw-Trees periodically perform **consolidation**:

1.  The base page and all its deltas are merged into a single, new base page.
2.  The new base page is written to a new location.
3.  The mapping table is updated to point to the new base page, making the old base page and its deltas unreachable.

#### Epoch-Based Reclamation

Because there are no locks, some active reader threads might still be traversing the old, un-consolidated delta chain when the mapping table is updated. Bw-Trees use **epoch-based reclamation** to safely reclaim this memory:

- The system maintains a global **epoch counter**.
- Active threads register themselves in the current epoch when starting an operation.
- Unreachable pages are placed in a retirement queue associated with the current epoch.
- Once all threads registered in an epoch (and all earlier epochs) finish their operations, the retired pages from that epoch are safely freed.

> ### 💡 Beginner's Corner: Epoch-Based Reclamation
>
> - **What it is**: Epoch-based reclamation (EBR) is a memory management technique used in lock-free data structures to safely reclaim (free) memory that has been logically deleted but might still be accessed by concurrent reader threads.
> - **Why it exists & What problem it solves**: In a lock-free system like a Bw-Tree, when a delta chain is consolidated, the old delta nodes and the old base page are removed from the mapping table and replaced by a new consolidated page. They are now logically deleted. However, because there are no locks, some concurrent reader threads might still be actively traversing the old delta chain. If we free that memory immediately, those reader threads will access deallocated memory, causing segmentation faults or data corruption. EBR solves this by delaying memory reclamation until it is guaranteed that no threads are still accessing the old memory.
> - **Underlying Mechanism**: The database maintains a global epoch counter (an integer, e.g., $E$). When a thread starts a read or write operation, it registers itself in the active epoch $E$. When a thread consolidates a node, it places the old memory blocks into a "retirement queue" labeled with the current epoch $E$. Periodically, the global epoch is bumped to $E+1$. The memory blocks in the retirement queue for epoch $E-1$ can only be safely freed when all threads registered in epoch $E-1$ and all prior epochs have completed their operations (i.e., their active operation count drops to zero).

---

## Cache-Oblivious B-Trees

Configurable database parameters—such as block sizes, page alignments, and cache line boundaries—greatly affect B-Tree performance. **Cache-oblivious structures** are designed to perform asymptotically optimal searches across a memory hierarchy without needing any platform-specific tuning.

While a cache-aware algorithm must explicitly manage data transfers between two specific levels (e.g., page cache and disk), a cache-oblivious algorithm operates under the assumption of a generic two-level memory model but naturally scales its benefits across all levels of a multi-level hierarchy (CPU L1/L2/L3 caches, RAM, SSD, HDD).

### van Emde Boas Layout

A cache-oblivious B-Tree consists of a static tree structure and a dynamic packed array. The static tree is organized using the **van Emde Boas layout**.

- The tree is split at the middle level of its height, dividing it into a top subtree and several bottom subtrees.
- This split is applied recursively, resulting in subtrees of size $\sqrt{N}$.
- Each recursive subtree is stored in a **contiguous block of memory**, ensuring that nodes that are logically close to each other in the tree are physically close to each other on disk or in RAM.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//7f9fd7a5-18eb-459d-9336-39288ebeeb6c/markdown_0/imgs/img_in_image_box_193_676_1047_1014.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A22%3A01Z%2F-1%2F%2F612db4ce84e466fb79e0ebcc8352e040d3378e700223ac5ab03a34e1314c734d" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 6-8. van Emde Boas layout</div> </div>

---

### Packed Array Structure

To support dynamic inserts, updates, and deletes, the leaves of the static tree point into a **packed array structure**.

- Elements are stored in contiguous memory segments but are separated by **gaps** (empty slots) to allow new elements to be inserted without shifting the entire array.
- If an insertion falls into a region that has no gaps, elements in that region are shifted locally to create a gap.
- If the packed array becomes too full (violating a density threshold), it is resized and rebuilt, and the static van Emde Boas tree index is updated to point to the new offsets.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//7f9fd7a5-18eb-459d-9336-39288ebeeb6c/markdown_0/imgs/img_in_image_box_142_1364_1048_1409.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A22%3A01Z%2F-1%2F%2F49d35e4c91910e823a854b23835a5df43bcc9d8dcdb63aec53eb2d98d98b390d" alt="Image" width="76%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 6-9. Packed array</div> </div>

> [!NOTE]
> Although cache-oblivious B-Trees are theoretically elegant, they are rarely used in commercial databases today. One reason is that page eviction and OS-level paging still heavily impact performance. However, interest may rise as byte-addressable, non-volatile memory (NVM) devices become more common.

---

## Summary

The original B-Tree design was optimized for spinning disks but exhibits performance issues on modern solid-state drives (SSDs). These include high write amplification (due to full-page random writes) and high space overhead (due to reserving empty space in nodes).

To address these limitations, several B-Tree variants have been designed:

- **Lazy B-Trees** (e.g., **WiredTiger**, **LA-Trees**) use in-memory buffers (such as skiplists) to cache modifications and write them to disk in batches, reducing write amplification.
- **FD-Trees** use **immutability** and **fractional cascading** to write updates into sequential, log-like runs on disk, converting random writes into sequential ones.
- **Bw-Trees** represent nodes as a **delta chain** and use a lock-free, in-memory **mapping table** to perform updates using atomic Compare-and-Swap operations, solving concurrency and write-amplification challenges.
- **Cache-Oblivious B-Trees** use the **van Emde Boas layout** and **packed arrays** to achieve asymptotically optimal performance across all levels of the memory hierarchy without hardware-specific tuning.
