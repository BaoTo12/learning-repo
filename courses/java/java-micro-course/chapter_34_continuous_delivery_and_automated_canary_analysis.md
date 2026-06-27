# Chapter 34: Continuous Delivery & Automated Canary Analysis

Maintaining reliability at scale requires automating the software delivery pipeline. Manual interventions, ad-hoc server configurations, and untested deployment operations are the primary drivers of production incidents. To scale microservice updates safely, we must treat infrastructure as immutable and automate rollouts.

This chapter covers the technical design and implementation of automated continuous delivery pipelines. We will contrast multicloud deployment platforms (IaaS, CaaS, PaaS), define Spinnaker cluster resources (Instances, Server Groups, Clusters, Applications), configure automated build tools (Nebula ospackage Gradle plug-ins) to compile immutable Debian and Docker artifacts, evaluate deployment strategies (Delete + None, Highlander, Blue/Green), implement **Automated Canary Analysis (ACA)** using **Spinnaker** and **Kayenta**, and write statistical metrics validations using Prometheus data.

---

## Learning Objectives

By the end of this chapter, you will be able to:
1. Explain how continuous delivery differs from continuous integration (CI vs. CD boundaries).
2. Differentiate between Infrastructure as a Service (IaaS), Container as a Service (CaaS), and Platform as a Service (PaaS).
3. Map Spinnaker resource abstractions (Server Groups, Clusters, Load Balancers) to cloud infrastructure elements (ASGs, Kubernetes Deployments).
4. Configure Nebula Gradle plug-ins to package Spring Boot applications as Debian files and Docker images.
5. Identify the security and reproducibility risks of consuming base images without organization-level validation.
6. Evaluate the trade-offs of the Highlander and Blue/Green deployment strategies in terms of rollback speed and operational cost.
7. Explain the Kubernetes rolling update process and identify why it behaves like a specific kind of Blue/Green deployment.
8. Design Spinnaker pipelines to orchestrate canary rollouts involving Baseline, Canary, and Production server groups.
9. Configure Kayenta to perform automated canary judgements using Prometheus queries.
10. Evaluate canary runs using time series plots, histograms, and beeswarm visualizations.
11. Apply statistical metrics analysis to identify why measuring median or average latency fails to detect canary performance degradations.

---

## 34.1 Cloud Platforms: IaaS, CaaS, and PaaS Architectures

Continuous delivery pipelines deploy applications to one of three platform levels:

* **Infrastructure as a Service (IaaS)**: Manages physical compute, hypervisors, and storage. The deployment unit is a virtual machine image (e.g. AWS Amazon Machine Image). Bakers (like HashiCorp Packer) compile this VM image by installing OS-level packages (like Debian/RPM) onto a validated base OS.
* **Container as a Service (CaaS)**: Manages containerized workloads. The deployment unit is a Docker image, which is scheduled on container runtimes (like Kubernetes). 
* **Platform as a Service (PaaS)**: Exposes a developer-centric interface. The deployment unit is a raw application artifact (such as a Spring Boot JAR). The platform automatically bakes and runs the artifact (e.g. Cloud Foundry Buildpacks).

---

## 34.2 Spinnaker Resource Hierarchy and Abstractions

Spinnaker defines a standardized, multicloud resource model:

* **Instance**: A single running host or container (e.g. AWS EC2 instance, Kubernetes pod).
* **Server Group**: An immutable collection of instances running the same version of code. In AWS EC2, this is an Auto Scaling Group (ASG). In Kubernetes, it maps to a ReplicaSet.
* **Cluster**: A logical collection of server groups representing different versions of a service across regions.
* **Application**: A logical business function. An application spans multiple clusters and regions.
* **Load Balancer**: Directs traffic to instances within a server group. In Kubernetes, this maps to a Service.
* **Firewall**: Rules governing network ingress and egress. In AWS EC2, these are Security Groups.

We manage these resources inside Spinnaker's infrastructure view:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//1ef37be2-b8bc-4ce2-89ac-a8f647bb5d4d/markdown_0/imgs/img_in_image_box_147_280_861_705.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A41Z%2F-1%2F%2F63f42c8d2c4e9d5c9bd217850ebdd0f545e6c51681ec9b14c4e56e7ad60663aa" alt="Image" width="70%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 5-1. Spinnaker infrastructure view showing three Kubernetes ReplicaSets</div> </div>

---

## 34.3 Immutable Infrastructure and Packaging

To ensure reliability, deployments must be **Immutable**. Rather than logging into servers to update code, we bake the code into a static image and replace the instances.

### 1. IaaS VM Baking Pipeline
For IaaS environments, the build tool output is wrapped in an OS-level package (Debian or RPM) and baked onto a base VM image:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//c4a2f4d1-c9d4-4b2d-af4b-e96a729c22e9/markdown_1/imgs/img_in_image_box_144_110_864_431.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A34Z%2F-1%2F%2Fb5bab28c1519dc0f3ce9bcebeb73d95a7bb89658eee15f9a302a86e725c4e7cb" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 5-6. VM baking pipeline boundary showing Packer integration</div> </div>

We use the Nebula `ospackage` Gradle plug-in to compile Spring Boot applications as Debian packages:

```groovy
// build.gradle configuration compiling a Debian package
plugins {
    id 'org.springframework.boot' version '2.7.5'
    id 'io.spring.dependency-management' version '1.0.15.RELEASE'
    id 'nebula.ospackage-application-spring-boot' version '9.1.1'
}

group = 'com.ftgo'
version = '1.0.0-SNAPSHOT'

ospackage {
    packageName = "order-service"
    version = project.version
    release = '1'
    arch = I386
    os = LINUX
}
```

### 2. Container Image Baking
For Kubernetes workloads, we package our applications as Docker images. 

```groovy
// build.gradle configuration compiling and publishing a Docker container
plugins {
    id 'org.springframework.boot' version '2.7.5'
    id 'io.spring.dependency-management' version '1.0.15.RELEASE'
    id 'com.bmuschko.docker-spring-boot-application' version '7.3.0'
}

docker {
    registryCredentials {
        username = System.getenv("DOCKER_USER")
        password = System.getenv("DOCKER_PASSWORD")
        email = "bot@myorg.com"
    }

    springBootApplication {
        tag = "myorg/${project.name}:${project.version}"
        baseImage = "openjdk:17-alpine"
    }
}
```

> [!CAUTION]
> Consuming public base images directly (e.g. `openjdk:17-alpine`) poses security risks. Organizations must validate base images for CVEs and distribute them via internal registries.

To decouple builds from base image updates, you can use **Kaniko** inside Spinnaker to bake container images directly, removing the need for a local Docker daemon.

---

## 34.4 Deployment Strategies: Rollout Trade-offs

When deploying a new server group, we use one of four strategies:

### 1. Delete + None (Recreate)
Destroys the old server group before launching the new one. This strategy causes downtime and is only suitable for non-critical workloads.

### 2. Highlander
Launches the new server group, validates its health, and immediately deletes the old one. This strategy minimizes cost but results in slow rollbacks because the old image must be rebaked and redeployed.

### 3. Blue/Green (Red/Black)
Launches the new server group (Green) alongside the old one (Blue). Traffic is switched to Green via the load balancer. The Blue server group is kept running but disabled, enabling near-instant rollbacks.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//57ff9a47-4085-4c92-9088-df3f94922a03/markdown_1/imgs/img_in_image_box_143_110_863_408.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A43Z%2F-1%2F%2Fcf7d05e2e96058e064c24e57c9cc76c67f2de489b08215bcb3858b009be21883" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 5-7. Spinnaker Blue/Green cluster showing active and disabled server groups</div> </div>

We trigger rollback operations in Spinnaker by re-enabling a previous server group version:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//57ff9a47-4085-4c92-9088-df3f94922a03/markdown_1/imgs/img_in_image_box_142_558_861_904.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A43Z%2F-1%2F%2F0284616106660cde9b51c102c298fcca2866e6de654e61c3c8b4c264831fdc0a" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 5-8. Triggering rollbacks inside the Spinnaker interface</div> </div>

### 4. Kubernetes Rolling Updates
The `kubectl apply` command performs a rolling update, gradually replacing old pods with new ones. 

> [!IMPORTANT]
> A rolling update is a specific kind of Blue/Green deployment. If a failure is detected mid-rollout, pods in the process of rolling out are terminated, and traffic remains routed to the surviving old pods.

We evaluate the trade-offs of each strategy based on cost and rollback speed:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//57ff9a47-4085-4c92-9088-df3f94922a03/markdown_2/imgs/img_in_image_box_141_274_865_437.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A45Z%2F-1%2F%2Fe84aec70d8e32603780261cce66534b4986f9c8101ae61aeb580ef5b64812ea1" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 5-9. Rollback speed vs. operational cost by deployment strategy</div> </div>

---

## 34.5 Automated Canary Analysis (ACA) and Kayenta

While Blue/Green rollouts enable rapid rollbacks, a bad release can still impact users before we rollback. To prevent this, we use **Automated Canary Analysis (ACA)**.

An ACA pipeline deploys three distinct server groups side-by-side:
* **Production**: The existing live version handling 98% of traffic.
* **Baseline**: A small server group running the *same* version as Production, handling 1% of traffic.
* **Canary**: A small server group running the *new* version, handling 1% of traffic.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//9f466dd6-8578-4e32-bf67-451acb834cea/markdown_0/imgs/img_in_image_box_141_807_865_1060.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A41Z%2F-1%2F%2Fce83f0c6401cda5fb4600248d55fd5339b790f43ad10d1c5797268dbdf6f680d" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 5-10. Canary rollout architecture showing Baseline and Canary groups</div> </div>

> [!IMPORTANT]
> You must deploy a Baseline group. Comparing the Canary directly to the Production group is statistically invalid because the Production group is larger and has warm JVMs and connection pools, while the Canary is cold. Comparing Canary to Baseline ensures that both groups are identical in size and age.

### 1. Relative vs. Fixed Threshold Canary Judgement
Do not test canary metrics against fixed thresholds. System latency naturally rises during peak traffic periods, which can cause false alerts. Instead, compare the Canary's performance relative to the Baseline:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//9f466dd6-8578-4e32-bf67-451acb834cea/markdown_2/imgs/img_in_chart_box_221_108_863_449.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A44Z%2F-1%2F%2F35a6a2dc6cf61ea8d5f21809ae8c954ec3bb9f0d5a1b24c0958e87ffa5498851" alt="Image" width="63%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 5-11. Fixed threshold limitations compared to relative baseline evaluations</div> </div>

SREs view these participating clusters inside Spinnaker:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//9f466dd6-8578-4e32-bf67-451acb834cea/markdown_3/imgs/img_in_image_box_148_112_861_565.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A46Z%2F-1%2F%2Fc678c0722dd670e03df65e83b6d4bed3468c97586a0b16fe61f43cc41f3dd7f3" alt="Image" width="70%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 5-12. Spinnaker clusters list showing Baseline and Canary server groups</div> </div>

---

## 34.6 Kayenta Canary Judgement Metrics and Configurations

Spinnaker routes canary analysis to **Kayenta**, an automated canary judgment engine. Kayenta collects metrics for both the Baseline and Canary groups, compares their distributions using statistical tests (like the Mann-Whitney U test), and returns a pass/fail score.

If a metric deviates significantly (e.g. latency rises), Kayenta flags the run:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//9f466dd6-8578-4e32-bf67-451acb834cea/markdown_4/imgs/img_in_image_box_144_107_862_404.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A47Z%2F-1%2F%2F75281429ac4f1f73ce1b37c17a71970afdb08cfe733bb2dbeadd46d632212373" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 5-13. Kayenta metrics classification report dashboard showing failure</div> </div>

SREs define these indicators inside the Spinnaker Canary configuration panel:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//9f466dd6-8578-4e32-bf67-451acb834cea/markdown_4/imgs/img_in_image_box_144_579_861_1018.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A47Z%2F-1%2F%2F216050989d5992d1ec2a52d1bf9276d4d462f9ac8ab17cc3dc73b9415d26d79b" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 5-14. Spinnaker Canary Configs editor panel</div> </div>

We configure the query details and baseline comparisons for each metric:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//aff48df1-e8f4-449e-a48e-0dd63454f7f2/markdown_0/imgs/img_in_image_box_146_262_862_570.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A34Z%2F-1%2F%2F496187896edf984968d7134aa92940507ee221d08379f8c3df05aeea2b283c45" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 5-15. Processor utilization metric query setup in Kayenta</div> </div>

Once defined, we reference this configuration in our deployment pipelines:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//aff48df1-e8f4-449e-a48e-0dd63454f7f2/markdown_0/imgs/img_in_image_box_145_798_862_1084.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A34Z%2F-1%2F%2Fd162a4ba25f47ef5d53771eded4d6cc20fe615c0a62b3fb4cf8be3145805c33e" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 5-16. Spinnaker deployment pipeline orchestrating baseline and canary instances</div> </div>

---

## 34.7 Evaluating Canary Runs: Visualizations

We evaluate canary performance using three visualizations:

### 1. Time Series Comparison
Plots baseline and canary metrics over time:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//aff48df1-e8f4-449e-a48e-0dd63454f7f2/markdown_1/imgs/img_in_image_box_144_463_862_971.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A35Z%2F-1%2F%2F4eabd50e23fdd72d385664bcd5afdf7f3c79a9c315709355d28de2471f5ce628" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 5-17. Processor utilization time series comparison for baseline (blue) and canary (green)</div> </div>

### 2. Histogram Comparison
Plots the distribution frequency of metrics:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//aff48df1-e8f4-449e-a48e-0dd63454f7f2/markdown_2/imgs/img_in_image_box_143_423_863_904.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A36Z%2F-1%2F%2Faa760fdbb6b0be0839bbd44bc5c6a66a740e6dbe4191e1ab82185c6407544b02" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 5-18. Histogram comparison showing a latency distribution shift</div> </div>

### 3. Beeswarm and Box-and-Whisker Plots
Displays individual samples plotted alongside quartile ranges (min, 25th percentile, median, 75th percentile, and max):

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//aff48df1-e8f4-449e-a48e-0dd63454f7f2/markdown_3/imgs/img_in_image_box_144_202_862_679.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A36Z%2F-1%2F%2Fc6a1d3995f8b0a1e1aa24125d57edbe3d13d290c1a867cae15c266f9bab6826b" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 5-19. Beeswarm comparison showing a latency shift between baseline and canary</div> </div>

> [!WARNING]
> Do not evaluate canary health using averages or medians. Outliers (like slow database queries or GC stalls) are obscured by centrality metrics. You must evaluate latency using high-percentile approximations (such as p95 or p99).

---

## 34.8 Kayenta Canary Metrics in PromQL

Below are the Prometheus queries used to configure Kayenta canary analysis:

### 1. Inbound Server Latency (P99)
```promql
# 99th percentile inbound request latency for the target group
histogram_quantile(0.99, sum(rate(http_server_requests_seconds_bucket{app="${app}",version="${version}"}[5m])) by (le))
```

### 2. HTTP Error Ratio
```promql
# Error ratio for the target group
sum(rate(http_server_requests_seconds_count{app="${app}",version="${version}",status=~"5.."}[5m])) / sum(rate(http_server_requests_seconds_count{app="${app}",version="${version}"}[5m]))
```

### 3. Memory Allocation Rate
```promql
# Heap memory allocation rate in bytes per second
sum(rate(jvm_gc_memory_allocated_bytes_total{app="${app}",version="${version}"}[5m]))
```

### 4. CPU Utilization
```promql
# CPU utilization rate for the target group
sum(rate(process_cpu_seconds_total{app="${app}",version="${version}"}[5m]))
```

---

## 34.9 Defining Canary Templates: Kayenta Metric Configuration

To configure Kayenta to automatically parse and evaluate custom Prometheus metrics, we define metric templates in YAML.

These templates specify the query filters, scope parameters, and aggregation rules:

```yaml
# Kayenta Canary Metric Configuration definition template
name: order-service-canary-config
description: "Canary configuration for order-service evaluating release stability"
templates:
  # Define Prometheus query scopes using placeholders
  prometheus-query-template: "sum(rate(http_server_requests_seconds_bucket{app='${scope}',version='${location}'}[5m])) by (le)"
metrics:
  - name: HTTPServerRequestsLatency
    scopeName: default
    group: latency
    analysisConfigurations:
      canary:
        direction: increase # Flag a failure if the Canary metric increases relative to the Baseline
    query:
      type: prometheus
      customInlineTemplate: prometheus-query-template
  - name: ProcessCPUUtilization
    scopeName: default
    group: system
    analysisConfigurations:
      canary:
        direction: increase
    query:
      type: prometheus
      customInlineTemplate: "sum(rate(process_cpu_seconds_total{app='${scope}',version='${location}'}[5m]))"
classifier:
  groupWeights:
    latency: 60
    system: 40
```

---

## 34.10 Kubernetes Canary Orchestration Manifests (`canary-deployment.yaml`)

When running canary deployments on Kubernetes, Spinnaker creates dedicated server groups. 

Below is a complete Kubernetes manifest file demonstrating the declaration of Baseline and Canary Deployments alongside routing Service bindings:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: order-service-baseline
  namespace: production
  labels:
    app: order-service
    track: canary-baseline
spec:
  replicas: 2
  selector:
    matchLabels:
      app: order-service
      track: canary-baseline
  template:
    metadata:
      labels:
        app: order-service
        track: canary-baseline
        version: v1.0.0 # Matches current production version
    spec:
      containers:
        - name: order-service
          image: myorg/order-service:1.0.0
          ports:
            - containerPort: 8080
          env:
            - name: SPRING_PROFILES_ACTIVE
              value: "prod"
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: order-service-canary
  namespace: production
  labels:
    app: order-service
    track: canary-test
spec:
  replicas: 2
  selector:
    matchLabels:
      app: order-service
      track: canary-test
  template:
    metadata:
      labels:
        app: order-service
        track: canary-test
        version: v1.1.0-RC1 # Target release version
    spec:
      containers:
        - name: order-service
          image: myorg/order-service:1.1.0-RC1
          ports:
            - containerPort: 8080
          env:
            - name: SPRING_PROFILES_ACTIVE
              value: "prod"
---
apiVersion: v1
kind: Service
metadata:
  name: order-service-canary-routing
  namespace: production
spec:
  selector:
    app: order-service
    # Route traffic to both baseline and canary pods under test
  ports:
    - protocol: TCP
      port: 80
      targetPort: 8080
```

---

## 34.11 Spinnaker Pipeline JSON Representation: Canary Stage

Spinnaker pipelines are declared as JSON documents. Below is a snippet of a pipeline JSON declaration that defines the `canary` stage, linking Kayenta configurations with target evaluation metrics:

```json
{
  "name": "Automated Canary Judge",
  "type": "kayentaCanary",
  "refId": "canaryStage1",
  "requisiteStageRefIds": [
    "deployCanaryStage"
  ],
  "context": {
    "canaryConfig": {
      "canaryConfigId": "order-service-canary-config",
      "scopes": [
        {
          "controlScope": "order-service",
          "controlLocation": "v1.0.0",
          "experimentScope": "order-service",
          "experimentLocation": "v1.1.0-RC1",
          "startTime": "2026-06-27T08:00:00Z",
          "endTime": "2026-06-27T09:00:00Z",
          "step": 60
        }
      ],
      "scoreThresholds": {
        "marginal": 75,
        "pass": 90
      }
    }
  }
}
```

---

## 34.12 Handling Cold Starts and JVM Warmup in Canary Analysis

When new instances are provisioned, the JVM must load classes, execute initializers, and apply JIT compilation compiler optimizations. During this **warmup period**, request latency is naturally higher.

If Kayenta starts evaluating the Canary group immediately after deployment, the cold-start latency spike will trigger a false canary failure:

* **Warmup Warm-up Period**: SREs configure a lookup delay parameter (e.g. `lifetimeHours: 1` or `warmupMinutes: 10`) inside the canary stage context. This instructs Kayenta to ignore metrics collected during the initial warmup window.
* **Warmup Mocking Traffic**: Alternatively, the pipeline can execute a warmup script stage that routes synthetic benchmark traffic to the Canary group before starting the official Kayenta evaluation window.

---

## 34.13 Automated Rollback Shell Scripts via Spinnaker Orca

If Kayenta scores a canary run below the marginal threshold (e.g. less than 75%), Spinnaker terminates the pipeline and triggers automated rollbacks.

Below is the shell execution script used inside Spinnaker's Jenkins/Run-Job stages to trigger rollbacks using the Kubernetes API:

```bash
#!/usr/bin/env bash
# Automated Rollback script triggered on Canary failure
set -eo pipefail

APP_NAME="order-service"
NAMESPACE="production"
TARGET_REVERSION="v1.0.0"

echo "Canary Analysis scored below threshold! Initiating rollbacks to ${TARGET_REVERSION}..."

# 1. Scale down Canary Deployments immediately to preserve resource usage
kubectl scale deployment/${APP_NAME}-canary --replicas=0 -n ${NAMESPACE}
kubectl scale deployment/${APP_NAME}-baseline --replicas=0 -n ${NAMESPACE}

# 2. Assert routing service points exclusively to stable production instances
kubectl patch service ${APP_NAME}-canary-routing -n ${NAMESPACE} -p '{"spec":{"selector":{"app":"'"${APP_NAME}"'","track":"production"}}}'

# 3. Verify stable pods are active and healthy
kubectl rollout status deployment/${APP_NAME}-production -n ${NAMESPACE}

echo "Rollback operation successfully completed."
```

---

## 34.14 SRE Mathematics: The Mann-Whitney U Test in Kayenta

Rather than comparing simple means or medians, Kayenta applies the **Mann-Whitney U Test** (also known as the Wilcoxon rank-sum test) to compare Baseline and Canary metric samples.

### 1. Why a Non-Parametric Test?
Standard parametric tests (like the Student's t-test) assume that the data follows a normal (bell-curve) distribution. However, microservice response latency is typically **bimodal** or highly skewed due to garbage collection pauses and database timeouts. The Mann-Whitney U test is non-parametric, meaning it makes no assumptions about the shape of the underlying distribution, making it ideal for evaluating bimodal latency curves.

### 2. Calculating the U-Statistic
The test ranks all observed data points from both groups combined (Baseline and Canary) in ascending order. If $n_1$ is the number of samples in the Baseline and $n_2$ is the number of samples in the Canary, the U-statistic for each group is calculated as:

$$U_1 = R_1 - \frac{n_1(n_1 + 1)}{2}$$

$$U_2 = R_2 - \frac{n_2(n_2 + 1)}{2}$$

Where:
* $R_1$ is the sum of ranks for the Baseline samples.
* $R_2$ is the sum of ranks for the Canary samples.

Kayenta compares the smaller of $U_1$ and $U_2$ against critical tables (or uses a normal approximation $z$-score for large sample sizes) to evaluate the **$p$-value**. If the $p$-value falls below the significance threshold (typically $p < 0.05$), Kayenta rejects the null hypothesis, indicating that the Canary's latency distribution is statistically different from the Baseline's.

---

## 34.15 Advanced Canary Traffic Shifting: Istio VirtualService

To route a precise percentage of production traffic to the Baseline and Canary pods under test, we use service mesh configurations instead of standard round-robin Kubernetes routing.

Below is the Istio `VirtualService` manifest that routes 98% of traffic to the stable Production deployment and splits the remaining 2% equally between the Baseline and Canary groups:

```yaml
apiVersion: networking.istio.io/v1alpha3
kind: VirtualService
metadata:
  name: order-service-routing
  namespace: production
spec:
  hosts:
    - order-service.prod.myorg.com
  http:
    - route:
        - destination:
            host: order-service
            subset: stable
          weight: 98
        - destination:
            host: order-service
            subset: baseline
          weight: 1
        - destination:
            host: order-service
            subset: canary
          weight: 1
---
apiVersion: networking.istio.io/v1alpha3
kind: DestinationRule
metadata:
  name: order-service-subsets
  namespace: production
spec:
  host: order-service
  subsets:
    - name: stable
      labels:
        track: production
    - name: baseline
      labels:
        track: canary-baseline
    - name: canary
      labels:
        track: canary-test
```

---

## 34.16 Spinnaker Naming Conventions: Frigga Rules

Spinnaker groups resource versions into clusters using naming conventions originally defined in the **Frigga** open-source library. To prevent Spinnaker from misinterpreting server groups, resources must follow the Frigga naming convention:

`[application]-[stack]-[detail]-[version]`

* **Application**: The name of the business function (e.g. `order`).
* **Stack**: The target deployment environment or infrastructure classification (e.g. `prod`, `staging`).
* **Detail**: Optional free-form descriptors (e.g. `canary`, `west`).
* **Version**: A Spinnaker-managed sequence token (e.g. `v001`, `v002`).

For example, a server group named `order-prod-canary-v042` represents:
* Application: `order`
* Stack: `prod`
* Detail: `canary`
* Version sequence: `v042`

If you do not follow these conventions, Spinnaker cannot manage cluster rollouts or clean up old server groups automatically.

---

## 34.17 Spinnaker Internal Microservices Architecture

Spinnaker itself is designed as a collection of independent microservices, each responsible for a distinct part of the continuous delivery pipeline:

* **Deck**: The browser-based user interface.
* **Gate**: The API Gateway microservice that exposes endpoints for Deck and external scripts.
* **Orca**: The orchestration engine. It coordinates pipeline runs, managing task execution, retries, and database states.
* **Clouddriver**: The integration engine that calls cloud provider APIs (like AWS EC2, Kubernetes, or Google Cloud Platform) to manipulate resources.
* **Rosco**: The bakery service that compiles Debian packages and VM images.
* **Igor**: The CI integrator that polls Jenkins, GitHub Actions, or TravisCI pipelines to trigger rollouts.
* **Front50**: The storage metadata wrapper that persists pipeline configs, applications profiles, and templates.
* **Kayenta**: The automated canary analysis judge that analyzes metrics data using statistical test engines.

By separating pipeline coordination (Orca) from cloud execution (Clouddriver), Spinnaker scales to thousands of concurrent pipeline steps without bottlenecking cloud API endpoints.

---

## 34.18 Advanced Traffic Shadowing: Istio Mirroring Manifest

Rather than routing real user requests to unvalidated canary pods, we can use **Traffic Shadowing** (or mirroring). 

Traffic shadowing copies live production traffic and forwards it to the Canary and Baseline groups, but discards the canary responses. This allows you to evaluate canary performance under real production load without impacting users:

```yaml
apiVersion: networking.istio.io/v1alpha3
kind: VirtualService
metadata:
  name: order-service-shadowing
  namespace: production
spec:
  hosts:
    - order-service.prod.myorg.com
  http:
    - route:
        # Route 100% of real user traffic to the stable Production subset
        - destination:
            host: order-service
            subset: stable
          weight: 100
      # Mirror a copy of the traffic to the Canary subset
      mirror:
        host: order-service
        subset: canary
      # Percentage of production traffic to mirror (10%)
      mirrorPercentage:
        value: 10.0
```

---

## 34.19 The CI/CD Boundary: Separating Concerns

To scale deployments safely, organizations must define the boundaries between **Continuous Integration (CI)** and **Continuous Delivery (CD)**:

* **Continuous Integration (CI)**:
  * **Objective**: Compile source code, execute unit and integration tests, verify quality gates, and output a validated, version-stamped binary.
  * **Tooling**: Jenkins, GitHub Actions, GitLab CI.
  * **End Result**: Code is packaged into an immutable artifact (such as a JAR, Debian package, or Docker image) and published to a central repository (e.g. Nexus, JFrog Artifactory, or Docker Registry).
* **Continuous Delivery (CD)**:
  * **Objective**: Orchestrate the deployment of the immutable artifact across multiple target environments (staging, production), shift traffic, verify service health, and handle automated rollbacks.
  * **Tooling**: Spinnaker, ArgoCD.
  * **End Result**: Artifacts are running safely in production clusters.

By maintaining a clear boundary, the platform team ensures that code compilation issues do not impact running services, and that deployment configurations are managed consistently across all teams.

---

## 34.20 Packaging vs. Configuration Templating: Kubernetes Manifests

When deploying workloads to CaaS platforms (like Kubernetes), you must decouple the application packaging step from the environmental configuration step:

* **Baking Container Images**: Ben Muschko's Gradle Docker plugin or Cloud Native Buildpacks package the application binary (JAR) and runtime (JVM) into a static container image. This image contains no environmental configuration (such as database credentials or API endpoints) and is identical across staging and production.
* **Templating Kubernetes Manifests**: We use tools like Helm, Kustomize, or Spinnaker's manifest templating engine to inject environmental properties (like replica counts or ConfigMap environment variables) into generic Kubernetes manifest templates at deploy time.

This separation ensures that when you need to change a configuration parameter (like scaling the replica count from 2 to 10), you do not need to compile and bake a new container image, reducing pipeline duration and preserving the stability of the binary.

---

## 34.21 SRE Practices: Kayenta Scoring Mechanics

When Kayenta evaluates a canary run, it performs statistical tests on each registered metric. It then aggregates the results into a single **Canary Score**:

$$\text{Canary Score} = \frac{\text{Number of passed metrics}}{\text{Total number of evaluated metrics}} \times 100$$

### 1. Threshold Evaluations
SREs configure two thresholds inside the pipeline:
* **Pass Threshold (e.g. 90)**: If the Canary Score is greater than or equal to this limit, the canary run succeeds, and Spinnaker promotes the release, replacing the remaining production server groups.
* **Marginal Threshold (e.g. 75)**: If the Canary Score falls below this limit, the canary run fails immediately. Spinnaker halts the pipeline and runs the rollback scripts to tear down the baseline and canary pods.
* **Marginal Range (75 to 89)**: If the Canary Score falls between the two limits, the pipeline goes into a suspended state. Spinnaker stops routing new traffic and alerts the on-call engineer, requiring manual judgment to either promote or rollback the release.

This automated scoring model ensures that minor, non-critical metrics variance (e.g. a slight CPU shift) does not block rollouts, while severe availability failures (e.g. an error rate increase) trigger instant rollbacks.

---

## 34.22 Database Backward Compatibility: The Expand/Contract Pattern

Canary deployments share the same physical database instances with the active Production group. If the new release includes a database schema migration, the migration must be backward-compatible with the old code.

To execute schema refactoring without downtime, we apply the **Expand/Contract Pattern**:

1. **Expand**:
   * **Action**: Add new columns, tables, or indexes. Never drop or rename columns in this phase. If you are renaming a column, add the new column and run a background task to synchronize values.
   * **Canary Run**: Run the canary using the expanded database. Both the Production (v1.0) and Canary (v1.1) microservices can execute query calls safely because the old columns remain intact.
2. **Contract**:
   * **Action**: Once the canary test passes and v1.1 is fully promoted to 100% of traffic, run a subsequent cleanup migration to drop the old columns or tables.

This pattern ensures that if a canary fails and we rollback, the stable Production pods can continue querying the database without database syntax errors.

---

## 34.23 Canary Analysis for Event-Driven Microservices

While HTTP-based services can route traffic using load balancer weights, event-driven consumers (e.g., Kafka message listeners) process messages pushed from messaging queues.

To deploy a 1% event-driven canary safely:

* **Consumer Group Sharing**: Deploy the Baseline and Canary pods in the same Kafka consumer group. Because Kafka balances partitions across consumers, the Canary will automatically receive a subset of partitions.
* **Weighted Partition Routing**: For precise control, configure a custom partitioner on the Producer side to tag a percentage of records with a canary header (`X-Canary-Routing: true`). The listener code uses Spring Cloud Stream routing rules to dispatch tagged records to the Canary consumer instances specifically:

```java
package com.ftgo.order.consumer;

import org.springframework.cloud.stream.annotation.EnableBinding;
import org.springframework.cloud.stream.annotation.StreamListener;
import org.springframework.cloud.stream.messaging.Sink;
import org.springframework.messaging.Message;
import org.springframework.stereotype.Component;

@Component
@EnableBinding(Sink.class)
public class OrderEventConsumer {

    @StreamListener(target = Sink.INPUT, condition = "headers['X-Canary-Routing']=='true'")
    public void processCanaryEvents(Message<String> message) {
        // Canary instance processes event under test...
        System.out.println("Processing canary message: " + message.getPayload());
    }

    @StreamListener(target = Sink.INPUT, condition = "headers['X-Canary-Routing']!='true'")
    public void processStandardEvents(Message<String> message) {
        // Standard production instance processes event...
    }
}
```

---

## 34.24 Spinnaker Clouddriver Provider Caching Mechanisms

To show real-time instance counts, Spinnaker relies on Clouddriver to poll Kubernetes and AWS provider endpoints. This polling mechanism is optimized using **Provider Caching Agents**:

* **Caching Cycles**: Caching agents run asynchronously on a cron schedule (typically every 30 seconds), fetching resource states (Deployments, Pods, Services) and persisting them in a Redis or SQL cache.
* **API Reductions**: When you view the Spinnaker Deck UI, all queries are served from the cache rather than hitting the cloud provider APIs directly. This design prevents Spinnaker from hitting cloud rate limits under large deployments.
* **Cache Eviction**: When a pipeline runs a `Deploy` stage, Spinnaker issues a force cache refresh command to update the local cache immediately, ensuring that subsequent verification stages receive correct instance health markers without waiting for the default polling interval.

---

## 34.25 Resiliency Telemetry in Canary Judgements

When evaluating canary versions, you must verify that dependency failures do not degrade overall application throughput. We monitor **Resilience4j** telemetry during canary analysis:

* **Short-Circuited Counts**: If the Canary version triggers circuit breakers, the number of short-circuited requests will rise:
  ```promql
  sum(rate(resilience4j_circuitbreaker_buffered_calls{app="${app}",version="${version}",kind="failed"}[5m]))
  ```
* **Fallback Executions**: Monitor fallback invocation rates. If fallbacks increase on the Canary while remaining stable on the Baseline, the Canary contains a dependency communication issue:
  ```promql
  sum(rate(resilience4j_circuitbreaker_not_permitted_calls{app="${app}",version="${version}"}[5m]))
  ```

Kayenta uses these resiliency metrics to reject releases that would otherwise pass standard latency and HTTP 200/500 thresholds (e.g. when failing silently using fallback default values).

---








## 34.24 Summary of Canary Analysis and Deployment Configurations

This table summarizes the configurations, rules, and parameters used to build automated canary analysis pipelines:

| Deployment Element | Kayenta / Spinnaker Config | Main Implementation Target | Scope Location |
| :--- | :--- | :--- | :--- |
| **Baking OS** | `buildDeb` / `buildRpm` | Packages code as immutable OS-level dependencies. | Gradle Build |
| **Baking Container** | `springBootApplication` | Compiles applications as static container images. | Gradle Build |
| **Highlander Strategy**| instanceReplacement = true | Replaces instances immediately, minimizing cost. | Spinnaker Stage |
| **Blue/Green Strategy**| disabledReplicasCount | Keeps the old server group disabled for fast rollbacks. | Spinnaker Stage |
| **Canary Group** | `Canary` | The test group running the new version of code. | Deployment stage |
| **Baseline Group** | `Baseline` | The control group running the production version. | Deployment stage |
| **Kayenta Judge** | Mann-Whitney U test | Evaluates metric distribution differences. | Kayenta Config |
| **Canary Latency** | `http_server_requests` | Tracks response time distributions. | Prometheus Query |
| **Allocation Rate** | `jvm_gc_memory_allocated` | Tracks heap allocation rates to detect memory leaks. | Prometheus Query |
| **Beeswarm Plot** | Box-and-whisker | Displays latency quartiles and outliers. | Kayenta Report |

---

## Chapter Summary

* Immutable infrastructure requires baking code into static VM or container images rather than modifying running instances.
* Spinnaker defines a multicloud resource model using Applications, Clusters, Server Groups, and Instances.
* Nebula ospackage Gradle plug-ins simplify immutable packaging by compiling Spring Boot applications as Debian files and Docker images.
* Highlander deployments minimize operational costs but result in slow rollbacks. Blue/Green deployments maintain disabled server groups to enable near-instant rollbacks.
* Kubernetes rolling updates behave like a specific kind of Blue/Green deployment by default.
* Automated Canary Analysis (ACA) deploys Baseline and Canary server groups side-by-side to evaluate new code.
* Comparing the Canary directly to the Production group is statistically invalid. You must use a Baseline control group.
* Kayenta evaluates canary health relative to the Baseline, preventing false alarms during peak traffic periods.
* Averages and medians hide outliers. SREs evaluate canary latency using high-percentile approximations (p95 or p99).
* Kayenta evaluates canary health using time series comparison, histograms, and beeswarm visualizations.
* JVM cold starts require configuring a metric lookup delay to prevent false canary failures during JVM warmups.
* Write automated rollback scripts inside Spinnaker Orca to scale down failed canaries and restore stable routing parameters.
* Apply the non-parametric Mann-Whitney U statistical test inside Kayenta to compare bimodal latency distributions reliably.
* Route traffic dynamically to Baseline and Canary groups using Istio VirtualService weights or Kafka message listeners header routes.
* Follow the Frigga naming convention in Spinnaker to automate version sequencing and old server group cleanups.
* Understand the boundaries between CI (packaging code artifacts) and CD (deploying and validating release stability).
* Apply the Expand/Contract database schema pattern to ensure backward compatibility during canary runs.
* Understand Spinnaker internal microservices architecture (Deck, Gate, Orca, Clouddriver, Rosco, Igor, Front50, Kayenta).
* Apply traffic shadowing configurations using Istio mirroring rules to stress-test canaries safely.
* Understand Clouddriver caching agents polling schedules and forced cache eviction methods.
* Track Resilience4j short-circuits and fallbacks rates metrics during canary evaluations to prevent silent failures.
---

## 34.12 Production-Grade Spinnaker and Kayenta Canary Analysis Configuration

To automate canary releases, the platform engineering team leverages **Spinnaker** integrated with **Kayenta** for Automated Canary Analysis (ACA). During a deployment, Spinnaker provisions two temporary server groups alongside the stable production environment:
1. **Baseline**: Runs the currently active production version of the service but receives the same amount of traffic as the canary.
2. **Canary**: Runs the newly compiled release candidate.

Kayenta queries Prometheus to extract latency and error rate metrics from both groups and computes a metric comparison score using the non-parametric **Mann-Whitney U test**.

```
+---------------------------------------------------------------------------------+
|                       KAYENTA AUTOMATED CANARY JUDGEMENT                       |
+---------------------------------------------------------------------------------+
|                                                                                 |
|                      [ Ingress Traffic / Load Balancer ]                        |
|                         /                          \                            |
|                        v                            v                           |
|           [ Baseline Server Group ]       [ Canary Server Group ]               |
|            - Version: Stable v1.1.0        - Version: Candidate v1.2.0          |
|            - Metrics Scraped (Prom)        - Metrics Scraped (Prom)             |
|                        \                          /                             |
|                         v                        v                              |
|                    [ Kayenta Canary Judgment Engine ]                           |
|                      - Mann-Whitney U statistical comparison                    |
|                      - Pass Score: 90 / Marginal Score: 75                      |
|                                                                                 |
+---------------------------------------------------------------------------------+
```

---

### The Spinnaker Pipeline Canary Stage: `spinnaker-kayenta-stage.json`
Below is the complete Spinnaker JSON pipeline configuration for executing a 1-hour canary check of the **review-service** using Kayenta.

```json
{
  "name": "Kayenta Canary Analysis",
  "type": "kayentaCanary",
  "refId": "canaryStage1",
  "requisiteStageRefIds": [
    "deployBaselineCanary"
  ],
  "context": {
    "analysisType": "realTime",
    "canaryConfig": {
      "canaryConfigId": "review-service-canary-config",
      "canaryAnalysisConfig": {
        "lookbackMins": 0,
        "notificationHours": [
          1
        ],
        "useLookback": false
      },
      "combinedCanaryResultDecisions": [],
      "scopes": [
        {
          "controlLocation": "us-east-1",
          "controlScope": "review-service-baseline",
          "experimentLocation": "us-east-1",
          "experimentScope": "review-service-canary",
          "extendedScopeParams": {
            "dataset": "production"
          },
          "scopeName": "default",
          "step": 60
        }
      ]
    },
    "deployments": {
      "baseline": "review-service-baseline",
      "canary": "review-service-canary"
    },
    "metricsAccountName": "prometheus-prod-cluster",
    "storageAccountName": "s3-canary-results",
    "canaryConfigMap": {
      "name": "review-service-canary-config",
      "metrics": [
        {
          "name": "Reviews Latency p99",
          "query": {
            "type": "prometheus",
            "customFilter": "service=\"review-service\"",
            "metricName": "ftgo_order_reviews_fetch_latency_seconds_bucket"
          },
          "scopeName": "default",
          "groups": [
            "Latency"
          ],
          "analysisConfigurations": {
            "canary": {
              "direction": "increase",
              "nanStrategy": "replaceWithZero"
            }
          }
        },
        {
          "name": "Reviews Error Ratio",
          "query": {
            "type": "prometheus",
            "customFilter": "service=\"review-service\"",
            "metricName": "ftgo_order_reviews_submitted_count_total"
          },
          "scopeName": "default",
          "groups": [
            "Errors"
          ],
          "analysisConfigurations": {
            "canary": {
              "direction": "increase",
              "nanStrategy": "replaceWithZero"
            }
          }
        }
      ],
      "classifier": {
        "groupWeights": {
          "Latency": 60,
          "Errors": 40
        }
      },
      "scoreThresholds": {
        "marginal": 75,
        "pass": 90
      }
    }
  }
}
```
