### Index

##### A

Abstract QueuedSynchronizer, 357

abusing correlated logs antipattern, 253

access control, method handle, 350

access flags, 54

acknowledgment (ACK), 380

action bias, 46

actor-based task representation techniques, 367-368

AGCT (AsyncGetCallTrace), 319

agents, 63-64

hprof heap profiling native agent, 333

manual versus automatic instrumentation, 251

OTel, 286, 296

perf-map-agent, 317

profiling, 306

aggregation

avoiding percentile aggregation, 252, 277

logs, 242

metrics, 239, 250, 266

ahead-of-time (AOT) compilation

code execution, 163-164

for faster Java application launching, 221

GraalVM, 71, 416

versus JIT compilation, 59

and zero-overhead principle, 57

alerting systems, purpose of, 306

allocation rates, 13

cache hardware, 175-177

garbage collection, 85, 101, 102

allocation, memory

garbage collection, 97-102, 107

mark and sweep algorithm, 77-79

profiling, 329-331

TLABs, 87-88, 93, 177, 331

Amazon Corretto, 71

Amazon EC2 virtual machines, 200

ambient context data, and scoped values, 411

Amdahl, Gene, 12

Amdahl's law, 12, 338-339

Andreessen, Marc, 170

Android project, 72

anewarray bytecode, 148

antipatterns, 249-254

causes of performance, 26-28

and cognitive biases, 44

AOT compilation (see ahead-of-time (AOT) compilation)

Apache Pekko framework, 368

AppendEntry, Raft, 387

Application class loader, 52

application performance monitoring (APM), 238, 288

application versus platform threads, 61

architecture robustness, 10

Argo CD, canary releases, 226-229

arithmetic bytecodes, 144

arraylets, Balanced collector, 130

arrayOops, 81, 83

arrays

  allocating large arrays in Balanced, 130-131

  anewarray bytecode, 148

  memory layout in Java, 421-422

  struct-like, 423

as-if-serial JMM guarantee, 345

Async Profiler, 319-320, 329

AsyncGetCallTrace (AGCT), 319

AsyncGetCallTrace() method, 319

asynchronous contagion, 373

asynchronous execution, 362-363

asynchronous messaging, distributed tracing for, 244

AtomicDouble class, 269

AtomicInteger class, 353-354

AtomicLong, 378

attach mechanism, in VisualVM, 67

attributes, role of, 54

automatic tracing, OTel, 296-297

automatic versus manual instrumentation, 250-252

average (simple mean), problems in latency testing, 19

Azul Systems (Zulu), 71

##### B

Bakker, Paul, 51

Balanced collector (Eclipse OpenJ9), 128-132

barriers and latches, concurrency, 360-361

@Benchmark annotation, 436

benchmarking (see microbenchmarking)

big-endian hardware architecture, 142

binary semaphore, 359

binding values to specific scope, 409

bindTo() method, 277

blackholes, in benchmarking code, 437-439

Blame Donkey antipattern, 44, 46, 448-449

blocking queues, 347

blocking threads

avoiding, 355

two-phase commit issue with, 380

vthreads and I/O, 371

blue/green deployment technique, 224-225

Bootstrap class loader, 50-52

bootstrap method (BSM), 348

bootstrapping classes, initializing, 138

boredom, as cause of performance antipatterns, 27

branch prediction, 177

breaking point, latency and throughput, 19

Brooks pointers, 113, 124

BSM (bootstrap method), 348

buckets, in histograms, 35

“build and run” teams, 211

build cache, container image, 203

build phase, Quarkus, 165-166

Builder pattern, for vthreads in Thread class, 372

Burns, Brendan, 223

burst rate, bandwidth to memory, 174

bytecode

Java agent's role in transformation, 63

java.lang.instrument to modify, 63

JVM execution, 52-56

bytecode interpretation, 137, 140-152

families and categories, 142-149

HotSpot specifics, 150-152

simple interpreters, 149-150

bytecode weaving, 52, 251

##### C

C++11 model, 347

C1 and C2 JIT compilers in HotSpot, 156-157, 419

C or C++, 57, 59, 64

cache consistency protocols, 173

Cache interface, Infinispan, 391

cache lines, and mechanical sympathy, 190

call site, 146

call target, 348

Callable interface, 362

canary deployment technique, 226-229

CAP theorem, 383

capacity metric, 8

capacity planning test, 20

card tables

HotSpot, 91

Parallel collector, 120

cardinality, metric dimensions, 239

carrier threads, and vthreads, 180, 370, 372, 374

cascading failure, 259-260

Cassandra DB, 389-391

Cassandra Query Language (CQL), 389

causation versus correlation, 38-40

CDS (class-data sharing), Leyden, 418

centralized logging pattern, 242

cgroups, containers, 205, 233

Chaos Monkey, 21

Clark, Jason, 51

class files, bytecode, 52-56

class loading, 50-52, 138

Class object, 52, 81

class slot, as OpenJ9 object header, 129

class-data sharing (CDS), Leyden, 418

ClassLoader::getPlatformClassLoader, 51

ClassNotFoundException, 52

Cleanup phase, GI mixed collection, 119, 120

client push delivery, metrics, 250, 267

client-side metrics aggregation, 250, 266

clocks, generation, 378, 384, 387

closed world constraint, Leyden, 416

Cloud Native Computing Foundation (CNCF), 195-197

cloud systems, 193-209

applications native to, 5

as clusters of JVM processes, 16

deployment of Java to (see deployment of Java to cloud)

design for failure aspect, 21

failure mode awareness in clustered applications, 21

Fighting Animals example, 206-208

images and containers, 202-205

Java standards for, 194-195

migration to cloud, 229-232

networking, 205-206

performance optimization, 14-16

testing environment considerations, 23

virtualization, 198-201

cluster-based observability, 262

cluster-wide IDs, 378

clusters (see cloud systems; Kubernetes)

CMS (Concurrent Mark Sweep) collector, 92, 115, 132-133

CNCF (Cloud Native Computing Foundation), 195-197

CNCF Landscape, 196

code cache, JIT compilation in HotSpot, 157-159

code execution, 137-168

AOT compilation, 163-164

asynchronous, 362-363

bytecode, 52-56, 137, 140-152

GraalVM, 167

JIT compilation in HotSpot, 152-162

JMH execution benchmarks, 436

lifecycle of Java application, 138-140, 162

profiling (see profiling)

Quarkus framework, 164-166

speculative, 177

speed of Java and JVM, 3

cognitive biases, 44-47, 305

collections interfaces, concurrency, 359, 366

Collector, OTel, 290-291

colored pointers, ZGC, 126, 127

colorless pointers, ZGC, 127

common causation, 38

commonPool() static method, 365

compacting, GC, 80

compaction property, garbage collection, 107, 158

compare-and-swap (CAS) operations, 113, 353-354

compareAndSwap(), 357

compiler intrinsics, 163

@CompilerControl annotation, 439-441

CompositeMeterRegistry, 273

compound failures, observability diagnosis, 260

compressed oops, 82-83

computation shifting, Leyden, 416

ConcGCT Threads, 118

concurrency, 335-376

distributed systems (see distributed systems)

JMM, 342-347

libraries for, 347-361

  atomics and CAS, 353-354

  collections interfaces, 359

  latches and barriers, 360-361

  locks and spinlocks, 354

  locks in java.util.concurrent, 356-357

  method and var handles, 348-352

  read/write locks, 358

  semaphores, 359

  nature of Java, 339-342

  scoped values, 409-412

  structured, 405-409

  task abstraction and executors, 362-368

  virtual threads, 369-375, 405-409

Concurrent Mark phase, G1 mixed collection, 119

concurrent mode failure, G1 col

Concurrent Start phase, G1 mixed collection, 119

condenser transformation, Leyden, 417

confirmation bias, 44, 45

conservative scheme, GC, 79

consistency level, Cassandra, 389

const versus ldc bytecodes, 144

constant pool, 54

constructors, 56

container image, 202-204

containers

deployment techniques, 223-232

G1 garbage collector caution, 121

GC concern with, 232-233

JFR profiling, 326

local container, Java deployment, 212-214

and observability, 237

orchestrating for Java deployment, 197, 215-223

perf profiler issues, 319, 320

removal development, 223

running, 205

scheduling challenges, 221-223

as units of deployable code in cloud system, 15

versions, dependencies and, 208

contention level, concurrent processing, 354, 364

context switches, 183-184

Continuous profile, JFR, 321

continuous profiling, 249

control plane, container orchestration, 215, 223

CopyOnWriteArrayList, 360

CopyOnWriteArraySet, 360

cores (see processors)

correlated logs, antipattern, 253

correlation versus causation, 38-40

correlations between observables metric, 10

cost optimization

adjusting VMs, 201

in moving to cloud, 198

networking, 205

counted loop, safepointing bias, 315

counter() method, 269

counters, 239, 268, 339-342

CPUs

garbage collection challenge for, 189, 232

memory caches, 172-177

OS process scheduler to manage, 180-182

out-of-order, 320

utilization metric, 8, 186-188, 307

cpu_memory_usage, dimensional metric, 239

CQL (Cassandra Query Language), 389

crash dump files, 64

Cryostat, 326-327

curl statement, working with local containers, 212, 214

CyclicBarrier, 361

##### D

DAG (directed acyclic graph), 50

data exfiltration, OTel focus on, 292

data parallelism, 12

(see also concurrency)

Amdahl's law, 12, 338-339

versus task parallelism, 337

data plane, container orchestration, 215

data sampling (see sampling)

data sources (see three pillars model for data sources)

database (Cassandra), distributed systems, 389-391

DataLite antipattern, 452-454

DDR RAM, 175

decision point, blue/green deployments, 224

degradation metric, 9, 10, 11, 21-22

deoptimization, 139

dependencies

loading, 52

versions, dependencies and containers, 208

deployment of Java to cloud, 211-234

blue/green technique, 224-225

canary technique, 226-229

evolutionary architecture, 229-232

feature flags technique, 230-232

GC and containers concern, 232-233

local container, 212-214

memory and OOMEs, 233-234

orchestrating containers, 197, 215-223

versus release, 223

Deployment, container orchestration, 216

deserialization, 381

Designing Data-Intensive Applications (Kleppmann), 380

DevOps, 211, 237, 243

diagnosing application problems, 254-261

dimensions, metric, 239, 249

direct causation, 38

directed acyclic graph (DAG), 50

Distracted by Shiny antipattern, 45, 443-444

Distracted by Simple antipattern, 444

distributed systems, 377-404

cloud native (see cloud systems)

consensus protocols, 384-388

data structures, 378-384

database (Cassandra), 389-391

event streaming (Kafka), 391-393

fallacies of, 377

Fighting Animals, 393-404

in-memory data grid (Infinispan), 391

logging, 242

“split-brain”, 256-258

traces, 243-247, 248, 256, 274

distributed_systems, Fighting Animals, 207

distribution summaries, Micrometer, 274-277

distributions, JVM, 68-73

Docker Compose, 212-214

Docker OCI, 202, 204

docker-compose up command, 212-214

docker-compose.yml, 212

Dockerfile, 203, 204

domain-specific language (DSL), 279

.dot (offset operator), 80

dotted naming convention, metrics, 249

dynamic scope, 410

dynamic VM mode, 140, 165

##### E

Eclipse Adoptium, 70

Eclipse Foundation, 194

Eclipse Memory Analyzer (MAT), 332

Eclipse Open J9, 72

Eden space, 86, 87-88

efficiency metric, 9, 15

Elasticsearch, 242

ELK stack, 242

embarrassingly parallel tasks, 338, 364, 366

encryption by proxy, service mesh, 218

endurance (soak) test, 20

entrypoint class, JVM, 50

Envoy proxy, 217

ephemeral compute, 205

Epsilon collector, 134

error types, 29-33

evacuation of live objects after GC, 80

evaluation stack, 140-142

EvaluationStack variable, 150

Evans, Benjamin J., 51, 202

event streaming (Kafka), 391

events, log, 242

eventual consistency behavior, Cassandra, 389

evolutionary architecture in Java deployment, 229-232

exact GC scheme, 79

execMethod() method, 149-150

execution contexts, 61

(see also code execution; multithreaded code)

Executor objects, 337

Executors helper class, 363

Executors.newVirtualThreadPerTaskExecutor(), 374

ExecutorService, 362, 363

AutoCloseable feature, 374

Fork/Join framework, 364-366

ExecutorService, Micrometer, 278

experimental science

JVM as, 5-6

performance analysis as, 5-6

external versus internal pointers, GC roots, 84

##### F

facade pattern, 266, 280

false sharing, 191

fault tolerance

data partitioning, 382

Infinispan, 391

feature flags technique in deployment, 230-232

Feynman, Richard, 39

FFM (Foreign Function and Memory) API, 412-414

Fiddling with Switches antipattern, 83, 451

fields, role of, 54

Fighting Animals example, 206-208

active hospital service, 400-404

automatic tracing, 296

blue/green deployment technique, 224-225

canary deployment technique, 226

data plane deployments, 216

distribution summaries, 275-276

Docker containers, 206

enhancement with Kafka, 393-404

feature flags, 231-232

manual tracing, 292

OTel metrics, 298-299

Pods and Services, 219-220

Prometheus with Micrometer, 280-284

simple hospital service, 397-400

timer code, 273

versions, dependencies and containers, 208

filters, meter, 271-273

final method, 151-152

Fischer, Lynch, and Paterson (FLP) Impossibility result, 386

flame charts, 319

flame graphs, 317-319

Flanagan, David, 51

Fichel, Carey, 27

floating garbage problem, 120, 129

flow control opcodes, 144

fMethod() method, 151

fog of war bias, 46

Foreign Function and Memory (FFM) API, 412-414

Fork/Join framework, 364-366

ForkJoinPool implementation, 364-366

ForkJoinTask class, 364, 367

forwarding pointers, GC, 113-114

full generational collection, 86, 120

##### G

G1 (Garbage First) collector, 114-122  

collection types, 117  

full collections, 120  

heap layout and regions, 115-117  

JVM config flags for, 121-122  

mixed collections, 117-119  

remark phase, 113  

remembered sets (RSets), 119  

garbage collection (GC), 4, 75-102, 105-134  

allocation rate and object lifetime, 85  

Balanced collector, 128-132  

benchmarking complications from, 430  

concurrent GC theory, 107-114  

containers concern, 232-233  

and CPU usage, 188, 232  

fragmentation of, 158  

G1 collector, 114-122  

glossary, 79-80  

HotSpot runtime, 80-85  

impact on performance, 60  

importance of logging for performance testing, 307  

at JVM startup, 139  

mark and sweep algorithm, 75, 77-79  

memory allocation role, 97-102, 107  

niche HotSpot collectors, 132-134  

nondeterminism of, 107

parallel collectors, 75, 79, 92-97

pluggable collectors, 106-107

production techniques, 87-92

reading performance graphs, 13

Shenandoah collector, 122-125

thread sharing, 62

WGH in memory management, 86-87

ZGC, 125-128

gauge() method, 270, 271

gauges, 239, 269-271

Gaussian distribution, 31

GC roots, HotSpot, 84

generation clocks, 378, 384, 387

Generational ZGC, 127-128

generations in garbage collections, 115, 128

get() method, atomic integer class, 353

GetCallTrace() function, HotSpot, 315

global garbage collection (GGC), 129

global mark phase, Balanced collector, 129

Go runtime metrics, with Prometheus, 283

goals for performance, identifying before testing, 24-25

Goetz, Brian, 306, 338, 365, 381, 423

Goldratt, Eli, 6

Google Caliper, 435

Google Cloud virtual machines, 200

Gosling, James, 4, 77

Governor, James, 235

GraalVM, 71, 165, 167

Graduated template, CNCF projects, 196

Grafana graphing tools, 279

graphical user interface (GUI) tools, profiling, 308-314

Gregg, Brendan, 252

gRPC, OTLP, 289

##### H

happens-before JMM guarantee, 345

hardware, 169-179

benchmarking challenges, 431

branch prediction, 177

CPUs (see CPUs)

file I/O, 189

garbage collection, 188, 232

JVM portability, 142

mechanical sympathy, 190

memory models, 178-179

memory performance, 171

performance counters, 316

simple system model, 184

speculative execution, 177

speed limit on, 337

TLB, 177

hashed slots, OpenJ9 object headers, 129

Hashemi, Mahmoud, 44

“hat/elephant” problem, 41-44

HDR (high dynamic range) distributions, 35

HdrHistogram, 35-37

heap memory management, 60

(see also garbage collection)

classic heap in HotSpot, 90-92

heap dump analysis, 332-333

IHOP, 117, 121

layout and regions, G1 collector, 115-117

reserving userspace memory for Java, 138

Segmented Code Cache, 159

visualizing, 78, 79, 332

heartbeating network connections, 382, 387

hemispheric evacuating collector, GC, 88-90

Hibernate, 28

high dynamic range (HDR) distributions, 35

histogram, 35

Honest Profiler, 320

horizontal partitioning, 382

horizontal scaling, 193

hot loop, 155

“hot paths” in JIT compilation, 34

HotSpot, 10, 56-58, 72

(see also JDK Flight Recorder)

and Async Profiler, 319

bytecode interpretation specifics, 150-152

classic heap, 90-92

G1 collector, 114-122

garbage collection, 80-85

and Java distributions, 69

JIT compilation in, 58-60, 152-162, 419

niche garbage collectors, 132-134

objects representation at runtime, 81-84

production GC techniques, 87-92

sampling execution profilers, 315

system clock access, 182-183

hprof heap profiling native agent, 333

HTTP/2, OTLP, 289, 300

humongous object, G1 collector, 117

hybrid architecture choice, 230

HyperAlloc tool, Amazon, 101

hypervisors, 199

### I

I/O

file, 189

virtual threads, 371, 374

IDs, cluster-wide, 378

ifstat, 186

IHOP (Initiating Heap Occupancy Percent), 117, 121

imagePullPolicy, Kubernetes, 221

images, container, 202-204, 221

immutability of configuration, 237

immutable infrastructure, 23

immutable objects, distributed data structures, 378

in-memory data

Infinispan grid, 391

partition backups, 382

virtual thread competition in, 406

incremental collection, G1 collector, 116

Incubating template, CNCF projects, 196

Infinispan, 208, 391

inflection point, latency and throughput, 19

ingress traffic (north to south), 205

Ingress, Kubernetes resource, 224

inheritance hierarchy, oops, 84

Initiating Heap Occupancy Percent (IHOP), 117, 121

instance method calls, 146

instanceOops, 81

instant vector, 284

instrument types, Micrometer, 267-277

instrumentation, OTels focus on, 245, 286-289

integration tests versus microbenchmarks, 307

inter-process communication (IPC) call, 183

interface entries, 54

internal versus external pointers, GC roots, 84

interpreter, JVM, 49

(see also bytecode interpretation)

invocation count, 156

invoke() method, 349-350

invokedynamic opcode, 146-147, 348

invokeinterface opcode, 146

invokespecial opcode, 56, 146, 151

invokevirtual opcode, 146, 152

iostat, 187, 190

IPC (inter-process communication) call, 183

Istio (service mesh project), 217

##### J

Jakarta EE, 194

Java

application lifecycle, 138-140

cloud stack standards, 194-195

measuring low-level performance, 427-432

portability issue, 202

reserving userspace heap memory for, 138

testing limitations due to runtime optimizations, 428

Java 9 Modularity (Mak and Bakker), 51

Java agents (see agents)

java binary, starting virtual machine process, 50

Java Concurrency in Practice (Goetz et al.), 336, 338

Java in a Nutshell (8th Ed.) (Evans, Clark, and Flanagan), 51

Java language and JVM, independence of, 53

Java Management Extensions (JMX), 63

Java Memory Model (JMM), 62, 179, 339, 342-347

Java Microbenchmark Harness (JMH), 134, 435-442

Java Native Interface (JNI), 182

Java Platform Module System (JPMS), 50

Java Virtual Machine Tool Interface (JVMTI), 64

Java virtual machines (JVMs), 49-74

benchmarking complications of, 429

class loading mechanism, 50-52

distributions and implementations, 68-73

executing bytecode, 52-56

as experimental science, 5-6

HotSpot virtual machine, 56-58

as interpreter, 49

Java's practical focus and development with, 4-5

JIT compilation, 58-60

JVM warmup, 153

lifecycle of Java application, 138-140

memory management, 60

modularity of, 50

monitoring and tooling for, 62-68

multithreaded programming, 61-62

operating system access, 182-183

release cycle, 73

statistics for performance, 29

strong memory model challenge for, 344

Java-specific issues in performance testing, 25

java.base, loading with Bootstrap, 51

java.lang.instrument,63

java.lang.invoke package, 349

java.util.concurrent, 356-357

java.util.concurrent libraries, 347

java.util.concurrent.AtomicInteger, 353

java.util.concurrent.lock.Lock, 356

javac (compiler), 52, 55, 56, 153

javap (file disassembler), 53, 55

Java_java_lang_System_registerNatives(), 182

jconsole tool, 64

JDK Flight Recorder (JFR), 329

and JDK Mission Control, 310-314

memory allocation profiling, 331

profiling tools, 321-327

JDK Mission Control (JMC), 310-314, 328, 330

JFR Analytics, 324

JFR Event Streaming, 326

jgroups library, Infinispan, 391

Jib, 203

JITWatch tool, 161, 441

jmap -histo command-line tool, 78

jmap command, heap dump analysis, 332

JMH (Java Microbenchmark Harness), 435-442

JMH (Java Microbenchmark Harness)), 134

JMM (Java Memory Model), 62, 179, 339, 342-347

JMX (Java Management Extensions), 63

JNI (Java Native Interface), 182

JNI CreateJavaVM function, 138

join() method, structured concurrency, 406

joinUntil() method, 407

JPMS (Java Platform Module System), 50

JSON serialization format, 381

JSR-133 Cookbook for Compiler Writers, 346

jstatd process, 67

just-in-time (JIT) compilation, 2, 25

versus AOT compilation, 163

benchmarking complications from, 431

HotSpot's use of, 58, 152-162

code cache, 157-159

logging, 159-161

multiple compilers (C1 and C2), 156-157, 419

PGO, 152-154

simple JIT tuning, 161

vtables, klass words, pointer swizzling, 154-155

impact on performance, 10

at JVM startup, 139

JVM's use of, 58-60

Valhalla's impact on, 424

jvisualvm binary, 64

JVM config flags

G1 collector, 121-122

Shenandoah, 123

JVM intrinsics, 59

JvmMemoryMetrics class, Micrometer, 278

JVMTI (Java Virtual Machine Tool Interface), 64

JVM CurrentTimeMillis().182

##### K

Kabutz, Heinz, 365

Kafka, 207, 391-404

kernal switching, 183-184, 188, 199

Kibana, 243

klass word, 81-84, 155

Kleppmann, Martin, 380

Knuth, Donald, 306

KRAft consensus protocol, 393

kubectl command, 216

Kubernetes (K8s), 197

container orchestration, 215-223

Cryostat profiling, 327

deployment techniques, 223-232

k8s-with-argo, 207

local container environment, 212-214

and observability, 237

service-to-service calls, 206

Kubernetes Best Practices (Burns), 223

##### L

lacing call target to site, 348

lack of understanding, as cause of performance

  antipatterns, 28

Lamport, Leslie, 384

large arrays in Java, allocating in Balanced collector, 130-131

latches, 110, 360-361

latency metric, 8, 18

LaunchDarkly, 231-232

ldc versus const bytecodes, 144

leader-follower based protocol, Raft as, 386

lexical (Java) versus dynamic scoping, 411

Leyden, Project, 414-420

lifetime, object, Java's handling of, 75

lift-and-shift approach to rehosting for cloud migration, 230

lightweight transactions versus regular operations, 390

linear scalability, 11, 13

linearizable consistency, with Cassandra DB, 390

Liskov substitution principle, 151

little-endian hardware architecture, 142

live object graph, 77

liveness health check, Pods, 218

load and store opcodes, 143

load balancer, container orchestration, 205

load test (binary test), 20

LoadBalancer, connecting Services to Kubernetes cluster, 220

loaded-reference barriers, HotSpot, 124

local container, Java deployment, 212-214

local variables, 140

Lock class, 357

lock() method, 356

lock-free techniques, 355

locks and locking

disadvantages of traditional schemes, 368

HashMap segments, 359

in java.util.Concurrent, 356-357

for multithreaded code operation, 179

read/write locks, concurrency, 358

spinlocks, 354

via synchronization, 345-346

synchronous partition backups, 382

LockSupport class, 357

logarithmic percentiles, for long-tail distribution, 35

Logback appender, OTel logs, 301

LogCompilation switch, 160

LoggingMeterRegistry, 267

logs and log handling, 241-243

abusing correlated logs antipattern, 253

data volumes, 248

GC, 189

JIT compilation, 159-161

manual instrumentation, 251

OTel, 292, 300-302

unstructured text for logs, 247

Logstash, 242

long-tail distribution, sampling, 34

lookup phase of method handle, 350-351

##### M

magic numbers, 54

main branch, Fighting Animals, 207

main() method, 56

major generational collections, ZGC, 127

Majors, Charity, 236

Mak, Sander, 51

managed subsystems, Java's use of, 4

manual memory management, 85

manual tracing, OTel, 292-296

manual versus automatic instrumentation, 250-252

manual_tracing, Fighting Animals, 207

mark and sweep algorithm, GC, 75, 77-79

mark word, 81

Mastering API Architecture (Gough et al.), 217

maxage versus maxsize parameter, ring buffer in JFR, 326

measurement challenges with JVM applications, 5

mechanical sympathy, 179, 190

memory caches, 172-177

memory management, 4, 60

(see also garbage collection)

allocation rates, 13, 85, 101, 102, 175-177

array layout, 421-422

deployment of Java to cloud, 233-234

hardware models, 178-179

heap (see heap memory management) profiling, 329-333

reading performance graphs, 13-14

strong memory model, 343

TLABs, 87-88, 93, 177, 331

utilization metric, 8

weak memory model, 343, 344

memory management unit (MMU), 179

memory performance, 171

memory pool, 91

MESI protocol, 173

Metaspace in HotSpot, 138

meter filters, 271-273

Meter interface, 267

MeterBinder, 277-278

MeterFilter interface, 272

meterFilter(), 273

MeterFilterReply enum, 272

MeterRegistry class, 270

meters and registries, Micrometer, 266-268

method call semantics (call-by-value), 80

method dispatch performance, 2

Method Handles API, 349-352

method handles, concurrency, 348-352, 353

method invocation (call) opcodes, 145

MethodHandle object, 349

methods, role of, 54

metric customers, Micrometer, 266

metrics, 238-241

aggregation, 239, 250, 266

architectural patterns for, 249-250

capacity, 8

counters, 239, 268, 339-342

data volumes, 247

gauges, 239, 269-271

histograms, 35

latency, 8, 18

manual versus automatic instrumentation, 252

Micrometer (see Micrometer)

naming conventions, 249

observable types, 7-11

OTel, 298-300

shoehorning data antipattern, 252-253

SLO association, 255

structure of, 247

throughput (see throughput metric)

utilization (see utilization metric)

microbenchmarking, 22, 59, 427-442

case for avoiding, 432

execution benchmarks (with JMH), 436

heuristics for, 433-434

versus integration tests, 307

JMH framework, 435-442

measuring low-level Java performance, 427-432

Micrometer, 266-278

counters, 268

distribution summaries, 274-277

gauges, 269-271

meter filters, 271-273

meters and registries, 266-268

and Prometheus, 280-285

runtime metrics, 277-278

timers, 273-274

with OTel exporter, 299

Micrometer API, 267

micrometer_only, Fighting Animals, 207

micrometer_with_otel, Fighting Animals, 207

micrometer_with_prom, Fighting Animals, 207

MicroProfile, 194

microservices

OpenTelemetry Collector, 295

publish-subscribe paradigm, 391

and virtualization, 199

Microsoft Azure virtual machines, 200

Microsoft OpenJDK, 71

migration to cloud, considerations, 229-232

minor generational collections, ZGC, 127

Missing the Bigger Picture antipattern, 449-450

misunderstood/nonexistent problem, as cause of performance antipatterns, 28

mixed collections (G1Old), G1 collector, 117

mixed collections, G1 collector, 118-119

MMU (memory management unit), 179

mode switch, 183

ModelAllocator (simulator scenario), 99-101

modules system, JVM, 50

monitor slots, OpenJ9 object headers, 129

monitoring tools, 62-68, 306

monitoring versus observability, 237

monotonic value, 269

Moore's law, 169, 335

Morling, Gunnar, 324

moving garbage collector, 79

multimapping, ZGC, 126

multithreaded code, 61-62

benchmarking challenges, 431, 437

dependence on locks and volatile access controls, 179

garbage collection, 79

HotSpot and code execution, 154

Parallel GC, 92

mutex, 359

mutual-exclusion lock, 62, 355

##### N

namespaces, containers, 205, 223

native compilation of Java (see ahead-of-time (AOT) compilation)

native interface of JVM, 64

native keyword, 182

native mode, Quarkus, 165

network partitioning antipattern, 256-258

network partitions, 383

network utilization metric, 8

networking, cloud stack, 205-206

new factor methods, Executors, 363

new tech distractions antipattern, 443-444

newarray bytecode, 148

newCondition() method, 356

nmethod (compiled code unit), 156

nodes, Kubernetes cluster, 222

non method code heap, Segmented Code Cache, 159

non-normal statistics, 33-37

non-profiled code heap, Segmented Code Cache, 159

non-uniform memory access (NUMA), 131

nonblocking I/O (NIO), 371, 373

nonfunctional requirements (NFRs), 24

nonstatic versus static methods, 146

normal distribution in statistics, 30

#### 0

object heap, 140

Object Pool pattern, 373

object references, 62, 80

objects

HotSpot representation at runtime, 81-84

lifetime of, 85-87

mutability of, 62, 378

serialization of, 381

transitive closure of reachable, 77

unreachable, 77

observability, 4, 235-263

consensus protocols, 384

diagnosing application problems, 254-261

implementing Java, 265-303

Micrometer, 266-278

OpenTelemetry, 285-302

Prometheus, 278-285

Infinispan features, 391

JFR profiling capabilities, 326

metric types, 7-11

versus monitoring, 237

for partitioning and replication, 383

patterns and antipatterns, 249-254

simple system model for analysis, 184

three pillars model for data sources, 238-249

vendor or OSS solution for deploying, 261-263

and vthreads, 373

OCI (Open Container Initiative), 196, 202

offset operator (.), 80

old generational collection, 90-92, 96

old parallel collections (ParallelOld), 94-95

on-demand profiling, 248

on-stack replacement (OSR), 155

one-permit semaphore, 359

OOO (out-of-order) CPUs, 320

oops (ordinary object pointers), 81-84

opcodes (operation codes), 56, 142-149

Open Container Initiative (OCI), 196, 202

open source software (OSS) approach to deploying observability, 261-262

OpenJ9, 71

OpenJ9 object headers, 129

OpenJDK

choosing a distribution, 70

and Java distributions, 69

Leyden, 414-420

Loom, 61, 370, 373

Panama, 412-414

Valhalla, 420-425

OpenTelemetry (OTel), 197, 285-302

Collector, 290-291

dotted naming convention, metrics, 249

JFR and OTel profiling, 327

logs, 300-302

metrics, 298-300

observability scope of, 261

OTLP, 289

trace context propagation, 245

tracing, 207, 292-297

OpenTelemetry Collector, 286, 300, 302

OpenTelemetry Protocol (OTLP), 289

operating systems, 179-184

Async Profiler, 319

Hotspot/Oracle support for, 155

role in performance diagnosis, 186

scheduler issue, 62, 340

stack segment in OS processes, 370

operation codes (opcodes), 56, 142-149

operational approach

for containerized systems, 237

profiling, 325-329

optimization, performance (see performance optimization)

Oracle JDK, choosing an implementation), 70

Oracle, Java release cycle role of, 73

Oracle/OpenJDK VM (see HotSpot virtual machine)

orchestration technologies, 5

(see also Kubernetes)

ordinary object pointers (oops), 81-84

OS process scheduler, 180-184

os::javaTimeMillis() function, 182

OSR (on-stack replacement), 155

OSS (open source software) approach to deploying observability, 261-262

otel_metrics_raw_api, Fighting Animals, 207

out-of-order (OOO) CPUs, 320

outliers, special attention for, 33, 34

OWASP Security Cheat Sheet, 223

##### P

page tables, hardware cache for, 177

Panama, Project, 412-414, 423

Parallel GC, 92

parallelism, 337-342

    actor-based task representation techniques, 367-368

    Amdahl's law, 12, 338-339

    capacity metric, 8

    data versus task parallelism, 337

    embarrassingly parallel tasks, 338, 364, 366

    Fork/Join framework, 364-366

    GC parallel collectors, 75, 79, 92-97

    serial versus parallel computation, 367

    streams, 366-367

    task parallelism, 405-409

ParallelOld collector, 92, 96

parallelStream() method, 366

park() method, 357

ParNew collector, 92

partial garbage collection (PGC), 128, 132

partitioning, 382-383

Kafka, 392

    network partitioning antipattern, 256-258

    network partitions, 383

    repartitioning, 256-258, 383

patterns and antipatterns, observability, 249-254

pause goals, G1 collector, 115, 121

pause times (stop-the-world events) (see stop-the-world (STW) events)

Paxos consensus protocol, 384-386, 390

Pepperdine, Kirk, 314

percentiles, reaggregation issue, 277

perf (profiler), 316-319, 329

performance counters (perf profiler), 316-319

performance elbow, reading performance graphs, 11

performance optimization, 1-16

    in cloud systems, 14-16

as experimental science, 5-6

historical problems with, 2-3

HotSpot's ability to perform without

recompiling, 59

Java's practical focus and development with

JVMs, 4-5

observable quantities (metrics), 7-11

OpenJDK performance characteristics, 72

reading performance graphs, 11-14

simple system model, 184

performance regressions, 46, 225, 254-255, 307

performance requirements, 24

Performance Tuning Wizard antipattern, 445

Petroski, Henry, 5

PGC (partial garbage collection), 128, 132

PGO (profile-guided optimization), 59,

152-154

physical servers versus cloud servers, as assets

versus costs/liabilities, 15

pipeline, building OSS-based observability, 26

Platform class loader, 51

platform opcodes, 147

platform threads

versus application threads, 61

OS process scheduler, 180-182, 183-184

pluggable garbage collectors, 106-107

Pods, 217-219

Point3D type, 422

pointer swizzling, 154

portability, 194, 202

precise processor capability detection, 59

premain() method, 63

premain, Leyden, 418-420

premature promotion, GC, 102

primitive types, 80

PrintCompilation switch, 159-160

privilege escalation, scoped values for, 411

ProcessorMetrics class, Micrometer, 278

processors, 177-179, 364

(see also hardware)

production environment, testing as close as

possible to, 23-24

profile-guided optimization (PGO), 59,

152-154

profiled code heap, Segmented Code Cache,

159

profiling, 305-334

as fourth observability data type, 248

GUI tools, 308-314

JDK Flight Recorder (JFR), 321-324

memory, 329-333

modern profilers, 316-321

operational aspects, 325-329

sampling and safepointing bias, 314-316

Project Leyden, 414-420

Project Loom, 61, 370, 373

Project Panama, 412-414, 423

Project Valhalla, 420-425

Prometheus, 240, 278-285

metrics format, 197

server polls for metrics delivery, 250

server-side metrics aggregation, 250

snake-cased naming convention, metrics, 249

PromQL, 279

Protocol Buffers (protobuf), OTLP, 289

publish-subscribe paradigm, Kafka, 391

##### Q

Quarkus framework, 164-166

condensers, 417

and GraalVM, 167

shifting compilation time, 416

Simple Hospital Service, 397-400

tracing with, 251

quorum system, partitioning, 382

quorum-based protocol, Paxos as, 385

##### R

Raft consensus protocol, 386-388, 391, 393

random error type, 30-31

range vector, 284

re-entrant locking, 357

read and write operations, locked data rules, 346

read/write locks, concurrency, 358

readiness health check, Pods, 218

reading performance graphs, 11-14

rebinding by subscopes, 411

receiver type, 146

recency bias, 44, 256

record() method (Timer), 273

Red Hat, 71

Red Hat Cryostat, 326-327

reductionist thinking, 45

ReentrantLock class, 357

ReentrantReadWriteLock class, 358

refactor/re-architect approach, cloud migration, 230

references, object, 62, 80

reflection,164,349-351

Reflection API, 349

region-based collectors, 91

Balanced, 128, 131

G1 collector, 114-122

register() method, 269

registries and meters, Micrometer, 266-268

regression testing,46,225,254-255,307

rehosting approach, cloud migration, 230

release cycle, Java, 73

release-before-acquire JMM guarantee, 345

reliability optimization, 205

Remark phase, G1 collector, 113, 119

remembered sets (RSets), G1 collector, 91, 119

remocal development, containers, 223

Remote Method Invocation (RMI), 63

reoptimization, 139

repartitionning, data, 256-258, 383

replatform approach, cloud migration, 230

replication, data, 382-383

Infinispan, 391

Kafka, 392

Raft, 386

repurchase approach, cloud migration, 230

request queue, mitigating thundering herd issues, 258

RequestVote, Raft, 387

resilience and failover testing,21

résumé padding, as cause of performance anti-patterns, 27

reverse causation, 38

ring buffer configuration pattern, JFR, 325

risk bias, 46

RMI (Remote Method Invocation), 63

RSets (remembered sets), G1 collector, 91, 119

run queue, OS process scheduler, 180

Runnable interface, 362

runtime behavior of JVM under test perspec-

tive, 4

runtime metrics, Micrometer, 277-278

Rust, 59

##### S

SA (Serviceability Agent), 64

saFePointing bias, profiling, 314-316, 320

safepoints, JVM, 108-110, 125, 148

sampling

and safepointing bias, 314-316

tail-based, 35

traces, 246, 297

Sandbox level, CNCF projects, 196

SATB (snapshot at the beginning), 111

scalability

and Amdahl's law, 12

and ephemeral compute, 205

horizontal scaling, 193

linear, 11, 13

near-linear scaling graph example, 11

relationship to load on system, 10

and throughput, 9

scheduler, OS process, 180-184

oped Value class, 409

Scoped Values API, 409-412

scraping server polls for metrics delivery, 250

5DLC (software development lifecycle), 25

seasonality of events, as unstable components, 256

security

Kubernetes cluster, 223

serialization issues with, 381

Segmented Code Cache, 158

semantic versioning, OTel, 288

Semaphore::acquire(), 359

Semaphore::release(),359

semaphores, concurrency, 359

separation of concerns, and automatic tracing with OTel, 297

Serial and SerialOld collectors, 95

serial versus parallel computation, 367

serialization, 381

server poll delivery, metrics, 250, 267

service level objectives (SLOs), 255

server-side metrics aggregation, 250, 266

serverSpan() method, 294

service mesh, CNCF, 217

service provider interface (SPI), 266

service-to-service calls, orchestration tier (east to west), 206

Serviceability Agent (SA), 64

Services, Pods, 219-220

sharding (see partitioning)

shared access to storage and network, Pods, 217-218

Shenandoah collector, 72, 114, 122-125

Shipilév, Aleksey, 347, 428

shoehorning data into metrics antipattern, 252-253

shortcut forms, opcode families, 143

shutdown policies, structured concurrency, 407

shutdown() method, 407

ShutdownOnFailure, 407-408

ShutdownOnSuccess, 407

signature polymorphism, 352

simple mean (average), problems in latency testing, 19

SimpleMeterRegistry, 267

single static assignment, 156

“six Rs” approach to cloud migration (AWS), 229

skid, profiler, 320

SLOs (service level objectives), 255

snake-cased naming convention, metrics, 249

snapshot at the beginning (SATB), 111

soak (endurance) test, 20

social pressure, as cause of performance anti-patterns, 27

software development lifecycle (SDLC), 25

spans, trace, 244

speculative execution, 177

SPI (service provider interface), 266

spinlocks, concurrency, 354

“split-brain” distributed systems, 256-258

Splitterator, 366

spot computing, 205

spurious correlation, 38-40

SQL versus CQL, 389

stack machine, JVM interpreter as, 140-142

stack segment, 370

standard deviation, challenge in JVM applications, 4

@State annotation, benchmarking, 437

static run-time image, Leyden, 415

static versus nonstatic methods, 146

statistics

challenge in JVM applications, 4

interpretation of, 37-44

for JVM performance, 29

stop-the-world (STW) events, 20

garbage collection, 79, 92, 117, 123, 125, 131

managing in Java, 108-110

safepoints, 108-110, 125

storage I/O subsystem, 8

stream() method, 366

streams, parallel, 366-367

stress test, 19

strong memory model, 343

struct-like arrays, 423

structured concurrency, 405-409

structured logs, 242

StructuredTaskScope, 407, 408

Subtask interface, structured concurrency, 406

superclass, 54

Sutter, Herb, 335

sweeper process, JIT compilation, 157

switch statement inside while loop, interpreter

as, 50, 149

Sync static subclass, 357

synchronization to control value updating, 342

synchronized keyword, 345, 354

synchronizes-with JMM guarantee, 345

synchronous backups, data partitioning, 382

synchronous messaging, 244

 ventures, 244

system.exception(interrupt), 183

system.currentTime(Millis()) method, 182

system.gc() method, 76

systematic error type, 31-33, 37-40

##### T

tail-based sampling, 35, 247

task abstraction and executors, concurrency, 362-368

task parallelism, structured concurrency, 405-409

TCO (total cost of ownership) efficiency metric, 9

Telepresence, 223

template interpreter, HotSpot as, 150

Tene, Gil, 35

test environment, creating, 23-24

testing methodology, 17-47

antipatterns, causes of performance, 26-28

cognitive biases and performance testing, 44-47

creating a test environment, 23-24

identifying performance requirements, 24

interpretation of statistics, 37-44

Java-specific issues, 25

as part of SDLC, 25

questions, importance of, 18

statistics for JVM performance, 29

top-down performance, 22

types of performance tests, 17–22

testing theory as applied to performance, 11-14

Thompson, Martin, 179, 190

Thread API, 356

thread bottleneck problem, 61

Thread class, and virtual threads, 371

“thread hot” performance, 347, 359

thread-local allocation buffers (TLABs), 87-88, 93, 177, 331

thread-local variables, ScopedValues API as alternative, 409

Thread.start(), 369

ThreadFactory, 363

ThreadLocal, 373

threads and thread handling

application versus platform threads, 61

blocking threads, 355, 371, 380

carrier threads, 180, 370, 372, 374

concurrent evacuation by GC threads, 123

GC thread sharing, 62

Java's ability to create new threads, 97

lifecycle of threads, 370-372

multithreaded programming (see multi-threaded code)

number in thread pool, 364

OS process scheduler, 180-182, 183-184

Scoped Values API, 409-412

stopping for GC, 148

structured concurrency, 405-409

task parallelism, 337

virtual threads, 61, 369-375, 405-409

three pillars model for data sources, 238-249

individual pillars as data sources, 247-248

logs and log handling, 241-243

metrics, 238-241

profiling as fourth data type, 248

traces, distributed, 243-247

throughput metric, 7

and capacity, 8

in garbage collection, 106

and scalability, 9

stress test, 19

testing, 19

thundering herd, observability diagnosis, 258

tiered compilation, 156, 158

Tilt, 214

Tiltfile, 214

time series data, metrics as, 240

timers, Micrometer, 273-274

TLABs (thread-local allocation buffers), 87-88, 93, 177, 331

TLB (translation lookaside buffer), 177

top-down performance, testing best practices, 22

topics, Kafka, 392

total cost of ownership (TCO) efficiency metric, 9

trace-flags field, 246

traces and tracing, 243-247

automatic tracing, 250, 296-297

data volumes, 248

distributed systems, 243-247, 248, 256, 274

garbage collection, 75, 77-79

manual tracing, 250, 292-296

OTel, 207, 292-297

sampling, 246, 297

unstable component challenge, 256

traceview, 245, 246

traffic categories, network, 205

transactional use cases, Infinispan, 391

transitive closure of reachable objects, 77

translation lookaside buffer (TLB), 177

tri-color invariant, object node as, 112

tri-color marking algorithm, 110-112

Truffle, 167

tryLock() method, 356

Tuning by Folklore antipattern, 446

two-phase commit, distributed systems, 379-380

##### U

UAT Is My Desktop antipattern, 451-452

Universal Base Image (UBI) Minimal, 204

unlock() method, 356

UNNAMED module, JVM, 51

unreachable (dead) objects, 77

Unsafe class, 352, 353

unstable application components, 256

UnsupportedClassVersionError, 54

update releases, Java, 73

utilization metric, 8

in cloud systems, 15

CPUs, 8, 186-188, 307

and degradation metric, 9

memory management, 8

relationship to load changes, 10

### V

Valhalla, Project, 420-425

value classes in JVM, Valhalla's exploration, 420-425

value types in Java, 80

variance, challenge in JVM applications, 4

Vector API, 414

vendor solutions, observability deployment, 262-263

versions, dependencies and containers, 208

versions, role in class file structure, 54

vertical partitioninging, 382

virtual dynamic shared object (vDSO), 184

virtual machines, choosing cloud-based, 200-201

virtual threads (vthreads), 61, 369-375, 405-409

virtualization, 198-201

VirtualThread subclass, 371

Visitor pattern, 329

VisualGC plug-in, 89

VisualVM, 64-68

allocation profiling, 329

execution profiling, 308-309, 328

heap dump, 332

heap visualization for GC, 79

vmstat, 186-188

volatile access, 179

Volatile Shutdown pattern, 375

voting-based consensus algorithm, Paxos as, 384

vtables (virtual function tables), 154-155

##### W

WAL (write-ahead log), 379, 380

wall, performance term, 437

weak generational hypothesis (WGH), GC, 86-87, 99

weak memory model, 343, 344

with_infinispan, Fighting Animals, 208

Wohlstetter, Roberta, 254

Woods, Audrey, 169

work-stealing algorithm, 365-366

Works for Me antipattern, 45

write barrier, HotSpot GC heap, 91

write-ahead log (WAL), 379, 380

write-back behavior, processor, 174

write-through behavior, processor, 174

##### Y

yield(), carrier threads, 371

young generational collections, 89, 90-92

G1New, 117, 118

parallel, 86, 93-94, 96

Parallel GC, 92

#### 7

Z Garbage Collector (ZGC), 72, 125-128

zero-effort collector, Epsilon as, 134

zero-overhead abstraction, 57

#### About the Authors

Ben Evans, senior principal software engineer and observability lead at Red Hat Runtimes, is an architect, author, and educator. He's also a Java Champion who's written seven books on programming, including Optimizing Java and Java in a Nutshell. Previously, he was lead architect for instrumentation at New Relic, a cofounder of jClarity (acquired by Microsoft), and a member of the Java SE/EE Executive Committee.

James (Jim) Gough is a Distinguished Engineer at Morgan Stanley working on cloud native architecture and API programs. He's a Java Champion who has sat on the Java Community Process Executive Committee on behalf of the London Java Community and contributed to OpenJDK. James is also coauthor of Mastering API Architecture and enjoys speaking about architecture and low-level Java.

#### Colophon

The animal on the cover of Optimizing Cloud Native Java is a markhor goat (Capra falconeri). This species of wild goat is distinguished by its wizard-esque beard and twisting, towering horns. Found in the mountainous regions of western and central Asia, these goats inhabit high-altitude monsoon forests and can be found at 600–3,600 meters in elevation.

The markhor are herbivores that primarily graze on a variety of vegetation including grasses, leaves, herbs, fruits, and flowers. Like other wild goats, the markhor play a valuable role within their ecosystem as they munch the leaves from the low-lying trees and scrub, spreading the seeds in their dung.

The mating season takes place in winter, during which the males fight each other by lunging, locking horns, and attempting to push each other off balance. The subsequent births occur from late April to early June and result in one or two kids. Adult males are largely solitary and prefer the forest while the females and their young live in flocks on the rocky ridges high above.

Many of the animals on O'Reilly covers are endangered; all of them are important to the world.

The cover image is from Riverside Natural History. The series design is by Edie Freedman, Ellie Volckhausen, and Karen Montgomery. The cover fonts are Gilroy Semibold and Guardian Sans. The text font is Adobe Minion Pro; the heading font is Adobe Myriad Condensed; and the code font is Dalton Maag's Ubuntu Mono.

### O'REILLY $ ^{®} $

## Learn from experts. Become one yourself.

Books | Live online courses

Instant answers | Virtual events

Videos | Interactive learning

Get started at oreilly.com.

