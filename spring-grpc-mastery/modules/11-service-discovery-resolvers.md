# Module 11: Service Discovery & Cloud-Native Deployment

## 1. What Problem This Module Solves
In dynamic cloud environments, container instances (Kubernetes pods) are constantly created and destroyed, changing their IP addresses.
*   **Static IP Fragility**: Hardcoding IP addresses or routing through static IP endpoints creates a single point of failure (SPOF).
*   **Virtual IP Pinning**: Traditional DNS round-robin load balancers resolve the hostname IP once during initialization. Because gRPC maintains a single persistent TCP connection, the client remains pinned to the first resolved IP, starving new server instances of traffic.

To solve this, gRPC supports client-side load balancing, allowing clients to query service registries (Consul, Eureka, or Kubernetes DNS) and distribute requests dynamically across backend IPs.

---

## 2. Load Balancing Architectures: Client-Side vs Server-Side

```
[ Client-Side Load Balancing ]
                       [ Client Stub ]
                              │
            ┌─────────────────┼─────────────────┐ (Resolves IPs from Registry)
            ▼                 ▼                 ▼
     [ Backend Pod 1 ] [ Backend Pod 2 ] [ Backend Pod 3 ]

[ Server-Side Load Balancing ]
                       [ Client Stub ]
                              │
                              ▼ (Single persistent TCP connection)
                       [ L7 Proxy / Envoy ]
                              │
            ┌─────────────────┼─────────────────┐ (Routes streams)
            ▼                 ▼                 ▼
     [ Backend Pod 1 ] [ Backend Pod 2 ] [ Backend Pod 3 ]
```

*   **Client-Side Load Balancing**: The client queries the service registry directly, maintains a TCP connection pool to each instance, and distributes requests (e.g. round-robin) across them. This eliminates proxy bottlenecks but increases client memory usage.
*   **Server-Side Load Balancing**: The client routes traffic through a proxy (e.g., Envoy). The proxy terminates the connection, processes the streams, and balances traffic across the backend instances.

---

## 3. Spring Boot Service Registry Integration (Consul)

Configure Spring Boot to register your gRPC server with a **Consul** registry and allow clients to resolve endpoints dynamically:

### 3.1 Server Registration Config (`application.yml`)
```yaml
spring:
  application:
    name: user-service
  cloud:
    consul:
      host: localhost
      port: 8500
      discovery:
        enabled: true
        register: true
        # Register the specific gRPC port (not the web port)
        port: 9090
        tags: gRPC, microservice
```

Ensure your server is annotated to enable discovery:
```java
package com.example.grpc;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.cloud.client.discovery.EnableDiscoveryClient;

@SpringBootApplication
@EnableDiscoveryClient
public class ServerApplication {
    public static void main(String[] args) {
        SpringApplication.run(ServerApplication.class, args);
    }
}
```

---

### 3.2 Client Integration Config (`application.yml`)
Configure the client stub to resolve addresses dynamically from Consul using the `discovery:///` scheme:

```yaml
grpc:
  client:
    user-service:
      address: 'discovery:///user-service' # Resolve dynamically from Consul
      negotiation-type: plaintext
      default-load-balancing-policy: round_robin # Distribute calls round-robin
```

---

## 4. Common Mistakes and Anti-Patterns
*   **Routing Through Standard Kubernetes ClusterIP**: Pointing client stubs to a standard Kubernetes `ClusterIP` service. A ClusterIP represents a virtual IP managed by `iptables`. Because gRPC uses long-lived multiplexed connections, the client will connect once, pinning all future requests to a single pod behind the ClusterIP.
    *   *Correction*: Use **Kubernetes Headless Services** (`clusterIP: None`) so CoreDNS returns the list of all active pod IPs directly, allowing the client to load balance across them.
*   **Failing to configure Health Checks in Consul**: Registering services in Consul without configuring gRPC health checks (`grpc-health-probe`). If a pod hangs or experiences an OOM exception, Consul will keep routing traffic to it.

---

## 5. Interview Questions

### Q1: Why does a standard DNS A-record round-robin config fail to balance gRPC traffic evenly?
**Answer**: 
Standard HTTP/1.1 clients open and close TCP connections regularly. This forces them to perform DNS resolutions repeatedly, naturally distributing connections across backend servers.
gRPC keeps a single HTTP/2 TCP connection open long-term. A client resolves the DNS hostname **once** during channel creation, opens a socket connection to one resolved IP, and routes all future requests over that single connection, leaving other backend instances completely idle.

### Q2: What is a Kubernetes Headless Service, and how does it enable client-side load balancing in gRPC?
**Answer**: 
*   **Headless Service**: Is configured by setting `clusterIP: None` in the Kubernetes service spec. This tells Kubernetes not to allocate a virtual IP for the service.
*   **gRPC Integration**: When a client performs a DNS lookup on a headless service hostname, CoreDNS returns a list containing the **IP addresses of all active pods** matching the service label selector. The gRPC client DNS name resolver receives this list, establishes direct TCP connections to each pod IP, and distributes requests across them using its load-balancing policy (e.g. round-robin).
