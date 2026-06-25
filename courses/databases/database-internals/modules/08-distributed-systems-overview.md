# Part II: Distributed Systems

> "A distributed system is one in which the failure of a computer you didn't even know existed can render your own computer unusable." — *Leslie Lamport*

Without distributed systems, we would not be able to make phone calls, transfer money, or exchange information over long distances. We use distributed systems daily—often without realizing it—as any client/server application is a distributed system.

For many modern software systems, **vertical scaling** (running the same software on a bigger, faster machine with more CPU, RAM, or faster disks) is not viable. Larger machines are more expensive, harder to replace, and require special maintenance. An alternative is to **scale horizontally**: running software on multiple machines connected over the network, working together as a single logical entity.

Modern database systems use multiple nodes connected in clusters to increase storage capacity, improve performance, and enhance availability. 

### Basic Definitions

*   **Participants (Processes/Nodes/Replicas)**: The independent machines that run local state and communicate by exchanging messages over network links.
*   **Logical Clocks**: Monotonically growing counters used to order events without relying on physical time.
*   **Physical Clocks (Wall Clocks)**: Time sources bound to the physical world, accessible through the operating system.
*   **Unreliable Links**: Remote processes communicate through links that can be slow, reorder, delay, or lose messages, making it difficult to know the exact state of remote nodes.

Concurrent programming on a single machine shares many concepts with distributed programming. In fact, modern multi-core CPUs are like tiny distributed systems with links, processors, and communication protocols. However, most concurrent primitives cannot be reused directly in distributed systems because of the high cost of network communication and the unreliability of links and processes.

### Categories of Distributed Algorithms

To overcome these challenges, we use **distributed algorithms**, which define the local behavior and interactions of independent nodes:

*   **Coordination**: A process supervising the actions and behavior of several workers.
*   **Cooperation**: Multiple participants relying on one another to complete their tasks.
*   **Dissemination**: Processes cooperating to spread information to all interested parties quickly and reliably.
*   **Consensus**: Multiple processes agreeing on a specific value.

---

## Module 08: Introduction and Overview

What makes distributed systems inherently different from single-node systems? In a single-threaded program, we define variables and a step-by-step execution process:

```java
int i = 1;
i += 2;
i *= 2;
```

This has a single execution history: we declare a variable, increment it by two, multiply it by two, and get a predictable result: `6`. But what if we have two concurrent threads with read and write access to a shared variable `x`?

### Concurrent Execution

As soon as multiple execution threads access a variable concurrently, the exact outcome becomes unpredictable unless they are synchronized. Instead of a single possible outcome, we end up with four different interleavings, as shown in Figure 8-1. $ ^{1} $

<table border=1 style='margin: auto; word-wrap: break-word;'><tr><td style='text-align: center; word-wrap: break-word;'>Adder</td></tr><tr><td style='text-align: center; word-wrap: break-word;'>read(x)→1</td></tr><tr><td style='text-align: center; word-wrap: break-word;'></td></tr><tr><td style='text-align: center; word-wrap: break-word;'>write(x,1+2)</td></tr><tr><td style='text-align: center; word-wrap: break-word;'></td></tr></table>

<div style="text-align: center;"><div style="text-align: center;">Multiplier</div> </div>

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//29983066-bbd9-408b-a4a6-fa9741c93fa2/markdown_3/imgs/img_in_image_box_371_471_567_660.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A22%3A02Z%2F-1%2F%2F05eaa0c73601f5c516ddbc7050ff4a29794280516ab5b4aa80e73071f3306d40" alt="Image" width="16%" /></div>

a) Result: x = 2

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//29983066-bbd9-408b-a4a6-fa9741c93fa2/markdown_3/imgs/img_in_image_box_621_455_820_661.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A22%3A02Z%2F-1%2F%2F0d525de7cba16d8a5be9dee3f7de7d8e63ff62bcd57f300b549b061f6d346f04" alt="Image" width="16%" /></div>

<table border=1 style='margin: auto; word-wrap: break-word;'><tr><td style='text-align: center; word-wrap: break-word;'>Multiplier</td></tr><tr><td style='text-align: center; word-wrap: break-word;'></td></tr><tr><td style='text-align: center; word-wrap: break-word;'>read(x)→1</td></tr><tr><td style='text-align: center; word-wrap: break-word;'>write(x,1*2)</td></tr><tr><td style='text-align: center; word-wrap: break-word;'></td></tr></table>

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//29983066-bbd9-408b-a4a6-fa9741c93fa2/markdown_3/imgs/img_in_image_box_141_769_340_974.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A22%3A02Z%2F-1%2F%2Fcc39bda4897cea4e5f7962cc1e5774d1cea7d72c61f77d753e912df53320c5bc" alt="Image" width="16%" /></div>

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//29983066-bbd9-408b-a4a6-fa9741c93fa2/markdown_3/imgs/img_in_image_box_369_768_568_977.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A22%3A02Z%2F-1%2F%2F9467eb1368bc2ae85a90702f89b091bcb1b4c0f62380d66698c18b92dd4c5f03" alt="Image" width="16%" /></div>

c) Result: x = 4

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//29983066-bbd9-408b-a4a6-fa9741c93fa2/markdown_3/imgs/img_in_image_box_621_769_820_980.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A22%3A03Z%2F-1%2F%2Fa0a5b5057763d22758164e033019be2fa150e7dd0eb7626f3975a6aac2e34cd2" alt="Image" width="16%" /></div>

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//29983066-bbd9-408b-a4a6-fa9741c93fa2/markdown_3/imgs/img_in_image_box_851_769_1048_975.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A22%3A03Z%2F-1%2F%2Fb0576e49ac8eb327cef6741c1540e754a580d3a253c8f28c9b0562c341a572f0" alt="Image" width="16%" /></div>

d) Result: x = 6

<div style="text-align: center;"><div style="text-align: center;">Figure 8-1. Possible interleavings of concurrent executions</div> </div>

*   **a) $x = 2$**: Both threads read the initial value `1`. The adder writes its value `3` first, but it is immediately overwritten by the multiplier's write of `2`.
*   **b) $x = 3$**: Both threads read the initial value `1`. The multiplier writes its value `2` first, but it is overwritten by the adder's write of `3`.
*   **c) $x = 4$**: The multiplier reads the initial value `1`, runs, and writes `2` before the adder starts. The adder then reads `2` and writes `4`.
*   **d) $x = 6$**: The adder reads the initial value `1`, runs, and writes `3` before the multiplier starts. The multiplier then reads `3` and writes `6`.

> ### 💡 Beginner's Corner: Thread Interleaving & The Lost Update Problem
> * **What it is**: Thread interleaving is the order in which the operating system's scheduler executes individual assembly-level instructions from multiple concurrent threads on the CPU. A lost update occurs when two concurrent threads attempt to modify a shared variable, and one thread's update overwrites the other thread's update without incorporating it.
> * **Why it exists & What problem it solves**: In single-threaded programming, execution is sequential and deterministic. In multi-threaded programming, threads share the same virtual memory space. To maximize CPU utilization, the OS scheduler can preemptively pause a thread at any instruction and run another thread. Unless we use synchronization primitives (like locks or mutexes), this arbitrary switching can split high-level operations across threads in ways that corrupt shared data.
> * **Underlying Mechanism**: At the hardware level, a high-level statement like `x += 2` is not a single atomic operation. It is compiled into three distinct CPU instructions:
>   1. **Load**: Read the value of `x` from main RAM into a CPU register.
>   2. **Modify**: Add `2` to the value in the register.
>   3. **Store**: Write the value from the register back to the memory address of `x`.
>   If two threads run this operation concurrently, Thread 1 may execute the **Load** instruction (reading `1`) and then get paused by the scheduler. Thread 2 then runs completely (Load `1`, Add `2`, Store `3`). When Thread 1 resumes, its register still holds the old value `1`. It executes Add `2` (resulting in `3`) and Store `3`. Thread 2's update is completely lost.

Concurrency is the first major problem we encounter, even before crossing a single node boundary. To restrict the number of possible outcomes and guarantee correctness, we use **consistency models**. These models describe concurrent executions and establish rules for the order in which operations can occur and become visible.

> [!NOTE]
> **Concurrent vs. Parallel**: 
> *   **Concurrent**: Two sequences of steps are both in progress, but only one is executed at any single moment (like two queues sharing one coffee machine).
> *   **Parallel**: Two sequences of steps are executed simultaneously by multiple processors (like two queues using two coffee machines) [WEIKUM01].

---

### Shared State in a Distributed System

We can try to introduce a shared memory concept to a distributed system by using a central database. However, this does not automatically solve synchronization problems.

*   **Synchrony Assumptions**: We must define how long a process should wait for a database response. Is the network fully **asynchronous**, or are there **synchronous** timing bounds? Timing bounds allow us to define timeouts and retry strategies.
*   **Uncertainty of Crashes**: If a database does not respond, we do not know if it is overloaded, slow, down, or if the network dropped the message. This requires a formal **failure model**.
*   **Fault Tolerance**: To eliminate a single point of failure, we can add a backup database. But this introduces a new challenge: how do we keep these multiple replicas of the shared state in sync?

---

### Fallacies of Distributed Computing

Assuming that network operations always succeed is dangerous. In 1994, Peter Deutsch published a list of assertions representing the most common, easily overlooked assumptions in distributed systems, known as the **"Fallacies of Distributed Computing"**:

1.  **The network is reliable**: Connections can get interrupted at any time. A message might reach the destination, but the response can get lost.
2.  **Latency is zero**: Remote calls must travel through software layers and physical media. They are never instantaneous.
3.  **Bandwidth is infinite**: Piling up huge volumes of data or message rates will saturate network capacity.
4.  **The network is secure**: Intentional or adversarial interceptions must be expected.
5.  **Topology doesn't change**: Nodes can join, leave, or fail, changing the network layout.
6.  **There is one administrator**: No single authority has complete knowledge and control over the entire network.
7.  **Transport cost is zero**: Exchanging messages adds CPU, memory, and network overhead.
8.  **The network is homogeneous**: Nodes have different hardware, operating systems, configurations, and software versions.

---

### Processing and Backpressure

We cannot assume that processing at the remote node is instantaneous. 

*   **Queuing Delay**: Delivered messages often sit in a pending queue on the remote server, waiting for their turn.
*   **Slowest Node Bottleneck**: If an operation must wait for responses from multiple parallel servers, the execution as a whole is only as fast as the slowest server.
*   **Backpressure**: When producers publish messages faster than consumers can process them, we must use backpressure to slow down the producers. Increasing queue capacity indefinitely does not solve the problem; it only increases latency.

In-memory queues help achieve:
*   **Decoupling**: Separating message receipt from processing in time.
*   **Pipelining**: Allowing different stages of requests to be processed by independent system components without blocking.
*   **Absorbing Bursts**: Smoothing out spikes in traffic, though this increases temporary queue latency.

---

### Clocks and Time

> "Time is an illusion. Lunchtime doubly so." — *Ford Prefect, The Hitchhiker's Guide to the Galaxy*

Assuming that clocks on remote machines run in perfect sync is a critical error. 
*   **Clock Drift**: Clocks on different machines drift over time due to temperature and hardware differences.
*   **Uncertainty**: Unless you use specialized high-precision time sources, you should not rely on raw physical timestamps for synchronization or transaction ordering.
*   **Monotonicity**: We must distinguish between wall-clock time (which can jump backward due to NTP adjustments) and monotonic time (which only goes forward).

For example, **Spanner** (see "Distributed Transactions with Spanner") uses a specialized TrueTime API that returns physical time with explicit uncertainty bounds to guarantee strict transaction ordering.

> ### 💡 Beginner's Corner: Clock Drift, NTP, and Spanner's TrueTime
> * **What it is**: Clock drift is the phenomenon where a computer's hardware clock gradually diverges from the actual physical time. The Network Time Protocol (NTP) is a networking protocol used to synchronize computer clocks over variable-latency networks. TrueTime is Google Spanner's distributed clock synchronization API that provides physical time with bounded uncertainty.
> * **Why it exists & What problem it solves**: Distributed databases need to order transactions globally. If Transaction B starts after Transaction A finishes, Transaction B must have a higher timestamp. In a single database, this is easy. In a globally distributed database, nodes are separated by thousands of miles. Relying on local quartz-crystal clocks is impossible because they drift due to temperature and aging (up to several seconds a day). NTP synchronizes clocks by querying atomic time servers, but network latency jitter makes perfect synchronization impossible, leaving clocks skewed by milliseconds to seconds. This clock skew can cause a database to assign a lower timestamp to a later transaction, violating consistency.
> * **Underlying Mechanism**: 
>   * **NTP Limitations**: NTP adjustments can cause the system clock to jump backward or run slow/fast, meaning local timestamps are not monotonic and cannot be trusted for transaction ordering.
>   * **TrueTime API**: To solve this, Google places GPS receivers and atomic rubidium clocks in every datacenter. These two independent time sources have different failure modes (GPS can lose signal; atomic clocks drift slowly over time). The TrueTime API does not return a single timestamp; instead, it returns an interval $[t_{\text{earliest}}, t_{\text{latest}}]$, where the width of the interval $2\epsilon$ represents the maximum possible clock uncertainty (typically under 7 milliseconds).
>   * **Commit Wait**: To guarantee that Transaction B (which starts after Transaction A commits) gets a higher timestamp, Spanner assigns Transaction A a commit timestamp $s = t_{\text{latest}}$ from its current TrueTime interval. It then forces Transaction A to wait (delaying its commit) until physical time has definitely passed $s$ (i.e., until TrueTime's $t_{\text{earliest}} > s$). This *commit wait* ensures that any subsequent transaction globally is guaranteed to receive a TrueTime interval where $t_{\text{earliest}}$ is greater than $s$, enforcing absolute physical ordering without communication between datacenters.

---

### State Consistency

Distributed systems do not always guarantee strict, immediate consistency. 
*   **Eventual Consistency**: Replicas are allowed to diverge temporarily, relying on conflict resolution and read-time repairs to bring them back in sync later.
*   **Schema Propagation**: If database schema updates propagate to servers at different times, a read during this window can cause data corruption due to mismatched serialization formats.
*   **Routing Views**: If nodes have divergent views of the cluster layout, writes or reads might route to the wrong node, leading to data loss or misplaced records.

---

### Local vs. Remote Execution

Hiding network calls behind a local API interface (e.g., RPC) is dangerous [WALDO96]. 
*   **Latency Differences**: A remote call is orders of magnitude slower than a local function call.
*   **Failure Semantics**: Local calls fail only if the process runs out of memory or crashes. Remote calls can fail due to network drops, remote crashes, timeouts, or congestion.
*   **API Design**: Interfaces must expose parameters for timeouts, retries, and paging to allow developers to manage the realities of remote execution.

---

### Fault Tolerance and Failure Handling

Long-running systems will inevitably experience failures. Nodes can crash due to bugs, hardware faults, or OS out-of-memory (OOM) killers [KERRISK10].

*   **Heartbeats**: Nodes exchange periodic messages to monitor each other's status.
*   **Failure Detectors**: Algorithms that analyze heartbeat patterns to form a hypothesis about whether a remote node is alive or dead.
*   **Network Partitions**: A state where two or more groups of healthy nodes cannot communicate due to link failures, which can lead to conflicting writes if both groups continue to accept updates independently.

> [!TIP]
> **Chaos Engineering**: The best way to design a fault-tolerant system is to test it under failure. Tools like **Toxiproxy** (simulates network latency and bandwidth limits), **Chaos Monkey** (randomly shuts down production services), and **CharybdeFS** (simulates filesystem and hardware errors) are essential for validating system behavior under stress.

---

### Cascading Failures

Failures are rarely isolated. A single node crashing under heavy load forces its workload onto the remaining nodes, making it more likely that they will fail too, propagating a **cascading failure** across the cluster.

To protect against cascading failures, we use:
*   **Circuit Breakers**: Monitor failure rates for a remote service. If failures cross a threshold, the breaker "trips," immediately failing subsequent calls locally to give the remote service time to recover.
*   **Exponential Backoff**: Instead of retrying failed requests immediately, clients wait for an exponentially increasing delay between attempts, preventing them from overwhelming an already struggling server.
*   **Jitter**: Adds a random time offset to the backoff delay to prevent all retrying clients from waking up and hitting the server at the exact same moment.
*   **Validation & Checksums**: Verifies data integrity at each step to prevent corrupted writes from replicating and destroying healthy data elsewhere.

---

## Distributed Systems Abstractions

### Links

Since physical networks are unreliable, we build abstract communication protocols (links) to describe the exact guarantees they provide.

#### Fair-Loss Link
The simplest, most basic communication channel.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//21471b2e-7c7e-418c-a43e-7d125f1064c5/markdown_4/imgs/img_in_image_box_142_932_1047_1069.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A22%3A03Z%2F-1%2F%2Fdb38b6519fce36b84fa6eabcca61f2f44b6dd27c15e80c647620e2db73202837" alt="Image" width="75%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 8-2. Simplest, unreliable form of communication</div> </div>

*   **Fair Loss**: If the sender keeps sending a message infinitely, a correct recipient will eventually receive it at least once. $ ^{3} $
*   **Finite Duplication**: Messages are not duplicated infinitely.
*   **No Creation**: The link never delivers a message that was not sent.
*   *Real-World Analogy*: UDP.

#### Stubborn Link
Built on top of a fair-loss link by adding infinite retries.
*   **Retransmission**: The sender keeps resending the message indefinitely at regular intervals.
*   **Guarantee**: The message is guaranteed to eventually reach the recipient, but it will result in massive message duplication.

#### Perfect Link
Combines stubborn links with acknowledgments and deduplication to offer reliable, ordered, and duplicate-free communication.

*   **Reliable Delivery**: Every message sent is eventually delivered exactly once.
*   **No Duplication**: No message is delivered more than once.
*   **No Creation**: Only sent messages are delivered.
*   *Real-World Analogy*: TCP (within a single session).

---

### Message Acknowledgments and Retransmits

To convert a stubborn link into a practical protocol, we use bidirectional communication and **acknowledgments (ACKs)**:

1.  The sender marks each message with a unique, monotonically increasing **sequence number** $ M(n) $.
2.  Upon receipt, the recipient replies with an acknowledgment $ ACK(n) $.
3.  If the sender does not receive $ ACK(n) $ within a timeout $ T $, it retransmits the message.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//cee8cc29-46a4-4213-a0f4-fd395e7a1538/markdown_1/imgs/img_in_image_box_141_162_1047_300.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A22%3A02Z%2F-1%2F%2F88c5d0b52b26d72bc3823e78fa816a4bb0158ef51b77f769b810df85cc0ac34e" alt="Image" width="76%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 8-3. Sending a message with an acknowledgment</div> </div>

Retransmissions can cause message duplication if the original ACK was dropped or delayed. Therefore, operations must be **idempotent**, or the receiver must perform **deduplication**.

> [!NOTE]
> An **idempotent** operation is one that can be executed multiple times without producing additional side effects (e.g., setting a value to `5` is idempotent; incrementing a value by `1` is not).

> ### 💡 Beginner's Corner: Deduplication & Idempotent Operations
> * **What it is**: Deduplication is the process of detecting and discarding duplicate packets or messages at the receiver. An idempotent operation is one that can be applied multiple times without changing the result beyond the initial application.
> * **Why it exists & What problem it solves**: In an unreliable network, the only way a sender can guarantee that a message is delivered is to keep retrying until it receives an acknowledgment (ACK). However, if the message was successfully received and processed by the recipient, but the return ACK packet was lost or delayed, the sender's retry will result in a duplicate message arriving at the recipient. If the message represents a database mutation (like "add $100 to balance"), executing it twice will corrupt the state. Deduplication and idempotency prevent this.
> * **Underlying Mechanism**: 
>   * **Deduplication**: The receiver maintains a history of processed message sequence numbers. When a message arrives, the receiver checks its sequence number against this history. If it has already been processed, the receiver immediately sends an ACK back to the sender but does not pass the message to the application layer, safely filtering out the duplicate.
>   * **Idempotency**: An operation is mathematically defined as idempotent if $f(f(x)) = f(x)$. In database API design, we prefer idempotent commands. For example, the command `SetBalance(150)` is idempotent: if it is executed five times, the balance remains $150. In contrast, the command `IncrementBalance(50)` is not idempotent: executing it five times increases the balance by $250. Designing APIs around idempotent state mutations makes them resilient to network retries without requiring infinite deduplication buffers.

### Message Ordering & Deduplication

To put out-of-order messages back in their original sequence, the receiver tracks two pointers:
*   $ n_{\text{consecutive}} $: The highest sequence number up to which all messages have been received.
*   $ n_{\text{processed}} $: The highest sequence number up to which messages have been processed and passed to the application.

If a message arrives with a gap (e.g., receiving sequence `5` when the last consecutive was `3`), it is placed in a **reordering buffer** until the missing sequence (`4`) arrives. Discarding duplicate messages with sequence numbers $\le n_{\text{processed}}$ guarantees duplicate-free processing.

---

### Exactly-Once Delivery

> "There are only two hard problems in distributed systems: 
> 2. Exactly-once delivery 
> 1. Guaranteed order of messages 
> 2. Exactly-once delivery." 
> — *Mathias Verraes*

Is exactly-once delivery truly possible?
*   **At-Least-Once**: The sender retries until acknowledged. Duplicates are possible.
*   **At-Most-Once**: The sender sends once and never retries. Data loss is possible.
*   **Exactly-Once**: It is physically impossible to guarantee that a packet travels over an unreliable link *exactly once* without ever being retransmitted. 

However, we can achieve **exactly-once processing** by combining at-least-once delivery with receiver-side deduplication. From the application's perspective, the message appears to be delivered and processed exactly once.

---

## Two Generals' Problem

The **Two Generals' Problem** is a famous thought experiment proving that it is impossible for two parties to achieve absolute agreement over an unreliable link in a fully asynchronous system.

Imagine two generals leading armies on opposite sides of a fortified enemy city. They can only capture the city if they attack simultaneously. If only one attacks, they will be defeated.

```
[General A] ----- (Messenger) -----> [Enemy City] <----- (Messenger) ----- [General B]
```

1.  General A sends a messenger to General B: *"Let's attack at 9:00 AM."*
2.  General A cannot attack yet because he does not know if the messenger was captured.
3.  General B receives the message and sends an acknowledgment: *"Agreed. We will attack at 9:00 AM."*
4.  General B cannot attack yet because he does not know if his acknowledgment reached General A. If A didn't get it, A won't attack, leaving B to be defeated.
5.  To reassure B, General A must send a second-order acknowledgment: *"I received your agreement."*
6.  But now General A is unsure if B received this confirmation...

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//bcde9ad7-9052-4e5d-9bc0-31097812d46e/markdown_2/imgs/img_in_image_box_140_155_1050_555.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A22%3A02Z%2F-1%2F%2Ff6d9264b51288e4f5ebd01283fecf5a78ebadee0daf6e6f3d35afd49de65e3ca" alt="Image" width="76%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 8-4. Two Generals' Problem illustrated</div> </div>

No matter how many acknowledgments they send, they will always be one confirmation away from absolute certainty. In a fully asynchronous environment with unreliable links, **perfect coordination is impossible**.

---

## FLP Impossibility

The **FLP Impossibility** theorem [FISCHER85] is a foundational result in distributed systems. It states that:

> **Theorem**: In a fully asynchronous system, no deterministic consensus protocol can guarantee agreement in the presence of even a single unannounced process crash.

For a consensus protocol to be correct, it must guarantee three properties:
1.  **Agreement**: Every non-faulty process must decide on the same value.
2.  **Validity**: The decided value must have been proposed by at least one process.
3.  **Termination**: Every non-faulty process must eventually reach a decision state.

Because an asynchronous system has no physical clocks or timeouts, it is impossible to distinguish between a process that has crashed and one that is simply running extremely slowly. The theorem proves that any protocol guaranteeing agreement and validity cannot guarantee termination in all cases if a node can crash.

In practice, we bypass FLP Impossibility by introducing **partial synchrony** (timeouts and clocks) to detect failures, which allows us to build reliable, practical consensus protocols (like Paxos and Raft).

> ### 💡 Beginner's Corner: Mathematical Proofs of Agreement Limits
> * **What it is**: The Two Generals' Problem and the FLP Impossibility theorem are mathematical proofs that define the absolute physical limits of consensus and coordination in distributed systems.
> * **Why it exists & What problem it solves**: Beginners often assume that with sophisticated enough software, we can build a distributed system that is 100% reliable, fast, and always in sync. These proofs mathematically demonstrate that this is impossible. They force engineers to make explicit trade-offs rather than searching for non-existent perfect solutions.
> * **Underlying Mechanism**:
>   * **Two Generals' Proof (Unreliable Links)**: Suppose General A sends a message $M_1$ proposing an attack. To be sure General B received it, A requires an ACK $M_2$. But B now requires an ACK $M_3$ to be sure A received $M_2$ (otherwise B will not attack). A then requires $M_4$ to confirm receipt of $M_3$. Because any message can be dropped by the network, the last sender in the chain can never be sure their message arrived. Since some finite number of messages $N$ must be sent to reach agreement, the $N$-th message can always be lost, meaning the $N$-th general will never have certainty. Thus, perfect consensus over an unreliable link is mathematically impossible.
>   * **FLP Impossibility Proof (Asynchronous System, Node Crashes)**: A consensus protocol must satisfy three properties: Agreement (everyone decides the same), Validity (decisions match proposals), and Termination (everyone eventually decides). In a fully asynchronous system, there are no clocks, and network delays are unbounded. If Node 1 stops responding, Node 2 cannot distinguish between two scenarios: (A) Node 1 has crashed, or (B) Node 1 is alive but the network is extremely slow. If the protocol guarantees *termination*, Node 2 must eventually make a decision without Node 1. However, if Node 1 was merely slow and later wakes up, it might make a conflicting decision, violating *agreement*. If the protocol guarantees *agreement*, Node 2 must wait indefinitely, violating *termination*. Therefore, no deterministic consensus protocol can guarantee all three properties if even a single node can crash.

---

## System Synchrony

Distributed systems are analyzed under three primary timing models:

| Synchrony Model | Description | Guarantees |
| :--- | :--- | :--- |
| **Synchronous** | Node processing speeds, message delivery latencies, and clock drifts have strict, known upper bounds. | Timeouts are 100% reliable for detecting node crashes. |
| **Asynchronous** | No timing assumptions are made. Node speeds and network latencies can be arbitrarily slow. | Crash detection is impossible. Consensus cannot be guaranteed in bounded time (FLP). |
| **Partially Synchronous** | The system behaves asynchronously most of the time but exhibits synchronous bounds during stable periods [DWORK88]. | Most practical consensus and failure detection protocols are designed for this model. |

---

## Failure Models

To design robust distributed algorithms, we must define a **failure model** that specifies exactly how nodes can fail:

```
Crash-Stop ---> Crash-Recovery ---> Omission ---> Arbitrary (Byzantine)
  (Simplest)                                          (Most Complex)
```

### 1. Crash Faults
*   **Crash-Stop (Fail-Stop)**: A process executes correctly until it halts. Once crashed, it remains in that state and never participates again.
*   **Crash-Recovery**: A process halts but can recover at a later point. It must use durable storage to save its state before crashing so it can safely resume execution and reconcile its state with the cluster upon recovery [SKEEN83].

### 2. Omission Faults
A process fails to send or receive messages. This can be due to:
*   Network partitions isolating groups of nodes.
*   Buffer overflows dropping incoming packets.
*   Temporary process hangs (e.g., long GC pauses) causing it to miss time windows.

### 3. Arbitrary Faults (Byzantine Faults)
A process continues running but behaves in arbitrary ways that violate the protocol (e.g., sending conflicting messages to different peers, corrupting data, or acting maliciously). 
*   Commonly handled in safety-critical systems (e.g., aerospace control) or untrusted environments (e.g., blockchains).
*   Byzantine fault-tolerant (BFT) algorithms are highly complex and require significantly more coordination.

---

## Summary

Distributed systems are inherently complex because their components are separated in space, connected by unreliable networks, and lack a shared perception of physical time.

*   **Germaneness of Concurrency**: We must use consistency models to establish an order of operations and handle concurrent state changes.
*   **Link Guarantees**: We build reliable communication abstractions (Perfect Links) on top of unreliable channels (Fair-Loss Links) using sequence numbers, acknowledgments, and retransmissions.
*   **Impossibility Proofs**: The Two Generals' Problem and FLP Impossibility show the physical limits of achieving absolute agreement over unreliable, asynchronous networks.
*   **Resiliency**: Practical systems use partial synchrony (timeouts), exponential backoff, circuit breakers, and crash-recovery state to build fault-tolerant databases that continue operating despite inevitable node and link failures.

---

##### FURTHER READING

*   **Distributed Algorithms**: Lynch, Nancy A. 1996. *Distributed Algorithms.* San Francisco: Morgan Kaufmann.
*   **Principles of Distributed Systems**: Tanenbaum et al., 2006. *Distributed Systems: Principles and Paradigms (2nd Ed).* Boston: Pearson.
*   **Reliable Distributed Programming**: Cachin et al., 2011. *Introduction to Reliable and Secure Distributed Programming (2nd Ed.).* New York: Springer.

---

##### Footnotes

1. Interleaving, where the multiplier reads before the adder, is left out for brevity, since it yields the same result as a).
2. Murphy’s Law is an adage that can be summarized as “Anything that can go wrong, will go wrong,” which was popularized and is often used as an idiom in popular culture.
3. A more precise definition is that if a correct process A sends a message to a correct process B infinitely often, it will be delivered infinitely often ([CACHIN11]).
4. Transmission Control Protocol.
