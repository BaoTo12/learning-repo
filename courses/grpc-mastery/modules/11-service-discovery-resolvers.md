# Module 11: Service Discovery & Custom Name Resolvers

## 1. What Problem This Module Solves
In modern dynamic container environments (such as Kubernetes or Consul-based cloud meshes), pod IP addresses change constantly.
*   **Static Endpoint Fragility**: Hardcoding IP addresses or routing through single static IP endpoints creates a single point of failure (SPOF).
*   **Multiplexing vs DNS Cache**: gRPC keeps a single connection socket open long-term. Standard DNS load balancing only resolves the IP *once* during channel initialization. When the backend scales out from 2 instances to 10 instances, the client remains connected *only* to the first resolved IP, starving the new instances of traffic.

To solve this, gRPC provides the **NameResolver** and **LoadBalancer** APIs, allowing clients to dynamically query service registries (Consul, Eureka, or local configuration files) and adjust connection pools dynamically.

---

## 2. gRPC Client-Side Load Balancing Architecture

Unlike HTTP/1.1 which delegates routing to server-side proxies, gRPC supports client-side load balancing:

```
[ Client ManagedChannel ]
       │
       ▼ (Uses custom URI: file:///services/payment-service)
[ Custom NameResolver ]  <--- Polls config file or registry
       │
       ▼ (Resolves IP list: [10.0.0.1:9090, 10.0.0.2:9090])
[ LoadBalancer (Round-Robin) ]
       │
       ├───────► Connection 1 to 10.0.0.1:9090
       └───────► Connection 2 to 10.0.0.2:9090
```

1.  The client initializes a `ManagedChannel` with a URI target (e.g., `dns:///payment-service:9090`).
2.  The **NameResolver** intercepts this target URI, queries the registry, and returns a list of backend IP addresses (`EquivalentAddressGroup`).
3.  The client **LoadBalancer** consumes this list, opens TCP sockets to each IP, and distributes RPC requests across them (e.g., via `round_robin` policy).

---

## 3. Trade-offs and Limitations
*   **Client Complexity**: Distributing connection management to the client increases client SDK memory usage. The client must constantly check connectivity and maintain sockets to multiple backend pods.
*   **Service Registry Coupling**: The client must include libraries or handlers capable of authenticated communication with your registry (Consul, ZooKeeper, Eureka).

---

## 4. Common Mistakes and Anti-Patterns
*   **Routing Through standard Kubernetes ClusterIP**: Target-pointing your client stubs to a standard Kubernetes `ClusterIP` service. Kubernetes ClusterIP is a virtual IP routed via `iptables` at the TCP layer. Because gRPC multiplexes traffic on a single connection, the client will connect to ClusterIP once, pinning all future streams to a single physical pod behind the virtual IP.
    *   *Correction*: Use Kubernetes headless services (`dns:///my-service-headless.default.svc.cluster.local`) or a custom Kubernetes NameResolver.
*   **Failing to Notify Listeners on Failure**: Implementing a custom NameResolver that crashes silently when querying a service registry, rather than calling `listener.onError()`. This leaves the channel in a broken, unresolvable state.

---

## 5. Implementing a Custom NameResolver in Pure Java

Let's build a static, file-based `NameResolver` that dynamically reads IP listings from a configuration file.

### 5.1 Custom NameResolver Implementation
```java
package com.example.grpc.discovery;

import io.grpc.*;
import java.io.BufferedReader;
import java.io.FileReader;
import java.io.IOException;
import java.net.InetSocketAddress;
import java.net.URI;
import java.util.ArrayList;
import java.util.List;
import java.util.stream.Collectors;

public class FileBasedNameResolver extends NameResolver {

    private final String filePath;
    private Listener2 listener;

    public FileBasedNameResolver(URI targetUri) {
        // Parse file path from target URI, e.g. file:///c:/temp/services.txt
        this.filePath = targetUri.getPath();
    }

    @Override
    public String getServiceAuthority() {
        return "file-registry";
    }

    @Override
    public void start(Listener2 listener) {
        this.listener = listener;
        resolveAddresses();
    }

    @Override
    public void refresh() {
        resolveAddresses(); // Re-read file on demand when connection drops
    }

    private void resolveAddresses() {
        List<EquivalentAddressGroup> servers = new ArrayList<>();
        try (BufferedReader reader = new BufferedReader(new FileReader(filePath))) {
            String line;
            while ((line = reader.readLine()) != null) {
                line = line.trim();
                if (line.isEmpty() || line.startsWith("#")) continue;

                String[] parts = line.split(":");
                String host = parts[0];
                int port = Integer.parseInt(parts[1]);

                InetSocketAddress socketAddress = new InetSocketAddress(host, port);
                servers.add(new EquivalentAddressGroup(socketAddress));
            }

            // Emit resolved address targets to gRPC client LoadBalancer
            ResolutionResult result = ResolutionResult.newBuilder()
                .setAddresses(servers)
                .setAttributes(Attributes.EMPTY)
                .build();
            
            listener.onResult(result);
            System.out.println("[NameResolver] Successfully resolved targets: " + servers);

        } catch (IOException | NumberFormatException e) {
            listener.onError(Status.UNAVAILABLE
                .withDescription("Failed to read backend listing file: " + filePath)
                .withCause(e));
        }
    }

    @Override
    public void shutdown() {
        // Clean up resources if any
    }
}
```

---

### 5.2 NameResolver Provider registration
To register the custom resolver scheme (`file://`) with gRPC, we implement a `NameResolverProvider`:

```java
package com.example.grpc.discovery;

import io.grpc.NameResolver;
import io.grpc.NameResolverProvider;
import java.net.URI;

public class FileBasedNameResolverProvider extends NameResolverProvider {

    @Override
    protected boolean isAvailable() {
        return true;
    }

    @Override
    protected int priority() {
        return 6; // Priority level higher than standard DNS resolver (which is 5)
    }

    @Override
    public String getScheme() {
        return "file"; // Match file:// URIs
    }

    @Override
    public NameResolver newNameResolver(URI targetUri, NameResolver.Args args) {
        if ("file".equals(targetUri.getScheme())) {
            return new FileBasedNameResolver(targetUri);
        }
        return null;
    }
}
```

---

### 5.3 Client Channel Wiring Example
```java
package com.example.grpc.discovery;

import io.grpc.ManagedChannel;
import io.grpc.ManagedChannelBuilder;
import io.grpc.NameResolverRegistry;

public class ServiceDiscoveryClient {

    public static void main(String[] args) throws InterruptedException {
        // Register Provider globally
        NameResolverRegistry.getDefaultRegistry().register(new FileBasedNameResolverProvider());

        // Target: file scheme pointing to backend definitions
        String targetUri = "file:///C:/Users/Admin/Desktop/projects/learning-repo/grpc-mastery/services.txt";

        ManagedChannel channel = ManagedChannelBuilder.forTarget(targetUri)
            .defaultLoadBalancingPolicy("round_robin") // Rotate requests round-robin
            .usePlaintext()
            .build();

        System.out.println("Channel built using custom service discovery target!");
        channel.shutdown().awaitTermination(2, java.util.concurrent.TimeUnit.SECONDS);
    }
}
```

To run this sandbox, create a simple `services.txt` at the target location:
```text
# Active Backend Pod Addresses
127.0.0.1:9091
127.0.0.1:9092
```

---

## 6. Interview Questions

### Q1: Why does a standard DNS provider (like AWS Route 53 or Kubernetes internal CoreDNS) fail to load balance gRPC connections evenly when configured in a standard round-robin DNS setup?
**Answer**: 
Standard HTTP/1.1 clients open and close TCP connections regularly. Thus, they resolve the DNS host address repeatedly, receiving different IP addresses and naturally distributing traffic.
gRPC operates over long-lived HTTP/2 TCP streams. A client resolves DNS **once** during channel creation, selects one resolved IP, and stays connected to it. Even if the DNS registry returns multiple IP records, the client will only open a TCP socket to the first IP and funnel all subsequent streams over that single socket, leaving other backend servers completely idle.

### Q2: What is a Kubernetes Headless Service, and how does the standard gRPC DNS Resolver use it to distribute traffic?
**Answer**: 
A standard Kubernetes Service maps a single virtual IP (`ClusterIP`) that handles TCP load balancing.
A **Headless Service** is configured by setting `clusterIP: None` in the service specification. When a client performs an A-record DNS lookup on a headless service host, CoreDNS returns the list of **all active pod IPs** belonging to that service directly, rather than returning a virtual IP.
The gRPC DNS NameResolver handles this IP list, returns it to the client LoadBalancer as a collection of `EquivalentAddressGroup` targets, and the client LoadBalancer establishes separate HTTP/2 channels to *each individual pod* and routes traffic across them using its load-balancing policy.
