# Module 01: Async & ASGI Foundations — Concurrency and Event Loops

Welcome, class. Today we initiate our study of **FastAPI & Uvicorn Essentials (CS-521)**.

To understand why FastAPI is highly performant under concurrent loads, we must analyze Python's concurrency models. Traditional web frameworks (like Flask or Django) are built on the **WSGI (Web Server Gateway Interface)** standard. They use a synchronous, thread-per-request model. If a request blocks waiting for a database query or an external API response, the thread remains blocked.

FastAPI is built on **ASGI (Asynchronous Server Gateway Interface)**, using Python's **async/await** coroutines. It executes requests on a single-threaded **Event Loop**. Today, we will study event loop mechanics, contrast WSGI with ASGI, and write non-blocking async handlers in Python.

---

## 1. Academic Lecture: Event Loops vs. Thread Pools

To write high-performance Python code, we must shift from multithreaded blocking execution to asynchronous event-driven loops.

### 1. The WSGI Thread-Per-Request Model
In a WSGI application (e.g., Flask running on Gunicorn), the server allocates a pool of threads.
*   **The Problem**: If a thread processes a request that calls a slow database, that thread halts (`blocks`). It cannot process any other requests. If your pool has 20 threads, and 20 users trigger slow database queries, the 21st user will experience a timeout error.
*   **The Memory Penalty**: Threads are OS-level constructs. Each thread allocates around 8MB of stack memory, meaning 1,000 idle threads consume 8GB of RAM.

### 2. The ASGI Event Loop Model
ASGI (e.g., FastAPI running on Uvicorn) uses a single thread executing a cooperative **Event Loop**:
*   When a request starts, the event loop runs the coroutine.
*   When the coroutine hits an I/O operation (like fetching an API or querying PostgreSQL), it explicitly yields control back to the event loop using the `await` keyword.
*   The event loop immediately switches to process other incoming requests.
*   When the I/O operation completes, the event loop resumes the original coroutine.
*   **The Benefit**: A single thread can handle tens of thousands of concurrent, idle connections (like WebSockets) using minimal memory.

```
       WSGI (Blocking Threads)
  User 1 ---> [ Thread 1 ] ---> Block on DB (Halted)
  User 2 ---> [ Thread 2 ] ---> Block on DB (Halted)
  
       ASGI (Async Event Loop)
  User 1 -\
  User 2 ---> [ Single Event Loop Thread ] ---> [ I/O Waits Delegated ]
  User 3 -/
  (Event loop switches instantly between tasks while waiting for I/O)
```

```mermaid
sequenceDiagram
    autonumber
    actor Client A
    actor Client B
    participant Loop as Event Loop Thread
    participant DB as Postgres Database

    Client A->>Loop: GET /profile (async)
    Loop->>DB: Send Query A
    Note over Loop: Client A yields control!<br/>Event loop is free.
    Client B->>Loop: GET /status (async)
    Loop-->>Client B: 200 OK
    DB-->>Loop: Query A complete
    Loop-->>Client A: Return profile data
```

---

## 2. Theory vs. Production Trade-offs

### Async Handlers (`async def`) vs. Synchronous Handlers (`def`) in FastAPI
FastAPI allows you to declare endpoints using either `async def` or standard `def`.
*   **Async Handler (`async def`)**:
    *   *Rule*: You **must** only use non-blocking, async libraries (like `httpx` or `asyncpg`) and prepend calls with `await`.
    *   *Danger*: If you call a blocking library (like `requests` or `time.sleep()`) inside an `async def` handler, you **freeze the entire event loop**, blocking all other concurrent users.
*   **Synchronous Handler (`def`)**:
    *   *FastAPI Handling*: If you declare an endpoint using standard `def`, FastAPI automatically runs it in a separate thread pool (`anyio` worker pool).
    *   *Trade-off*: Safe for legacy, blocking code, but introduces the thread allocation and memory overhead of WSGI.

---

## 3. How to Use: Writing Asynchronous Endpoints

Let us write a compile-grade FastAPI application demonstrating the difference between blocking and non-blocking handlers.

### A. The Event Loop Freeze (Anti-Pattern)

Avoid calling blocking operations inside an asynchronous handler:

```python
import time
from fastapi import FastAPI

app = FastAPI()

@app.get("/vulnerable")
async def vulnerable_endpoint():
    # DANGER: time.sleep is a blocking call. Because it is executed inside
    # an async function without yielding, it freezes the entire event loop thread.
    # No other user can connect to the server during these 5 seconds.
    time.sleep(5)
    return {"status": "completed"}
```

### B. The Hardened Asynchronous Endpoint (Production Pattern)

Here is the hardened code. It uses non-blocking async sleep and delegates blocking CPU operations to background threads.

```python
import asyncio
from fastapi import FastAPI, BackgroundTasks
from anyio import to_thread

app = FastAPI()

def expensive_cpu_calculation(n: int) -> int:
    # Simulates a heavy CPU calculation (e.g. image sizing or hash check)
    result = 0
    for i in range(n):
        result += i
    return result

@app.get("/secure")
async def secure_endpoint():
    # SECURE: Yields control back to the event loop. Other requests can process.
    await asyncio.sleep(2)
    return {"status": "completed"}

@app.get("/compute")
async def compute_endpoint(limit: int):
    # SECURE: Because expensive_cpu_calculation is blocking and CPU-bound,
    # we run it in a separate worker thread using anyio's to_thread,
    # preventing the event loop from freezing.
    result = await to_thread.run_sync(expensive_cpu_calculation, limit)
    return {"result": result}

@app.post("/tasks")
async def start_background_task(background_tasks: BackgroundTasks):
    # SECURE: Offload long tasks (like sending emails) to FastAPI's background runner
    background_tasks.add_task(async_write_audit_log, "Task started successfully.")
    return {"message": "Task queued."}

async def async_write_audit_log(message: str):
    await asyncio.sleep(1) # Simulates non-blocking writing
    print(f"Logged: {message}")
```

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Bypassing the await keyword on async calls
Calling an async function without prepending the `await` keyword.
```python
# DANGER: Does not execute the function. It returns a Coroutine object,
# which can cause database connections to leak or logic to fail silently.
db_helper.save_record(data) 
```
*   **Mitigation**: Always verify that async calls are preceded by `await`:
    ```python
    await db_helper.save_record(data)
    ```

---

## 5. Socratic Review Questions

### Question 1
Explain what happens to the Uvicorn event loop if a developer executes a blocking network call using `requests.get("https://external-api.com")` inside an `async def` endpoint.

#### Answer
Because `requests.get` is a synchronous, blocking network call, it does not support yielding control back to the event loop. The thread executing the event loop will block, waiting for the external server's TCP response. 
Since the event loop thread is blocked, it cannot process any other events, meaning all other concurrent users connected to the server will experience frozen requests and potential connection timeouts.

### Question 2
How does FastAPI handle standard synchronous endpoints declared using `def` instead of `async def`?

#### Answer
When FastAPI encounters a route handler declared with `def` rather than `async def`, it knows the code is synchronous and might block. To prevent this from freezing the event loop, FastAPI automatically routes the request to an external thread pool (managed by the `anyio` library). This allows the synchronous code to run on a separate thread, keeping the primary event loop thread free.

---

## 6. Hands-on Challenge: Asynchronous Task Aggregation

### The Challenge
In this challenge, you will implement an asynchronous aggregator.

Your task is to complete the `fetch_dashboard_data` endpoint:
1.  Trigger two asynchronous simulated database queries (`fetch_users` and `fetch_metrics`) concurrently.
2.  Combine their results into a single dictionary response.
3.  Ensure the total wait time does not exceed the duration of the longest individual task (2 seconds), verifying they ran concurrently rather than sequentially.

Complete the implementation below:

```python
import asyncio
from fastapi import FastAPI

app = FastAPI()

async def fetch_users():
    await asyncio.sleep(1.5) # Simulates database load
    return ["Alice", "Bob"]

async def fetch_metrics():
    await asyncio.sleep(2.0) # Simulates metrics fetch
    return {"active_users": 102}

@app.get("/dashboard")
async def fetch_dashboard_data():
    # TODO: Complete the logic.
    # 1. Use asyncio.gather to execute fetch_users() and fetch_metrics() concurrently.
    # 2. Extract their returned values.
    # 3. Return a combined dictionary: {"users": users, "metrics": metrics}.
    
    return {}
```

Write the concurrency aggregation code. Save the completed file and explain the difference between sequential and concurrent task processing inside `modules/01-async-concurrency-asgi.md`.
