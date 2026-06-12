# CS-525: Lightweight Local LLMs & Structured Inference

Welcome to **CS-525: Lightweight Local LLMs & Structured Inference**. I am Professor Antigravity. In this course, we will explore running and orchestrating lightweight Large Language Models (LLMs) locally to act as structured technical interview assessment engines.

In an automated hiring pipeline, the language model serves as the "BRAIN." Rather than acting as a standard conversational chatbot, it must function as a strict evaluator, mapping candidate transcripts against complex rubrics and outputting deterministic JSON metadata (e.g. scores, correctness, feedback, follow-up transition state) that traditional software systems can reliably process.

To achieve this, we will run lightweight models (like Qwen2.5-3B/7B-Instruct or Llama-3-8B-Instruct) using **Ollama**, study **Prompt Engineering** techniques to isolate persona boundaries, and leverage Pydantic validation via the **Instructor** framework to guarantee type-safe structured JSON inputs/outputs.

---

## Course Syllabus & Navigation

The course is divided into 5 modules:

| Module | Core Classification | Focus Topics |
| :--- | :--- | :--- |
| **01** | [Local LLM Orchestration](file:///c:/Users/Admin/Desktop/projects/learning-repo/local-llm-structured-inference/modules/01-ollama-local-llms.md) | Ollama architecture (llama.cpp backend), client-server model, python SDK connections, API endpoints, timeouts, and connection resilience. |
| **02** | [Prompt Engineering](file:///c:/Users/Admin/Desktop/projects/learning-repo/local-llm-structured-inference/modules/02-prompt-engineering-interviewer.md) | System prompt isolation, role boundary management, anti-injection formatting, context state variables, and establishing a strict interviewer evaluator persona. |
| **03** | [JSON Parsing & Validation](file:///c:/Users/Admin/Desktop/projects/learning-repo/local-llm-structured-inference/modules/03-json-parsing-validation.md) | Non-deterministic parser failures, Ollama native `format="json"`, validation try-except blocks, and programmatic json string corrections. |
| **04** | [Instructor & Pydantic V2](file:///c:/Users/Admin/Desktop/projects/learning-repo/local-llm-structured-inference/modules/04-instructor-pydantic-validation.md) | Declarative modeling, using Pydantic V2 schemas for output verification, Instructor retry validations, and structural error handling. |
| **05** | [Final Capstone Project](file:///c:/Users/Admin/Desktop/projects/learning-repo/local-llm-structured-inference/modules/05-capstone-evaluation-engine.md) | Building a production-grade local evaluation engine. Matches transcripts against rubrics, executes retry validation loop, handles API failures defensively, and records audit cards. |

---

## Local Environment Configuration

Ensure you have **Python 3.11+** installed on your system.

### 1. Installing Ollama
Ollama is a lightweight service that packages model weights, configurations, and a compiled runner into a single backend process.
*   **macOS / Linux**: Run the installation script:
    ```bash
    curl -fsSL https://ollama.com/install.sh | sh
    ```
*   **Windows**: Download the Windows Installer directly from the official website [ollama.com](https://ollama.com) or run:
    ```powershell
    winget install Ollama.Ollama
    ```

### 2. Pulling the Local Models
Once installed, start the Ollama service and download the target lightweight instruction models:
```bash
# Pull the highly efficient Qwen2.5 3B Instruct model (approx. 1.9 GB)
ollama pull qwen2.5:3b

# Pull the standard Llama 3 8B Instruct model (approx. 4.7 GB)
ollama pull llama3:8b
```

Verify that the models are loaded by running:
```bash
ollama list
```

### 3. Python Virtual Environment & Dependencies
Initialize your environment and install the required client libraries:
```bash
# Create and activate virtual environment
python -m venv .venv
# On Windows:
.venv\Scripts\Activate.ps1
# On macOS/Linux:
source .venv/bin/activate

# Install required dependencies
pip install --upgrade pip
pip install ollama>=0.2.1 instructor>=1.3.0 pydantic>=2.6.0 pydantic-settings>=2.1.0 httpx>=0.27.0
```

---

## Grading Criteria & Defensive Success Metrics

Your progress in this course is evaluated based on the following engineering rubrics:

*   **Model Schema Rigor (30%)**: Designing Pydantic validation structures, using field descriptions, and enforcing data constraints.
*   **Execution Resilience (25%)**: Handling connection timeouts, implementing recovery loops for malformed JSON, and establishing connection fallbacks.
*   **Prompt Alignment (25%)**: Preventing chat drifts, ensuring the model stays in-character as an evaluator, and rejecting user-injected prompt overrides.
*   **Verification Completeness (20%)**: Implementing robust test files checking schema parsing correctness, error recovery, and API integrations.
