# CS-524: Speech-to-Text & Whisper ASR Systems

Welcome to **CS-524: Speech-to-Text & Whisper ASR Systems**. I am Professor Antigravity. In this course, we will study high-performance Automatic Speech Recognition (ASR) systems engineering using OpenAI's **Whisper** and optimized local execution backends.

Transcribing voice inputs (such as candidate interview recordings) into structured text is essential for downstream semantic processing. However, deploying ASR features into production presents severe execution bottlenecks: standard Whisper model executions consume massive CPU cycles, transcription accuracy degrades on domain-specific technical terms (like transcribing "JPA" as "GPA" or "Spring Boot" as "Spring Boat"), and evaluating ASR quality requires mathematical distance metrics.

In this course, we will study **ASR audio pipelines**, configure **`faster-whisper` local inference engines**, calculate **Word Error Rate (WER)** metrics, and learn how to **fine-tune Whisper models** on custom technical vocabularies using LoRA.

---

## Course Syllabus & Navigation

The course is divided into 5 detailed modules:

| Module | Core Classification | Focus Topics |
| :--- | :--- | :--- |
| **01** | [ASR Pipeline Foundations](file:///c:/Users/Admin/Desktop/projects/learning-repo/speech-to-text-whisper/modules/01-asr-pipelines.md) | Speech signal audio capture, Mel-spectrogram features extraction, Encoder-Decoder architectures, hosted APIs vs. local self-hosted models. |
| **02** | [High-Performance Inference](file:///c:/Users/Admin/Desktop/projects/learning-repo/speech-to-text-whisper/modules/02-faster-whisper-inference.md) | CTranslate2 compilation speedups, 8-bit/16-bit local model loading, decoding variables (beam size, VAD thresholds), timestamp segments. |
| **03** | [Transcription Evaluation Metrics](file:///c:/Users/Admin/Desktop/projects/learning-repo/speech-to-text-whisper/modules/03-transcription-evaluation-wer-cer.md) | Word Error Rate (WER) & Character Error Rate (CER) mathematics, Levenshtein edit distance, text normalizations via `jiwer`. |
| **04** | [Whisper Model Fine-Tuning](file:///c:/Users/Admin/Desktop/projects/learning-repo/speech-to-text-whisper/modules/04-whisper-fine-tuning.md) | Technical jargon vocabulary drift, custom tokenization expansions, training datasets formatting, frozen baselines with LoRA adapters. |
| **05** | [Final Capstone Project](file:///c:/Users/Admin/Desktop/projects/learning-repo/speech-to-text-whisper/modules/05-final-capstone-asr-pipeline.md) | Building an automated local transcription auditor: transcodes audio files, generates transcriptions, calculates WER against ground truths, logs metadata. |

---

## Local Environment Configuration

To configure your local development workspace, ensure you have **Python 3.11+** and **FFmpeg** installed.

### 1. System-Level Dependencies (FFmpeg)
Whisper relies on FFmpeg to convert incoming audio files into standard 16000Hz mono PCM streams before processing:
*   **macOS**: `brew install ffmpeg`
*   **Linux (Ubuntu/Debian)**: `sudo apt-get update && sudo apt-get install -y ffmpeg`
*   **Windows**: Install via winget: `winget install Gyan.FFmpeg`.

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
# Install faster-whisper, evaluation metrics, and transformers training stack
pip install faster-whisper>=0.10.0 jiwer>=3.0.3 transformers>=4.37.0 peft>=0.7.0 torch>=2.1.0 accelerate>=0.26.0
```

---

## Grading Criteria & Defensive Success Metrics

Your progress is evaluated based on the following engineering rubrics:

*   **ASR Resource Efficiency (30%)**: Implementing quantized formats, utilizing appropriate decoding variables, and optimizing CPU/GPU runtimes.
*   **Transcription Evaluation Accuracy (25%)**: Correctly computing WER/CER metrics, implementing spelling normalizations, and logging performance logs.
*   **Domain Vocabulary Resilience (25%)**: Correctly setting up tokenizers and adapters to resolve jargon transcriptions, preventing semantic translation drifts.
*   **Verification Completeness (20%)**: Writing automated test units to verify text cleanup and metric assertions.
