# Chapter 14. Consensus

We’ve discussed quite a few concepts in distributed systems, starting with basics, such as links and processes, and the problems of distributed computing; then going through failure models, failure detectors, and leader election; discussing consistency models; and we’re finally ready to put it all together for the pinnacle of distributed systems research: **distributed consensus**.

Consensus algorithms in distributed systems allow multiple processes to reach an agreement on a value. **FLP Impossibility** (see **FLP Impossibility**) shows that it is impossible to guarantee consensus in a completely asynchronous system in a bounded time. Even if message delivery is guaranteed, it is impossible for one process to know whether another one has crashed or is running slowly.

In Chapter 9, we discussed that there's a trade-off between failure-detector accuracy and how quickly a failure can be detected. Consensus algorithms assume an asynchronous model and guarantee safety, while an external failure detector can provide information about other processes, guaranteeing liveness [CHANDRA96]. Since failure detection is not always fully accurate, there will be situations when a consensus algorithm waits for a process failure to be detected, or when the algorithm is restarted because some process is incorrectly suspected to be faulty.

Processes have to agree on some value proposed by one of the participants, even if some of them happen to crash. A process is said to be **correct** if it hasn’t crashed and continues executing algorithm steps. Consensus is extremely useful for putting events in a particular order, and ensuring consistency among the participants. Using consensus, we can have a system where processes move from one value to the next one without losing certainty about which values the clients observe.

From a theoretical perspective, consensus algorithms have three properties:

* **Agreement**: The decision value is the same for all correct processes.
* **Validity**: The decided value was proposed by one of the processes.
* **Termination**: All correct processes eventually reach the decision.

Each one of these properties is extremely important. 

The **agreement** is embedded in the human understanding of consensus. The dictionary definition of consensus has the word “unanimity” in it. This means that upon agreement, no process is allowed to have a different opinion about the outcome. Think of it as an agreement to meet at a particular time and place with your friends: all of you would like to meet, and only the specifics of the event are being agreed upon.

**Validity** is essential, because without it, consensus can be trivial. Consensus algorithms require all processes to agree on some value. If processes use some predetermined, arbitrary default value as a decision output regardless of the proposed values, they will reach unanimity, but the output of such an algorithm will not be valid, and it wouldn't be useful in reality.

Without **termination**, our algorithm will continue forever without reaching any conclusion or will wait indefinitely for a crashed process to come back, which is not very useful, either. Processes have to agree eventually and, for a consensus algorithm to be practical, this has to happen rather quickly.

---

## Broadcast

A **broadcast** is a communication abstraction often used in distributed systems. Broadcast algorithms are used to disseminate information among a set of processes. There exist many broadcast algorithms, making different assumptions and providing different guarantees. Broadcast is an important primitive and is used in many places, including consensus algorithms. We’ve discussed one of the forms of broadcast — gossip dissemination — already (see **Gossip Dissemination**).

Broadcasts are often used for database replication when a single coordinator node has to distribute the data to all other participants. However, making this process reliable is not a trivial matter: if the coordinator crashes after distributing the message to some nodes but not the other ones, it leaves the system in an inconsistent state: some of the nodes observe a new message and some do not.

The simplest and most straightforward way to broadcast messages is through a **best-effort broadcast** [CACHIN11]. In this case, the sender is responsible for ensuring message delivery to all the targets. If it fails, the other participants do not try to rebroadcast the message, and in the case of a coordinator crash, this type of broadcast will fail silently.

For a broadcast to be **reliable**, it needs to guarantee that all correct processes receive the same messages, even if the sender crashes during transmission.

To implement a naive version of a reliable broadcast, we can use a failure detector and a fallback mechanism. The most straightforward fallback mechanism is to allow every process that received the message to forward it to every other process it’s aware of. 

When the source process fails, other processes detect the failure and continue broadcasting the message, effectively flooding the network with $ N^2 $ messages (as shown in Figure 14-1). Even if the sender has crashed, messages still are picked up and delivered by the rest of the system, improving its reliability, and allowing all receivers to see the same messages [CACHIN11].

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//f1d9ddac-cfe0-45c5-804f-17ac1b568c7a/markdown_2/imgs/img_in_chart_box_410_181_826_391.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A22%3A05Z%2F-1%2F%2F0a92ef6c75ee7c59d8df8a00774af4a63d01e74a867ae77dad8748b42e99affe" alt="Image" width="34%" /></div>


<div style="text-align: center;"><div style="text-align: center;">Figure 14-1. Broadcast flooding the network.</div> </div>


One of the downsides of this approach is the fact that it uses $ N^2 $ messages, where N is the number of remaining recipients (since every broadcasting process excludes the original process and itself). Ideally, we’d want to reduce the number of messages required for a reliable broadcast.

---

## Atomic Broadcast

Even though the flooding algorithm just described can ensure message delivery, it does not guarantee delivery in any particular order. Messages reach their destination eventually, at an unknown time. If we need to deliver messages in order, we have to use the **atomic broadcast** (also called the **total order multicast**), which guarantees both reliable delivery and total order.

> While a **reliable broadcast** ensures that the processes agree on the set of messages delivered, an **atomic broadcast** also ensures they agree on the same sequence of messages (i.e., message delivery order is the same for every target).

In summary, an atomic broadcast has to ensure two essential properties:

* **Atomicity**: Processes have to agree on the set of received messages. Either all nonfailed processes deliver the message, or none do.
* **Order**: All nonfailed processes deliver the messages in the same order.

Messages here are delivered atomically: every message is either delivered to all processes or none of them and, if the message is delivered, every other message is ordered before or after this message.

> ### 💡 Beginner's Corner: Reliable vs. Atomic Broadcast
> In distributed systems, a **reliable broadcast** is a transmission protocol ensuring that if a message is delivered to one correct node, it is eventually delivered to all correct nodes. However, it does not enforce any sequence. If node $A$ broadcasts message $M_1$ and node $B$ broadcasts message $M_2$ concurrently, replica $R_1$ might receive $M_1$ then $M_2$, while replica $R_2$ receives $M_2$ then $M_1$. If these messages represent state updates (e.g., $M_1$: "set balance to 100", $M_2$: "add 10 to balance"), the replicas will diverge, resulting in inconsistent state.
> 
> An **atomic broadcast** solves this by adding a **total order** guarantee. It ensures not only reliable delivery but also that all correct nodes receive all messages in the exact same sequence. By enforcing this strict sequence, atomic broadcast behaves as a replicated append-only log, allowing independent state machines on different replicas to process the same inputs in the same order, thereby guaranteeing identical state transitions and preventing data divergence.

### Virtual Synchrony

One of the frameworks for group communication using broadcast is called **virtual synchrony**. An atomic broadcast helps to deliver totally ordered messages to a static group of processes, and virtual synchrony delivers totally ordered messages to a dynamic group of peers.

Virtual synchrony organizes processes into groups. As long as the group exists, messages are delivered to all of its members in the same order. In this case, the order is not specified by the model, and some implementations can take this to their advantage for performance gains, as long as the order they provide is consistent across all members [BIRMAN10].

Processes have the same view of the group, and messages are associated with the group identity: processes can see identical messages only as long as they belong to the same group.

As soon as one of the participants joins, leaves the group, or fails and is forced out of it, the group view changes. This happens by announcing the group change to all its members. Each message is uniquely associated with the group it originated from.

Virtual synchrony distinguishes between the **message receipt** (when a group member receives the message) and its **delivery** (which happens when all the group members receive the message). If the message was sent in one view, it can be delivered only in the same view, which can be determined by comparing the current group with the group the message is associated with. Received messages remain pending in the queue until the process is notified about successful delivery.

Since every message belongs to a specific group, unless all processes in the group have received it before the view change, no group member can consider this message delivered. This implies that all messages are sent and delivered between the view changes, which gives us atomic delivery guarantees. In this case, group views serve as a barrier that message broadcasts cannot pass.

Some total broadcast algorithms order messages by using a single process (**sequencer**) that is responsible for determining it. Such algorithms can be easier to implement, but rely on detecting leader failures for liveness. Using a sequencer can improve performance, since we do not need to establish consensus between processes for every message, and can use a sequencer-local view instead. This approach can still scale by partitioning the requests.

Despite its technical soundness, virtual synchrony has not received broad adoption and isn’t commonly used in end-user commercial systems [BIRMAN06].

### ZooKeeper Atomic Broadcast (ZAB)

One of the most popular and widely known implementations of the atomic broadcast is **ZAB** used by **Apache ZooKeeper** [HUNT10][JUNQUEIRA11], a hierarchical distributed key-value store, where it's used to ensure the total order of events and atomic delivery necessary to maintain consistency between replica states.

Processes in ZAB can take on one of two roles:
* **Leader**: A temporary role. It drives the process by executing algorithm steps, broadcasts messages to followers, and establishes the event order.
* **Follower**: To write new records and execute reads that observe the most recent values, clients connect to one of the nodes in the cluster. If the node happens to be the leader, it will handle the request. Otherwise, it forwards the request to the leader.

To guarantee leader uniqueness, the protocol timeline is split into **epochs**, identified with a unique, monotonically- and incrementally-sequenced number. During any epoch, there can be only one leader. The process starts by finding a prospective leader using any election algorithm, as long as it chooses a process that is up with a high probability. Since safety is guaranteed by the further algorithm steps, determining a prospective leader is more of a performance optimization. A prospective leader can also emerge as a consequence of the previous leader's failure.

> ### 💡 Beginner's Corner: ZAB Epochs and History Synchronization
> In ZooKeeper Atomic Broadcast (ZAB), the timeline is divided into logical epochs, which act as a logical clock. An **epoch** is represented by a monotonically increasing integer that is incremented every time a new leader election occurs. This epoch number is prefixed to every transaction identifier (creating a 64-bit `zxid` consisting of a 32-bit epoch number and a 32-bit transaction counter).
> 
> The purpose of epochs and the Synchronization phase is to prevent **split-brain** scenarios and resolve histories from crashed leaders. If a previous leader crashed while partially replicating transactions to only a minority of followers, those transactions must not be lost if they were committed, or must be discarded if they were never committed. During the Synchronization phase, the new leader compares its transaction history with the followers. It forces all followers to truncate any uncommitted transactions from older epochs and streams any missing committed transactions to them, ensuring that the cluster converges to a single, identical history before any new transactions from the new epoch can be proposed.

As soon as a prospective leader is established, it executes the protocol in three phases:

#### 1. Discovery
The prospective leader learns about the latest epoch known by every other process, and proposes a new epoch that is greater than the current epoch of any follower. Followers respond to the epoch proposal with the identifier of the latest transaction seen in the previous epoch. After this step, no process will accept broadcast proposals for earlier epochs.

#### 2. Synchronization
This phase is used to recover from the previous leader's failure and bring lagging followers up to speed. The prospective leader sends a message to the followers proposing itself as a leader for the new epoch and collects their acknowledgments. As soon as acknowledgments are received, the leader is established. 

After this step, followers will not accept attempts to become the epoch leader from any other processes. During synchronization, the new leader ensures that followers have the same history and delivers committed proposals from the established leaders of earlier epochs. These proposals are delivered before any proposal from the new epoch is delivered.

#### 3. Broadcast
As soon as the followers are back in sync, active messaging starts. During this phase, the leader receives client messages, establishes their order, and broadcasts them to the followers: it sends a new proposal, waits for a quorum of followers to respond with acknowledgments, and, finally, commits it. 

This process is similar to a two-phase commit without aborts: votes are just acknowledgments, and the client cannot vote against a valid leader's proposal. However, proposals from leaders from incorrect epochs should not be acknowledged. The broadcast phase continues until the leader crashes, is partitioned from the followers, or is suspected to have crashed due to message delay.

> ### 🚶‍♂️ Step-by-Step Breakdown: ZAB Broadcast Cycle
> The ZAB broadcast phase operates using a simplified two-phase commit protocol without aborts, ensuring total order replication:
> 1. **Client Request Reception**: The leader receives a write request from a client. If a follower receives a write request, it forwards the request to the leader.
> 2. **Proposal Generation**: The leader assigns a unique, monotonically increasing transaction ID (`zxid`) to the request. The `zxid` includes the leader's current epoch number, ensuring that any proposal is uniquely bound to that leader's epoch.
> 3. **Proposal Dissemination**: The leader appends the proposal to its local log and broadcasts a `PROPOSAL` message containing the transaction details and the `zxid` to all followers over FIFO (First-In, First-Out) TCP connections, guaranteeing message order is preserved in transit.
> 4. **Follower Acknowledgment**: Each follower receives the `PROPOSAL` message, validates that the epoch in the `zxid` matches the leader's current epoch, appends the proposal to its local disk-backed log, and sends an `ACK` message back to the leader.
> 5. **Quorum Verification**: The leader waits to collect acknowledgments from a quorum (a majority, $\lfloor N/2 \rfloor + 1$) of followers. Once a quorum is reached (including the leader itself), the transaction is considered committed.
> 6. **Commit Broadcast and Client Reply**: The leader broadcasts a `COMMIT` message to all followers, prompting them to apply the transaction to their in-memory state machines. Simultaneously, the leader applies the transaction to its own state machine and sends a success response to the client.

Figure 14-2 shows the three phases of the ZAB algorithm, and the messages exchanged during each step.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//f2dab4e5-3ffc-4aa0-9b05-3befeea2cd01/markdown_2/imgs/img_in_image_box_140_1054_1048_1179.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A22%3A05Z%2F-1%2F%2F2a9a6a386c88288802a354aeabd7c68cb7fe6be470d73e449b14c962a24d956c" alt="Image" width="76%" /></div>


<div style="text-align: center;"><div style="text-align: center;">Figure 14-2. ZAB protocol summary.</div> </div>


The safety of this protocol is guaranteed if followers ensure they accept proposals only from the leader of the established epoch. Two processes may attempt to get elected, but only one of them can win and establish itself as an epoch leader. It is also assumed that processes perform the prescribed steps in good faith and follow the protocol.

Both the leader and followers rely on heartbeats to determine the liveness of remote processes. 
* If the leader does not receive heartbeats from a quorum of followers, it steps down and restarts the election process.
* Similarly, if one of the followers has determined the leader crashed, it starts a new election process.

Messages are totally ordered, and the leader will not attempt to send the next message until the message that preceded it was acknowledged. Even if some messages are received by a follower more than once, their repeated application does not produce additional side effects, as long as the delivery order is followed. ZAB is able to handle multiple outstanding concurrent state changes from clients, since a unique leader will receive write requests, establish the event order, and broadcast the changes.

Total message order also allows ZAB to improve recovery efficiency. During the synchronization phase, followers respond with their highest committed proposal. The leader can simply choose the node with the highest proposal for recovery, and this can be the only node messages have to be copied from.

One of the advantages of ZAB is its efficiency: the broadcast process requires only two rounds of messages, and leader failures can be recovered from by streaming the missing messages from a single up-to-date process. Having a long-lived leader can have a positive impact on performance: we do not require additional consensus rounds to establish a history of events, since the leader can sequence them based on its local view.

---

## Paxos

An atomic broadcast is a problem equivalent to consensus in an asynchronous system with crash failures [CHANDRA96], since participants have to agree on the message order and must be able to learn about it. You will see many similarities in both motivation and implementation between atomic broadcast and consensus algorithms.

Probably the most widely known consensus algorithm is **Paxos**. It was first introduced by Leslie Lamport in “The Part-Time Parliament” paper [LAMPORT98]. In this paper, consensus is described in terms of terminology inspired by the legislative and voting process on the Aegean island of Paxos. In 2001, the author released a follow-up paper titled “Paxos Made Simple” [LAMPORT01] that introduced simpler terms, which are now commonly used to explain this algorithm.

Participants in Paxos can take one of three roles:
* **Proposers**: Receive values from clients, create proposals to accept these values, and attempt to collect votes from acceptors.
* **Acceptors**: Vote to accept or reject the values proposed by the proposer. For fault tolerance, the algorithm requires the presence of multiple acceptors, but for liveness, only a quorum (majority) of acceptor votes is required to accept the proposal.
* **Learners**: Take the role of replicas, storing the outcomes of the accepted proposals.

Any participant can take any role, and most implementations colocate them: a single process can simultaneously be a proposer, an acceptor, and a learner.

Every proposal consists of a value proposed by the client and a unique, monotonically increasing proposal number. This number is then used to ensure a total order of executed operations and establish happened-before/after relationships among them. Proposal numbers are often implemented using an `(id, timestamp)` pair, where node IDs are also comparable and can be used to break ties for timestamps.

### Paxos Algorithm

The Paxos algorithm can be generally split into two phases: **voting** (or **propose phase**) and **replication**. During the voting phase, proposers compete to establish their leadership. During replication, the proposer distributes the value to the acceptors.

1. The proposer is the initial point of contact for the client. It receives a value that should be decided upon, and attempts to collect votes from a quorum of acceptors.
2. When this is done, acceptors distribute the information about the agreed value to the learners, ratifying the result.
3. Learners increase the replication factor of the value that's been agreed on.

Only one proposer can collect the majority of votes. Under some circumstances, votes may get split evenly between the proposers, and neither one of them will be able to collect a majority during this round, forcing them to restart. We discuss this and other scenarios of competing proposers in **Failure Scenarios**.

> ### 💡 Beginner's Corner: The Paxos Two-Phase Consensus Mechanism
> Classic Paxos operates in two distinct phases to achieve consensus safely in an asynchronous network:
> - **Phase 1 (Prepare / Promise)**: This is a read-and-lock phase. A proposer attempts to establish leadership for a round by broadcasting a `Prepare(n)` message with a unique proposal number $n$ to a majority of acceptors. When an acceptor receives this, if $n$ is greater than any proposal number it has previously seen, it returns a `Promise` not to accept any future proposals numbered less than $n$. Crucially, if the acceptor has already accepted a value in a previous round, it returns that value and its associated proposal number ($V_{accepted}, m$) to the proposer. This phase allows the proposer to "lock" out older concurrent proposals and discover if any value has already been agreed upon by a majority.
> - **Phase 2 (Propose / Accept)**: This is the write phase. Once the proposer receives promises from a majority of acceptors, it must choose the value to replicate. If any acceptor returned an accepted value in Phase 1, the proposer **must** set its proposal's value $v$ to the value with the highest proposal number among all returned promises. If no acceptor returned a previously accepted value, the proposer is free to use its own proposed value. The proposer then broadcasts `Accept!(n, v)` to a majority of acceptors. If an acceptor hasn't promised to ignore proposal $n$ (due to a higher Phase 1 prepare in the meantime), it accepts the value.
> 
> This two-phase structure guarantees safety through **quorum intersection**. Because any two majorities of nodes must overlap by at least one node, if a value was already accepted by a majority in an earlier round, any new majority quorum in Phase 1 will contain at least one node that accepted that value. That node will report the value to the proposer, forcing the new proposer to adopt and replicate the existing value, preventing consensus from ever being overwritten.

During the propose phase, the proposer sends a `Prepare(n)` message (where `n` is a proposal number) to a majority of acceptors and attempts to collect their votes.

When the acceptor receives the prepare request, it has to respond, preserving the following invariants [LAMPORT01]:
* If this acceptor hasn’t responded to a prepare request with a higher sequence number yet, it promises that it will not accept any proposal with a lower sequence number.
* If this acceptor has already accepted (received an `Accept!(m, V_accepted)` message) any other proposal earlier, it responds with a `Promise(m, V_accepted)` message, notifying the proposer that it has already accepted the proposal with a sequence number `m`.
* If this acceptor has already responded to a prepare request with a higher sequence number, it notifies the proposer about the existence of a higher-numbered proposal.

An acceptor can respond to more than one prepare request, as long as the later one has a higher sequence number.

During the replication phase, after collecting a majority of votes, the proposer can start the replication, where it commits the proposal by sending acceptors an `Accept!(n, v)` message with value `v` and proposal number `n`. `v` is the value associated with the highest-numbered proposal among the responses it received from acceptors, or any value of its own if their responses did not contain old accepted proposals.

The acceptor accepts the proposal with a number `n`, unless during the propose phase it has already responded to `Prepare(m)`, where `m` is greater than `n`. If the acceptor rejects the proposal, it notifies the proposer about it by sending the highest sequence number it has seen along with a request to help the proposer catch up [LAMPORT01].

You can see a generalized depiction of a Paxos round in Figure 14-3.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//dc1ca55d-df6e-4273-991e-7061b6926d65/markdown_2/imgs/img_in_chart_box_139_667_1048_916.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A22%3A05Z%2F-1%2F%2Fd263189c5341e02b3e54f42f8480f5b196f93a40e09d4211997e4f671be83810" alt="Image" width="76%" /></div>


<div style="text-align: center;"><div style="text-align: center;">Figure 14-3. Paxos algorithm: normal execution.</div> </div>


Once a consensus was reached on the value (in other words, it was accepted by at least one acceptor), future proposers have to decide on the same value to guarantee the agreement. This is why acceptors respond with the latest value they’ve accepted. If no acceptor has seen a previous value, the proposer is free to choose its own value.

A learner has to find out the value that has been decided, which it can know after receiving notifications from a majority of acceptors. To let the learner know about the new value as soon as possible, acceptors can notify it about the value as soon as they accept it. If there’s more than one learner, each acceptor will have to notify each learner. One or more learners can be distinguished, in which case they will notify other learners about accepted values.

In summary, the goal of the first algorithm phase is to establish a leader for the round and understand which value is going to be accepted, allowing the leader to proceed with the second phase: broadcasting the value. For the purpose of the base algorithm, we assume that we have to perform both phases every time we’d like to decide on a value. In practice, we’d like to reduce the number of steps in the algorithm, so we allow the proposer to propose more than one value. We discuss this in more detail later in **Multi-Paxos**.

> ### 🚶‍♂️ Step-by-Step Breakdown: Classic Paxos Consensus Run
> Here is the sequential execution path of a single-decree Paxos round where a proposer $P_1$ successfully proposes and commits a value $V_1$:
> 1. **Proposer Phase 1a (Prepare)**: Proposer $P_1$ generates a unique, monotonically increasing proposal number $n = 101$ and broadcasts `Prepare(101)` to a majority of acceptors $A_1, A_2, A_3$.
> 2. **Acceptor Phase 1b (Promise)**: Each acceptor receives `Prepare(101)`.
>    - $A_1, A_2, A_3$ check if they have seen a proposal number greater than $101$. They have not.
>    - They persist $101$ as the highest seen proposal number, promising never to accept any future proposals numbered less than $101$.
>    - Since none of them have accepted any value yet, they send `Promise(101, null, null)` back to $P_1$.
> 3. **Proposer Phase 2a (Propose/Accept)**: Proposer $P_1$ receives promises from a majority ($A_1, A_2$). Since all returned values are `null`, $P_1$ is free to choose its own value, $V_1$. It broadcasts `Accept!(101, V_1)` to $A_1, A_2, A_3$.
> 4. **Acceptor Phase 2b (Accepted)**: Acceptors receive `Accept!(101, V_1)`.
>    - They check if they have promised to ignore proposal $101$ (i.e., if they have seen a prepare number $> 101$). They have not.
>    - They accept the proposal, write $(101, V_1)$ to their persistent storage, and broadcast an `Accepted(101, V_1)` notification to all learners and the proposer.
> 5. **Consensus Achieved**: Once the proposer or learners receive `Accepted` notifications from a majority of acceptors, the value $V_1$ is committed, and consensus is reached.

### Quorums in Paxos

Quorums are used to make sure that some of the participants can fail, but we still can proceed as long as we can collect votes from the active ones. 

> A **quorum** is the minimum number of votes required for the operation to be performed. This number usually constitutes a majority of participants. 

The main idea behind quorums is that even if participants fail or happen to be separated by a network partition, there's at least one participant that acts as an arbiter, ensuring protocol correctness.

Once a sufficient number of participants accept the proposal, the value is guaranteed to be accepted by the protocol, since any two majorities have at least one participant in common.

Paxos guarantees safety in the presence of any number of failures. There's no configuration that can produce incorrect or inconsistent states, since this would contradict the definition of consensus.

Liveness is guaranteed in the presence of $ f $ failed processes. For that, the protocol requires $ 2f + 1 $ processes in total so that, if $ f $ processes happen to fail, there are still $ f + 1 $ processes able to proceed. By using quorums, rather than requiring the presence of all processes, Paxos (and other consensus algorithms) guarantee results even when $ f $ process failures occur. 

In **Flexible Paxos**, we talk about quorums in slightly different terms and describe how to build protocols requiring quorum intersection between algorithm steps only.

> [!TIP]
> It is important to remember that quorums only describe the blocking properties of the system. To guarantee safety, for each step we have to wait for responses from at least a quorum of nodes. We can send proposals and accept commands to more nodes; we just do not have to wait for their responses to proceed. We may send messages to more nodes (some systems use speculative execution: issuing redundant queries that help to achieve the required response count in case of node failures), but to guarantee liveness, we can proceed as soon as we hear from the quorum.

### Failure Scenarios

Discussing distributed algorithms gets particularly interesting when failures are discussed. One of the failure scenarios, demonstrating fault tolerance, is when the proposer fails during the second phase, before it is able to broadcast the value to all the acceptors (a similar situation can happen if the proposer is alive but is slow or cannot communicate with some acceptors). In this case, the new proposer may pick up and commit the value, distributing it to the other participants.

Figure 14-4 shows this situation:
* Proposer $ P_1 $ goes through the election phase with a proposal number 1, but fails after sending the value $ V_1 $ to just one acceptor $ A_1 $.
* Another proposer $ P_2 $ starts a new round with a higher proposal number 2, collects a quorum of acceptor responses ($ A_1 $ and $ A_2 $ in this case), and proceeds by committing the old value $ V_1 $, proposed by $ P_1 $.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//86eeac9d-0e1b-4c9d-bbcf-a0fd067f32dd/markdown_0/imgs/img_in_chart_box_138_853_1047_1074.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A22%3A04Z%2F-1%2F%2F99b6f233f78f0cf82c6efbdf963c843c01fba9af9c9780199bb5ea72b2537aa4" alt="Image" width="76%" /></div>


<div style="text-align: center;"><div style="text-align: center;">Figure 14-4. Paxos failure scenario: proposer failure, deciding on the old value.</div> </div>


Since the algorithm state is replicated to multiple nodes, proposer failure does not result in a failure to reach a consensus. If the current proposer fails after even a single acceptor $ A_1 $ has accepted the value, its proposal can be picked by the next proposer. This also implies that all of this may happen without the original proposer knowing about it.

In a client/server application, where the client is connected only to the original proposer, this might lead to situations where the client doesn’t know about the result of the Paxos round execution. $ ^{1} $

However, other scenarios are possible, too, as Figure 14-5 shows. For example:
* $ P_1 $ has failed just like in the previous example, after sending the value $ V_1 $ only to $ A_1 $.
* The next proposer, $ P_2 $, starts a new round with a higher proposal number 2, and collects a quorum of acceptor responses, but this time $ A_2 $ and $ A_3 $ are the first to respond. After collecting a quorum, $ P_2 $ commits its own value despite the fact that theoretically there’s a different committed value on $ A_1 $.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//86eeac9d-0e1b-4c9d-bbcf-a0fd067f32dd/markdown_1/imgs/img_in_image_box_139_551_1047_773.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A22%3A05Z%2F-1%2F%2F4e8cefd0e23aa5b5ab33430d898da60a2aaad497bcfe205c760d73482fea6b2d" alt="Image" width="76%" /></div>


<div style="text-align: center;"><div style="text-align: center;">Figure 14-5. Paxos failure scenario: proposer failure, deciding on the new value.</div> </div>


There's one more possibility here, shown in Figure 14-6:
* Proposer $ P_1 $ fails after only one acceptor $ A_1 $ accepts the value $ V_1 $. $ A_1 $ fails shortly after accepting the proposal, before it can notify the next proposer about its value.
* Proposer $ P_2 $, which started the round after $ P_1 $ failed, does not overlap with $ A_1 $ and proceeds to commit its value instead.
* Any proposer that comes after this round that overlaps with $ A_1 $ will ignore $ A_1 $'s value and choose a more recent accepted proposal instead.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//86eeac9d-0e1b-4c9d-bbcf-a0fd067f32dd/markdown_1/imgs/img_in_image_box_138_1325_1047_1527.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A22%3A05Z%2F-1%2F%2F52565d9a18380fa22a95998a22e256536ae6f56508cb5bc13c07df0bb86d6699" alt="Image" width="76%" /></div>


<div style="text-align: center;"><div style="text-align: center;">Figure 14-6. Paxos failure scenario: proposer and acceptor failure.</div> </div>


Another failure scenario is when two or more proposers start competing, each trying to get through the propose phase, but keep failing to collect a majority because the other one beat them to it.

While acceptors promise not to accept any proposals with a lower number, they still may respond to multiple prepare requests, as long as the later one has a higher sequence number. When a proposer tries to commit a value, it might find that acceptors have already responded to a prepare request with a higher sequence number. This may lead to multiple proposers constantly retrying and preventing each other from making further progress. This problem is usually solved by incorporating a random backoff, which eventually lets one of the proposers proceed while the others sleep.

> ### 💡 Beginner's Corner: The Dueling Proposers Livelock
> A major vulnerability of classic Paxos is **livelock** (also known as the **dueling proposers** problem), where the algorithm is safe (it will never decide on conflicting values) but fails to terminate (liveness is lost). 
> 
> This happens when two proposers, $P_1$ and $P_2$, concurrently attempt to achieve consensus and continuously preempt each other's proposal numbers:
> 1. Proposer $P_1$ broadcasts `Prepare(1)` and collects promises from a majority of acceptors.
> 2. Before $P_1$ can send `Accept!(1, V_1)`, proposer $P_2$ broadcasts `Prepare(2)`.
> 3. Acceptors receive `Prepare(2)`. Since $2 > 1$, they grant a promise to $P_2$ and update their highest seen proposal number to $2$.
> 4. $P_1$ sends its `Accept!(1, V_1)` message. The acceptors reject it because they have promised not to accept any proposals numbered less than $2$.
> 5. Seeing its proposal rejected, $P_1$ immediately increments its proposal number and broadcasts `Prepare(3)`.
> 6. Acceptors receive `Prepare(3)`. Since $3 > 2$, they promise to ignore proposal $2$ and grant a promise to $P_1$.
> 7. $P_2$ attempts to send `Accept!(2, V_2)`, which is rejected because the acceptors have promised to ignore proposals less than $3$.
> 8. $P_2$ increments its proposal number and broadcasts `Prepare(4)`, starting the cycle again.
> 
> This loop can continue indefinitely, consuming network bandwidth and CPU cycles without ever reaching the accept phase. To resolve this without adding coordination overhead, nodes use **randomized backoff**. When a proposer's accept request is rejected, it waits for a random number of milliseconds before retrying, allowing one proposer sufficient time to complete both Phase 1 and Phase 2 without preemption.

The Paxos algorithm can tolerate acceptor failures, but only if there are still enough acceptors alive to form a majority.

### Multi-Paxos

So far we discussed the classic Paxos algorithm, where we pick an arbitrary proposer and attempt to start a Paxos round. One of the problems with this approach is that a propose round is required for each replication round that occurs in the system. Only after the proposer is established for the round, which happens after a majority of acceptors respond with a `Promise` to the proposer's `Prepare`, can it start the replication. 

To avoid repeating the propose phase and let the proposer reuse its recognized position, we can use **Multi-Paxos**, which introduces the concept of a **leader**: a distinguished proposer [LAMPORT01]. This is a crucial addition, significantly improving algorithm efficiency.

Having an established leader, we can skip the propose phase and proceed straight to replication: distributing a value and collecting acceptor acknowledgments.

In the classic Paxos algorithm, reads can be implemented by running a Paxos round that would collect any values from incomplete rounds if they're present. This has to be done because the last known proposer is not guaranteed to hold the most recent data, since there might have been a different proposer that has modified state without the proposer knowing about it.

A similar situation may occur in Multi-Paxos: we’re trying to perform a read from the known leader after another leader is already elected, returning stale data, which contradicts the linearizability guarantees of consensus. 

To avoid that and guarantee that no other process can successfully submit values, some Multi-Paxos implementations use **leases**. The leader periodically contacts the participants, notifying them that it is still alive, effectively prolonging its lease. Participants have to respond and allow the leader to continue operation, promising that they will not accept proposals from other leaders for the period of the lease [CHANDRA07].

Leases are not a correctness guarantee, but a performance optimization that allows reads from the active leader without collecting a quorum. To guarantee safety, leases rely on bounded clock synchrony between the participants. If their clocks drift too much and the leader assumes its lease is still valid while other participants think its lease has expired, linearizability cannot be guaranteed.

> ### 💡 Beginner's Corner: Multi-Paxos Optimization and Leases
> In classic Paxos, every single value write requires running the full two-phase protocol, incurring at least two round-trip times (RTT) over the network. **Multi-Paxos** optimizes this by electing a stable **leader** (a distinguished proposer) who runs Phase 1 (Prepare/Promise) exactly once for the entire sequence of log slots. Once the leader receives promises from a majority, it can execute subsequent writes (appends to the log) using only Phase 2 (Accept/Accepted), reducing the latency of write operations from two RTTs to a single RTT.
> 
> To support **linearizable reads** (ensuring that a read always returns the most up-to-date committed value), a naive implementation would require the leader to run a quorum read (contacting a majority of acceptors) to ensure it hasn't been deposed by a newer leader. To avoid this overhead, Multi-Paxos introduces **leases**. A lease is a time-bound contract where acceptors promise not to respond to any new prepare requests from other proposers for a specific duration (e.g., 5 seconds). The active leader can then serve read requests directly from its local memory without network round-trips, confident that no other leader could have committed a newer value.
> 
> However, leases introduce a dependency on physical hardware clocks. If the leader's hardware clock drifts and runs slower than the acceptors' clocks, the leader might believe its 5-second lease is still active at $t = 4.9\text{s}$ (local time), while the acceptors' clocks have already passed $t = 5.0\text{s}$, allowing them to grant a promise to a new leader. If the new leader writes a new value and the old leader serves a local read, the client will observe stale data, violating linearizability.

Multi-Paxos is sometimes described as a replicated log of operations applied to some structure. The algorithm is oblivious to the semantics of this structure and is only concerned with consistently replicating values that will be appended to this log. To preserve the state in case of process crashes, participants keep a durable log of received messages.

To prevent a log from growing indefinitely large, its contents should be applied to the aforementioned structure. After the log contents are synchronized with a primary structure, creating a snapshot, the log can be truncated. Log and state snapshots should be mutually consistent, and snapshot changes should be applied atomically with the truncation of the log segment [CHANDRA07].

We can think of single-decree Paxos as a write-once register: we have a slot where we can put a value, and as soon as we’ve written the value there, no subsequent modifications are possible. During the first step, proposers compete for ownership of the register, and during the second phase, one of them writes the value. 

At the same time, Multi-Paxos can be thought of as an append-only log, consisting of a sequence of such values: we can write one value at a time, all values are strictly ordered, and we cannot modify already written values [RYSTSOV16]. 

There are examples of consensus algorithms that offer collections of read-modify-write registers and use state sharing rather than replicated state machines, such as Active Disk Paxos [CHOCKLER15] and CASPaxos [RYSTSOV18].

### Fast Paxos

We can reduce the number of round-trips by one, compared to the classic Paxos algorithm, by letting any proposer contact acceptors directly rather than going through the leader. For this, we need to increase the quorum size to $ 2f + 1 $ (where $ f $ is the number of processes allowed to fail), compared to $ f + 1 $ in classic Paxos, and the total number of acceptors to $ 3f + 1 $ [JUNQUEIRA07]. This optimization is called **Fast Paxos** [LAMPORT06].

The classic Paxos algorithm has a condition where, during the replication phase, the proposer can pick any value it has collected during the propose phase. Fast Paxos has two types of rounds:
* **Classic**: The algorithm proceeds the same way as the classic version.
* **Fast**: It allows acceptors to accept other values.

While describing this algorithm, we will refer to the proposer that has collected a sufficient number of responses during the propose phase as a **coordinator**, and reserve the term **proposer** for all other proposers. Some Fast Paxos descriptions say that clients can contact acceptors directly [ZHAO15].

In a fast round, if the coordinator is permitted to pick its own value during the replication phase, it can instead issue a special `Any` message to acceptors. Acceptors, in this case, are allowed to treat any proposer's value as if it is a classic round and they received a message with this value from the coordinator. In other words, acceptors independently decide on values they receive from different proposers.

Figure 14-7 shows an example of classic and fast rounds in Fast Paxos. From the image, it might look like the fast round has more execution steps, but keep in mind that in a classic round, in order to submit its value, the proposer would need to go through the coordinator to get its value committed.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//c10c3e61-bb0b-4935-a127-2ca8356cadaa/markdown_1/imgs/img_in_chart_box_141_161_1048_538.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A22%3A05Z%2F-1%2F%2Fe98fbb80c9ea9b4495ec9c7110d414321bfb59623d0733d77248077bc89d84d5" alt="Image" width="76%" /></div>


<div style="text-align: center;"><div style="text-align: center;">Figure 14-7. Fast Paxos algorithm: fast and classic rounds.</div> </div>


This algorithm is prone to **collisions**, which occur if two or more proposers attempt to use the fast step to reduce the number of round-trips, and acceptors receive different values. The coordinator has to intervene and start recovery by initiating a new round.

This means that acceptors, after receiving values from different proposers, may decide on conflicting values. When the coordinator detects a conflict (value collision), it has to reinitiate a Propose phase to let acceptors converge to a single value.

One of the disadvantages of Fast Paxos is the increased number of round-trips and request latency on collisions if the request rate is high. [JUNQUEIRA07] shows that, due to the increased number of replicas and, **as a result**, messages exchanged between the participants, despite a reduced number of steps, Fast Paxos can have higher latencies than its classic counterpart.

### Egalitarian Paxos

Using a distinguished proposer as a leader makes a system prone to failures: as soon as the leader fails, the system has to elect a new one before it can proceed with further steps. Another problem is that having a leader can put a disproportionate load on it, impairing system performance.

> [!NOTE]
> One of the ways to avoid putting an entire system load on the leader is partitioning. Many systems split the range of possible values into smaller segments and allow a part of the system to be responsible for a specific range without having to worry about the other parts. 
> 
> This helps with:
> * **Availability**: By isolating failures to a single partition and preventing propagation to other parts of the system.
> * **Performance**: Since segments serving different values are nonoverlapping.
> * **Scalability**: Since we can scale the system by increasing the number of partitions.
> 
> It is important to keep in mind that performing an operation against multiple partitions will require an atomic commitment.

Instead of using a leader and proposal numbers for sequencing commands, we can use a leader responsible for the commitment of a specific command, and establish the order by looking up and setting dependencies. This approach is commonly called **Egalitarian Paxos**, or **EPaxos** [MORARU11]. 

The idea of allowing nonconflicting writes to be committed to the replicated state machine independently was first introduced in [LAMPORT05] and called **Generalized Paxos**. EPaxos is the first implementation of Generalized Paxos.

EPaxos attempts to offer the benefits of both the classic Paxos algorithm and Multi-Paxos. Classic Paxos offers high availability, since a leader is established during each round, but has a higher message complexity. Multi-Paxos offers high throughput and requires fewer messages, but the leader may become a bottleneck.

EPaxos starts with a **Pre-Accept** phase, during which a process becomes a leader for a specific proposal. Every proposal has to include:

* **Dependencies**: All commands that potentially interfere with the current proposal, but are not necessarily already committed.
* **Sequence number**: This breaks cycles between the dependencies. Set it to a value larger than any sequence number of the known dependencies.

After collecting this information, it forwards a `Pre-Accept` message to a fast quorum of replicas. A **fast quorum** is $ \lceil 3f/4 \rceil $ replicas, where $ f $ is the number of tolerated failures.

Replicas check their local command logs, update the proposal dependencies based on their view of potentially conflicting proposals, and send this information back to the leader. If the leader receives responses from a fast quorum of replicas, and their dependency lists are in agreement with each other and the leader itself, it can commit the command.

If the leader does not receive enough responses or if the command lists received from the replicas differ and contain interfering commands, it updates its proposal with a new dependency list and a sequence number. 
* The new dependency list is based on previous replica responses and combines all collected dependencies. 
* The new sequence number has to be larger than the highest sequence number seen by the replicas. 

After that, the leader sends the new, updated command to $ \lfloor f/2 \rfloor + 1 $ replicas. After this is done, the leader can finally commit the proposal.

Effectively, we have two possible scenarios:

* **Fast path**: When dependencies match, the leader can safely proceed with the commit phase with only a fast quorum of replicas.
* **Slow path**: When there’s a disagreement between the replicas, and their command lists have to be updated before the leader can proceed with a commit.

Figure 14-8 shows these scenarios — $ P_1 $ initiating a fast path run, and $ P_5 $ initiating a slow path run:
* $ P_1 $ starts with proposal number 1 and no dependencies, and sends a `PreAccept(1, ∅)` message. Since the command logs of $ P_2 $ and $ P_3 $ are empty, $ P_1 $ can proceed with a commit.
* $ P_5 $ creates a proposal with sequence number 2. Since its command log is empty by that point, it also declares no dependencies and sends a `PreAccept(2, ∅)` message. $ P_4 $ is not aware of the committed proposal 1, but $ P_3 $ notifies $ P_5 $ about the conflict and sends its command log: `{1}`.
* $ P_5 $ updates its local dependency list and sends a message to make sure replicas have the same dependencies: `Accept(2, {1})`. As soon as the replicas respond, it can commit the value.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//c10c3e61-bb0b-4935-a127-2ca8356cadaa/markdown_4/imgs/img_in_chart_box_137_606_1049_909.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A22%3A06Z%2F-1%2F%2F2d831581aacab716d757b41128af11a3654759591d869beb2dcf8f60e4caff9c" alt="Image" width="76%" /></div>


<div style="text-align: center;"><div style="text-align: center;">Figure 14-8. EPaxos algorithm run.</div> </div>


Two commands, A and B, interfere only if their execution order matters; in other words, if executing A before B and executing B before A produce different results.

Commit is done by responding to the client and asynchronously notifying replicas with a `Commit` message. Commands are executed after they're committed.

Since dependencies are collected during the Pre-Accept phase, by the time requests are executed, the command order is already established, and no command can suddenly appear somewhere in-between: it can only get appended after the command with the largest sequence number.

> ### 💡 Beginner's Corner: EPaxos Dependency Resolution
> In Multi-Paxos and Raft, a single leader must sequence all commands, creating a network and CPU bottleneck. **Egalitarian Paxos (EPaxos)** removes the single-leader bottleneck by allowing *any* replica to act as a coordinator for any command. Instead of relying on a pre-determined, centralized sequence of log slots, EPaxos establishes the order of commands dynamically by tracking their **dependencies**.
> 
> Two commands **interfere** if they are concurrent and access the same key (e.g., command $A$ writes to key $K$, and command $B$ reads or writes to key $K$, meaning their execution order affects the final state). During the Pre-Accept phase, replicas examine their local command history to build a list of all concurrent commands that interfere with the new proposal. If all replicas in a fast quorum agree on the exact same set of interfering commands, the command can be committed immediately (the **Fast Path**). If there is a disagreement (e.g., because some replicas saw a concurrent interfering command and others did not), the coordinator must run a slow path to reconcile the dependency list across a majority of nodes.
> 
> Because commands are committed with different dependency lists, replicas cannot simply execute them in slot order. Instead, they construct a **directed dependency graph** where each committed command is a node, and edges point to its dependencies. Replicas run a topological sort algorithm to find strongly connected components, resolve any circular dependencies (cycles) using the sequence numbers, and execute the commands in topological order. This ensures that even though commands are proposed and committed out of order across different replicas, they are executed in the exact same logical order everywhere.
> 
> ### 🚶‍♂️ Step-by-Step Breakdown: EPaxos Fast and Slow Paths
> The execution path of an EPaxos command depends on whether concurrent interfering commands cause a conflict:
> 
> #### The Fast Path (No Concurrent Conflicts)
> 1. **Command Initiation**: A client sends a write command $C_1$ to any replica $R_1$ (acting as the command coordinator).
> 2. **Pre-Accept Proposal**: $R_1$ appends $C_1$ to its local log, determines its initial dependencies (empty, or containing known older interfering commands), and broadcasts `PreAccept(C_1, Deps_1, Seq_1)` to a **fast quorum** ($\lceil 3f/4 \rceil$) of replicas.
> 3. **Replica Dependency Check**: Each replica in the fast quorum receives the message, checks its local log for any conflicting concurrent commands, updates the dependency list `Deps` and sequence number `Seq` if needed, and returns its local list of dependencies to $R_1$.
> 4. **Quorum Consensus**: $R_1$ receives the responses. If all replicas in the fast quorum return the *identical* dependency list and sequence number, $R_1$ has achieved consensus.
> 5. **Commit**: $R_1$ immediately commits the command, responds to the client (taking only 1 network RTT), and asynchronously broadcasts `Commit(C_1, Deps_1, Seq_1)` to all replicas.
> 
> #### The Slow Path (Concurrent Conflict Occurs)
> 1. **Conflict Discovery**: If two concurrent commands $C_1$ and $C_2$ interfere, some replicas might see $C_1$ first, while others see $C_2$ first, returning *different* dependency lists and sequence numbers to the coordinator $R_1$.
> 2. **Dependency Merging**: Seeing the mismatch, $R_1$ must merge the responses. It creates a union of all returned dependency lists and chooses a sequence number greater than the maximum returned.
> 3. **Accept Phase**: $R_1$ broadcasts `Accept(C_1, Merged_Deps, Max_Seq)` to a classic majority quorum ($\lfloor f/2 \rfloor + 1$) of replicas, forcing them to overwrite their local records with this unified view.
> 4. **Acknowledgment and Commit**: Once the majority acknowledges the `Accept` message, $R_1$ commits the command, replies to the client (taking 2 network RTTs due to the extra phase), and broadcasts the final `Commit` message to all replicas.

To execute a command, replicas build a dependency graph and execute all commands in a reverse dependency order. In other words, before a command can be executed, all its dependencies (and, **then**, all their dependencies) have to be executed. Since only interfering commands have to depend on each other, this situation should be relatively rare for most workloads [MORARU13].

Similar to Paxos, EPaxos uses proposal numbers, which prevent stale messages from being propagated. Sequence numbers consist of:
1. An **epoch**: Identifier of the current cluster configuration that changes when nodes leave and join the cluster.
2. A **monotonically incremented node-local counter**.
3. A **replica ID**.

If a replica receives a proposal with a sequence number lower than one it has already seen, it negatively acknowledges the proposal, and sends the highest sequence number and an updated command list known to it in response.

### Flexible Paxos

A quorum is usually defined as a majority of processes. By definition, we have an intersection between two quorums no matter how we pick nodes: there's always at least one node that can break ties.

We have to answer two important questions:
* Is it necessary to contact a majority of servers during every execution step?
* Do all quorums have to intersect? In other words, does a quorum we use to pick a distinguished proposer (first phase), a quorum we use to decide on a value (second phase), and every execution instance (for example, if multiple instances of the second step are executed concurrently), have to have nodes in common?

Since we’re still talking about consensus, we cannot change any safety definitions: the algorithm has to guarantee agreement.

In Multi-Paxos, the leader election phase is infrequent, and the distinguished proposer is allowed to commit several values without rerunning the election phase, potentially staying in the lead for a longer period. In **Tunable Consistency**, we discussed formulas that help us to find configurations where we have intersections between the node sets. One of the examples was to wait for just one node to acknowledge the write (and let the requests to the rest of the nodes finish asynchronously), and read from all the nodes. In other words, as long as we keep $ \mathbf{R} + \mathbf{W} > \mathbf{N} $, there’s at least one node in common between read and write sets.

Can we use a similar logic for consensus? It turns out that we can, and in Paxos we only require the group of nodes from the first phase (that elects a leader) to overlap with the group from the second phase (that participates in accepting proposals).

In other words, a quorum doesn't have to be defined as a majority, but only as a non-empty group of nodes. If we define the total number of participants as N, the number of nodes required for a propose phase to succeed as Q1, and the number of nodes required for the accept phase to succeed as Q2, we only need to ensure that Q1 + Q2 > N. 

Since the second phase is usually more common than the first one, Q2 can contain only N/2 acceptors, as long as Q1 is adjusted to be correspondingly larger (Q1 = N - Q2 + 1). This finding is an important observation crucial for understanding consensus. The algorithm that uses this approach is called **Flexible Paxos** [HOWARD16].

For example, if we have five acceptors, as long as we require collecting votes from four of them to win the election round, we can allow the leader to wait for responses from two nodes during the replication stage. Moreover, since there's an overlap between any subset consisting of two acceptors with the leader election quorum, we can submit proposals to disjoint sets of acceptors. Intuitively, this works because whenever a new leader is elected without the current one being aware of it, there will always be at least one acceptor that knows about the existence of the new leader.

Flexible Paxos allows trading availability for latency: we reduce the number of nodes participating in the second phase but have to collect more votes, requiring more participants to be available during the leader election phase. The good news is that this configuration can continue the replication phase and tolerate failures of up to N - Q2 nodes, as long as the current leader is stable and a new election round is not required.

> ### 💡 Beginner's Corner: Flexible Paxos Quorum Mathematics
> In classic Paxos, every phase must use a majority quorum ($Q > N/2$). The mathematical justification is that any two majorities of size $Q$ in a set of size $N$ must share at least one node in common ($2Q > N \implies Q \cap Q' \neq \emptyset$). This ensures that Phase 2 of a previous round intersects with Phase 1 of a subsequent round, and also that two concurrent Phase 2 rounds would intersect, preventing two different values from being committed at the same slot.
> 
> **Flexible Paxos** refines this by observing that we do not actually need *all* quorums to intersect with *all* other quorums. Specifically, we only need the quorum used to elect the leader in Phase 1 ($Q_1$) to intersect with the quorum used to replicate values in Phase 2 ($Q_2$). We do *not* need two Phase 2 quorums ($Q_2$) to intersect with each other, because a single, stable leader sequences all writes in Phase 2, meaning concurrent conflicting writes at the same slot are impossible.
> 
> Mathematically, we only require:
> $$Q_1 + Q_2 > N$$
> 
> This inequality guarantees that the leader election phase ($Q_1$) will always intersect with any previously committed write quorum ($Q_2$), ensuring the new leader discovers the committed value. This allows database designers to tune the system:
> - **Low Write Latency / High Write Throughput**: In a cluster of $N = 7$ nodes, we can set the write quorum $Q_2 = 2$ (the leader only waits for 1 follower to acknowledge a write, which is extremely fast). To satisfy the inequality, we must set the leader election quorum $Q_1 = 6$ ($6 + 2 = 8 > 7$). 
> - **Trade-off**: The leader election phase is now much heavier (requires 6 out of 7 nodes to be healthy) and less fault-tolerant to node failures during elections. However, since leader elections are rare and writes are frequent, this trade-off significantly improves steady-state write performance.

Another Paxos variant using the idea of intersecting quorums is **Vertical Paxos**. Vertical Paxos distinguishes between read and write quorums. These quorums must intersect. A leader has to collect a smaller read quorum for one or more lower-numbered proposals, and a larger write quorum for its own proposal [LAMPORT09]. [LAMPSON01] also distinguishes between the out and decision quorums, which translate to prepare and accept phases, and gives a quorum definition similar to Flexible Paxos.

### Generalized Solution to Consensus

Paxos might sometimes be a bit difficult to reason about: multiple roles, steps, and all the possible variations are hard to keep track of. But we can think of it in simpler terms. Instead of splitting roles between the participants and having decision rounds, we can use a simple set of concepts and rules to achieve the guarantees of a single-decree Paxos. We discuss this approach only briefly as this is a relatively new development [HOWARD19] — it’s important to know, but we’ve yet to see its implementations and practical applications.

We have a client and a set of servers. Each server has multiple registers. A register has an index identifying it, can be written only once, and it can be in one of three states:
* **unwritten**
* **containing a value**
* **containing nil** (a special empty value)

Registers with the same index located on different servers form a register set. Each register set can have one or more quorums. Depending on the state of the registers in it, a quorum can be in one of the undecided or decided states:

* **Any** (Undecided): Depending on future operations, this quorum set can decide on any value.
* **Maybe v** (Undecided): If this quorum reaches a decision, its decision can only be `v`.
* **None** (Decided): This quorum cannot decide on the value.
* **Decided v** (Decided): This quorum has decided on the value `v`.

The client exchanges messages with the servers and maintains a state table, where it keeps track of values and registers, and can infer decisions made by the quorums.

To maintain correctness, we have to limit how clients can interact with servers, which values they may write, and which they may not. In terms of reading values, the client can output the decided value only if it has read it from the quorum of servers in the same register set.

The writing rules are slightly more involved because, to guarantee algorithm safety, we have to preserve several invariants:
1. We have to make sure that the client doesn't just come up with new values: it is allowed to write a specific value to the register only if it has received it as input or has read it from a register.
2. Clients cannot write values that allow different quorums in the same register to decide on different values.
3. Lastly, clients cannot write values that override previous decisions made in the previous register sets (decisions made in register sets up to $ r - 1 $ have to be `None`, `Maybe v`, or `Decided v`).

#### Generalized Paxos Algorithm

Putting all these rules together, we can implement a generalized Paxos algorithm that achieves consensus over a single value using write-once registers [HOWARD19]. Let's say we have three servers `[S0, S1, S2]`, registers `[R0, R1, ...]`, and clients `[C0, C1, ...]`, where each client can only write to its assigned subset of registers. We use simple majority quorums for all registers (`{S0, S1}`, `{S0, S2}`, `{S1, S2}`).

The decision process here consists of two phases. The first phase ensures that it is safe to write a value to the register, and the second phase writes the value to the register:

##### Phase 1
The client checks if the register it is about to write is unwritten by sending a $ P1_A(\text{register}) $ command to the server. 
* If the register is unwritten, all registers up to `register - 1` are set to `nil`, which prevents clients from writing to previous registers.
* The server responds with a set of registers written so far.
* If it receives responses from the majority of servers, the client chooses either the nonempty value from the register with the largest index or its own value in case no value is present.
* Otherwise, it restarts the first phase.

##### Phase 2
The client notifies all servers about the value it has picked during the first phase by sending them $ P2_A(\text{register}, \text{value}) $. 
* If the majority of servers respond to this message, it can output the decision value.
* Otherwise, it starts again from phase 1.

Figure 14-9 shows this generalization of Paxos (adapted from [HOWARD19]). Client $ C_0 $ tries to commit value $ V $. During the first step, its state table is empty, and servers $ S_0 $ and $ S_1 $ respond with the empty register set, indicating that no registers were written so far. During the second step, it can submit its value $ V $, since no other value was written.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//3349c68e-8918-4463-bb9c-39fdd1ec74b0/markdown_0/imgs/img_in_chart_box_138_457_1047_922.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A22%3A04Z%2F-1%2F%2F20f075f63a036ec2ebd1c6bc61dd61cd81ffb1f4539c8d44bea945e8a6c7eab0" alt="Image" width="76%" /></div>


<div style="text-align: center;"><div style="text-align: center;">Figure 14-9. Generalization of Paxos.</div> </div>


At that point, any other client can query servers to find out the current state. Quorum $ \{S_0, S_1\} $ has reached the `Decided A` state, and quorums $ \{S_0, S_2\} $ and $ \{S_1, S_2\} $ have reached the `Maybe V` state for $ R_0 $, so $ C_1 $ chooses the value $ V $. At that point, no client can decide on a value other than $ V $.

This approach helps to understand the semantics of Paxos. Instead of thinking about the state from the perspective of interactions of remote actors (e.g., a proposer finding out whether or not an acceptor has already accepted a different proposal), we can think in terms of the last known state, making our decision process simple and removing possible ambiguities. Immutable state and message passing can also be easier to implement correctly.

We can also draw parallels with the original Paxos. For example:
* In a scenario in which the client finds that one of the previous register sets has the `Maybe V` decision, it picks up $ V $ and attempts to commit it again. This is similar to how a proposer in Paxos can propose a value after the failure of a previous proposer that was able to commit the value to at least one acceptor.
* Similarly, if in Paxos leader conflicts are resolved by restarting the vote with a higher proposal number, in the generalized algorithm, any unwritten lower-ranked registers are set to `nil`.

---

## Raft

Paxos was the consensus algorithm for over a decade, but in the distributed systems community, it has been known to be difficult to reason about. In 2013, a new algorithm called **Raft** appeared. The researchers who developed it wanted to create an algorithm that is easy to understand and implement. It was first presented in a paper titled "In Search of an Understandable Consensus Algorithm" [ONGARO14].

There’s enough inherent complexity in distributed systems, and having simpler algorithms is very desirable. Along with the paper, the authors released a reference implementation called LogCabin to resolve possible ambiguities and help future implementors gain a better understanding.

Locally, participants store a log containing the sequence of commands executed by the state machine. Since the inputs that processes receive are identical and logs contain the same commands in the same order, applying these commands to the state machine guarantees the same output. 

Raft simplifies consensus by making the concept of a **leader** a first-class citizen. A leader is used to coordinate state machine manipulation and replication. There are many similarities between Raft and atomic broadcast algorithms, as well as Multi-Paxos: a single leader emerges from replicas, makes atomic decisions, and establishes the message order.

Each participant in Raft can take one of three roles:

* **Candidate**: Leadership is a temporary condition, and any participant can take this role. To become a leader, the node first has to transition into a candidate state, and attempt to collect a majority of votes. If a candidate neither wins nor loses the election (the vote is split between multiple candidates and none of them has a majority of votes), the new term is slated and the election restarts.
* **Leader**: A current, temporary cluster leader that handles client requests and interacts with a replicated state machine. The leader is elected for a period called a **term**. Each term is identified by a monotonically increasing number and may continue for an arbitrary time period. A new leader is elected if the current one crashes, becomes unresponsive, or is suspected by other processes to have failed.
* **Follower**: A passive participant that persists log entries and responds to requests from the leader and candidates. The follower in Raft is a role similar to the acceptor and learner from Paxos. Every process begins as a follower.

To guarantee global partial ordering without relying on clock synchronization, time is divided into **terms** (also called epochs), during which the leader is unique and stable. Terms are monotonically numbered, and each command is uniquely identified by the term number and the message number within the term [HOWARD14].

It may happen that different participants disagree on which term is current, since they can find out about the new term at different times, or could have missed the leader election for one or multiple terms. Since each message contains a term identifier, if one of the participants discovers that its term is out-of-date, it updates its term to the higher-numbered one [ONGARO14]. 

This means that there may be several terms in flight at any given point in time, but the higher-numbered one wins in case of a conflict. A node updates its term only if it starts a new election process or finds out that its term is out-of-date.

On startup, or whenever a follower doesn’t receive messages from the leader and suspects that it has crashed, it starts the leader election process. A participant attempts to become a leader by transitioning into the candidate state and collecting votes from the majority of nodes.

Figure 14-10 shows a sequence diagram representing the main components of the Raft algorithm:

#### Leader Election
Candidate $ P_1 $ sends a `RequestVote` message to the other processes. This message includes the candidate's term, the last term known by it, and the ID of the last log entry it has observed. After collecting a majority of votes, the candidate is successfully elected as a leader for the term. Each process can give its vote to at most one candidate.

#### Periodic Heartbeats
The protocol uses a heartbeat mechanism to ensure the liveness of participants. The leader periodically sends heartbeats to all followers to maintain its term. If a follower doesn’t receive new heartbeats for a period called an **election timeout**, it assumes that the leader has failed and starts a new election.

#### Log Replication / Broadcast
The leader can repeatedly append new values to the replicated log by sending `AppendEntries` messages. The message includes the leader's term, index, and term of the log entry that immediately precedes the ones it's currently sending, and one or more entries to store.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//3349c68e-8918-4463-bb9c-39fdd1ec74b0/markdown_4/imgs/img_in_image_box_137_672_1049_874.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A22%3A06Z%2F-1%2F%2F654507355ad0c21e6365a2753bb56adcba01bf37b37397e79ad5666696b82e62" alt="Image" width="76%" /></div>


<div style="text-align: center;"><div style="text-align: center;">Figure 14-10. Raft consensus algorithm summary.</div> </div>

### Leader Role in Raft

A leader can be elected only from the nodes holding all committed entries: if during the election, the follower's log information is more up-to-date (in other words, has a higher term ID, or a longer log entry sequence, if terms are equal) than the candidate's, its vote is denied.

To win the vote, a candidate has to collect a majority of votes. Entries are always replicated in order, so it is always enough to compare IDs of the latest entries to understand whether or not one of the participants is up-to-date.

> ### 💡 Beginner's Corner: Raft Election Safety and Log Up-to-Dateness
> In Raft, the **Leader Completeness** safety property guarantees that if a log entry is committed in a given term, that entry will be present in the logs of the leaders for all higher-numbered terms. Raft achieves this without needing to backfill or pull missing entries from followers to the leader; instead, it enforces a strict rule: **a node can only be elected leader if its log is at least as up-to-date as any other node in the majority that elects it.**
> 
> To enforce this, when a candidate requests a vote, it includes the index and term of its last log entry. A follower compares the candidate's last entry with its own:
> 1. **Term Comparison**: If the candidate's last entry has a lower term than the follower's last entry, the candidate is out-of-date, and the follower denies its vote. If the candidate's term is higher, the candidate is more up-to-date, and the vote is granted.
> 2. **Length Comparison**: If the terms of their last entries are identical, the follower compares the log lengths. If the follower has a longer log (more entries) than the candidate, the candidate is out-of-date, and the vote is denied. Otherwise, the candidate is at least as up-to-date, and the vote is granted.
> 
> Mathematically, since any committed entry must be present on a majority of nodes, and any candidate must collect votes from a majority of nodes to win the election, the candidate's election quorum must overlap with the quorum of nodes that received the committed entry. The intersecting node(s) will have the committed entry in their logs. Since their logs contain that committed entry, any candidate lacking that entry will have an out-of-date log compared to them, and those nodes will deny their votes, preventing the under-replicated candidate from ever becoming leader.
> 
> ### 🚶‍♂️ Step-by-Step Breakdown: Raft Leader Election and Log Matching
> When a Raft follower's election timeout fires, it initiates a leader election and attempts to synchronize logs:
> 
> #### 1. Election Initiation
> - The follower increments its current term (e.g., from Term 2 to Term 3), transitions to the **Candidate** state, and votes for itself.
> - It broadcasts a `RequestVote(term=3, candidateId=P_1, lastLogIndex=45, lastLogTerm=2)` to all other nodes.
> 
> #### 2. Vote Evaluation by Followers
> - A follower $P_2$ receives the `RequestVote`.
> - $P_2$ compares the candidate's `lastLogTerm` and `lastLogIndex` against its own last entry (which is at index 44, term 2).
>   - Since the terms are equal (both 2), and the candidate's index ($45$) is greater than or equal to $P_2$'s index ($44$), $P_2$ concludes the candidate is up-to-date.
>   - $P_2$ grants its vote, updates its current term to 3, and resets its election timer.
> - Follower $P_3$ receives the `RequestVote`. Its last log entry is at index 46, term 2.
>   - Since $P_3$'s log is longer than the candidate's (index 46 > 45), $P_3$ denies its vote to $P_1$.
> 
> #### 3. Leader Establishment
> - Once the candidate collects votes from a majority of nodes (e.g., 3 out of 5), it transitions to the **Leader** state.
> - It immediately broadcasts empty `AppendEntries` heartbeats to all nodes to assert its authority and prevent them from starting new elections.
> 
> #### 4. Log Reconciliation (Log Matching Property)
> - For each follower, the leader maintains a `nextIndex` (the index of the next log entry the leader will send to that follower, initialized to `leaderLastLogIndex + 1`) and a `matchIndex` (the highest index known to be replicated on that follower, initialized to 0).
> - When sending new entries, the leader includes `prevLogIndex` and `prevLogTerm` (the index and term of the entry immediately preceding the new ones).
> - If a follower receives an `AppendEntries` and finds that its log does not have an entry at `prevLogIndex` matching `prevLogTerm`, it rejects the message.
> - The leader then decrements `nextIndex` for that follower and retries until it finds where their histories match. Once the match point is found, the follower's conflicting entries are overwritten with the leader's entries, ensuring both logs become identical.

Once elected, the leader has to accept client requests (which can also be forwarded to it from other nodes) and replicate them to the followers. This is done by appending the entry to its log and sending it to all the followers in parallel.

When a follower receives an `AppendEntries` message, it appends the entries from the message to the local log and acknowledges the message, letting the leader know that it was persisted. As soon as enough replicas send their acknowledgments, the entry is considered committed and is marked correspondingly in the leader's log.

Since only the most up-to-date candidates can become a leader, followers never have to bring the leader up-to-date, and log entries are only flowing from leader to follower and not vice versa.

Figure 14-11 shows this process:
* a) A new command `x = 8` is appended to the leader's log.
* b) Before the value can be committed, it has to be replicated to the majority of participants.
* c) As soon as the leader is done with replication, it commits the value locally.
* d) The commit decision is replicated to the followers.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//29e0c9b3-3346-44a9-8f04-496dbc6780be/markdown_1/imgs/img_in_image_box_150_162_1049_496.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A22%3A04Z%2F-1%2F%2F07c6ce6d33aff73af29d449eec91ed6c6b78e49f50cb3e6b83e6ebbf546464c6" alt="Image" width="75%" /></div>


<div style="text-align: center;"><div style="text-align: center;">Figure 14-11. Procedure of a commit in Raft with $ P_1 $ as a leader.</div> </div>


Figure 14-12 shows an example of a consensus round where $ P_1 $ is the leader, which has the most recent view of the events. The leader proceeds by replicating the entries to the followers and committing them after collecting acknowledgments. Committing an entry also commits all entries preceding it in the log. Only the leader can make a decision on whether or not the entry can be committed. 

Each log entry is marked with a term ID (a number in the top-right corner of each log entry box) and a log index, identifying its position in the log. Committed entries are guaranteed to be replicated to the quorum of participants and are safe to be applied to the state machine in the order they appear in the log.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//29e0c9b3-3346-44a9-8f04-496dbc6780be/markdown_2/imgs/img_in_image_box_133_145_1053_967.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A22%3A05Z%2F-1%2F%2Fbcb1ed13e6bdd2b94dd8be8dbc422bb9fed0ee6421578b28c377366c904f5374" alt="Image" width="77%" /></div>


<div style="text-align: center;"><div style="text-align: center;">Figure 14-12. Raft state machine.</div> </div>

### Failure Scenarios

When multiple followers decide to become candidates, and no candidate can collect a majority of votes, the situation is called a **split vote**. Raft uses randomized timers to reduce the probability of multiple subsequent elections ending up in a split vote. One of the candidates can start the next election round earlier and collect enough votes, while the others sleep and give way to it. This approach speeds up the election without requiring any additional coordination between candidates.

Followers may be down or slow to respond, and the leader has to make the best effort to ensure message delivery. It can try sending messages again if it doesn’t receive an acknowledgment within the expected time bounds. As a performance optimization, it can send multiple messages in parallel.

Since entries replicated by the leader are uniquely identified, repeated message delivery is guaranteed not to break the log order. Followers deduplicate messages using their sequence IDs, ensuring that double delivery has no undesired side effects.

Sequence IDs are also used to ensure log ordering. A follower rejects a higher-numbered entry if the ID and term of the entry that immediately precedes it, sent by the leader, do not match the highest entry according to its own records. If entries in two logs on different replicas have the same term and the same index, they store the same command and all entries that precede them are the same.

Raft guarantees to never show an uncommitted message as a committed one, but due to network or replica slowness, already committed messages can still be seen as in progress, which is a rather harmless property and can be worked around by retrying a client command until it is finally committed [HOWARD14].

For failure detection, the leader has to send heartbeats to the followers. This way, the leader maintains its term. When one of the nodes notices that the current leader is down, it attempts to initiate an election. 

The newly elected leader has to restore the state of the cluster to the last known up-to-date log entry. It does so by finding common ground (the highest log entry on which both the leader and follower agree) and ordering followers to discard all (uncommitted) entries appended after this point. It then sends the most recent entries from its log, overwriting the followers' history. The leader's own log records are never removed or overwritten: it can only append entries to its own log.

Summing up, the Raft algorithm provides the following guarantees:
* Only one leader can be elected at a time for a given term; no two leaders can be active during the same term.
* The leader does not remove or reorder its log contents; it only appends new messages to it.
* Committed log entries are guaranteed to be present in logs for subsequent leaders and cannot get reverted, since before the entry is committed it is known to be replicated by the leader.
* All messages are identified uniquely by the message and term IDs; neither current nor subsequent leaders can reuse the same identifier for a different entry.

Since its appearance, Raft has become very popular and is currently used in many databases and other distributed systems, including CockroachDB, `etcd`, and Consul. This can be attributed to its simplicity, but also may mean that Raft lives up to the promise of being a reliable consensus algorithm.

---

## Byzantine Consensus

All the consensus algorithms we have been discussing so far assume non-Byzantine failures (see **Arbitrary Faults**). In other words, nodes execute the algorithm in “good faith” and do not try to exploit it or forge the results.

As we will see, this assumption allows achieving consensus with a smaller number of available participants and with fewer round-trips required for a commit. However, distributed systems are sometimes deployed in potentially adversarial environments, where the nodes are not controlled by the same entity, and we need algorithms that can ensure a system can function correctly even if some nodes behave erratically or even maliciously. Besides ill intentions, Byzantine failures can also be caused by bugs, misconfiguration, hardware issues, or data corruption.

Most Byzantine consensus algorithms require $ N^2 $ messages to complete an algorithm step, where N is the size of the quorum, since each node in the quorum has to communicate with each other. This is required to cross-validate each step against other nodes, since nodes cannot rely on each other or on the leader and have to verify other nodes' behaviors by comparing returned results with majority responses.

We’ll only discuss one Byzantine consensus algorithm here: **Practical Byzantine Fault Tolerance (PBFT)** [CASTRO99]. PBFT assumes independent node failures (i.e., failures can be coordinated, but the entire system cannot be taken over at once, or at least with the same exploit method). The system makes weak synchrony assumptions, like how you would expect a network to behave normally: failures may occur, but they are not indefinite and are eventually recovered from.

All communication between the nodes is encrypted, which serves to prevent message forging and network attacks. Replicas know one another's public keys to verify identities and encrypt messages. Faulty nodes may leak information from inside the system, since, even though encryption is used, every node needs to interpret message contents to react upon them. This doesn't undermine the algorithm, since it serves a different purpose.

### PBFT Algorithm

For PBFT to guarantee both safety and liveness, no more than $ (n - 1)/3 $ replicas can be faulty (where $ n $ is the total number of participants). For a system to sustain $ f $ compromised nodes, it is required to have at least $ n = 3f + 1 $ nodes. 

This is the case because a majority of nodes have to agree on the value: $ f $ replicas might be faulty, and there might be $ f $ replicas that are not responding but may not be faulty (for example, due to a network partition, power failure, or maintenance). The algorithm has to be able to collect enough responses from nonfaulty replicas to still outnumber those from the faulty ones.

> ### 💡 Beginner's Corner: PBFT Quorum Mathematics and Equivocation Prevention
> In crash-tolerant consensus (like Paxos or Raft), we assume nodes only fail by stopping (crashing), and that they never send corrupt or malicious messages. In such systems, we only need $N \ge 2f + 1$ nodes to tolerate $f$ failures, because any two majorities of size $f+1$ must intersect by at least one node, which is guaranteed to be honest and up-to-date.
> 
> In Byzantine consensus, nodes can exhibit arbitrary (Byzantine) behavior: they can crash, lie, forge signatures, or send conflicting messages to different peers (a behavior called **equivocation**, where a malicious primary proposes value $V_1$ to node $A$ and value $V_2$ to node $B$ to split the cluster).
> 
> To tolerate $f$ Byzantine nodes, PBFT requires a minimum of:
> $$N \ge 3f + 1$$
> 
> Here is the mathematical proof of why $3f + 1$ is the absolute minimum required:
> 1. **Liveness**: If $f$ nodes are faulty and completely stop responding, the system must still make progress. Therefore, any quorum we wait for can be at most $N - f$ nodes.
> 2. **Safety**: Suppose $f$ nodes are faulty, but instead of stopping, they actively lie and collude. If the system proceeds with a quorum of $N - f$ nodes, that quorum could contain all $f$ faulty nodes. The number of honest nodes in that quorum is $(N - f) - f = N - 2f$.
> 3. To guarantee safety, the honest nodes in our active quorum must strictly outnumber the faulty nodes, ensuring the honest nodes can dominate the vote:
>    $$N - 2f > f \implies N > 3f \implies N_{\min} = 3f + 1$$
> 
> This $3f + 1$ quorum size ensures that even if $f$ nodes crash, the remaining $2f + 1$ nodes can still achieve consensus, and even if $f$ nodes actively lie, they are mathematically guaranteed to be in the minority of any active quorum, preventing them from committing conflicting values.

Consensus properties for PBFT are similar to those of other consensus algorithms: all nonfaulty replicas have to agree both on the set of received values and their order, despite possible failures.

To distinguish between cluster configurations, PBFT uses **views**. In each view, one of the replicas is the **primary**, and the rest of them are considered **backups**. All nodes are numbered consecutively, and the index of the primary node is `v mod N`, where `v` is the view ID and `N` is the number of nodes in the current configuration. The view can change in cases when the primary fails. 

Clients execute their operations against the primary. The primary broadcasts the requests to the backups, which execute the requests and send a response back to the client. The client waits for $ f + 1 $ replicas to respond with the same result for any operation to succeed.

After the primary receives a client request, protocol execution proceeds in three phases:

#### 1. Pre-prepare
The primary broadcasts a message containing a view ID, a unique, monotonically increasing identifier, a payload (client request), and a payload digest. Digests are computed using a strong, collision-resistant hash function and are signed by the sender. The backup accepts the message if its view matches the primary view and the client request hasn’t been tampered with: the calculated payload digest matches the received one.

#### 2. Prepare
If the backup accepts the pre-prepare message, it enters the prepare phase and starts broadcasting `Prepare` messages containing a view ID, message ID, and a payload digest, but without the payload itself, to all other replicas (including the primary). Replicas can move past the prepare state only if they receive $ 2f $ prepares from different backups that match the message received during pre-prepare: they have to have the same view, same ID, and digest.

#### 3. Commit
After that, the backup moves to the commit phase, where it broadcasts `Commit` messages to all other replicas and waits to collect $ 2f + 1 $ matching `Commit` messages (possibly including its own) from the other participants.

A digest in this case is used to reduce the message size during the prepare phase, since it’s not necessary to rebroadcast an entire payload for verification, as the digest serves as a payload summary. Cryptographic hash functions are resistant to collisions: it is difficult to produce two values that have the same digest, let alone two messages with matching digests that make sense in the context of the system. In addition, digests are signed to make sure that the digest itself is coming from a trusted source.

The number $ 2f $ is important, since the algorithm has to make sure that at least $ f + 1 $ nonfaulty replicas respond to the client.

Figure 14-13 shows a sequence diagram of a normal-case PBFT algorithm round: the client sends a request to $ P_1 $, and nodes move between phases by collecting a sufficient number of matching responses from properly behaving peers. $ P_4 $ may have failed or could've responded with unmatching messages, so its responses wouldn't have been counted.

> ### 🚶‍♂️ Step-by-Step Breakdown: PBFT Consensus Cycle
> A normal-case PBFT round (without view changes) executes across three distinct communication phases to commit a client request safely:
> 
> #### 1. Pre-Prepare Phase (Primary to Backups)
> - **Client Request**: A client sends a request $m$ to the primary node $P_1$.
> - **Proposal**: The primary assigns a sequence number $s$ and view $v$ to the request. It computes a cryptographic digest $d = \text{hash}(m)$ and broadcasts a `<<PRE-PREPARE, v, s, d>_sig_P1, m>` message to all backups.
> - **Validation**: Each backup receives the message and verifies that:
>   1. The primary's signature is valid.
>   2. The view $v$ matches its current view.
>   3. It has not accepted a different digest for sequence $s$ in view $v$.
>   4. The hash of the payload $m$ matches the digest $d$.
> 
> #### 2. Prepare Phase (All-to-All Broadcast)
> - **Broadcast**: If backup $i$ validates the pre-prepare, it broadcasts a `<PREPARE, v, s, d, i>_sig_i` message to all other replicas.
> - **Quorum Collection**: Replicas wait to collect $2f$ matching `PREPARE` messages from different backups (plus their own pre-prepare/prepare state, making $2f + 1$ total votes).
> - **Equivocation Check**: This phase is crucial. Because backups exchange prepare messages directly with each other, they verify that a quorum of nodes has received the *exact same* proposal (same digest $d$ for sequence $s$) from the primary. If the primary attempted to equivocate (send $d_1$ to node $A$ and $d_2$ to node $B$), the nodes would see conflicting prepare messages and refuse to proceed, blocking the malicious primary.
> 
> #### 3. Commit Phase (All-to-All Broadcast)
> - **Broadcast**: Once a replica has $2f + 1$ matching prepares, it enters the "Prepared" state, proving that the request is ordered and locked for this view. It then broadcasts a `<COMMIT, v, s, d, i>_sig_i` message to all replicas.
> - **Quorum Collection**: Replicas wait to collect $2f + 1$ matching `COMMIT` messages from different nodes. This proves that a quorum of honest nodes has successfully entered the "Prepared" state, meaning the request is guaranteed to survive even if a view change occurs.
> - **Execution and Reply**: Once a replica has $2f + 1$ commits, it executes the request locally against its state machine and sends a signed reply back to the client.
> - **Client Confirmation**: The client waits to receive $f + 1$ matching replies from different replicas. Since at most $f$ replicas can be faulty, receiving $f + 1$ identical replies mathematically guarantees that at least one honest node has executed and committed the transaction.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//1f152bc4-7f3f-4374-8dff-1b96e1ffdfd9/markdown_3/imgs/img_in_chart_box_140_161_1050_452.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A22%3A06Z%2F-1%2F%2F13c698ec4f442dcd6a4c81311793eef2355d3fc654bf7cda58d642a81405619b" alt="Image" width="76%" /></div>


<div style="text-align: center;"><div style="text-align: center;">Figure 14-13. PBFT consensus, normal-case operation.</div> </div>


During the prepare and commit phases, nodes communicate by sending messages to each other node and waiting for the messages from the corresponding number of other nodes, to check if they match and make sure that incorrect messages are not broadcasted. Peers cross-validate all messages so that only nonfaulty nodes can successfully commit messages. If a sufficient number of matching messages cannot be collected, the node doesn't move to the next step.

When replicas collect enough commit messages, they notify the client, finishing the round. The client cannot be certain about whether or not execution was fulfilled correctly until it receives $ f + 1 $ matching responses.

View changes occur when replicas notice that the primary is inactive and suspect that it might have failed. Nodes that detect a primary failure stop responding to further messages (apart from checkpoint and view-change related ones), broadcast a view change notification, and wait for confirmations. When the primary of the new view receives $ 2f $ view change events, it initiates a new view.

To reduce the number of messages in the protocol, clients can collect $ 2f + 1 $ matching responses from nodes that tentatively execute a request (e.g., after they’ve collected a sufficient number of matching `Prepared` messages). If the client cannot collect enough matching tentative responses, it retries and waits for $ f + 1 $ nontentative responses as described previously.

Read-only operations in PBFT can be done in just one round-trip. The client sends a read request to all replicas. Replicas execute the request in their tentative states, after all ongoing state changes to the read value are committed, and respond to the client. After collecting $ 2f + 1 $ responses with the same value from different replicas, the operation completes.

### Recovery and Checkpointing

Replicas save accepted messages in a stable log. Every message has to be kept until it has been executed by at least $ f + 1 $ nodes. This log can be used to get other replicas up to speed in case of a network partition, but recovering replicas need some means of verifying that the state they receive is correct, since otherwise recovery can be used as an attack vector.

To show that the state is correct, nodes compute a digest of the state for messages up to a given sequence number. Nodes can compare digests, verify state integrity, and make sure that messages they received during recovery add up to a correct final state. This process is too expensive to perform on every request.

After every N requests, where N is a configurable constant, the primary makes a stable checkpoint, where it broadcasts the latest sequence number of the latest request whose execution is reflected in the state, and the digest of this state. It then waits for $ 2f + 1 $ replicas to respond. 

These responses constitute a proof for this checkpoint, and a guarantee that replicas can safely discard state for all pre-prepare, prepare, commit, and checkpoint messages up to the given sequence number.

Byzantine fault tolerance is essential to understand and is used in storage systems deployed in potentially adversarial networks. Most of the time, it is enough to authenticate and encrypt internode communication, but when there’s no trust between the parts of the system, algorithms similar to PBFT have to be employed.

Since algorithms resistant to Byzantine faults impose significant overhead in terms of the number of exchanged messages, it is important to understand their use cases. Other protocols, such as the ones described in [BAUDET19] and [BUCHMAN18], attempt to optimize the PBFT algorithm for systems with a large number of participants.

---

## Summary

Consensus algorithms are one of the most interesting yet most complex subjects in distributed systems. Over the last few years, new algorithms and many implementations of the existing algorithms have emerged, which proves the rising importance and popularity of the subject.

In this chapter, we discussed the classic Paxos algorithm, and several variants of Paxos, each one improving its different properties:

* **Multi-Paxos**: Allows a proposer to retain its role and replicate multiple values instead of just one.
* **Fast Paxos**: Allows us to reduce the number of messages by using fast rounds, when acceptors can proceed with messages from proposers other than the established leader.
* **EPaxos**: Establishes event order by resolving dependencies between submitted messages.
* **Flexible Paxos**: Relaxes quorum requirements and only requires a quorum for the first phase (voting) to intersect with a quorum for the second phase (replication).

Raft simplifies the terms in which consensus is described and makes leadership a first-class citizen in the algorithm. Raft separates log replication, leader election, and safety.

To guarantee consensus safety in adversarial environments, Byzantine fault-tolerant algorithms should be used; for example, PBFT. In PBFT, participants cross-validate one another's responses and only proceed with execution steps when there's enough nodes that obey the prescribed algorithm rules.

---

### Further Reading

If you’d like to learn more about the concepts mentioned in this chapter, you can refer to the following sources:

##### Atomic broadcast
* Junqueira, Flavio P., Benjamin C. Reed, and Marco Serafini. "Zab: High-performance broadcast for primary-backup systems." 2011. In *Proceedings of the 2011 IEEE/IFIP 41st International Conference on Dependable Systems & Networks* (DSN '11): 245-256.
* Hunt, Patrick, Mahadev Konar, Flavio P. Junqueira, and Benjamin Reed. 2010. "ZooKeeper: wait-free coordination for internet-scale systems." In *Proceedings of the 2010 USENIX conference on USENIX annual technical conference* (USENIXATC'10): 11.
* Oki, Brian M., and Barbara H. Liskov. 1988. "Viewstamped Replication: A New Primary Copy Method to Support Highly-Available Distributed Systems." In *Proceedings of the seventh annual ACM Symposium on Principles of distributed computing* (PODC '88): 8-17.

##### Classic Paxos
* Van Renesse, Robbert, Nicolas Schiper, and Fred B. Schneider. 2014. "Vive la Différence: Paxos vs. Viewstamped Replication vs. Zab."
* Lamport, Leslie. 1998. "The part-time parliament." *ACM Transactions on Computer Systems* 16, no. 2 (May): 133-169.
* Lamport, Leslie. 2001. "Paxos made simple." *ACM SIGACT News* 32, no. 4: 51-58.
* Lamport, Leslie. 2005. "Generalized Consensus and Paxos." Technical Report MSR-TR-2005-33. Microsoft Research, Mountain View, CA.
* Primi, Marco. 2009. "Paxos made code: Implementing a high throughput Atomic Broadcast." (Libpaxos code: https://bitbucket.org/sciascid/libpaxos/src/master/).

##### Fast Paxos
* Lamport, Leslie. 2005. "Fast Paxos." 14 July 2005. Microsoft Research.

##### Multi-Paxos
* Chandra, Tushar D., Robert Griesemer, and Joshua Redstone. 2007. "Paxos made live: an engineering perspective." In *Proceedings of the twenty-sixth annual ACM symposium on Principles of distributed computing* (PODC '07): 398-407.
* Van Renesse, Robbert and Deniz Altinbuken. 2015. "Paxos Made Moderately Complex." *ACM Computing Surveys* 47, no. 3 (February): Article 42. https://doi.org/10.1145/2673577.

##### EPaxos
* Moraru, Iulian, David G. Andersen, and Michael Kaminsky. 2013. "There is more consensus in Egalitarian parliaments." In *Proceedings of the Twenty-Fourth ACM Symposium on Operating Systems Principles* (SOSP '13): 358-372.
* Moraru, I., D. G. Andersen, and M. Kaminsky. 2013. "A proof of correctness for Egalitarian Paxos." Technical report, Parallel Data Laboratory, Carnegie Mellon University, Aug. 2013.

##### Raft
* Ongaro, Diego, and John Ousterhout. 2014. “In search of an understandable consensus algorithm.” In *Proceedings of the 2014 USENIX conference on USENIX Annual Technical Conference* (USENIX ATC'14), Garth Gibson and Nickolai Zeldovich (Eds.): 305-320.
* Howard, H. 2014. "ARC: Analysis of Raft Consensus." Technical Report UCAM-CL-TR-857, University of Cambridge, Computer Laboratory, July 2014.
* Howard, Heidi, Malte Schwarzkopf, Anil Madhavapeddy, and Jon Crowcroft. 2015. "Raft Refloated: Do We Have Consensus?" *SIGOPS Operating Systems Review* 49, no. 1 (January): 12-21. https://doi.org/10.1145/2723872.2723876.

##### Recent developments
* Howard, Heidi and Richard Mortier. 2019. “A Generalised Solution to Distributed Consensus.” 18 Feb 2019.

---

## Part II Conclusion

Performance and scalability are important properties of any database system. The storage engine and node-local read-write path can have a larger impact on the performance of the system: how quickly it can process requests locally. At the same time, a subsystem responsible for communication in the cluster often has a larger impact on the scalability of the database system: maximum cluster size and capacity. 

However, the storage engine can only be used for a limited number of use cases if it's not scalable and its performance degrades as the dataset grows. At the same time, putting a slow atomic commit protocol on top of the fastest storage engine will not yield good results.

Distributed, cluster-wide, and node-local processes are interconnected and have to be considered holistically. When designing a database system, you have to consider how different subsystems fit and work together.

Part II began with a discussion of how distributed systems are different from single-node applications, and which difficulties are to be expected in such environments. We discussed the basic distributed system building blocks, different consistency models, and several important classes of distributed algorithms, some of which can be used to implement these consistency models:

#### Failure Detection
Identify remote process failures accurately and efficiently.

#### Leader Election
Quickly and reliably choose a single process to temporarily serve as a coordinator.

#### Dissemination
Reliably distributes information using peer-to-peer communication.

#### Anti-entropy
Identify and repair state divergence between the nodes.

#### Distributed Transactions
Execute a series of operations against multiple partitions atomically.

#### Consensus
Reach an agreement between remote participants while tolerating process failures.

These algorithms are used in many database systems, message queues, schedulers, and other important infrastructure software. Using the knowledge from this book, you’ll be able to better understand how they work, which, in turn, will help to make better decisions about which software to use and identify potential problems.

---

### Further Reading

At the end of each chapter, you can find resources related to the material presented in the chapter. Here, you'll find books you can address for further study, covering both concepts mentioned in this book and other concepts. This list is not meant to be complete, but these sources contain a lot of important and useful information relevant for database systems enthusiasts, some of which is not covered in this book:

##### Database systems
* Bernstein, Philip A., Vassco Hadzilacos, and Nathan Goodman. 1987. *Concurrency Control and Recovery in Database Systems*. Boston: Addison-Wesley Longman.
* Korth, Henry F. and Abraham Silberschatz. 1986. *Database System Concepts*. New York: McGraw-Hill.
* Gray, Jim and Andreas Reuter. 1992. *Transaction Processing: Concepts and Techniques* (1st Ed.). San Francisco: Morgan Kaufmann.
* Stonebraker, Michael and Joseph M. Hellerstein (Eds.). 1998. *Readings in Database Systems* (3rd Ed.). San Francisco: Morgan Kaufmann.
* Weikum, Gerhard and Gottfried Vossen. 2001. *Transactional Information Systems: Theory, Algorithms, and the Practice of Concurrency Control and Recovery*. San Francisco: Morgan Kaufmann.
* Ramakrishnan, Raghu and Johannes Gehrke. 2002. *Database Management Systems* (3rd Ed.). New York: McGraw-Hill.
* Garcia-Molina, Hector, Jeffrey D. Ullman, and Jennifer Widom. 2008. *Database Systems: The Complete Book* (2nd Ed.). Upper Saddle River, NJ: Prentice Hall.
* Bernstein, Philip A. and Eric Newcomer. 2009. *Principles of Transaction Processing* (2nd Ed.). San Francisco: Morgan Kaufmann.
* Elmasri, Ramez and Shamkant Navathe. 2010. *Fundamentals of Database Systems* (6th Ed.). Boston: Addison-Wesley.
* Lake, Peter and Paul Crowther. 2013. *Concise Guide to Databases: A Practical Introduction*. New York: Springer.
* Härder, Theo, Caetano Sauer, Goetz Graefe, and Wey Guy. 2015. "Instant recovery with write-ahead logging." *Datenbank-Spektrum*.

##### Distributed systems
* Lynch, Nancy A. *Distributed Algorithms*. 1996. San Francisco: Morgan Kaufmann.
* Attiya, Hagit, and Jennifer Welch. 2004. *Distributed Computing: Fundamentals, Simulations and Advanced Topics*. Hoboken, NJ: John Wiley & Sons.
* Birman, Kenneth P. 2005. *Reliable Distributed Systems: Technologies, Web Services, and Applications*. Berlin: Springer-Verlag.
* Cachin, Christian, Rachid Guerraoui, and Luis Rodrigues. 2011. *Introduction to Reliable and Secure Distributed Programming* (2nd Ed.). New York: Springer.
* Fokkink, Wan. 2013. *Distributed Algorithms: An Intuitive Approach*. The MIT Press.
* Ghosh, Sukumar. *Distributed Systems: An Algorithmic Approach* (2nd Ed.). Chapman & Hall/CRC.
* Tanenbaum, Andrew S. and Maarten van Steen. 2017. *Distributed Systems: Principles and Paradigms* (3rd Ed.). Boston: Pearson.

##### Operating databases
* Beyer, Betsy, Chris Jones, Jennifer Petoff, and Niall Richard Murphy. 2016. *Site Reliability Engineering: How Google Runs Production Systems* (1st Ed.). Boston: O'Reilly Media.
* Blank-Edelman, David N. 2018. *Seeking SRE*. Boston: O'Reilly Media.
* Campbell, Laine and Charity Majors. 2017. *Database Reliability Engineering: Designing and Operating Resilient Database Systems* (1st Ed.). Boston: O'Reilly Media.
* Sridharan, Cindy. 2018. *Distributed Systems Observability: A Guide to Building Robust Systems*. Boston: O'Reilly Media.
