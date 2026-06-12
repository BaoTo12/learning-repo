# Module 03: Consumer Group Coordination & Liveliness

To share work and scale read throughput horizontally, Kafka consumers collaborate in **Consumer Groups**. The broker cluster assigns a dedicated coordinator to monitor consumer status, coordinate partition distributions, and orchestrate rebalances. This module details the consumer group protocol, liveliness timeouts, and the configuration of static membership to eliminate transient rebalance overhead.

---

## 1. Consumer Group Mechanics and the Coordinator

When multiple consumers configure the same `group.id`, they form a single logical consumer group.

```
                  ┌─────────────────────────────────┐
                  │        GROUP COORDINATOR        │
                  │  (Broker designated for Group)  │
                  └─────────▲──────────────▲────────┘
                            │              │
                   Heartbeats / Status     │ JoinGroup / SyncGroup
                            │              │
┌───────────────────────────┴──┐        ┌──┴──────────────────────────┐
│          CONSUMER 1          │        │          CONSUMER 2         │
│        (Group Leader)        │        │          (Member)           │
└──────────────────────────────┘        └─────────────────────────────┘
```

### 1.1 The Group Coordinator Broker
The **Group Coordinator** is a specific broker within the Kafka cluster assigned to manage a subset of consumer groups.
*   **Routing**: The coordinator broker is selected based on a hash of the group ID:

$$\text{Coordinator Partition} = \text{hash}(\text{group.id}) \pmod{\text{Total Partitions of \_\_consumer\_offsets}}$$

The broker hosting the leader of that partition becomes the Group Coordinator.
*   **Role**: It tracks group membership, monitors client heartbeats, and notifies the group when a rebalance is required.

### 1.2 The Group Leader Consumer
During a rebalance, the Group Coordinator does not calculate the partition assignments itself. That responsibility is delegated to the first consumer that connects, designated as the **Group Leader**.
1.  All consumers send a `JoinGroup` request to the coordinator.
2.  The coordinator elects the Group Leader and sends it the full metadata list of active members and target topic-partitions.
3.  The Group Leader runs the configured partition assignor algorithm to generate the target mapping.
4.  The Group Leader sends the assignments back to the coordinator in a `SyncGroup` request.
5.  The coordinator distributes the assignments to all group members.

---

## 2. Liveliness Tuning: Session Timeouts vs. Poll Intervals

To detect when a consumer process has crashed, hung, or lost connection, Kafka uses two distinct timeout thresholds:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        CONSUMER PROCESS                                │
├───────────────────────────────────┬────────────────────────────────────┤
│         HEARTBEAT THREAD          │      MAIN APPLICATION THREAD       │
│  Sends periodic light heartbeats  │       Polls and processes batches  │
│      to the Group Coordinator     │        from the Kafka brokers      │
├───────────────────────────────────┼────────────────────────────────────┤
│  Monitored by: session.timeout.ms │ Monitored by: max.poll.interval.ms │
└───────────────────────────────────┴────────────────────────────────────┘
```

### 2.1 Heartbeat Thread and `session.timeout.ms`
The consumer client runs a separate, lightweight background thread dedicated to sending periodic heartbeat signals to the Group Coordinator.
*   **`heartbeat.interval.ms`** (Default: 3000 ms / 3 seconds): How frequently the thread sends heartbeats.
*   **`session.timeout.ms`** (Default: 45000 ms / 45 seconds): The maximum time the coordinator will wait without receiving a heartbeat before marking the consumer dead.
*   **Usage**: Detects sudden process crashes, JVM halts, or network failures.

### 2.2 Main Processing Thread and `max.poll.interval.ms`
This threshold monitors the health of the application's processing thread executing the poll-and-process loop.
*   **`max.poll.interval.ms`** (Default: 300000 ms / 5 minutes): The maximum time allowed between successive calls to `consumer.poll()`.
*   **Usage**: Detects soft failures, such as when the main processing thread is alive but blocked (e.g., waiting indefinitely for a database lock or hung in an infinite loop).
*   **Failure Behavior**: If the application thread fails to call `poll()` within this window, the background heartbeat thread sends a explicit `LeaveGroup` request to the coordinator, triggering a rebalance.

---

## 3. Static Membership (`group.instance.id`)

In cloud-native environments (e.g., Kubernetes), pods frequently restart during rolling updates, health checks, or node migrations. Under default settings, these transient restarts trigger two rebalances: one when the pod stops and sends a `LeaveGroup` request, and another when the pod restarts and sends a `JoinGroup` request. This causes unnecessary processing downtime.

**Static Membership** eliminates this rebalance overhead for transient restarts.

```
Consumer A restarts (group.instance.id = "srv-node-1")
  1. Stops/restarts (No LeaveGroup request is sent)
  2. Partitions remain unassigned during session.timeout.ms
  3. Re-joins within timeout presenting same ID -> Re-binds original partitions instantly (No rebalance)
```

### 3.1 Configuration
To enable static membership, assign a unique instance identifier to each consumer instance:

```java
Properties props = new Properties();
props.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, "localhost:9092");
props.put(ConsumerConfig.GROUP_ID_CONFIG, "retail-order-service");

// Configure Static Membership ID (Must be unique per consumer instance)
props.put(ConsumerConfig.GROUP_INSTANCE_ID_CONFIG, "retail-pod-01");

// Set session timeout to a window long enough to cover a container restart
// (e.g. 2 minutes)
props.put(ConsumerConfig.SESSION_TIMEOUT_MS_CONFIG, 120000);
```

### 3.2 Dynamic Behavior
*   When a static consumer drops offline, it does *not* send a `LeaveGroup` request. The Group Coordinator preserves its partition assignments.
*   If the consumer restarts and rejoins the group before the `session.timeout.ms` window expires, the coordinator returns its original partition assignments immediately. **No rebalance occurs across the rest of the group.**
*   If the consumer fails to return within the timeout, the coordinator considers it a hard failure, kicks it out, and triggers a rebalance.
