# Module 10: Leader Election

Synchronization in a distributed system can be expensive. If each algorithm step requires contacting every other participant, we end up with significant communication overhead. This is especially true in large and geographically distributed networks. 

To reduce synchronization overhead and the number of message round-trips required to reach a decision, some algorithms rely on a **leader** (sometimes called a **coordinator**) process. The leader is responsible for executing or coordinating the steps of a distributed algorithm.

### Characteristics of Leadership

*   **Uniformity**: Processes in distributed systems are typically uniform; any process can take over the leadership role.
*   **Temporality**: Processes assume leadership for long periods, but it is not a permanent role. A process remains the leader until it crashes.
*   **Reelection**: After a leader crashes, any other process can start a new election round, assume leadership (if elected), and continue the failed leader's work.
*   **Liveness**: The liveness property guarantees that a leader exists most of the time and the election will eventually complete (the system will not remain in an election state indefinitely).
*   **Safety**: Ideally, there should be at most one leader at any given time. We want to eliminate **split-brain** situations, where two leaders serving the same purpose are elected concurrently but are unaware of each other.

> ### 💡 Beginner's Corner: The Split-Brain Problem & Quorum Mathematics
> * **What it is**: Split-brain is a critical safety violation in distributed systems where a single cluster is partitioned into two or more isolated networks, and each sub-network independently elects a leader. A quorum is the minimum number of votes (typically a strict majority, $Q > N/2$) required to validate a leader election or commit a write.
> * **Why it exists & What problem it solves**: In a distributed database, a leader is responsible for ordering writes to ensure consistency. If a network partition occurs and isolates Node A and Node B on the left, and Node C, D, and E on the right, and both sides elect a leader, we get two active leaders. If a client writes to the left leader and another writes to the right leader, the two partitions will accept conflicting updates, causing their histories to diverge permanently. Quorums solve this: by requiring a strict majority of nodes to agree on a leader, we guarantee that at most one leader can exist.
> * **Underlying Mechanism**: In a cluster of size $N$, a quorum requires at least $\lfloor N/2 \rfloor + 1$ nodes. If a partition occurs, it splits the cluster into segments of sizes $N_1$ and $N_2$. Because $N_1 + N_2 = N$, it is mathematically impossible for both $N_1$ and $N_2$ to be greater than $N/2$. For example, in a 5-node cluster, a quorum requires 3 nodes. If partitioned into a 2-node group and a 3-node group, only the 3-node group can form a quorum and elect a leader; the 2-node group cannot, preventing split-brain. Furthermore, because any two majorities of size $Q$ must overlap by at least one node ($2Q > N$), the overlapping node acts as a bridge, ensuring that the new leader's term is known and preventing old leaders from committing stale writes.

### The Role of a Leader
*   **Total Order Broadcast**: The leader collects, orders, and disseminates messages to establish a global sequence.
*   **System Reorganization**: The leader coordinates cluster updates during initialization, peer failures, or major state changes.
*   **Centralized Execution**: A stable leader avoids peer-to-peer coordination, reducing the total number of messages exchanged.

> [!NOTE]
> **Leader Election vs. Distributed Locking**: 
> *   **Distributed Locking**: A process acquires exclusive ownership of a shared resource to execute a critical section. Other processes do not need to know *who* holds the lock, as long as it is eventually released (liveness).
> *   **Leader Election**: The elected leader process has special coordination properties and **must be known to all other participants**. Therefore, a newly elected leader must notify all its peers.
> *   Additionally, distributed locking must avoid starving non-preferred processes, whereas leader election prefers long-lived, stable leaders to avoid reelection overhead.

To prevent the leader from becoming a performance bottleneck, databases often **partition** data into independent replica sets (see Module 11). Instead of having a single system-wide leader, each replica set has its own leader (e.g., in **Spanner**).

---

## Bully Algorithm

The **bully algorithm** [MOLINA82] uses process ranks to identify the new leader. Each process is assigned a unique rank (or identifier). During an election, the active process with the highest rank becomes the leader. 

The algorithm is named "bully" because the highest-ranked node "bullies" lower-ranked nodes into accepting its leadership. It is also known as a monarchial leader election.

### The Bully Election Workflow
An election is triggered when a process notices that no leader is active (during initialization) or when the previous leader stops responding to requests. The election proceeds in three steps: $ ^{1} $

1.  **Propose**: A process sends an `Election` message to all processes with higher ranks.
2.  **Wait**: The process waits for responses from higher-ranked nodes. 
    *   If no higher-ranked process responds, the process assumes it is the highest-ranked active node and proceeds to step 3.
    *   If higher-ranked processes respond (sending an `Alive` message), the initiating process steps aside and lets those higher-ranked nodes finish the election.
3.  **Coordinate**: The highest-ranked active process broadcasts an `Elected` message to all lower-ranked processes, declaring itself the new leader.

> ### 💡 Beginner's Corner: Rank-Based Suppression & Reelection Loops
> * **What it is**: The Bully algorithm is a rank-based leader election protocol where each node is assigned a unique static rank. A reelection loop (or flapping) is a failure state where an unstable, high-ranked node repeatedly joins and leaves the cluster, triggering continuous elections and preventing the database from serving requests.
> * **Why it exists & What problem it solves**: To elect a leader without complex consensus, we can assign static priorities (ranks) to nodes. The node with the highest rank always takes precedence. Lower-ranked nodes automatically defer to higher-ranked ones, avoiding negotiation overhead. However, this static priority creates a severe vulnerability: if the highest-ranked node is faulty (e.g., suffering from periodic out-of-memory crashes or flapping network links), it will continuously disrupt the cluster.
> * **Underlying Mechanism**:
>   * **Rank Suppression**: When a node triggers an election, it sends an `Election` message only to nodes with higher ranks. If a higher node receives it, it replies with an `Alive` message, which *suppresses* the lower-ranked node from declaring itself leader. The higher node then starts its own election.
>   * **Reelection Loop**: If Node 6 (highest rank) is unstable, it crashes. The remaining nodes elect Node 5. Node 6 then recovers, boots up, and immediately broadcasts an `Election` message. Node 5 receives it and is forced to step down because of Node 6's higher rank. Node 6 declares itself leader, but immediately crashes again. The cluster must start another election. This cycle repeats indefinitely. Modern systems solve this by incorporating *liveness quality metrics* (like uptime history or network latency) into the ranking, rather than relying on static identifiers.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//073c39ea-5070-4220-a4fb-17d17d48fb58/markdown_4/imgs/img_in_image_box_156_162_362_364.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A22%3A05Z%2F-1%2F%2F4c71c4bc06f4f7b66500517b175fb89c41039c48d3ffcb305d3a3681bfd5ce97" alt="Image" width="17%" /></div>

<div style="text-align: center;"><div style="text-align: center;">a) Process 3 notices the previous leader 6 has crashed and sends Election messages to higher-ranked nodes (4 and 5).</div> </div>

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//073c39ea-5070-4220-a4fb-17d17d48fb58/markdown_4/imgs/img_in_image_box_381_188_437_328.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A22%3A05Z%2F-1%2F%2F9cc95e1cec1923380aec4592f984954ab1681745cb59d1c3dd555f5b6b0633fc" alt="Image" width="4%" /></div>

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//073c39ea-5070-4220-a4fb-17d17d48fb58/markdown_4/imgs/img_in_image_box_455_160_588_360.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A22%3A05Z%2F-1%2F%2Fdd89a80fd40e496091c90920d50d0ae2850d0056121583ca31a18ef8187ceffc" alt="Image" width="11%" /></div>

<div style="text-align: center;"><div style="text-align: center;">b) Processes 4 and 5 respond with Alive, since they have higher ranks than 3.</div> </div>

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//073c39ea-5070-4220-a4fb-17d17d48fb58/markdown_4/imgs/img_in_image_box_606_190_662_328.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A22%3A05Z%2F-1%2F%2Fd022aa5e5bc401ee557fb2026602870c96c2fc94e09fafb81814ae75a2d67dab" alt="Image" width="4%" /></div>

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//073c39ea-5070-4220-a4fb-17d17d48fb58/markdown_4/imgs/img_in_image_box_679_161_814_361.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A22%3A05Z%2F-1%2F%2F48f0f37b00726505ef52dfd03489ea184e9fff4fc10e6e9e3c86e86a1f93c0b5" alt="Image" width="11%" /></div>

<div style="text-align: center;"><div style="text-align: center;">c) Process 3 steps aside, notifying the highest responder (5) to take over the election.</div> </div>

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//073c39ea-5070-4220-a4fb-17d17d48fb58/markdown_4/imgs/img_in_image_box_834_160_1037_361.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A22%3A05Z%2F-1%2F%2F821e9dd345f5c1ae103f6da052ba33ec1dda94f586bf8a1caed20f28c72f89a4" alt="Image" width="17%" /></div>

<div style="text-align: center;"><div style="text-align: center;">d) Process 5 is elected as the new leader and broadcasts Elected messages to all lower-ranked processes.</div> </div>

<div style="text-align: center;"><div style="text-align: center;">Figure 10-1. Bully algorithm: previous leader (6) fails and process 3 starts the new election</div> </div>

### Shortcomings of the Bully Algorithm

*   **Split-Brain Vulnerability**: If a network partition isolates subsets of nodes, each subset will run an independent election and elect its own highest-ranked node as leader, violating the safety guarantee.
*   **Reelection Loop**: The algorithm strongly favors high-ranked nodes. If a high-ranked node is unstable (continually crashing and recovering), it will repeatedly trigger new election rounds, putting the cluster into a permanent reelection loop. This can be resolved by incorporating node quality metrics into the ranking.

---

## Bully Algorithm Optimizations

### Next-In-Line Failover

To shorten reelection windows, the **Next-in-Line Failover** optimization [GHOLIPOUR09] uses a backup list:

1.  The active leader publishes a prioritized list of fallback processes (its highest-ranked active successors).
2.  When a process detects a leader crash, it contacts the highest-ranked alternative on the failover list.
3.  If that alternative is online, it immediately assumes leadership and notifies the cluster, bypassing a full election.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//a790001c-7ead-4f73-a40f-a691500f670e/markdown_0/imgs/img_in_image_box_136_1085_401_1344.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A22%3A01Z%2F-1%2F%2F3a72d41d0024ef8a586dfb28a5400fa7f3f20e270893c8c35775816fee82c404" alt="Image" width="22%" /></div>

<div style="text-align: center;"><div style="text-align: center;">a) Leader 6 (with alternatives {5, 4}) crashes. Process 3 notices the failure and contacts the highest alternative (5).</div> </div>

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//a790001c-7ead-4f73-a40f-a691500f670e/markdown_0/imgs/img_in_image_box_427_1126_498_1311.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A22%3A02Z%2F-1%2F%2Fc15b055a33192a6db032a6531396abd79a95d37cbfd7ee37a889d2cfcf17dcd0" alt="Image" width="5%" /></div>

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//a790001c-7ead-4f73-a40f-a691500f670e/markdown_0/imgs/img_in_image_box_524_1086_693_1343.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A22%3A02Z%2F-1%2F%2F9f1d34e4063151999685ae57af75364b85926d9f1ba0d6f96dba6c8c7d5689b8" alt="Image" width="14%" /></div>

<div style="text-align: center;"><div style="text-align: center;">b) Process 5 responds to 3 that it is alive, stopping 3 from contacting lower-ranked nodes on the list.</div> </div>

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//a790001c-7ead-4f73-a40f-a691500f670e/markdown_0/imgs/img_in_image_box_733_1084_1000_1351.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A22%3A02Z%2F-1%2F%2F477c82951acb48efed4954495b8c36050d73d14444463c28beb3b80afbc4d5c8" alt="Image" width="22%" /></div>

<div style="text-align: center;"><div style="text-align: center;">{4,3}</div> </div>

<div style="text-align: center;"><div style="text-align: center;">c) Process 5 notifies the rest of the nodes that it is the new leader.</div> </div>

<div style="text-align: center;"><div style="text-align: center;">Figure 10-2. Bully algorithm with failover: previous leader (6) fails and process 3 starts the new election by contacting the highest-ranked alternative</div> </div>

---

### Candidate/Ordinary Optimization

To reduce total message overhead, nodes can be split into two subsets: **candidates** (nodes that can become leaders) and **ordinary nodes** (nodes that only follow) [MURSHED12].

*   **Workflow**: An ordinary node initiates an election by contacting only the candidate nodes. It collects responses, selects the highest-ranked active candidate as the new leader, and broadcasts the result to all other nodes.
*   **Tie-breaking**: To prevent multiple nodes from initiating concurrent elections, the algorithm uses a process-specific delay variable $\delta$. A node waits for $\delta$ periods before initiating an election. Higher-ranked nodes have smaller $\delta$ values, ensuring they start elections first and suppress lower-ranked nodes.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//a790001c-7ead-4f73-a40f-a691500f670e/markdown_2/imgs/img_in_image_box_140_1161_411_1464.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A22%3A03Z%2F-1%2F%2F264c705a0a4bbbe556024d98987f4aaa5ff54a3865a4f7fc81b547f76c6179b6" alt="Image" width="22%" /></div>

<div style="text-align: center;"><div style="text-align: center;">a) Process 4 (ordinary) notices the failure of leader 6 and contacts the candidate set.</div> </div>

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//a790001c-7ead-4f73-a40f-a691500f670e/markdown_2/imgs/img_in_image_box_458_1161_730_1468.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A22%3A03Z%2F-1%2F%2Fbc72462be69a4e90d84b9891852ba253030c1bd1567b2f2082b370a234d05f88" alt="Image" width="22%" /></div>

<div style="text-align: center;"><div style="text-align: center;">b) Candidate processes respond to 4 to confirm they are online.</div> </div>

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//a790001c-7ead-4f73-a40f-a691500f670e/markdown_2/imgs/img_in_image_box_778_1162_1050_1468.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A22%3A03Z%2F-1%2F%2Fa838026f6896900df9060689b906ef34b00f353fe2b0d702c9aad40be46589c5" alt="Image" width="22%" /></div>

<div style="text-align: center;"><div style="text-align: center;">c) Process 4 selects the highest candidate (2) and declares it the new leader.</div> </div>

<div style="text-align: center;"><div style="text-align: center;">Figure 10-3. Candidate/ordinary modification of the bully algorithm: previous leader (6) fails and process 4 starts the new election</div> </div>

---

## Invitation Algorithm

The **invitation algorithm** allows processes to build groups dynamically and merge them. Unlike rank-based algorithms, it allows multiple active leaders in the cluster by design, with each independent group having its own leader.

1.  **Initial State**: Every process starts as the leader of its own single-member group.
2.  **Invitation**: Group leaders periodically contact peers outside their group, inviting them to join.
3.  **Group Merge**: 
    *   If the invited peer is also a group leader, the two leaders negotiate to merge their groups.
    *   If the invited peer is a follower, it replies with its current leader's ID, allowing the two group leaders to connect and merge their groups.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//a790001c-7ead-4f73-a40f-a691500f670e/markdown_3/imgs/img_in_image_box_142_1068_416_1249.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A22%3A03Z%2F-1%2F%2F9a15182574c0fff4b6acd994aae37411e22278e5875e0c400ec7d6211c38fd36" alt="Image" width="23%" /></div>

<div style="text-align: center;"><div style="text-align: center;">a) Processes start as single-member group leaders. Node 1 invites 2, and 3 invites 4.</div> </div>

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//a790001c-7ead-4f73-a40f-a691500f670e/markdown_3/imgs/img_in_image_box_440_1067_739_1255.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A22%3A04Z%2F-1%2F%2F6a5fe039e1746ce904bd9af6f69132af2c89ff2da05e8d5baacfd3ff646e1c0c" alt="Image" width="25%" /></div>

<div style="text-align: center;"><div style="text-align: center;">b) Two groups form: {1, 2} led by 1, and {3, 4} led by 3. Leader 1 contacts leader 3 to initiate a merge.</div> </div>

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//a790001c-7ead-4f73-a40f-a691500f670e/markdown_3/imgs/img_in_image_box_776_1069_1048_1245.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A22%3A04Z%2F-1%2F%2F7019d8963681adf3514149087b39ae24b75913f4b392cfff7d4b7da035024f08" alt="Image" width="22%" /></div>

<div style="text-align: center;"><div style="text-align: center;">c) The groups merge. Process 1 becomes the leader of the combined group {1, 2, 3, 4}.</div> </div>

<div style="text-align: center;"><div style="text-align: center;">Figure 10-4. Invitation algorithm</div> </div>

To minimize the number of messages required during a merge, the leader of the larger group typically becomes the leader of the new combined group. This way, only the members of the smaller group need to be notified about the leader change.

---

## Ring Algorithm

In the **ring algorithm** [CHANG79], all nodes are organized in a logical ring topology. Every process is aware of its predecessor and successor in the ring.

### How It Works
1.  **Election Start**: When a node notices the leader has crashed, it starts a new election by creating an active list containing only its own ID and forwarding it to its successor.
2.  **Propagation**: 
    *   The successor appends its own ID to the active list and forwards it to the next node.
    *   If a successor is dead or unreachable, the sender skips it and attempts to contact the next node in the ring.
3.  **Completion**: The message traverses the entire ring and eventually returns to the node that initiated the election.
4.  **Selection**: The initiating node inspects the accumulated active list, selects the node with the highest rank as the new leader, and circulates a coordinator message around the ring to declare the winner.

> ### 🚶‍♂️ Step-by-Step Breakdown: The Ring Election Protocol
> 1. **Step 1 (Failure Detection)**: A node $P_i$ detects that the current leader has failed (e.g., via a timeout). It initiates an election by creating an `Election` message containing its own identifier $P_i$.
> 2. **Step 2 (Forward to Successor)**: $P_i$ sends the `Election` message to its immediate physical successor in the ring. If the successor is unresponsive, $P_i$ skips it and attempts to send to the next active successor.
> 3. **Step 3 (Accumulate and Propagate)**: When any node $P_j$ receives the `Election` message, it appends its own identifier $P_j$ to the message's list of active nodes and forwards it to its successor. This ensures the message accumulates the IDs of all reachable nodes as it circulates.
> 4. **Step 4 (Loop Completion)**: The message continues circulating until it returns to the initiating node $P_i$. $P_i$ recognizes its own ID at the start of the list, indicating the message has completed a full circuit of the ring.
> 5. **Step 5 (Leader Selection)**: $P_i$ parses the accumulated list, selects the node with the highest rank (identifier) from the list, and marks it as the new leader.
> 6. **Step 6 (Coordinator Broadcast)**: $P_i$ constructs a `Coordinator` message declaring the new leader's identity and circulates it around the ring. Each node receives the message, updates its local leader reference, and forwards it, completing the election.
> * **Max-Value Optimization**: To reduce network bandwidth, instead of accumulating all IDs in a growing list (which makes message size $O(N)$), the `Election` message can carry only a single integer representing the maximum ID seen so far. When a node receives the message, it compares the message's value with its own ID, updates the message with its own ID if it is larger, and forwards it.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//b00b3a51-8af9-46f8-aa9b-efc415294116/markdown_0/imgs/img_in_image_box_145_1263_1039_1507.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A22%3A02Z%2F-1%2F%2Fd6d503748042c8e87a5af3c494549c36089a2e3f7cdb105bd845b50d5fd9e6a7" alt="Image" width="75%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 10-5. Ring algorithm: previous leader (6) fails and 3 starts the election process</div> </div>

> [!NOTE]
> *   **Optimization**: Instead of accumulating a list of all active IDs, nodes can collect only the single highest-ranked ID seen so far (using the commutative `max` function) to reduce message size.
> *   **Safety**: Like the Bully algorithm, if the ring gets partitioned, each isolated segment can elect its own leader, resulting in split-brain behavior.

---

## Summary

Selecting a designated leader is a highly effective way to reduce coordination overhead and improve the performance of distributed systems. Because elections are relatively infrequent, their message costs do not negatively impact long-term system performance.

*   **Split-Brain Risk**: All classical leader election algorithms are vulnerable to split-brain errors when network partitions occur. To prevent this, modern consensus algorithms require a **quorum** (a majority of active nodes) to validate an election.
*   **Leader Election as Consensus**: Electing a leader is equivalent to reaching consensus on the leader's identity. If a cluster can solve leader election, it can solve consensus on any other value [ABRAHAM13].
*   **Conflict Resolution**: Many consensus systems (like Multi-Paxos and Raft) allow multiple nodes to believe they are the leader temporarily but resolve these conflicts quickly during the replication phase by collecting quorums or comparing term numbers.
*   **Liveness and Safety Trade-off**: Permitting temporary multiple leaders is an optimization for liveness. System safety is guaranteed by resolving these conflicts during data replication before any changes are committed.

---

##### FURTHER READING

*   **Distributed Algorithms**: Lynch, Nancy and Boaz Patt-Shamir. 1993. *Distributed algorithms.* Lecture notes for 6.852. Cambridge, MA: MIT.
*   **Fundamentals of Distributed Computing**: Attiya, Hagit and Jennifer Welch. 2004. *Distributed Computing: Fundamentals, Simulations, and Advanced Topics.* USA: John Wiley & Sons.
*   **Distributed Architecture**: Tanenbaum, Andrew S. and Maarten van Steen. 2006. *Distributed Systems: Principles and Paradigms (2nd Ed.).* Upper Saddle River, NJ: Prentice-Hall.

---

##### Footnotes

1. The election steps described here represent the classical Bully algorithm and timing assumptions.
