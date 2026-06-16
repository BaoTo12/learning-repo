# Module 01: The Big Picture — AI-Powered Software Architecture

Welcome back, class. Today we analyze **AI-Powered Software Architecture (CS-523)**.

If you are a traditional software engineer, the AI landscape can look overwhelming. The media focus is often on training massive models from scratch or writing complex neural networks. In reality, most modern AI applications do not train new models. Instead, engineers combine pre-trained components to add semantic capabilities to traditional software.

Today, we will study the **big picture** of AI architecture. We will analyze the differences between keyword search and semantic search, dissect the standard blocks of an AI pipeline (Embeddings, Vector Databases, and LLMs), and learn how they coordinate to build secure applications.

---

## 1. Academic Lecture: Evolving from Keywords to Meanings

Traditional databases are deterministic; they search for exact matches. AI-powered applications shift from matching characters to matching semantic meaning.

### 1. Keyword Search vs. Semantic Search
*   **Keyword Search (Deterministic)**: If a recruiter searches for `"database administrator"`, the database looks for those exact character sequences. If a candidate's resume lists `"DBA"` or `"PostgreSQL expert"` but omits the exact string "database administrator", they are missed.
*   **Semantic Search (Vector-based)**: Instead of characters, we compare meaning. The system translates text into coordinate points in a multi-dimensional mathematical space. Because `"database administrator"`, `"DBA"`, and `"SQL expert"` share similar semantic space, their coordinates sit close to each other, allowing the system to match them.

### 2. The AI Application Block Diagram
A production AI architecture is comprised of three core components:

*   **Embedding Models**: Specialized, lightweight neural networks whose only job is to convert text strings (sentences, paragraphs, documents) into a sequence of numbers (a vector). Examples include `all-MiniLM-L6-v2` or OpenAI's `text-embedding-3-small`.
*   **Vector Databases**: Databases optimized to store these sequences of numbers and perform fast spatial geometry calculations (distance queries) to find similar coordinates. Examples: `pgvector` in PostgreSQL, Pinecone, or Milvus.
*   **Large Language Models (LLMs)**: Generative engines that process prompts and return conversational text. They handle reasoning, summarizing, and translating. Examples: Qwen, GPT-4, Llama-3.

### 3. Execution Boundaries: Hosted APIs vs. Local Models
*   **Hosted APIs (SaaS)**: Services like OpenAI or Anthropic. Easy to implement via simple HTTP headers, but incur variable token costs, network latency, and present data privacy risks.
*   **Local Self-Hosted Models**: Running quantized models inside your own infrastructure using runners like `llama.cpp` or `Ollama`. They guarantee data privacy and have zero token costs, but require dedicated GPU hardware.

```mermaid
graph TD
    subgraph Data Ingestion (Offline Pipeline)
        Resume[Raw Resume Text] --> Parser[Text Sanitizer]
        Parser -->|Clean Text| EmbedModel[Embedding Model]
        EmbedModel -->|High-Dimensional Vector| VecDB[(Vector DB / pgvector)]
    end

    subgraph Query Execution (Online Pipeline)
        Query[Recruiter Search: 'DBA Expert'] --> QueryEmbed[Embedding Model]
        QueryEmbed -->|Query Vector| Search[Vector Similarity Query]
        VecDB -->|Calculate Cosine Similarity| Search
        Search -->|Ranked Match Scores| Ranker[Ranked Candidate List]
    end
```

---

## 2. Theory vs. Production Trade-offs

### API-Based Models vs. Self-Hosted Local Models
*   **API-Based Models (e.g. OpenAI)**:
    *   *Pro*: Zero server maintenance. Models scale automatically, and you always have access to state-of-the-art models.
    *   *Con*: Recurring costs. Sending millions of candidate profiles to an external API becomes expensive. Furthermore, transmitting personally identifiable information (PII) like names, phone numbers, and addresses outside your network can violate privacy laws (GDPR, HIPAA).
*   **Self-Hosted Local Models (e.g. Ollama / Llama.cpp)**:
    *   *Pro*: 100% data privacy. No data ever leaves your servers. Zero token cost regardless of usage volume.
    *   *Con*: High initial hardware cost. Running models with low latency requires buying and maintaining servers with dedicated GPUs (like NVIDIA A100/H100).
*   **Production Rule**: For prototypes or low-volume text, use **API-Based Models** to validate market fit quickly. For enterprise applications processing sensitive user profiles at scale, build **Local Embeddings Pipelines** to guarantee security and minimize running costs.

---

## 3. How to Use: Abstracting the AI Pipeline

Let us write a compile-grade Python 3.11+ application that abstracts an AI resume processing pipeline, sanitizing PII before mock indexing.

### A. The Data Leakage Pipeline (Anti-Pattern)

Avoid sending unvalidated, raw user profile data directly to external APIs:

```python
import httpx

# DANGER: Sending raw resume text containing candidate emails, home addresses,
# and phone numbers directly to a third-party API. This exposes your company
# to severe data security compliance penalties.
async def index_resume_vulnerable(candidate_id: int, raw_resume_text: str):
    api_url = "https://api.external-ai.com/v1/embeddings"
    
    # Directly transmitting sensitive data outside the boundary
    payload = {"input": raw_resume_text}
    async with httpx.AsyncClient() as client:
        response = await client.post(api_url, json=payload)
        return response.json()
```

### B. The Hardened Sandboxed Pipeline (Production Pattern)

Here is the hardened pattern. We write an orchestrator class that sanitizes PII (emails/phone numbers) locally before generating embeddings, and mocks the vector storage.

```python
import re
from typing import Dict, Any, List

class AISystemOrchestrator:
    def __init__(self, target_dimensions: int = 384):
        self.target_dimensions = target_dimensions
        # Simulated in-memory vector database
        self.vector_store: Dict[int, List[float]] = {}

    def sanitize_pii(self, text: str) -> str:
        """
        Locally strip sensitive PII from text before passing it to models.
        """
        # Redact email addresses
        email_pattern = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'
        sanitized = re.sub(email_pattern, "[EMAIL_REDACTED]", text)
        
        # Redact phone numbers (simple pattern for illustration)
        phone_pattern = r'\+?\d{1,4}?[-.\s]?\(?\d{1,3}?\)?[-.\s]?\d{1,4}[-.\s]?\d{1,4}[-.\s]?\d{1,9}'
        sanitized = re.sub(phone_pattern, "[PHONE_REDACTED]", sanitized)
        
        return sanitized

    def generate_mock_embeddings(self, sanitized_text: str) -> List[float]:
        """
        Simulate an embedding model converting text to a normalized coordinate vector.
        In later modules, we will use sentence-transformers for this.
        """
        # Create a deterministic mock vector based on text length and vocabulary
        words = sanitized_text.lower().split()
        vector = [0.0] * self.target_dimensions
        
        for idx, word in enumerate(words[:self.target_dimensions]):
            # Assign arbitrary float values derived from characters
            vector[idx] = round(sum(ord(c) for c in word) / 1000.0, 4)
            
        # Normalize the mock vector
        magnitude = sum(x**2 for x in vector)**0.5
        if magnitude > 0:
            vector = [round(x / magnitude, 4) for x in vector]
            
        return vector

    def store_vector(self, candidate_id: int, vector: List[float]):
        """
        Save the vector coordinates.
        """
        self.vector_store[candidate_id] = vector
        
    def process_and_index(self, candidate_id: int, raw_resume: str) -> Dict[str, Any]:
        # SECURE: Redact PII locally first
        clean_text = self.sanitize_pii(raw_resume)
        
        # Generate semantic representation
        vector = self.generate_mock_embeddings(clean_text)
        
        # Store in vector database
        self.store_vector(candidate_id, vector)
        
        return {
            "candidate_id": candidate_id,
            "sanitized_text": clean_text[:100] + "...",
            "vector_dimension": len(vector),
            "status": "indexed"
        }
```

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Treating Generative LLMs as Search Indexes
Attempting to feed thousands of resumes directly into an LLM's prompt context to ask: "Which candidate matches best?"
*   **Why it fails**: Exceeds context window limits (token boundaries), is extremely slow (taking minutes to execute), and costs significant money in API fees.
*   **Mitigation**: Use embedding models and vector databases to quickly filter down candidate lists to the top 5-10 matches, then pass only those top matches to the LLM for final reasoning.

### Pitfall 2: Bypassing Local PII Scrubbing
Assuming that HTTPS connections to model APIs satisfy data protection laws.
*   **Why it fails**: Even if the connection is encrypted, the third-party company receives, processes, and potentially logs your candidates' private data, violating compliance boundaries.
*   **Mitigation**: Redact sensitive metadata (names, emails, phones) at your application boundary before sending text to external servers.

---

## 5. Socratic Review Questions

### Question 1
Why are embedding models significantly cheaper and faster to run than generative LLMs (like GPT-4)?

#### Answer
Generative LLMs are massive autoregressive models designed to generate text token-by-token, which requires billions of computations per token. Embedding models are much smaller, encoder-only models. They process input text in a single forward pass and return a fixed-size vector, requiring thousands of times less compute power and memory.

### Question 2
How does semantic search handle synonyms (like "Backend Developer" vs. "Server-Side Engineer") without manual synonym lists?

#### Answer
During model training, the embedding model learns the contexts in which words appear. Since "Backend" and "Server-Side" appear in similar contexts, the model places them close to each other in the vector space, automatically resulting in high similarity scores during search queries.

---

## 6. Hands-on Challenge: Building a Secure Search Orchestrator

### The Challenge
In this challenge, you will implement the orchestration logic for an AI resume indexing pipeline.

Your task:
1.  Complete the `orchestrate_ingestion` method inside `ResumePipeline`.
2.  Locally sanitize the raw text of the resume to redact emails.
3.  Generate the mock vector embeddings.
4.  Store the vector inside `self.index`.
5.  Return the sanitized text.

Complete the implementation below:

```python
import re

class ResumePipeline:
    def __init__(self):
        # Maps candidate_id to their float vector
        self.index: dict[int, list[float]] = {}

    def clean_email(self, text: str) -> str:
        # Regex to match standard emails
        pattern = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'
        return re.sub(pattern, "[MASKED]", text)

    def generate_mock_vector(self, text: str) -> list[float]:
        # Returns a dummy 3-dimensional vector for testing
        return [0.1, 0.5, 0.8]

    def orchestrate_ingestion(self, candidate_id: int, raw_text: str) -> str:
        # TODO: Complete this orchestration pipeline.
        # 1. Sanitize raw_text using self.clean_email.
        # 2. Generate vector from sanitized text using self.generate_mock_vector.
        # 3. Save the vector in self.index under candidate_id key.
        # 4. Return the sanitized text string.
        
        return ""
```

Write the sanitization and registration logic. Save the completed file and verify that email addresses are correctly masked inside `modules/01-big-picture-architecture.md`.
