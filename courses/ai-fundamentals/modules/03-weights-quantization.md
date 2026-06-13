# Module 03: Model Weights & Quantization — FP16 Precision & GGUF Formats

Welcome back, class. Today we analyze **Model Weights & Quantization (CS-523)**.

Pre-trained AI models are enormous. A model with 7 billion parameters stores those parameters as high-precision floating-point numbers. If loaded in standard 32-bit float precision (FP32), the model requires 28 gigabytes of memory just to sit in RAM—far exceeding the memory of standard developer machines or cost-effective server containers.

To run Large Language Models (LLMs) and embeddings pipelines locally or inside standard microservices, we compress the weights using a technique called **Quantization**. Today, we will study **float representations**, analyze quantization scaling mathematics, explore the **GGUF container format**, and configure quantized local models.

---

## 1. Academic Lecture: Float Precision, Scaling Factors, and Clamping

Quantization reduces the precision of model weights to save memory and speed up computation:

### 1. Float Formats and Sizing
Model parameters are represented in different numerical formats:
*   **FP32 (Single Precision)**: 32 bits (4 bytes) per number. Used during training for absolute mathematical stability.
*   **FP16 / BF16 (Half Precision)**: 16 bits (2 bytes) per number. Standard distribution format for modern models.
*   **INT8 / INT4 (Quantized)**: 8 bits (1 byte) or 4 bits (0.5 bytes) per number. Used for compressed local execution.

### 2. Sizing Estimation Formula
To estimate the minimum VRAM or RAM required to load a model:
$$\text{Memory (GB)} \approx \left(\text{Parameters in Billions} \times \frac{\text{Bits per Weight}}{8}\right) \times 1.2$$
The $1.2$ factor accounts for the auxiliary memory needed for context caches and layer activations.
*   *Example*: A 7B parameter model in **FP16** requires $7 \times 2 \times 1.2 \approx 16.8\text{ GB}$.
*   *Example*: The same 7B model quantized to **4-bit** requires $7 \times 0.5 \times 1.2 \approx 4.2\text{ GB}$, allowing it to run on a standard laptop.

### 3. The Math of Linear Quantization
Linear quantization maps a continuous range of floats $[r_{\min}, r_{\max}]$ to a discrete range of integers $[q_{\min}, q_{\max}]$ (e.g., $[-128, 127]$ for signed INT8):
$$q = \text{round}\left(\frac{r}{S}\right) + Z$$
Where:
*   $r$ is the original float weight value.
*   $q$ is the target quantized integer.
*   $S$ is the **Scaling Factor** (defining step size):
    $$S = \frac{r_{\max} - r_{\min}}{q_{\max} - q_{\min}}$$
*   $Z$ is the **Zero-Point** integer offsets:
    $$Z = \text{round}\left(\frac{-r_{\min}}{S}\right) + q_{\min}$$

```mermaid
graph TD
    subgraph Quantization (Compression)
        F[FP16 Float Weight Matrix] -->|Analyze range min/max| Range[Calculate Scale S & Zero Z]
        F -->|Apply: q = round r/S + Z| QuantMath[Quantization Engine]
        Range --> QuantMath
        QuantMath -->|Write to Disk| GGUF[GGUF Compressed file: INT4 Matrix + Metadata]
    end

    subgraph Dequantization (Inference execution)
        GGUF -->|Load weights to RAM| Load[Read INT4 Matrix]
        Load -->|Apply: r = S * q - Z| Dequant[Dequantize back to float approximation]
        Dequant -->|Execute Forward Pass| Forward[Forward Pass Output]
    end
```

---

## 2. Theory vs. Production Trade-offs

### High-Precision Baseline (FP16) vs. 4-bit Quantization (Q4_K_M)
*   **High-Precision FP16**:
    *   *Pro*: Full accuracy. The model maintains its maximum language reasoning capabilities and experiences zero perplexity degradation.
    *   *Con*: High hosting cost. Requires expensive GPU cloud instances (like NVIDIA A10G/A100) to host.
*   **4-bit Quantization (Q4_K_M)**:
    *   *Pro*: Maximum memory savings. The model fits on standard consumer CPU/GPU hardware. Reduces memory bandwidth bottlenecking, which can speed up token generation on standard machines.
    *   *Con*: Minor accuracy degradation. The model's reasoning abilities are slightly reduced, and it may experience minor errors in complex formatting or logic tasks.
*   **Production Rule**: For mission-critical tasks where high precision is mandatory, deploy **FP16** models on dedicated GPUs. For semantic search pipelines, embeddings generation, or general conversational agents, use **4-bit or 5-bit quantized models** to minimize server infrastructure costs.

---

## 3. How to Use: Loading Quantized Models

Let us write a compile-grade Python 3.11+ application that configures and loads a local model in 4-bit precision using HuggingFace `transformers`.

### A. The Naive High-Precision RAM Overflow (Anti-Pattern)

Avoid loading massive raw models directly into memory on standard servers:

```python
from transformers import AutoModelForCausalLM, AutoTokenizer

# DANGER: Attempting to load a raw 7B parameter model in FP32
# on a standard 8GB RAM server. This triggers a memory overflow,
# forcing the OS to terminate the process or page memory to disk,
# rendering execution hundreds of times slower.
def load_raw_model_vulnerable():
    model_id = "Qwen/Qwen1.5-7B-Chat"
    # This will allocate ~28GB of memory and crash standard containers
    model = AutoModelForCausalLM.from_pretrained(model_id)
    return model
```

### B. The Hardened 4-bit Quantization Configuration (Production Pattern)

Here is the hardened pattern. We write a clean initialization script using `bitsandbytes` configurations to load models in 4-bit precision securely.

```python
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from pathlib import Path

def load_quantized_model_safely(model_id: str) -> Tuple[AutoModelForCausalLM, AutoTokenizer]:
    # 1. Define the 4-bit Quantization Configuration
    # BitsAndBytesConfig encapsulates linear quantization rules
    quant_config = BitsAndBytesConfig(
        load_in_4bit=True,                       # SECURE: Compress weights to 4-bit on load
        bnb_4bit_compute_dtype=torch.float16,    # Dequantize back to float16 during matrix computations
        bnb_4bit_quant_type="nf4",               # NormalFloat4 (optimized distribution for weights)
        bnb_4bit_use_double_quant=True           # Quantize the scaling factors too, saving extra memory
    )
    
    # 2. Extract Tokenizer
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    
    # 3. Load Model with Quantization parameters
    # device_map="auto" automatically splits layers across VRAM and system RAM
    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        quantization_config=quant_config,
        device_map="auto"
    )
    
    return model, tokenizer
```

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Double-quantizing pre-quantized models
Attempting to apply `BitsAndBytesConfig` configurations to a model that has already been quantized and saved on disk.
*   **Why it fails**: Pre-quantized models (like GPTQ or AWQ models) already have compressed integer structures. Applying quantization configs on top of them causes structural format errors and throws loading exceptions.
*   **Mitigation**: Only apply `BitsAndBytesConfig` configurations to raw base models (unquantized FP16/FP32).

### Pitfall 2: Missing GPU hardware runtime libraries
Attempting to run `bitsandbytes` 4-bit configurations on CPU-only machines.
*   **Why it fails**: `bitsandbytes` requires CUDA-compatible GPU kernels. Running it on CPU-only environments raises missing binary compiler errors.
*   **Mitigation**: For CPU-only environments, use GGUF model formats loaded via `llama-cpp-python` or Ollama, which are optimized for CPU execution.

---

## 5. Socratic Review Questions

### Question 1
Why is the "NF4" (NormalFloat 4) quantization type preferred over standard linear "FP4" (Floating Point 4) for model compression?

#### Answer
Model weights are not distributed uniformly; they cluster around zero in a normal distribution (bell curve). NF4 is an information-theoretically optimal quantization format that maps quantization levels to match a normal distribution profile. This minimizes accuracy loss compared to linear FP4 quantization.

### Question 2
What is the purpose of "Double Quantization" inside `BitsAndBytesConfig`?

#### Answer
Quantized models store a scaling factor float for every block of weights (e.g. every 64 weights). Double quantization quantizes these scaling factors themselves from 32-bit floats to 8-bit floats, saving an additional 0.4 bits per parameter, which is significant for large models.

---

## 6. Hands-on Challenge: Implementing a Weight Quantizer

### The Challenge
In this challenge, you will implement a linear quantization mapper to compress a float weight vector to signed INT8 integers.

Your task:
1.  Complete the function `quantize_weights_to_int8`.
2.  Compute the maximum absolute value `abs_max` of the float array to define the scaling boundary: `abs_max = max(abs(x))`.
3.  Calculate the scaling factor $S$:
    $$S = \frac{\text{abs\_max}}{127}$$
4.  Map each float $r$ to quantized integer $q$:
    $$q = \text{round}\left(\frac{r}{S}\right)$$
5.  Clamp $q$ strictly between `-127` and `127` to fit in signed 8-bit limits.
6.  Return the scaling factor and the INT8 list.

Complete the implementation below:

```python
def quantize_weights_to_int8(weights: list[float]) -> tuple[float, list[int]]:
    if not weights:
        return 0.0, []
        
    # TODO: Complete this quantizer.
    # 1. Find the maximum absolute float value: abs_max = max(abs(w) for w in weights)
    # 2. If abs_max == 0.0, return 1.0, [0]*len(weights).
    # 3. Compute scale factor: scale = abs_max / 127.0
    # 4. Map each float: quantized = []
    #      for w in weights:
    #        q = round(w / scale)
    #        # Clamp values
    #        q = max(-127, min(127, q))
    #        quantized.append(int(q))
    # 5. Return scale and quantized list.
    
    return 1.0, []
```

Write the scaling computations and clamping constraints. Save the completed file and verify the quantized integers map to signed byte coordinates inside `modules/03-weights-quantization.md`.
