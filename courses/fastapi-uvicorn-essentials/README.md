# CS-521: FastAPI & Uvicorn Essentials

Welcome to **CS-521: FastAPI & Uvicorn Essentials**. I am Professor Antigravity. In this course, we will study high-performance asynchronous API design in Python using **FastAPI** and the **Uvicorn** ASGI server.

Traditional Python web frameworks (like Flask or Django) are synchronous (WSGI-based) and block threads on database reads or I/O waits. This limits their scalability under heavy loads. FastAPI, built on **Starlette** and **Pydantic**, utilizes Python's modern **async/await** features to manage thousands of concurrent, non-blocking requests on a single thread. This makes it an ideal framework for building high-performance APIs, microservices, and AI inference layers.

In this course, we will study **Asynchronous Event Loops**, **Pydantic Data Validation**, **Dependency Injection**, **ASGI Middlewares**, **Structured Logging**, **OAuth2/JWT Security**, **Role-Based Access Control (RBAC)**, **File Uploads & Chunked Streaming**, and **ASGI Server Deployment**.

---

## Course Syllabus & Navigation

The course is divided into 14 detailed modules:

| Module | Core Classification | Focus Topics |
| :--- | :--- | :--- |
| **01** | [Async & ASGI Foundations](file:///c:/Users/Admin/Desktop/projects/learning-repo/fastapi-uvicorn-essentials/modules/01-async-concurrency-asgi.md) | Async/Await concurrency, Event Loops vs. Thread Pools, ASGI vs. WSGI protocols. |
| **02** | [Routing & Pydantic Validation](file:///c:/Users/Admin/Desktop/projects/learning-repo/fastapi-uvicorn-essentials/modules/02-routing-pydantic-validation.md) | Path/Query parameters, Pydantic v2 schemas, auto-generated OpenAPI documentation. |
| **03** | [Dependency Injection](file:///c:/Users/Admin/Desktop/projects/learning-repo/fastapi-uvicorn-essentials/modules/03-dependency-injection.md) | FastAPI `Depends` injection framework, database yields, resource lifetimes. |
| **04** | [ASGI Middleware](file:///c:/Users/Admin/Desktop/projects/learning-repo/fastapi-uvicorn-essentials/modules/04-middleware.md) | Request/Response lifecycle, writing custom middlewares, CORS, and Trusted Host headers. |
| **05** | [Structured Logging](file:///c:/Users/Admin/Desktop/projects/learning-repo/fastapi-uvicorn-essentials/modules/05-structured-logging.md) | Python standard logging, correlation ID tracing, structured JSON output formatting. |
| **06** | [Authentication](file:///c:/Users/Admin/Desktop/projects/learning-repo/fastapi-uvicorn-essentials/modules/06-authentication.md) | Stateless security, OAuth2 password flow, JWT generation, password hashing. |
| **07** | [Role-Based Authorization](file:///c:/Users/Admin/Desktop/projects/learning-repo/fastapi-uvicorn-essentials/modules/07-authorization.md) | Role-Based Access Control (RBAC), security scopes, and route dependency guards. |
| **08** | [File Uploads & Streaming](file:///c:/Users/Admin/Desktop/projects/learning-repo/fastapi-uvicorn-essentials/modules/08-file-uploads-streaming.md) | Multipart file uploads (`UploadFile`), binary buffers, chunked HTTP streaming (`StreamingResponse`). |
| **09** | [WebSockets](file:///c:/Users/Admin/Desktop/projects/learning-repo/fastapi-uvicorn-essentials/modules/09-websockets.md) | Full-duplex persistent connections, managing socket state, text/binary framing. |
| **10** | [Modern Project Structure](file:///c:/Users/Admin/Desktop/projects/learning-repo/fastapi-uvicorn-essentials/modules/10-project-structure.md) | APIRouter partitioning, configuration via Pydantic-Settings, Repository-Service layers. |
| **11** | [End-to-End Developer Workflow](file:///c:/Users/Admin/Desktop/projects/learning-repo/fastapi-uvicorn-essentials/modules/11-developer-workflow.md) | Virtual environment setups, pinning dependency configurations, Swagger validations, pytest. |
| **12** | [Testing Async APIs](file:///c:/Users/Admin/Desktop/projects/learning-repo/fastapi-uvicorn-essentials/modules/12-testing.md) | Integration testing async handlers using pytest and HTTPX `AsyncClient`. |
| **13** | [Uvicorn Production Deployments](file:///c:/Users/Admin/Desktop/projects/learning-repo/fastapi-uvicorn-essentials/modules/13-uvicorn-production.md) | Multi-process Uvicorn workers, Gunicorn wrappers, and Nginx reverse proxy configurations. |
| **14** | [Final Capstone Project](file:///c:/Users/Admin/Desktop/projects/learning-repo/fastapi-uvicorn-essentials/modules/14-final-capstone-audio-service.md) | Building an asynchronous, secure audio-processing and transcription microservice. |

---

## Local Environment Configuration

To set up your local development environment, make sure you have **Python 3.11+** installed. Use the following commands to configure your virtual environment:

### 1. Initialize Virtual Environment
```bash
# Create venv folder in project root
python -m venv .venv

# Activate virtual environment
# On Windows PowerShell:
.venv\Scripts\Activate.ps1
# On macOS/Linux:
source .venv/bin/activate
```

### 2. Core Dependencies configuration (`requirements.txt`)
Create a `requirements.txt` file containing the core framework libraries:
```text
fastapi>=0.109.0
uvicorn[standard]>=0.27.0
pydantic>=2.6.0
python-jose[cryptography]>=3.3.0
passlib[bcrypt]>=1.7.4
python-multipart>=0.0.9
httpx>=0.26.0
pytest>=8.0.0
anyio>=4.3.0
```

Install the dependencies:
```bash
pip install -r requirements.txt
```

---

## Grading Criteria & Defensive Success Metrics

Your progress in this course is evaluated based on the following metrics:

*   **Asynchronous Flow & Thread Safety (30%)**: Writing non-blocking handlers, executing CPU-bound operations on worker threads, and avoiding synchronous blocking APIs inside the event loop.
*   **Encapsulated Validation & Schemas (20%)**: Structuring strict Pydantic inputs/outputs, preventing raw database mapping leaks, and implementing robust type validations.
*   **Security & Access Control (30%)**: Correctly implementing JWT authentication, scoping route dependencies (RBAC), and securing endpoints against injection or token leakage.
*   **Production Readiness (20%)**: Structuring custom middlewares for request-id correlation, configuring structured JSON logs, and tuning Uvicorn multi-process workers.
