# Module 02: B-Tree Basics

In the previous module, we divided storage structures into two groups: **mutable** and **immutable** ones, and identified immutability as a core concept affecting their design and implementation. 

Most mutable storage structures use an **in-place update** mechanism. During insert, delete, or update operations, data records are updated directly in their physical locations in the target file.

Storage engines often allow multiple versions of the same data record to be present in the database—for example, when using **multiversion concurrency control (MVCC)** or **slotted page organization**. To keep things simple, for now we assume that each key is associated with only one data record, which has a unique location.

> ### 💡 Beginner's Corner: In-Place Updates vs. MVCC
> * **What it is**: 
>   * **In-Place Update**: Writing new data directly over the old data at the exact same location on disk.
>   * **Multiversion Concurrency Control (MVCC)**: Instead of overwriting, the database writes a new version of the record elsewhere, keeping both old and new versions.
> * **Why they exist**: In-place updates are simple and save space, but they require heavy locking so users don't read half-written data. MVCC allows readers to read the old version without blocking while writers write the new version.

One of the most popular storage structures is the **B-Tree**. Many open-source database systems are B-Tree based, and over the years they have proven to cover most use cases.

> **Historical Context**: B-Trees were introduced by Rudolph Bayer and Edward M. McCreight in 1971. By 1979, quite a few B-Tree variants had emerged, which were collected and organized by Douglas Comer.

Before we dive into B-Trees, let's first discuss why we must consider alternatives to traditional search trees like **binary search trees (BSTs)**, **2-3-Trees**, and **AVL Trees**.

> ### 💡 Beginner's Corner: Self-Balancing Trees (AVL & 2-3 Trees)
> * **What they are**: Binary Search Trees (BSTs) are great, but if they get out of balance, they become slow. **2-3 Trees** and **AVL Trees** are "self-balancing" variants that automatically reorganize their structure during inserts and deletes to keep their depth as shallow and balanced as possible.
> * **Why they exist**: To guarantee that searching for a key remains fast ($O(\log N)$ complexity) even as millions of random items are added or removed.

---

## Binary Search Trees

A **binary search tree (BST)** is a sorted, in-memory data structure used for fast key-value lookups. 

*   **Structure**: BSTs consist of multiple **nodes**. Each node contains:
    *   A **key**
    *   A **value** associated with this key
    *   Two **child pointers** (left and right)
*   **Root Node**: BSTs start from a single node called the **root node**. There can be only one root in a tree.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//dfc9688a-9aa8-4edb-94c7-02d952836c65/markdown_1/imgs/img_in_image_box_139_536_830_1158.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A21%3A58Z%2F-1%2F%2F0a8eba6cc4ef661a11d75d5383acdbfee15a4967ac8742f95ef4d5dd6aa038f6" alt="Image" width="58%" /></div>
<div style="text-align: center;">Figure 2-1. Binary search tree</div>

### Node Invariants

Each node splits the search space into left and right subtrees:
*   A node's key is **greater than** any key stored in its left subtree.
*   A node's key is **less than** any key stored in its right subtree.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//dfc9688a-9aa8-4edb-94c7-02d952836c65/markdown_2/imgs/img_in_image_box_135_157_1048_805.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A21%3A58Z%2F-1%2F%2F72a1542a31ad3dee5c47f083ff834d688e8b1e2f4dd11cd2a2e93cc9efbd4004" alt="Image" width="76%" /></div>
<div style="text-align: center;">Figure 2-2. Binary tree node invariants</div>

*   **Finding the Smallest Key**: Follow the left child pointers from the root down to the leaf level (where nodes have no children).
*   **Finding the Largest Key**: Follow the right child pointers from the root down to the leaf level.
*   **Value Storage**: Values can be stored in any node. Searches start at the root and can stop early if the key is found on a higher level.

### Tree Balancing

If elements are inserted in a random or unguided order, the tree can become **unbalanced** (where one branch is much longer than the other).

*   **Worst-Case (Pathological Tree)**: The tree degrades into a structure that looks like a linked list.
*   **Complexity Degradation**: Lookup complexity degrades from the desired logarithmic time ($O(\log_2 N)$) to linear time ($O(N)$).

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//dfc9688a-9aa8-4edb-94c7-02d952836c65/markdown_3/imgs/img_in_image_box_141_507_1053_850.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A21%3A59Z%2F-1%2F%2F9603e2a367491f3235f16723e62ab6303de6aa5c10275d86b56b78bf055f1f5c" alt="Image" width="76%" /></div>
<div style="text-align: center;">Figure 2-3. Balanced (a) and unbalanced or pathological (b) tree examples</div>

> **Definition**: A **balanced tree** is defined as one that has a height of $\log_2 N$ (where $N$ is the total number of items in the tree) and the difference in height between its two subtrees is at most one.

*   **Logarithmic Complexity**: In a balanced tree, following a pointer cuts the remaining search space in half on average, guaranteeing $O(\log_2 N)$ lookups.
*   **Self-Balancing**: To prevent degradation, the tree is balanced after every insertion or deletion.
*   **Tree Rotations**: Rebalancing is often done using a **rotation step**. If an insertion leaves a branch unbalanced, the nodes are rotated. The middle node (called the **rotation pivot**) is promoted one level higher, and its parent becomes its right child.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//dfc9688a-9aa8-4edb-94c7-02d952836c65/markdown_4/imgs/img_in_image_box_138_609_1054_996.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A21%3A59Z%2F-1%2F%2F1a1205145ccc39ece27b02e54fba94cd96f924184e77140dd666f0dc79e0c17c" alt="Image" width="76%" /></div>
<div style="text-align: center;">Figure 2-4. Rotation step example</div>

### Trees for Disk-Based Storage

While balanced binary trees provide $O(\log_2 N)$ lookups on average, their **low fanout** (maximum children per node is two) makes them impractical for disk-based storage:

*   **Locality Problem**: Because elements are added in random order, parent and child nodes may be written to completely different disk pages. Following a pointer requires jumps across physical pages.
*   **Tree Height Problem**: A low fanout of two means the tree height is $\log_2 N$. Finding an element requires $O(\log_2 N)$ disk seeks and page transfers.
*   **High Maintenance**: Rebalancing requires moving nodes and updating pointers frequently, which is highly expensive on disk.

> ### 💡 Beginner's Corner: The Disk I/O Bottleneck and Search Trees
> * **The Problem (Slow Disk Access)**: Memory (RAM) access latency is measured in nanoseconds. Physical disk access latency is measured in microseconds (for SSDs) or milliseconds (for HDDs) due to bus transit times and mechanical seek delays. Disk access is roughly 10,000 to 100,000 times slower than RAM.
> * **Why BSTs Fail on Disk**: In a Binary Search Tree (BST), each node has at most two children. For a dataset of 1 million items, a balanced BST is approximately 20 levels deep ($2^{20} \approx 1,048,576$). Finding an item requires traversing from the root down to a leaf. If the tree is on disk, each parent-child pointer traversal can require reading a different physical page, resulting in up to 20 slow, independent disk read operations (random I/O).
> * **The Solution (High Fanout & Low Height)**: Instead of storing 1 key per node, a B-Tree stores hundreds of keys per node (e.g., 512 keys). This gives each node a high **fanout** (up to 513 children). For 1 million items, a B-Tree with a fanout of 500 is only 3 levels deep ($\log_{500} 1,000,000 \approx 2.2$). This reduces the number of random disk reads to at most 3, drastically improving query performance.

For disk-based storage, an optimal tree structure must have:
1.  **High Fanout**: To group neighboring keys close together, improving **locality**.
2.  **Low Height**: To minimize the number of disk seeks during traversal.

> **Key Rule**: **Fanout** and **height** have an inverse relationship: the higher the fanout, the lower the height. If each node can hold more children, fewer nodes and levels are needed, reducing the tree's height.

---

## Disk-Based Structures

Just as database systems are divided into memory- and disk-based engines, data structures also differ: some are suited for memory, and others are adapted for disk.

### Persistent Medium Limitations
On-disk structures are used when datasets are too large to fit in RAM. Only a small fraction of the data can be cached in memory; the rest must be organized on disk for fast access.

#### Hard Disk Drives (HDDs)
*   **Random Reads**: Highly expensive because they require disk rotation and mechanical head movements to position the read/write head.
*   **Sequential reads/writes**: Relatively cheap once the head is positioned.
*   **Block-wise Access**: The smallest unit of physical data transfer is a **sector** (typically 512 bytes to 4 Kb). Operating systems hide this via a **block device abstraction**, buffering reads so that requesting a single word fetches the entire block.

#### Solid State Drives (SSDs)
*   **Structure**: No moving parts. Built from memory cells combined into strings, arrays, pages, and blocks.
*   **Smallest Read/Write Unit**: A **page** (typically 2 to 16 Kb).
*   **Erase Constraints**: Writes can only be performed on empty cells. The smallest unit that can be erased is a **block** (holding 64 to 512 pages), often called an **erase block**. Pages in an empty block must be written sequentially.
*   **Flash Translation Layer (FTL)**: A controller component that maps page IDs to physical locations, tracks page states, and performs **garbage collection** (relocating live pages from partially filled blocks to new blocks, then erasing the old ones).
*   **I/O Characteristics**: The latency gap between random and sequential reads is much smaller than in HDDs, though sequential operations are still faster due to prefetching and internal parallelism.

> ### 💡 Beginner's Corner: HDD vs. SSD Physical Media Constraints
> * **HDD (Hard Disk Drive)**: Data is stored on magnetic spinning platters. Reading data requires a physical drive head to seek the correct track (rotational and seek latency). Random reads are extremely slow because the head must physically reposition itself for every read, whereas sequential reads are faster as the head stays on the same track.
> * **SSD (Solid State Drive)**: Built on semiconductor flash memory with no moving parts. It accesses data electrically, making random reads much faster than HDDs. However, SSDs write data in small units called **Pages** (e.g., 4KB), but can only erase data in larger units called **Blocks** (e.g., 256KB). Writing to a page requires erasing its block first, which requires a specialized controller called the **Flash Translation Layer (FTL)** to relocate active pages, perform garbage collection, and erase blocks.
> * **Jargon Buster**:
>   * **Sector**: The smallest physical addressable unit on a hard drive (traditionally 512 bytes or 4KB).
>   * **Block-wise Access**: Operating systems transfer data to and from storage devices in fixed-size blocks (typically 4KB) rather than individual bytes, using buffer caches to group small reads and writes.

#### Designing for Blocks
Because both HDDs and SSDs access data block-wise, on-disk structures must:
*   Optimize for fewer disk accesses.
*   Maximize key **locality** within blocks.
*   Reduce the number of out-of-page pointers.

### Paged Binary Trees
One naive way to improve binary tree locality on disk is grouping multiple nodes into physical pages. 

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//340dab42-04e6-457e-9184-b2e3babea004/markdown_2/imgs/img_in_image_box_166_241_1046_748.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A21%3A59Z%2F-1%2F%2Fbf1803113f82b5ba011f91f79fa173518babb4450e396bbc9a81d9e92d55012e" alt="Image" width="73%" /></div>
<div style="text-align: center;">Figure 2-6. Paged binary trees</div>

*   **Advantage**: Finding the next node often only requires reading pointers within an already fetched page.
*   **Disadvantage**: Overhead from node metadata and pointers remains high. Laying out and maintaining this structure on disk is difficult. Rebalancing requires page reorganizations, causing cascading pointer updates.

---

## Ubiquitous B-Trees

A **B-Tree** builds a sorted index hierarchy that navigates to and locates searched items with very few disk accesses. B-Trees combine the ideas of balanced trees but increase node fanout, reducing tree height, the number of pointers, and the frequency of rebalancing operations.

### Visualizing Tree Nodes

| Binary Tree Node | 2-3 Tree Node | B-Tree Node |
| :--- | :--- | :--- |
| Circle representation | Hexagon/Rectangle | Large Rectangle |
| 1 key, 2 child pointers | 1 or 2 keys, 2 or 3 pointers | Up to $N$ keys, $N+1$ pointers |
| Splits range in 2 | Splits range in 2 or 3 | Splits range into $N+1$ subranges |

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//340dab42-04e6-457e-9184-b2e3babea004/markdown_3/imgs/img_in_image_box_143_982_1045_1128.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A21%3A59Z%2F-1%2F%2F1a8ec2e036d67c27cbeedd8c56b9a7ed084bd857e6dbb9105ae632f6e51761e4" alt="Image" width="75%" /></div>
<div style="text-align: center;">Figure 2-7. Binary tree, 2-3-Tree, and B-Tree nodes side by side</div>

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//340dab42-04e6-457e-9184-b2e3babea004/markdown_4/imgs/img_in_image_box_141_133_1045_850.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A22%3A00Z%2F-1%2F%2F846f5828880d596c066ed31bc6e851a067bc6e7b9ef22262f977729341e7c4af" alt="Image" width="75%" /></div>
<div style="text-align: center;">Figure 2-8. Alternative representation of a binary tree</div>

Keys inside B-Tree nodes are stored in sorted order. Because of this:
*   Lookups inside a node can use **binary search**.
*   Finding a key among 4 billion items takes only about 32 comparisons.
*   Because B-Tree nodes store hundreds of items, we only need to perform **one disk seek per level jump** (rather than one seek per comparison).
*   B-Trees support both **point queries** (exact matches) and **range queries** (ordered scans) efficiently.

### B-Tree Hierarchy

A B-Tree consists of three types of nodes (pages):

1.  **Root Node**: The top node in the tree, having no parent nodes.
2.  **Leaf Nodes**: The bottom layer of the tree, containing no child pointers. In $B^+$-Trees, leaf nodes store the actual data records or pointers to them.
3.  **Internal Nodes**: All intermediate layers connecting the root with the leaves. They guide the search algorithm.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//c9a5d94f-6bd1-451a-a3e5-0b8c63b1d7be/markdown_2/imgs/img_in_image_box_142_145_987_397.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A21%3A58Z%2F-1%2F%2F5717db8a268948431960b8cf31d57357fcdc9c3d9300eb43e09a5e0aec02909c" alt="Image" width="70%" /></div>
<div style="text-align: center;">Figure 2-9. B-Tree node hierarchy</div>

*   **Occupancy**: The ratio of keys currently held in a node to its total capacity.
*   **Fanout**: The number of child pointers originating from a node. High fanout reduces tree height and spreads out the cost of rebalancing.
*   **Page Organization**: Because B-Trees organize fixed-size pages on disk, the terms **node** and **page** are used interchangeably.

> ### $B^+$-Trees vs. B-Trees
> *   **Standard B-Trees**: Allow storing values (payloads) on any level: in the root, internal, or leaf nodes.
> *   **$B^+$-Trees**: Store values **only in leaf nodes**. Internal nodes store only **separator keys** used to guide searches.
> *   **Advantage**: Because internal nodes do not store values, they can hold more keys, resulting in much higher fanout and lower tree height. All inserts, updates, and deletes affect only leaf nodes directly, simplifying concurrency.
> *   $B^+$-Trees are the default design in modern databases (e.g., `MySQL InnoDB`).

### Separator Keys

Keys inside B-Tree nodes are called **separator keys**, **index entries**, or **divider cells**. They split the key range into subranges:
*   The first pointer in a node points to the subtree holding items **less than** the first key.
*   The last pointer points to the subtree holding items **greater than or equal to** the last key.
*   Intermediate pointers reference subtrees between two keys: $K_{i-1} \leq K_s < K_i$, where $K_s$ belongs to the subtree.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//c9a5d94f-6bd1-451a-a3e5-0b8c63b1d7be/markdown_3/imgs/img_in_image_box_145_718_1048_1015.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A21%3A58Z%2F-1%2F%2F8e3ba6bdfdbc7a3ad12daad46524c79a1f5790e7b9878a4719312a7fc05edc97" alt="Image" width="75%" /></div>
<div style="text-align: center;">Figure 2-10. How separator keys split a tree into subtrees</div>

*   **Sibling Pointers**: Many B-Trees include pointers to adjacent sibling nodes on the leaf level. This allows sequential range scans without traversing back up to parent nodes. A bidirectional pointer scheme forms a double-linked list on the leaf level, allowing reverse scans.
*   **Growth Direction**: Unlike BSTs which grow from top to bottom, B-Trees are constructed **from bottom to top**. As leaf nodes grow, splits propagate upward, increasing the height.
*   **Storage Reserve**: B-Trees reserve extra space inside nodes for future writes. Storage utilization can drop to 50% (but is usually higher) without hurting lookup performance.

### B-Tree Lookup Complexity

We analyze lookup complexity from two perspectives:

1.  **Block Transfers (Disk Seeks)**: The complexity base is $N$ (keys per node). Traversing a level reduces the search space by a factor of $N$. During a lookup, at most $\log_N M$ pages are read (where $M$ is the total number of items in the tree). The number of disk seeks equals the tree height $h$.
2.  **Key Comparisons (CPU)**: Inside each node, the search is performed using binary search (complexity base is 2). The CPU complexity across all traversed nodes is $O(\log_2 M)$.

### B-Tree Lookup Algorithm

To locate a key in a B-Tree:

1.  Start at the **root node**.
2.  Perform a **binary search** on the node keys to find the first separator key greater than the searched key.
3.  This identifies the correct child subtree. Follow the corresponding child pointer to descend one level.
4.  Repeat the process on the child node until reaching a **leaf node**.
5.  On the leaf node, perform a binary search to locate the exact key (for point queries) or its predecessor (for range scans and insertions).

> ### 🚶‍♂️ Step-by-Step Breakdown: Tracing a B-Tree Lookup
> Let's trace how a database locates the key **35** in a $B^+$-Tree:
> 1. **Step 1: The Root Page**: The database loads the Root page into RAM. It sees three separator keys: `[10, 20, 30]`, and four child pointers pointing to Pages A, B, C, and D.
> 2. **Step 2: Binary Search the Page**: The database performs a quick binary search in RAM on the sorted keys `[10, 20, 30]`. It looks for the first key greater than **35**. Since all keys are smaller, it selects the last pointer, which points to Page D (keys $\geq 30$).
> 3. **Step 3: Descend a Level**: The database requests Page D from disk. Page D is loaded into RAM.
> 4. **Step 4: Check if Leaf**: The database checks if Page D is a leaf node. 
>    * If Page D is an internal node (e.g., keys `[32, 40, 50]`), it repeats Step 2 (deciding to follow the pointer for keys between 32 and 40).
>    * If Page D is a leaf node, it performs a final binary search on Page D's records to locate the exact key **35** and reads its data.
> 5. **Step 5: Return**: The data is returned to the user.

### Counting Keys

Different books use different notations for key and pointer counts:
*   **Bayer & McCreight Notation**: Uses a natural number $k$ representing optimal page size. Non-root pages hold between $k$ and $2k$ keys, and between $k+1$ and $2k+1$ pointers.
*   **Graefe Notation**: Describes nodes holding up to $N$ separator keys and $N+1$ pointers.
*   We use **$N$ as the maximum number of keys** in a node for clarity.

### B-Tree Node Splits

To insert an item, the database first traverses to the target leaf node. If the target node is full, an **overflow** occurs, and the node must be split:
*   **Leaf Node Split**: Occurs when a node already holds $N$ key-value pairs, and inserting another would exceed capacity.
*   **Non-Leaf Node Split**: Occurs when a node holds $N+1$ pointers, and inserting another pointer would exceed capacity.

#### The Node Split Workflow

1.  **Allocate** a new sibling node.
2.  **Copy** half of the elements from the splitting node to the new one. The division point is the **split point** (midpoint).
3.  **Place** the new element into the correct node based on its key.
4.  **Promote** the split-point key to the parent node, along with a pointer to the new sibling node.

> ### 🚶‍♂️ Step-by-Step Breakdown: How a B-Tree Node Splits (Overflow)
> Imagine a leaf node can hold at most 3 keys. It currently has `[5, 8, 12]`, and we want to insert **10**.
> 1. **Step 1: Detection (Overflow)**: The database attempts to insert **10** into the leaf node. The node temporarily becomes `[5, 8, 10, 12]`. Since 4 keys exceed the limit of 3, the database triggers a split.
> 2. **Step 2: Split Point & Allocation**: The database allocates a brand-new page on disk (Sibling Node). It finds the midpoint of the elements.
> 3. **Step 3: Redistribution**: The elements are split:
>    * The left node keeps the lower half: `[5, 8]`.
>    * The new right node gets the upper half: `[10, 12]`.
> 4. **Step 4: Promotion**: The first key of the new right node (**10**) is "promoted" up to the parent node as a separator key, and the parent node is updated to point to the new right node.
> 5. **Step 5: Cascading Splits (If needed)**: If the parent node was already full, the parent node will also split, promoting a key to *its* parent. This can cascade all the way to the root!

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//b045432c-b5ad-4f65-ae08-4a99d5c82ae6/markdown_4/imgs/img_in_image_box_161_343_1035_595.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A21%3A59Z%2F-1%2F%2F52dfe461f80c4e9dc8042fdb77a70203651d012479cc7a59823e9f7dd86bb6e3" alt="Image" width="73%" /></div>
<div style="text-align: center;">Figure 2-11. Leaf node split during the insertion of 11. New element and promoted key are shown in gray.</div>

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//933551b7-3e7f-40ca-b10e-a9893d6144d9/markdown_0/imgs/img_in_image_box_141_147_1045_489.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A21%3A58Z%2F-1%2F%2F19782073fefd1b9f240c1be4fea4ce1fca32f3089ea40a97af7d2bb627a42b27" alt="Image" width="75%" /></div>
<div style="text-align: center;">Figure 2-12. Nonleaf node split during the insertion of 11. New element and promoted key are shown in gray.</div>

*   **Recursive Splits**: If the parent node is also full, the split propagates upward.
*   **Root Split**: When the split propagates to the root, a new root node is allocated to hold the promoted key. The old root and its new sibling become children, increasing the tree height by one. The tree only grows in height when the root splits; otherwise, it grows horizontally.

### B-Tree Node Merges

When keys are deleted, a node's occupancy can fall below a minimum threshold. This is called an **underflow**. If neighboring nodes have too few values, they are merged.

#### The Node Merge Workflow

1.  **Copy** all elements from the right sibling node to the left sibling node.
2.  **Demote** the corresponding separator key from the parent node into the left node.
3.  **Remove** the parent's pointer to the right sibling and **delete** the right sibling node.

> ### 🚶‍♂️ Step-by-Step Breakdown: How B-Tree Nodes Merge (Underflow)
> Imagine a node's occupancy drops below 50% because we deleted keys.
> 1. **Step 1: Detection (Underflow)**: A leaf node containing keys `[5]` is now too empty. The database checks its neighbors (siblings).
> 2. **Step 2: Sibling Check**: 
>    * If the right sibling is also almost empty (e.g., `[8, 12]`), the database decides to **merge** them.
>    * If the sibling has plenty of keys (e.g., `[8, 12, 15, 20]`), the database does not merge; it simply **borrows** a key from the sibling to balance them (called **rebalancing** or **redistribution**).
> 3. **Step 3: Consolidation**: To merge, the database copies all elements from the right sibling `[8, 12]` into the left node `[5]`, making it `[5, 8, 12]`.
> 4. **Step 4: Demoting the Separator**: The separator key in the parent node that was splitting these two siblings is no longer needed. It is removed (or "demoted") from the parent.
> 5. **Step 5: Deallocation**: The empty right sibling page is deleted, and its space is freed on disk.
> 6. **Step 6: Propagation**: If the parent node becomes too empty due to the demotion, this merge process propagates up the tree. If the root's last two children are merged, the merged node becomes the new root, and the tree height decreases by one.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//933551b7-3e7f-40ca-b10e-a9893d6144d9/markdown_1/imgs/img_in_image_box_164_1114_1017_1352.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A21%3A58Z%2F-1%2F%2F79e0cf62eca4b889d7fc97cefef3240d28a1bd4d486cb4658d3b06d2e3fd8d35" alt="Image" width="71%" /></div>
<div style="text-align: center;">Figure 2-13. Leaf node merge</div>

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//933551b7-3e7f-40ca-b10e-a9893d6144d9/markdown_3/imgs/img_in_image_box_142_147_1044_480.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A21%3A59Z%2F-1%2F%2F1bfa8f10f4fdc739cff5acc19159db8b47d9fc6b34b46b0f42de6105798d18b5" alt="Image" width="75%" /></div>
<div style="text-align: center;">Figure 2-14. Nonleaf node merge</div>

*   **Merge Propagation**: Just like splits, merges can propagate recursively up to the root. If the root's last two children are merged, the merged page becomes the new root, and the tree height decreases by one.
*   **Alternative (Rebalancing)**: If the combined content of the two siblings exceeds the node capacity $N$, they cannot be merged. Instead, keys are redistributed between them to restore balance.

---

## Summary

*   **BST Limitations**: Binary search trees have low fanout, leading to high tree height and frequent rebalancing operations that cause random disk seeks, making them unsuitable for persistent storage.
*   **B-Tree Optimizations**: B-Trees resolve this by grouping many keys into a single node (**high fanout**), which drastically reduces tree height and balancing frequency.
*   **Core Mechanics**: Lookups run in $O(\log M)$ time using binary search within nodes. Nodes restructure dynamically via **splits** (during overflows) and **merges** (during underflows) to keep the tree balanced.
*   **Next Steps**: To build an actual disk-based B-Tree, we must design the exact binary layouts of these nodes on disk.

---

### Further Reading

*   **General Algorithms**:
    *   Sedgewick, Robert and Kevin Wayne. 2011. *Algorithms* (4th Ed.). Boston: Pearson.
*   **Complexity & Search Trees**:
    *   Knuth, Donald E. 1997. *The Art of Computer Programming, Volume 2 (3rd Ed.): Seminumerical Algorithms*. Boston: Addison-Wesley Longman.
*   **B-Tree Splits and Merges**:
    *   Elmasri, Ramez and Shamkant Navathe. 2011. *Fundamentals of Database Systems* (6th Ed.). Boston: Pearson.
    *   Silberschatz, Abraham, Henry F. Korth, and S. Sudarshan. 2010. *Database Systems Concepts* (6th Ed.). New York: McGraw-Hill.

---

### Footnotes

*   $^1$ The height difference between any node's left and right subtrees is at most one.
*   $^2$ Logarithm base is omitted in big-$O$ complexity analysis because changing the base simply introduces a constant factor (e.g., $O(|c| \times n) = O(n)$), which does not affect asymptotic growth.
