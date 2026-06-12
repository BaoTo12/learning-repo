# CS-523: AI Fundamentals & Vector Search

Welcome to **CS-523: AI Fundamentals & Vector Search**. I am Professor Antigravity. In this course, we will study the foundational blocks of AI systems engineering from a software engineer's perspective. 

You do not need to be an AI research scientist or have a PhD in mathematics to build high-performance AI features. For modern software engineers, the challenge is architectural integration: understanding the boundaries between model training and inference, compressing models via quantization to run on cost-effective local servers, generating vector representation tokens (embeddings) from text documents, and indexing them inside databases to achieve lightning-fast semantic searches.

In this course, we will study **Inference vs. Training mechanics**, **Float Quantization standard scales**, **High-Dimensional Vector Math**, **Sentence Transformers pipelines**, and **PostgreSQL pgvector configurations**.

---

## Course Syllabus & Navigation

The course is divided into 8 detailed modules:

| Module | Core Classification | Focus Topics |
| :--- | :--- | :--- |
| **01** | [The Big Picture Architecture](file:///c:/Users/Admin/Desktop/projects/learning-repo/ai-fundamentals/modules/01-big-picture-architecture.md) | Keyword vs. Semantic Search, LLMs vs. Embeddings, API-based vs. Self-hosted local models. |
| **02** | [Inference vs. Training](file:///c:/Users/Admin/Desktop/projects/learning-repo/ai-fundamentals/modules/02-inference-vs-training.md) | Weights, logit predictions, gradients, backpropagation, and parameter fine-tuning (PEFT/LoRA). |
| **03** | [Model Weights & Quantization](file:///c:/Users/Admin/Desktop/projects/learning-repo/ai-fundamentals/modules/03-weights-quantization.md) | Float bit ranges (FP16, BF16, INT8, Q4_K_M), quantization scale mapping, GGUF formats. |
| **04** | [Vector Embeddings Theory](file:///c:/Users/Admin/Desktop/projects/learning-repo/ai-fundamentals/modules/04-vector-embeddings-theory.md) | High-dimensional vector spaces, distance math (Cosine, Euclidean L2, Inner Product), dimensions. |
| **05** | [Generating Embeddings in Python](file:///c:/Users/Admin/Desktop/projects/learning-repo/ai-fundamentals/modules/05-generating-embeddings-python.md) | Tokenization, Sentence-Transformers, pooling layers (Mean vs. CLS), tensor normalizations. |
| **06** | [Database Vector Stores](file:///c:/Users/Admin/Desktop/projects/learning-repo/ai-fundamentals/modules/06-vector-databases-pgvector.md) | PostgreSQL `pgvector` extension setup, tables with `vector(N)` fields, SQL similarity queries. |
| **07** | [Vector Indexing & Optimization](file:///c:/Users/Admin/Desktop/projects/learning-repo/ai-fundamentals/modules/07-indexing-hnsw-ivfflat.md) | Approximate Nearest Neighbor search algorithms, HNSW graphs vs. IVFFlat clusters, parameters tuning. |
| **08** | [Final Capstone Project](file:///c:/Users/Admin/Desktop/projects/learning-repo/ai-fundamentals/modules/08-final-capstone-resume-engine.md) | Building an AI-powered Candidate Matching and Semantic Resume Ranking pipeline application. |

---

## Local Environment Configuration

To set up your local development environment, make sure you have **Python 3.11+** and **Docker** installed.

### 1. Database Configuration (`docker-compose.yml`)
To run a local PostgreSQL database with the precompiled `pgvector` extension, create a `docker-compose.yml` file in your project root:
```yaml
version: '3.8'
services:
  postgres_vector:
    image: ankane/pgvector:v0.5.1
    container_name: pgvector_db
    ports:
      - "5432:5432"
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: securepassword
      POSTGRES_DB: vector_db
    volumes:
      - pgdata_vector:/var/lib/postgresql/data

volumes:
  pgdata_vector:
```
Launch the database:
```bash
docker-compose up -d
```

### 2. Python Virtual Environment & Requirements
Create your environment and install the required modules:
```bash
# Create and activate virtual environment
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
source .venv/bin/activate

# Install libraries
pip install --upgrade pip
pip install sentence-transformers>=2.3.0 numpy>=1.24.0 psycopg[binary]>=3.1.18 pytest>=8.0.0 torch>=2.1.0
```

---

## Grading Criteria & Defensive Success Metrics

Your progress is measured using the following engineering rubrics:

*   **Architectural Alignment (25%)**: Understanding where processing boundary edges sit, choosing the correct similarity metrics, and managing local vs. cloud execution latency.
*   **Vector Engine Precision (30%)**: Correctly handling sentence embeddings normalizations, token limit boundaries, and tensor dimensions alignment.
*   **Database Scaling & Query Speed (25%)**: Designing secure `pgvector` SQL schemas, structuring high-performance queries, and applying HNSW indices correctly.
*   **Verification Completeness (20%)**: Writing mockable validation tests using pytest fixtures to assert vector calculations.
