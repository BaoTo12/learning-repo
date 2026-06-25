# Module 09: Failure Detection

> "If a tree falls in a forest and no one is around to hear it, does it make a sound?" — *Unknown Author*

To react to failures appropriately, a distributed system must detect them in a timely manner. Contacting a faulty process that cannot respond increases latency and reduces overall system availability.

Detecting failures in asynchronous distributed systems (i.e., without making timing assumptions) is extremely difficult because it is impossible to distinguish between a process that has crashed and one that is simply running slowly and taking an indefinitely long time to respond (as discussed in **FLP Impossibility**).

### Terminology

*   **Dead / Failed / Crashed**: A process that has stopped executing its steps completely.
*   **Unresponsive / Faulty / Slow**: A suspected process that may be dead but is not yet confirmed.

Failures can occur on the **link level** (messages are lost or delayed) or the **process level** (a process crashes or runs slowly). Because slowness is often indistinguishable from failure, there is an inherent trade-off:
*   **False Positives**: Wrongly suspecting a live process of being dead.
*   **False Negatives**: Delaying marking an unresponsive process as dead, giving it the benefit of the doubt.

A **failure detector** is a local subsystem responsible for identifying failed or unreachable processes so they can be excluded from the algorithm, guaranteeing **liveness** while preserving **safety**.

> [!NOTE]
> **Liveness and Safety**:
> *   **Liveness**: A guarantee that a specific intended event must eventually occur (e.g., if a process fails, the failure detector must eventually detect it).
> *   **Safety**: A guarantee that unintended bad events will not occur (e.g., if a failure detector marks a process as dead, that process must indeed be dead) [LAMPORT77] [RAYNAL99] [FREILING11].

> ### 💡 Beginner's Corner: Formal Definitions of Safety and Liveness
> * **What it is**: Safety and Liveness are the two fundamental classes of properties used to define the correctness of distributed algorithms. Safety guarantees that "bad things do not happen," while Liveness guarantees that "good things eventually do happen."
> * **Why it exists & What problem it solves**: In single-node systems, correctness is often defined by simple input-output mapping. In distributed systems, where processes execute concurrently and fail independently, defining correctness is much more complex. A system that does nothing is perfectly safe (it never does anything bad) but lacks liveness. A system that randomly crashes is live (it eventually executes some steps) but lacks safety. To be correct, an algorithm must guarantee both.
> * **Underlying Mechanism**:
>   * **Safety**: A safety property specifies constraints that must never be violated at any point in time. Crucially, a violation of a safety property can be detected in a *finite* execution trace (e.g., if a system elects two leaders at time $t=5$, safety is permanently violated, and no future action can undo this). Examples include: "no two nodes commit different values for the same transaction" (consensus agreement) and "no data is corrupted on disk."
>   * **Liveness**: A liveness property specifies that a certain state or event must eventually occur. Crucially, a liveness property *cannot* be violated in any finite execution trace, because there is always infinite time in the future for the event to happen (e.g., if a node has not received a response after 10 minutes, we cannot say liveness is violated, only that we are still waiting). A violation of liveness can only be observed in an *infinite* execution trace where the event never occurs. Examples include: "a failed node is eventually detected" and "every sent message is eventually delivered."

---

## Properties of Failure Detectors

1.  **Completeness**: Every faulty member must eventually be noticed by every non-faulty member, allowing the algorithm to make progress.
2.  **Efficiency**: How fast the failure detector can identify a process failure.
3.  **Accuracy**: Whether the failure detector avoids falsely accusing live processes of being dead.

> [!IMPORTANT]
> It is provably impossible to build a failure detector that is both perfectly accurate and perfectly efficient in an asynchronous system. A more efficient detector is less accurate (producing more false positives), while a more accurate detector is less efficient (taking longer to declare a node dead). However, consensus and atomic broadcast algorithms are designed to tolerate failure detectors that make an infinite number of mistakes, as long as they eventually reach completeness [CHANDRA96].

> ### 💡 Beginner's Corner: Completeness vs. Accuracy Trade-offs
> * **What it is**: Completeness and Accuracy are the two metrics used to evaluate a failure detector. Completeness measures the detector's ability to identify actual failures. Accuracy measures the detector's ability to avoid false accusations.
> * **Why it exists & What problem it solves**: In a distributed database, if a node crashes, we must detect it and stop routing requests to it to prevent client timeouts (liveness). At the same time, if we falsely suspect a healthy node of having crashed, we might trigger expensive, unnecessary data replication and re-balancing processes (accuracy).
> * **Underlying Mechanism**:
>   * **Completeness**: Classifiably divided into *Strong Completeness* (every crashed process is eventually suspected by all correct processes) and *Weak Completeness* (every crashed process is suspected by at least one correct process).
>   * **Accuracy**: Divided into *Strong Accuracy* (no correct process is ever suspected by any correct process) and *Weak Accuracy* (at least one correct process is never suspected by any correct process).
>   * **The Impossibility**: In an asynchronous network, there is no upper bound on message propagation delay. If a failure detector ping times out, it is impossible to know if the target node has crashed (completeness) or if the network is merely slow (accuracy). If the detector waits longer to be sure (increasing accuracy), it delays detection (reducing efficiency). If it suspects the node quickly (increasing efficiency), it increases the rate of false suspicions (reducing accuracy). Practical systems accept *Weak Accuracy* (allowing temporary false suspicions) to guarantee *Strong Completeness* (ensuring all crashes are eventually handled).

---

## Heartbeats and Pings

Many distributed systems implement failure detectors using heartbeats or pings, assuming the absence of Byzantine failures (nodes do not lie about their state or their neighbors' states).

*   **Pings**: A process actively sends a query to a remote process and expects a response within a specified timeout.
*   **Heartbeats**: A process periodically broadcasts a message to its peers to notify them that it is still running.

Each process maintains a membership list (alive, dead, and suspected nodes) and updates it with the last response time. If a node fails to respond within a timeout window, it is marked as suspected.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//794b1f35-38f3-499f-9d44-fcc9c1bb7268/markdown_0/imgs/img_in_image_box_137_985_1048_1100.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A22%3A02Z%2F-1%2F%2F1b1cf747d5d182c2d455fcb087634b45a21cde29e4aaa549ebb21249b281b21d" alt="Image" width="76%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 9-1. Pings for failure detection: normal functioning, no message delays</div> </div>

If network latency spikes, acknowledgments might arrive late, causing a healthy but slow process to be falsely suspected as down:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//794b1f35-38f3-499f-9d44-fcc9c1bb7268/markdown_0/imgs/img_in_image_box_137_1294_1047_1415.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A22%3A02Z%2F-1%2F%2F5175c58f26a87a9c077d29a44ab008ebe698e8d36de73e52fe22a91e2a7e71be" alt="Image" width="76%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 9-2. Pings for failure detection: responses are delayed, coming after the next message is sent</div> </div>

---

### Timeout-Free Failure Detector

Some algorithms avoid timeouts entirely to operate under purely asynchronous assumptions. One such algorithm is the **Heartbeat Failure Detector** [AGUILERA97]:

*   **Assumptions**: Any two correct processes are connected by a *fair path* containing only *fair links* (if a message is sent infinitely often, it is eventually received infinitely often).
*   **Workflow**:
    1.  Each process maintains a list of neighbors and associated counters.
    2.  Nodes periodically broadcast heartbeat messages containing the path the heartbeat has traveled so far.
    3.  When a node receives a heartbeat, it increments the counters for all participants listed in the path.
    4.  It then appends itself to the path and forwards the heartbeat to any neighbors not yet in the path.
    5.  Propagation stops once all known processes are in the path.

Because heartbeats are routed through multiple paths, we can correctly identify an unreachable node as alive even if the direct link to it is broken, as long as it can communicate through a neighbor. The challenge lies in selecting a counter threshold that avoids false suspects.

---

### Outsourced Heartbeats (SWIM)

The **Scalable Weakly Consistent Infection-style Process Group Membership Protocol (SWIM)** [GUPTA01] uses **outsourced heartbeats** to distribute the responsibility of failure detection. It only requires nodes to be aware of a subset of connected peers rather than the entire network.

#### The SWIM Workflow
1.  Node $P_1$ sends a direct ping to $P_2$.
2.  If $P_2$ does not respond within a timeout, $P_1$ does not immediately declare it dead. Instead, it "outsources" the check by selecting a few random members ($P_3$ and $P_4$).
3.  These helper nodes attempt to ping $P_2$ directly.
4.  If $P_2$ responds to any of the helper nodes, they forward the acknowledgment back to $P_1$.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//794b1f35-38f3-499f-9d44-fcc9c1bb7268/markdown_3/imgs/img_in_chart_box_137_733_1045_979.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A22%3A03Z%2F-1%2F%2Fe9839ac82f787de576ced619f54e19ff56cb3442746c0923b6e27846cb0d4fa8" alt="Image" width="76%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 9-3. “Outsourcing” heartbeats</div> </div>

This approach accounts for both direct and indirect reachability, reducing false positives caused by localized link failures (e.g., if only the link between $P_1$ and $P_2$ is broken, but $P_2$ is otherwise healthy and reachable by the rest of the cluster).

> ### 🚶‍♂️ Step-by-Step Breakdown: SWIM Outsourced Heartbeats
> 1. **Step 1 (Direct Ping)**: At the start of a protocol period, Node $P_1$ selects a target node $P_2$ from its membership list and sends a direct `ping` message.
> 2. **Step 2 (Timeout Trigger)**: $P_1$ waits for a local timeout period. If $P_1$ receives a direct acknowledgment (`ack`) from $P_2$, the check succeeds, and the period ends. If the timeout expires without a response, $P_1$ does not declare $P_2$ dead; instead, it initiates an outsourced check.
> 3. **Step 3 (Select Helpers)**: $P_1$ randomly selects $K$ helper nodes (e.g., $P_3$ and $P_4$) from its membership list. It sends an indirect ping request `ping-req(P2)` to these helpers.
> 4. **Step 4 (Indirect Pings)**: Upon receiving the `ping-req(P2)` message, each helper node ($P_3$ and $P_4$) immediately sends a direct `ping` message to $P_2$ over their own independent network links.
> 5. **Step 5 (Forward Acknowledgment)**: If $P_2$ is healthy but its direct link to $P_1$ was broken, $P_2$ will respond to the helpers. If a helper (e.g., $P_3$) receives an `ack` from $P_2$, it immediately forwards a success message back to $P_1$.
> 6. **Step 6 (Resolution)**: 
>    * **If $P_1$ receives an indirect ACK**: $P_1$ marks $P_2$ as healthy. The check succeeds, avoiding a false positive.
>    * **If the second timeout expires**: If $P_1$ receives no indirect ACKs from any helper, it transitionally marks $P_2$ as `suspected`. If $P_2$ does not refute this suspicion within a configured grace period, it is declared `dead` and gossiped to the cluster.

---

## Phi-Accrual Failure Detector

Instead of treating node failure as a binary state (up or down), the **Phi-Accrual ($\phi$-accrual) Failure Detector** [HAYASHIBARA04] uses a continuous scale to capture the probability that a monitored process has crashed.

### How It Works
*   The detector maintains a sliding window of the arrival times of the most recent heartbeats.
*   This historical data is used to estimate the probability distribution of the next heartbeat's arrival time.
*   The detector compares the actual elapsed time since the last heartbeat with this distribution to compute a suspicion level $\phi$:
    $$\phi = -\log_{10}(P_{\text{later}}(t - t_{\text{last}}))$$
    Where $P_{\text{later}}(t - t_{\text{last}})$ is the probability that a heartbeat would arrive more than $t - t_{\text{last}}$ periods after the previous one.
*   If $\phi$ exceeds a configurable threshold (e.g., $\phi = 8$ or $\phi = 12$), the node is marked as down.

### Subsystem Architecture

```
[ Monitoring ] ---> [ Interpretation ] ---> [ Action ]
```

1.  **Monitoring**: Collects heartbeat arrival times and stores them in a sliding window, discarding the oldest data points.
2.  **Interpretation**: Estimates the mean and variance of the arrivals (assuming a normal distribution) to compute the probability of a crash ($\phi$).
3.  **Action**: Triggers a callback (e.g., marking the node as dead, initiating replica recovery) when the threshold is crossed.

Because it continuously adapts to changing network latencies, the $\phi$-accrual failure detector is highly resilient to network spikes and is widely used in databases like Apache Cassandra and frameworks like Akka.

> ### 💡 Beginner's Corner: Phi-Accrual Mathematical Mechanics
> * **What it is**: The Phi-Accrual ($\phi$-accrual) failure detector is a probabilistic failure detector that outputs a continuous suspicion level $\phi$ representing the likelihood that a monitored process has crashed, rather than a binary up/down state.
> * **Why it exists & What problem it solves**: Standard failure detectors use static timeouts (e.g., if no heartbeat is received in 5 seconds, mark as dead). However, network conditions fluctuate: a 5-second delay might be normal during a network spike, leading to a false positive, while a 10-second timeout delays crash detection during stable periods. The $\phi$-accrual detector solves this by dynamically adapting to the current network latency distribution, using historical heartbeat intervals to calculate the probability of failure.
> * **Underlying Mechanism**:
>   * **Sliding Window**: The detector stores the last $W$ (e.g., 1000) heartbeat arrival intervals $x_i = t_i - t_{i-1}$ in a sliding window. It calculates the sample mean $\mu$ and the standard deviation $\sigma$ of these intervals.
>   * **Probability Estimation**: When the current time is $t$, the elapsed time since the last heartbeat is $t_{\text{now}} - t_{\text{last}}$. Assuming that heartbeat intervals follow a normal (Gaussian) distribution, the detector calculates the probability $P_{\text{later}}(t_{\text{now}} - t_{\text{last}})$ that a heartbeat would arrive *later* than this elapsed time using the cumulative distribution function (CDF):
>     $$P_{\text{later}}(t) = 1 - \Phi(t) = \int_{t}^{\infty} \frac{1}{\sqrt{2\pi}\sigma} e^{-\frac{(x-\mu)^2}{2\sigma^2}} dx$$
>   * **Suspicion Level ($\phi$)**: The detector computes $\phi$ as:
>     $$\phi = -\log_{10}(P_{\text{later}}(t - t_{\text{last}}))$$
>     This logarithmic scale scales exponentially:
>     * $\phi = 1$: The probability that the heartbeat is merely delayed is $10^{-1} = 0.1$ ($10\%$).
>     * $\phi = 2$: The probability is $10^{-2} = 0.01$ ($1\%$).
>     * $\phi = 8$: The probability is $10^{-8} = 0.0000001\%$, indicating a near-certain crash.
>   * **Dynamic Thresholds**: Applications can tune their threshold: a replication coordinator might wait for $\phi \ge 12$ before starting expensive data recovery, while a load balancer might stop routing traffic to a node when $\phi \ge 3$ to minimize client-facing latency.

---

## Gossip and Failure Detection

A **gossip-style failure detector** [VANRENESSE98] uses gossip protocols (see Module 12) to collect and distribute node states without relying on a single node's perspective.

### Gossip Workflow
1.  Each member maintains a table of all known members, their heartbeat counters, and the local timestamp when that counter last increased.
2.  Periodically, each member increments its own heartbeat counter and sends its membership table to a randomly selected neighbor.
3.  Upon receipt, the neighbor merges the incoming table with its own, keeping the highest heartbeat counter for each node.
4.  Nodes periodically scan their tables. If a node's heartbeat counter has not increased for a defined timeout period, it is marked as failed.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//1ee3f475-694e-434e-b722-041c4bcc9d40/markdown_1/imgs/img_in_image_box_139_1278_1050_1501.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A22%3A02Z%2F-1%2F%2F69f0cfed638ba0166736c47739c90e75292b15b3cbe3db3a2daa39c6bc94e3d5" alt="Image" width="76%" /></div>

<div style="text-align: center;"><div style="text-align: center;">a) All three nodes communicate and update their timestamps normally.</div> </div>
<div style="text-align: center;"><div style="text-align: center;">b) P3 cannot communicate directly with P1, but its heartbeat can still propagate to P1 indirectly through P2.</div> </div>
<div style="text-align: center;"><div style="text-align: center;">c) P3 crashes. Since it stops sending updates, its counter freezes, and it is eventually detected as failed by all nodes.</div> </div>

By aggregating states from multiple nodes, gossip-style failure detection prevents false alarms caused by localized network partitions. Bandwidth overhead scales linearly with the number of processes in the system.

---

## Reversing the Failure Detection Problem: FUSE

Because notifying every member about an individual node failure can be expensive and fragile, the **FUSE (Failure Notification Service)** [DUNAGAN04] reverses the problem: it focuses on cheap and reliable failure propagation, converting individual failures into group failures.

FUSE arranges all active processes into a group. If a single process fails or becomes unreachable due to a partition, the failure is rapidly propagated so that the entire group is torn down:

1.  Processes in the group periodically ping each other.
2.  If a node $P_2$ crashes or becomes unreachable, its ping partner $P_4$ notices the failure.
3.  Instead of just reporting the failure, $P_4$ **intentionally stops responding** to pings from its other partners.
4.  This creates a chain reaction, propagating the failure across the entire group.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//1ee3f475-694e-434e-b722-041c4bcc9d40/markdown_3/imgs/img_in_image_box_145_1364_1041_1519.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A22%3A03Z%2F-1%2F%2F9b7772891893837f931f5d686beaaa6e520fbc0585db0c3c74ba2f168d92b6d1" alt="Image" width="75%" /></div>

<div style="text-align: center;">Figure 9-5. FUSE group failure propagation. (a) All alive. (b) P2 crashes. (c) P4 notices and stops responding. (d) The entire group detects the failure.</div>

By using the **absence of communication** (quiescence) to propagate failures, FUSE guarantees that every group member will learn about the failure. However, a single link failure can tear down the entire group, which must be accounted for in the application design.

---

## Summary

Failure detectors are a core building block for achieving reliability in distributed systems. While FLP Impossibility proves that consensus is unsolvable in a pure asynchronous system, failure detectors allow us to solve consensus by establishing practical, tunable trade-offs between completeness and accuracy.

*   **Timeout-Based Detectors**: Simple to implement but require careful tuning of intervals to balance speed and accuracy.
*   **Outsourced Heartbeats (SWIM)**: Leverage peer networks to verify node reachability indirectly, preventing false positives from local link drops.
*   **Phi-Accrual Detectors**: Dynamically adapt to changing network latencies by computing the statistical probability of a crash rather than relying on binary timeouts.
*   **Gossip-Style Detectors**: Disseminate heartbeat tables across random peers, building a robust, aggregate view of cluster membership.
*   **Notification Services (FUSE)**: Use the absence of communication to cheaply and reliably propagate localized failures as group-wide states.

---

##### FURTHER READING

*   **Unreliable Failure Detectors**: Chandra et al., 1996. *"Unreliable failure detectors for reliable distributed systems."* [Journal of the ACM](https://doi.org/10.1145/226643.226647)
*   **Failure Detector Abstraction**: Freiling et al., 2011. *"The failure detector abstraction."* [ACM Computing Surveys](https://doi.org/10.1145/1883612.1883616)
*   **Literature Review**: Phan-Ba, 2015. *"A literature review of failure detection within the context of solving the problem of distributed consensus."* [UBC Technical Report](https://www.cs.ubc.ca/~bestchai/theses/michael-phan-ba-msc-essay-2015.pdf)
