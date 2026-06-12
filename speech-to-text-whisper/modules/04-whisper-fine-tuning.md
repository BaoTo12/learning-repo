# Module 04: Whisper Fine-Tuning — Domain Vocabulary & LoRA Adapters

Welcome back, class. Today we analyze **Whisper Model Fine-Tuning (CS-524)**.

Out-of-the-box ASR models are trained on general datasets. When deployed in technical domains, their accuracy degrades on specialized jargon. In a software engineering interview recording, Whisper often transcribes technical acronyms as common words: `"JPA"` becomes `"GPA"`, `"REST API"` becomes `"rust api"`, and `"Spring Boot"` becomes `"spring boat"`. This semantic drift breaks subsequent keyword matching and resume evaluation scripts.

To fix this, we fine-tune the model on custom datasets. Because full-parameter training is computationally prohibitive for most software teams, we use **Parameter-Efficient Fine-Tuning (PEFT)** via **LoRA (Low-Rank Adaptation)**. Today, we will study **vocabulary drift**, prepare training datasets, and write a PEFT training script.

---

## 1. Academic Lecture: Jargon Drift, Tokenizer Expansions, and LoRA

Adapting a sequence-to-sequence audio model to a new domain requires modifying its decoding bias:

### 1. The Jargon Drift Problem
Whisper's decoder predicts the next word based on probability distributions learned from the internet. Because general text rarely combines words like "Spring" and "Boot" to refer to a Java framework, the decoder's prior probability favors the common phrase `"spring boat"`. We must train the model on domain-specific audio-transcript pairs to adjust this probability bias.

### 2. Tokenizers vs. Feature Extractors
Whisper requires two data conversion steps:
*   **The Audio Feature Extractor**: Converts raw 16kHz audio waves into 2D log-Mel spectrograms.
*   **The Text Tokenizer**: Converts text transcripts into token IDs.
*   **The Processor**: Combines the extractor and tokenizer into a single interface. If a technical term is completely missing from the model's default vocabulary list, we must append it to the tokenizer and resize the model's token embedding layers.

### 3. LoRA for Encoder-Decoder Models
Instead of updating all weights in Whisper's encoder and decoder, we apply LoRA:
*   **Target Modules**: We target the attention layers (typically the query `q_proj` and value `v_proj` projection matrices) in both the encoder and decoder.
*   **Rank ($r$)**: We define the rank of the update matrices (commonly $r=8$). This restricts the updates to low-dimensional subspaces, preventing the model from forgetting its base language capabilities (catastrophic forgetting).

```mermaid
sequenceDiagram
    autonumber
    participant Data as Training Pairs (Audio+Text)
    participant Proc as Whisper Processor
    participant Base as Frozen Whisper Base Weights
    participant LoRA as Trainable LoRA Matrices
    participant Opt as AdamW Optimizer

    Data->>Proc: Pass Raw WAV + Text ("Spring Boot")
    Proc->>Proc: Extractor: Wave -> Spectrogram<br/>Tokenizer: Text -> Token IDs
    Proc->>Base: Forward pass Spectrogram
    Base->>LoRA: Compute Attention activations
    LoRA-->>Opt: Calculate Loss against Token IDs
    Opt->>LoRA: Backpropagate and update LoRA weights (Base weights frozen)
    Note over LoRA: LoRA learns to bias "spring boot" over "spring boat"
```

---

## 2. Theory vs. Production Trade-offs

### Context Prompting (`initial_prompt`) vs. LoRA Fine-Tuning
*   **Context Prompting (`initial_prompt="JPA, REST, Spring Boot"`)**:
    *   *Pro*: Instant. Requires zero training, zero dataset gathering, and zero VRAM. You simply pass the technical keywords as a string parameter to the transcribe call.
    *   *Con*: Unreliable. The prompt context is small, easily ignored by the model on noisy recordings, and does not scale if you have hundreds of technical terms to inject.
*   **LoRA Fine-Tuning**:
    *   *Pro*: Highly robust. Permanently adapts the model's internal attention layers to recognize technical terms, even under high noise levels or heavy accents.
    *   *Con*: High development cost. Requires compiling an audio-to-text dataset, renting GPU servers for training, and managing custom model deployments.
*   **Production Rule**: Start by using the **`initial_prompt`** parameter with a list of your target keywords. Only invest in **LoRA Fine-Tuning** if evaluation metrics show that prompting is failing to prevent high Word Error Rates (WER) on critical technical terms.

---

## 3. How to Use: Scaffolding a LoRA Training Script

Let us write a compile-grade Python 3.11+ script using HuggingFace `transformers` and `peft` that configures a Whisper model for LoRA training.

### A. Full Parameter Training (Anti-Pattern)

Avoid attempting to fine-tune all model weights directly on consumer GPUs:

```python
from transformers import WhisperForConditionalGeneration

# DANGER: Running full-parameter fine-tuning without freezing layers.
# This will instantly trigger a GPU Out-of-Memory (OOM) crash on standard
# developer machines, and risks corrupting the model's general English
# capabilities (catastrophic forgetting).
def naive_train_vulnerable():
    model = WhisperForConditionalGeneration.from_pretrained("openai/whisper-base")
    # Attempting to train all parameters directly
    # trainer.train() 
```

### B. The Hardened LoRA ASR Configuration (Production Pattern)

Here is the hardened pattern. We load the model, configure a `LoraConfig` specifically targeting Whisper's attention projection layers, freeze the base model, and initialize the training wrapper securely.

```python
import torch
from transformers import WhisperForConditionalGeneration, WhisperProcessor, Seq2SeqTrainer, Seq2SeqTrainingArguments
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training

def configure_whisper_lora_training(
    model_id: str = "openai/whisper-base",
    rank: int = 8,
    alpha: int = 32
) -> Tuple[Any, WhisperProcessor] if 'Tuple' in globals() else Any:
    # 1. Load model and processor
    processor = WhisperProcessor.from_pretrained(model_id)
    model = WhisperForConditionalGeneration.from_pretrained(model_id)

    # 2. SECURE: Freeze base model parameters to prevent weight corruption
    model.config.use_cache = False  # Must be disabled during training
    
    # 3. Define the LoRA configuration targeting Whisper attention layers
    # Target modules in Whisper are typically 'q_proj' and 'v_proj'
    peft_config = LoraConfig(
        r=rank,                             # Rank dimension (lower = less VRAM)
        lora_alpha=alpha,                   # Scaling parameter
        target_modules=["q_proj", "v_proj"],# SECURE: Target attention layers
        lora_dropout=0.05,
        bias="none",
        task_type="SEQ_2_SEQ_LM"            # Whisper is an Encoder-Decoder model
    )

    # 4. SECURE: Wrap model with PEFT Lora layers
    # This freezes base parameters and mounts the trainable adapter layers
    peft_model = get_peft_model(model, peft_config)
    
    # Print trainable parameters to verify compression
    peft_model.print_trainable_parameters()
    
    return peft_model, processor
```

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Incorrect Target Module Keys
Setting `target_modules=["query", "value"]` in the `LoraConfig`.
*   **Why it fails**: Different model families use different names for their attention layers. Whisper uses `q_proj` and `v_proj`. Passing incorrect names prevents LoRA from attaching, resulting in zero weights being marked as trainable.
*   **Mitigation**: Always print the base model's named modules to verify layer names before writing configurations.

### Pitfall 2: Leaving Cache Enabled during Training
Forgetting to set `model.config.use_cache = False` during training.
*   **Why it fails**: The KV-cache optimization is designed to speed up inference by caching past token states. During training, backpropagation operations require re-calculating states. If cache remains active, it raises training runtime crashes.
*   **Mitigation**: Always set `use_cache = False` before starting the trainer.

---

## 5. Socratic Review Questions

### Question 1
Why does applying a LoRA adapter prevent "catastrophic forgetting" during fine-tuning?

#### Answer
Catastrophic forgetting occurs when a model's original pre-trained weights are overwritten by new training data, causing it to lose its general capabilities. Because LoRA freezes the base model weights, the original knowledge remains locked. Only the small adapter weights are updated, keeping the base model intact.

### Question 2
What is the purpose of the `lora_alpha` parameter in `LoraConfig`, and how does it relate to the rank `r`?

#### Answer
`lora_alpha` is a scaling factor for the LoRA adapter weights:
$$\Delta W \propto \frac{\text{lora\_alpha}}{r}$$
When training, keeping `lora_alpha` constant while changing the rank `r` ensures that you do not need to re-tune the learning rate hyperparameters, simplifying experimentation.

---

## 6. Hands-on Challenge: Configuring a Whisper LoRA Adapter

### The Challenge
In this challenge, you will implement a function that generates a PEFT `LoraConfig` configured for Whisper model adjustments.

Your task:
1.  Complete the function `get_whisper_lora_config`.
2.  Configure the `LoraConfig` to target modules `"q_proj"` and `"v_proj"`.
3.  Set the task type to `"SEQ_2_SEQ_LM"`.
4.  Set the rank to `8` and alpha to `32`.
5.  Return the config object.

Complete the implementation below:

```python
from peft import LoraConfig

def get_whisper_lora_config() -> LoraConfig:
    # TODO: Complete this configuration builder.
    # 1. Instantiate LoraConfig with:
    #      r=8
    #      lora_alpha=32
    #      target_modules=["q_proj", "v_proj"]
    #      lora_dropout=0.05
    #      bias="none"
    #      task_type="SEQ_2_SEQ_LM"
    # 2. Return the config instance.
    
    return None
```

Write the PEFT attention targets and task definitions. Save the completed file and verify the configuration parameters match the Whisper specs inside `modules/04-whisper-fine-tuning.md`.
