# Deploying Java in the Cloud

In Chapter 8, we covered the basic aspects of the cloud stack. In this chapter, we will take this topic further and look at the practical aspects of deploying Java processes on cloud native platforms.

We will begin by covering working locally with containers and understanding some of the basics of how containers interact when deployed. The interaction and details of how things are deployed will lead into looking at how container orchestration works and what you need to be aware of.

One highly useful aspect of cloud native platforms is access to ephemeral compute and the ability to scale—but this needs to be coordinated to be useful. With these basics in place, you will learn about options for release and deployment patterns. Deployment techniques are extremely helpful when rolling out changes to your JVM-based processes quickly while still reducing the risk of bugs.

If you are a developer, you might be wondering if deployment is really an important aspect for you to consider. In the past, you may have built software and handed it over to an operations team to run. However, one of the major changes with cloud native development is that the lines have blurred between operations and development, hence the term **DevOps**.

For example, it is much simpler to create consistent environments for production and non-production systems. As a result, many teams are choosing to operate as **“build and run”** teams, finding a balance between building and supporting services. Building and operating as a single team can result in improved efficiency (or “speed”). Speed gains come from fewer miscommunications, frustrations, or errors during the dev-to-ops handover. Build and run teams develop deep knowledge and a sense of responsibility for the stack as a whole, which increases engagement and job satisfaction.

Let's start by looking at how you can work with containers locally.

---

## Working Locally with Containers

In “Images and Containers” on page 202, we covered a basic guide to the basics of images and containers. One of the benefits of containers is creating a matching environment at deployment time on your local machine. Containers eliminate the problems linked with fixing differences between the operating system of the developer's machine and the production runtime environment.

Running the following commands will build and launch `mammal_demo` from the Fighting Animals demo. However, running the `curl` statement will not actually succeed due to missing dependencies—i.e., the other services are not yet available:

```shell
git clone https://github.com/kittylyst/fighting-animals.git .
git checkout main

mvn clean package
docker build -t mammal_demo -f src/main/docker/mammal/Dockerfile .
docker run -p 8081:8081 -t mammal_demo
curl localhost:8081/getAnimal
```

```json
{
  "timestamp": "2024-04-29T17:18:00.170+00:00",
  "status": 500,
  "error": "Internal Server Error",
  "path": "/getAnimal"
}
```

Looking at the map of services in `MammalController` shown in the following code, there is a DNS dependency at the code level. Both the mustelid and feline services are referred to as `mustelid-service` and `feline-service` in the URL. Later in this chapter, we will demonstrate how DNS works in orchestration platforms; however, for now, we need a way to recreate this locally:

```java
private static final Map<String, String> SERVICES =
    Map.of(
        "mustelids", "http://mustelid-service:8084/getAnimal",
        "felines", "http://feline-service:8085/getAnimal"
    );
```

One option is to run a Kubernetes cluster locally; another is to use Docker Compose, which is a simpler place to start.

### Docker Compose

**Docker Compose** is a tool for defining and running multi-container Docker applications locally during development. A `docker-compose.yml` file is used to configure your application's services and define the dependencies between them. Then, with a single command, `docker-compose up`, you can create and start all the services based on your configuration.

The following YAML is an example `docker-compose.yml`. The Fighting Animals example has a simple setup with five services, each of which is defined in a separate `Dockerfile`. The `depends_on` clauses define the service topology, and the name of the services (e.g., `mustelid-service`) creates a lightweight DNS entry that other containers can address:

```yaml
version: '3.8'
services:
  # Fish service
  fish-service:
    image: fish_demo:latest
    ports:
      - "8083:8083"

  # Mustelid service
  mustelid-service:
    image: mustelid_demo:latest
    ports:
      - "8084:8084"

  # Feline service
  feline-service:
    image: feline_demo:latest
    ports:
      - "8085:8085"

  # Mammal service
  mammal-service:
    image: mammal_demo:latest
    ports:
      - "8081:8081"
    depends_on:
      - feline-service
      - mustelid-service

  # Animal service
  animal-service:
    image: animals_demo:latest
    ports:
      - "8080:8080"
    depends_on:
      - fish-service
      - mammal-service
```

Running `docker-compose up` launches five distinct microservices in this example, each of them listening on a different TCP port. Running `curl localhost:8081/getAnimal` will provide a response from the mammal service. The feline and mustelid dependencies are set up on a named service and can be referenced from the other containers.

It is worth noting that the `curl` command had to target `localhost`, as outside the containers, the named services are not visible. The abstraction of the named service is useful for creating local service names, which is consistent with orchestration systems.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//0cf953a0-4ff7-4466-9d92-2453f519a13a/markdown_2/imgs/img_in_image_box_167_205_253_321.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A13Z%2F-1%2F%2Fd1fcb6c223d3825338bb9f4f925c56e5930b07acc8b85ee7c3a23de6fbe4042a" alt="Image" width="8%" /></div>

> [!NOTE]
> One challenge for developers is that there is a lot of tooling in the development loop (Maven, Docker, Docker Compose, etc.). Making changes and seeing them reflect immediately in the running local environment requires coordination.

### Tilt

**Tilt** is a tool that manages other tools to create a local workflow for microservices. After installation, a `Tiltfile` is created containing the recipe. The recipe contains multiple tasks required to compile, run, and deploy the example, and will redeploy parts of your application as files change, identified by `local_resource`.

In the following `Tiltfile` example, the `monorepo-java-compile` task rebuilds the code after it is changed. Following this, `docker_build` runs across the images and redeploys them in the configuration set out by `docker_compose`:

```python
local_resource(
    'monorepo-java-compile',
    'mvn clean package',
    deps=['src', 'pom.xml']
)

docker_build(
    'animals_demo',
    '.',
    dockerfile='./src/main/docker/animal/Dockerfile'
)

# ... All other docker_build tasks omitted

docker_compose("deploy/docker-compose.yml")
```

Figure 9-1 is an example of the Tilt UI, which provides visual feedback on the state of the build and running containers. It has some useful features in addition to seeing the current state of local deployments, such as quickly accessing the logs from a running container.

<div style="text-align: center;"><div style="text-align: center;">Figure 9-1. Tilt user interface</div> </div>

| Resource Name | Type | Status | Updated | Trigger |
| :--- | :--- | :--- | :---: | :---: |
| **(Tiltfile)** | Tiltfile | Updated | <45s ago | ☑ |
| **mustelid-service** | DCS | Updated | <30s ago | ☑ |
| **feline-service** | DCS | Updated | <30s ago | ☑ |
| **mammal-service** | DCS | Updated | <30s ago | ☑ |
| **fish-service** | DCS | Updated | <30s ago | ☑ |
| **animal-service** | DCS | Updated | <30s ago | ☑ |
| **monorepo-java-compile** | Local | Updated | <45s ago | ☑ |

---

## Container Orchestration

There are a variety of options for orchestrating containers; in this chapter, we will focus on Kubernetes, which is by far the most common choice.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//0cf953a0-4ff7-4466-9d92-2453f519a13a/markdown_3/imgs/img_in_image_box_176_909_253_1009.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A13Z%2F-1%2F%2Fadd86d660c8fa8d61a249ce430252bf72ab3661af7dd8c539963c7ca792b453a" alt="Image" width="7%" /></div>

> [!NOTE]
> The name “Kubernetes” comes from Ancient Greek, meaning “helmsman” or “pilot.” Various other tools in the space play on this theme with their naming.

Cloud native container orchestration is generally implemented with two high-level components: a **control plane** and a **data plane**.

The **control plane** is where actions are taken to adjust the state of the cluster. The **data plane** is where the actual work happens and where the five Fighting Animals services will run. From a developer perspective, thinking about where a service is running and how it is addressed is simplified into a platform job handled by the control plane.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//0cf953a0-4ff7-4466-9d92-2453f519a13a/markdown_4/imgs/img_in_image_box_176_187_253_290.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A14Z%2F-1%2F%2Fdb909385d5d961626177884b42e0359742b61769ce6340e0d52e7240e5bf0590" alt="Image" width="7%" /></div>

> [!NOTE]
> Control plane operations are eventually consistent, meaning changes take time to reach the data plane. Tradeoffs are made between consistency and availability; Kubernetes, by design, prioritizing availability.

There are multiple ways to run Kubernetes locally to construct a local cluster. The key command to perform Kubernetes operations is `kubectl` (short for “Kubernetes Control”). In practice, many developers create aliases, such as `k` for `kubectl`.

### Deployments

A **Deployment** describes the desired state of the workloads running in the data plane. In the example deployment, the `mammal-service` is defined along with its container specification. This deployment is defined in `deployment-mammal.yaml`. Running `kubectl apply -f deployment-mammal.yaml` applies the deployment to the cluster:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mammal-service
spec:
  replicas: 1
  selector:
    matchLabels:
      app: mammal-service
  template:
    metadata:
      labels:
        app: mammal-service
    spec:
      containers:
        - name: mammaldemo
          image: mammal_demo
```

Once the Deployment is applied, the Kubernetes scheduler will create a Pod and orchestrate its deployment onto a node in the data plane. A **Pod** is a group of one or more containers deployed together on a node. In the deployment for the mammal service, a single Pod is created containing a single container.

Executing the `get pods` command shows the running pod:

```shell
$ kubectl get pods
NAME                              READY   STATUS    RESTARTS   AGE
 mammal-service-79b4ccb9bb-4bqrj   1/1     Running   0          3m56s
```

### Sharing Within Pods

Developing with Pods creates powerful abstractions and is the heart of several common deployment architectures:
- **Shared Resources**: Containers running within a Pod have shared access to storage volumes and the network stack.
- **Compositional Dependency**: Containers deployed together in a Pod have a close coupling or a compositional dependency on each other.
- **Localhost Sharing**: Containers deployed in a single Pod share `localhost`, making it possible for latency-sensitive services with out-of-process communication to be deployed together. This is possible because of the loopback adapter, which intercepts traffic as it travels down the network stack before it hits the physical network.

Egressing from one Pod to another will bring additional network latency, which is something you will want to observe in the performance of your overall request flow. The impact will be higher if the connecting service is located on a different physical node in the cluster.

A **service mesh** is a group of CNCF projects that relies on Pods to control network traffic and routing. Service mesh projects such as Istio deploy an Envoy proxy sidecar into the same Pod as the application container. It is possible to manipulate the IP tables inside the Pod to alter the behavior of the local network. To set this up, an Istio-supplied init-container process executes, configures the Pod's IP tables, and then exits.

Service mesh is used to provide additional features beyond what is provided out of the box by Kubernetes:
- **mTLS**: The proxy can enforce that all traffic uses TLS or mTLS when traversing a cluster, automatically handling encryption.
- **Telemetry**: As traffic is decrypted at the proxy, the proxy has access to the payload unencrypted, enabling telemetry collection at the network level.
- **Traffic Routing**: The proxy is capable of fine-grained traffic routing, such as prioritizing human user traffic over background batch processes.

### Container and Pod Lifecycles

Additional nonfunctional requirements are necessary for applications running in distributed and scheduled environments. One essential requirement is the need to provide liveness and readiness health checks:
- **Liveness probe**: Checks if the application is running at all (if it fails, the container is restarted).
- **Readiness probe**: Indicates whether the process is ready to serve active traffic.

Ensuring that liveness and readiness checks are correct means that a Pod will not be scheduled into rotation (attached to a service) until it is in the `Ready` state.

Pods have an execution cycle described by the current lifecycle phase, matching conditions such as `PodScheduled`, `ContainersReady`, `Initialized`, and `Ready`. Consult the Kubernetes documentation on the Pod lifecycle for details.

### Services

A **Service** provides an abstraction over Pods deployed in the cluster and is the basis for advertising a lightweight DNS entry and routing across the cluster.

In the following example, we deploy a Service named `mammal-service`. This will create a DNS entry at the cluster level. The selector matches our deployment labels:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: mammal-service
spec:
  selector:
    app: mammal-service
  ports:
    - protocol: TCP
      port: 8081
      targetPort: 8081
```

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//ab3eb0d2-ba19-4465-9281-e94b32aae00a/markdown_2/imgs/img_in_image_box_167_787_254_902.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A06Z%2F-1%2F%2F6d24ff5976b7c3324a2ecf19c7459ceae55274994e166b11ea3eb20faf63057f" alt="Image" width="8%" /></div>

> [!NOTE]
> In simple deployments, manually typing and retyping string metadata is fine, but it can get complicated. Tools like Helm and Kustomize address this by introducing data types, templates, and variables.

Running `kubectl get services` displays the Services running on the cluster:

```shell
$ kubectl get services
NAME             TYPE        CLUSTER-IP       EXTERNAL-IP   PORT(S)    AGE
kubernetes       ClusterIP   10.96.0.1        <none>        443/TCP    16d
mammal-service   ClusterIP   10.105.113.150   <none>        8081/TCP   57s
```

For clusters to accept external traffic, an external ingress point must be configured.

### Connecting to Services on the Cluster

The Pods and Services created so far are visible only inside the cluster. To expose an entry point, a common approach is to create a Service of type `LoadBalancer`.

In the Fighting Animals example, only the `animal-service` should be exposed outside the cluster. In the following Service YAML, the `animal-service` is created with `type: LoadBalancer`. This indicates that an external load balancer with a public IP address should be registered:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: animal-service
spec:
  type: LoadBalancer
  selector:
    app: animal-service
  ports:
    - protocol: TCP
      port: 8080
      targetPort: 8080
```

Creating this ingress point exposes an external IP address. Running `kubectl get services` displays the external IP and port:

```shell
$ kubectl get services
```

| NAME | TYPE | CLUSTER-IP | EXTERNAL-IP | PORT(S) |
| :--- | :--- | :--- | :--- | :--- |
| **animal-service** | LoadBalancer | 10.106.223.136 | 20.108.87.2 | 8080:31762/TCP |
| **feline-service** | ClusterIP | 10.101.233.232 | \<none\> | 8085/TCP |
| **fish-service** | ClusterIP | 10.101.40.193 | \<none\> | 8083/TCP |
| **kubernetes** | ClusterIP | 10.96.0.1 | \<none\> | 443/TCP |
| **mammal-service** | ClusterIP | 10.111.138.65 | \<none\> | 8081/TCP |
| **mustelid-service** | ClusterIP | 10.98.142.128 | \<none\> | 8084/TCP |

You can now connect using the external IP address on `http://20.108.87.2:8080`. LoadBalancer implementations vary depending on the cloud provider.

---

## Challenges with Containers and Scheduling

Operating environments at scale can pose various challenges:

- **Observability**: As the cluster increases in complexity, discovering the root cause of ongoing or past problems is difficult. Telemetry is required for operating Kubernetes workloads at scale (see Chapter 10).
- **Cold Starts**: Image loading is an important aspect of scheduling. The size of the image impacts the cost of a cold start (when a container must be pulled to a node for the first time). The larger the image, the longer it takes to download, placing load on networking infrastructure. AOT compilation can help reduce this by reducing launch times and image sizes.

To help reduce the impact of cold starts, Kubernetes caches images locally at the node level. The `imagePullPolicy` in the Deployment object determines this behavior:
- **`IfNotPresent`**: Will pull the image only if it doesn't exist on the node. This is the default when the `:latest` tag is not used.
- **`Always`**: Will always check and pull a newer image from the remote container registry, pulling only new layers as required.
- **`Never`**: Will never look in the remote container registry, assuming you have pre-loaded the image onto the node.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//dd71801c-68bc-472b-91f2-df62af620c1b/markdown_0/imgs/img_in_image_box_164_753_267_851.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A14Z%2F-1%2F%2F92b40f7448e934aa6eefbdabb0409068b01979322eae2cdda7b06a2413f2edc5" alt="Image" width="10%" /></div>

> [!WARNING]
> Avoid using the tag `:latest` in production. It sets the pull policy to `Always` (increasing network traffic) and risks introducing uncontrolled changes to your production environment during auto-scaling events, which is a major compliance risk. Always use pinned, versioned tags.

- **Resiliency & Placement**: Production clusters should contain multiple nodes positioned across different cloud availability zones. Operators can control node placement using **node affinity** and anti-affinity.
- **Security**: The control plane is a key target for compromise. Securing ingress points and using namespaces are essential security practices. **Namespaces** group resources and provide logical isolation and access control.

### Remocal Development

Another option is to make your local container appear as though it is part of a remote cluster. This **remocal development** approach allows you to use local IDE debugging and profiling tools while interacting with remote dependencies, avoiding the need to run all services locally. **Telepresence** is a tool that provides this capability by proxying traffic between the local machine and the cluster.

---

## Deployment Techniques

Understanding the difference between deployment and release unlocks new rollout techniques:
- **Deployment**: Changing application components (code or config) or infrastructure in the environment.
- **Release**: Making a feature or change available to end users.

Deployments can change production systems without releasing features, allowing deploys to be more frequent. Releases change user-visible behavior, but deploys may not.

Several useful deployment techniques can help manage these rollouts:
- **Blue/green deployments**
- **Canary deployments**
- **Feature flags** and how they contribute to an evolutionary architecture

### Blue/Green Deployments

Blue/green involves maintaining two identical environments behind a decision point (e.g., a load balancer):
- **Blue**: The currently active production environment.
- **Green**: The next version of the platform, set up in parallel.

In Kubernetes, this can be modeled by creating blue and green Services. A Kubernetes **Ingress** resource can be updated to flip traffic between the blue and green services. Figure 9-2 highlights how this works with Fighting Animals.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//dd71801c-68bc-472b-91f2-df62af620c1b/markdown_3/imgs/img_in_image_box_201_110_866_343.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A24Z%2F-1%2F%2F3db12bec40b543b97ca48065e572f031df5e46afc5eefee830e19d56d6dd6814" alt="Image" width="65%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 9-2. Example of a blue/green setup with Fighting Animals</div> </div>

Live traffic is flipped from blue to green. If a problem is spotted, rollback is accomplished instantly by redirecting the ingress back to the blue environment. One disadvantage is the requirement to duplicate all services, which can be costly.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//dd71801c-68bc-472b-91f2-df62af620c1b/markdown_3/imgs/img_in_image_box_164_724_265_822.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A25Z%2F-1%2F%2F75dc9df91fbee47ec673e63b0458e902b10674429e68a30335232d8c4fd16dbd" alt="Image" width="10%" /></div>

> [!NOTE]
> Accessing the green environment directly for regression testing is necessary to verify the release. Testing URL path routing changes carefully is critical to avoid routing bugs when going live.

### Canary Deployments

**Canary deployments** replace running services incrementally, flowing a small percentage of production traffic to the new version (the "canary") before a full rollout.

Tools like **Argo CD** automate canary releases within Kubernetes clusters. In this section, we demonstrate a rollout of the `mammal_demo` image where 20% of the replicas are initially updated and paused for verification before proceeding.

To try the example, you will need to install the Argo Rollouts controller on your cluster:

```shell
git checkout k8s-with-argo

kubectl create namespace argo-rollouts
kubectl apply -n argo-rollouts -f \
  https://github.com/argoproj/argo-rollouts/releases/latest/download/install.yaml
```

The rollout definition is defined in `operations/k8s-canary-rollout-demo.yaml`. This file configures 5 replicas using the `canary` strategy. The steps specify that the new version should initially receive 20% weight and then pause for manual promotion:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: rollouts-demo
spec:
  replicas: 5
  revisionHistoryLimit: 2
  selector:
    matchLabels:
      app: mammal-service
  template:
    metadata:
      labels:
        app: mammal-service
    spec:
      containers:
        - name: mammal-service
          image: mammal_demo
          ports:
            - name: http
              containerPort: 8081
              protocol: TCP
          resources:
            requests:
              memory: 32Mi
              cpu: 5m
  strategy:
    canary:
      steps:
        - setWeight: 20
        - pause: {}
        - setWeight: 40
        - pause: {duration: 10}
        - setWeight: 60
        - pause: {duration: 10}
        - setWeight: 80
        - pause: {duration: 10}
```

To trigger a release of a v2 container, execute the following command:

```shell
kubectl argo rollouts set image rollouts-demo mammal-service=mammal_demo:v2
```

This starts the rollout, updating one pod (20%) to the new version. Figure 9-3 shows the rollout state in the Argo CD dashboard, accessed via `kubectl argo rollouts dashboard`.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//a8c9de6d-460f-4b40-ba70-0ff990f2a9af/markdown_1/imgs/img_in_image_box_145_114_853_906.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A10%3A57Z%2F-1%2F%2Fe053d59e2c01ababb0758bb106ae7dc7459b519416129800018ee4db358a0ec0" alt="Image" width="70%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 9-3. Execution of a canary release of the mammal service</div> </div>

Pressing **Promote** triggers the next stages of the rollout, while pressing **Rollback** aborts and restores the previous version.

Instead of manual promotion, we can use automated signals, such as an `AnalysisTemplate` checking Prometheus metrics for request success rates:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: AnalysisTemplate
metadata:
  name: success-rate
spec:
  args:
    - name: service-name
    - name: prometheus-port
      value: 9090
  metrics:
    - name: success-rate
      successCondition: result[0] >= 0.95
      provider:
        prometheus:
          address: "http://prometheus.example.com:{{args.prometheus-port}}"
```

### Evolutionary Architecture and Feature Flagging

Changing complex, legacy systems all at once introduces significant risk. **Evolutionary architectures** address this by designing systems with the expectation that they will change incrementally over time. Neal Ford's *Building Evolutionary Architectures* is an excellent guide.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//a8c9de6d-460f-4b40-ba70-0ff990f2a9af/markdown_2/imgs/img_in_image_box_176_897_253_997.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A10%3A57Z%2F-1%2F%2Fabe6faa131e9f85183aa696b6527252de550d65142580badaef783ec68e5a150" alt="Image" width="7%" /></div>

> [!NOTE]
> Evolutionary architecture is a journey. Your target architecture will shift as you learn more about your system's real-world behavior and requirements.

AWS defines a **"Six R's"** approach to cloud migration:
1. **Retain or Revisit**: Keep the system in its current state if it is too difficult to move or currently adds significant value.
2. **Repurchase**: Drop the custom application and move to an off-the-shelf SaaS product.
3. **Rehost** (lift-and-shift): Move the same platform model to the cloud unchanged.
4. **Replatform**: Adjust the application slightly to take advantage of cloud services (e.g., moving to managed RDS databases).
5. **Refactor / Re-architect**: Redesign the application to make full use of cloud native platforms like Kubernetes.
6. **Retire**: Decommission components that are no longer required.

To support migration at a very detailed level, **feature flags** are code-level checks that query an external configuration store to dynamically alter system execution path flow. Here is a Java example using LaunchDarkly:

```java
LDUser user = new LDUser("authors");
boolean mammalService = 
    launchDarklyClient.boolVariation("user.enabled.mammals", user, false);

if (mammalService) {
    // Retrieves the mammal from the modern environment
} else {
    // Retrieves the mammal from the existing monolithic codebase
}
```

This separates deployment from release, permitting new features to be toggled dynamically.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//a8c9de6d-460f-4b40-ba70-0ff990f2a9af/markdown_4/imgs/img_in_image_box_176_698_253_798.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A10%3A58Z%2F-1%2F%2F2f19f0c25553ba6a55b5b636edf740f94a6decad4f3e1d17a168a477e48967d6" alt="Image" width="7%" /></div>

> [!TIP]
> Feature flags must be highly available, and code must always define a sensible, safe default fallback value in case of communication failures.

Feature flags are the primary release mechanism for systems too large for blue/green. However, they must be cleaned up regularly and have a defined lifetime.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//a8c9de6d-460f-4b40-ba70-0ff990f2a9af/markdown_4/imgs/img_in_image_box_164_1062_265_1160.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A10%3A58Z%2F-1%2F%2F10da6121e60e50c5bfc2d1006b4795f498c8617b8a8710d97e5e31262f7a1755" alt="Image" width="10%" /></div>

> [!CAUTION]
> Knight Capital is an extreme example where reusing feature flag names and failing to clean up outdated code led to $500M in electronic trading losses in a few hours. Establish a strict policy for naming and lifecycle management of feature flags.

---

## Java-Specific Concerns

Java deployments face some unique challenges when containerized.

### Containers and GC

According to research from New Relic, over 70% of Java applications are now deployed in containerized environments. <sup>1</sup> However, roughly half of these containers are configured to use a single CPU core.

This is a major performance bottleneck. On startup, the JVM detects the number of available CPUs to configure runtime ergonomics. The default G1 collector is concurrent and requires multiple CPUs. On a single-CPU container, the JVM will disable G1 and go back to the single-threaded **Serial** and **SerialOld** collectors.

Running GC serially leads to larger stop-the-world pauses and reduced application throughput. Unless absolutely necessary, Java applications should always be deployed in containers with **two or more vCPUs** to enable modern concurrent garbage collectors.

### Memory and OOMEs

Older versions of the JVM (predating Java 8u191) were not container-aware and did not respect cgroups limits. Instead, they inspected the host-level memory. This led to situations where the JVM attempted to allocate a heap larger than the container's memory quota, causing the OS **Out-Of-Memory (OOM) Killer** to suddenly stop the JVM process.

Cgroups support has been backported to Java 8, but we strongly recommend running modern LTS versions (such as Java 17 or 21) in containers. Java 17 introduced full cgroups v2 support and container awareness in `OperatingSystemMXBean`.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//08d4c711-7487-44e4-9f78-684212e9bd6f/markdown_1/imgs/img_in_image_box_164_745_266_842.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T01%3A11%3A32Z%2F-1%2F%2Ff0714f40f2da40d52f9b7e428cae1d0fc4111376ec9fa710b670f60e6d9ae856" alt="Image" width="10%" /></div>

> [!WARNING]
> Running an older JVM on a host that only supports cgroups v2 will cause the JVM to misread its memory constraints and look at host-level memory instead.

If you allocate 1 GB to a container, the JVM's default ergonomics will size the maximum heap size (`-Xmx`) to roughly 256 MB (25%). Overriding the maximum heap size using `-Xmx` or setting the `-XX:MaxRAMPercentage` flag is recommended to optimize memory utilization while leaving enough extra space for off-heap allocations, thread stacks, and container overhead.

In a lift-and-shift migration, <sup>2</sup> running with no constraints is a starting point, but setting explicit memory and CPU limits is essential to achieve long-term performance and resiliency.

---

## Summary

In this chapter, we have explored the relationship between development and deployment of Java applications in the cloud:
- We used **Docker Compose** and **Tilt** to establish high-speed local multi-container development workflows.
- We covered the basics of **Kubernetes** deployments, services, and the lifecycles of Pods and containers.
- We demonstrated how **Argo CD** automates canary releases.
- We analyzed release division strategies, including **blue/green deployments**, **canaries**, and **feature flags**.
- We highlighted Java-specific container concerns, emphasizing the need for multiple vCPU cores for concurrent GC and the importance of container-aware memory tuning to avoid OS OOM kills.

Operating these complex distributed topologies in production is impossible without deep visibility. In the next chapter, we will introduce the observability concepts and standards required to manage cloud native Java applications.
