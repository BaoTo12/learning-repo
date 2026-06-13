# CS-522: Advanced Python File I/O & Audio Processing

Welcome to **CS-522: Advanced Python File I/O & Audio Processing**. I am Professor Antigravity. In this course, we will study file system primitives, raw binary formatting, character encoding models, and programmatic audio processing pipelines.

Writing production-grade systems often requires loading, sanitizing, and manipulating file datasets. Many engineers handle files unsafely: leaking open file handles, corrupting character encodings due to lazy defaults, crashing containers on large file allocations, or misunderstanding the raw binary composition of multimedia files.

In this course, we will build a solid foundation of **pathway safety (`pathlib`)**, **deterministic encoding boundaries**, **efficient byte buffering (chunking & memory mapping)**, and **PCM audio container parsing**. We will also study standard and third-party libraries (like `pydub` and `librosa`) to build advanced audio processing pipelines.

---

## Course Syllabus & Navigation

The course is divided into 7 detailed modules:

| Module | Core Classification | Focus Topics |
| :--- | :--- | :--- |
| **01** | [Core File System Operations](file:///c:/Users/Admin/Desktop/projects/learning-repo/python-file-io-essentials/modules/01-pathlib-filesystem.md) | Path safety, folder crawling, metadata checks, permissions via `pathlib.Path`. |
| **02** | [Structured Text & Encodings](file:///c:/Users/Admin/Desktop/projects/learning-repo/python-file-io-essentials/modules/02-text-files-encodings.md) | UTF character set standards, decode error strategies, CSV & JSON data streams. |
| **03** | [Binary Files & Buffers](file:///c:/Users/Admin/Desktop/projects/learning-repo/python-file-io-essentials/modules/03-binary-files-buffers.md) | Raw byte array buffers, parsing layout contracts with `struct`, memory mapping performance. |
| **04** | [WAVE Audio Containers](file:///c:/Users/Admin/Desktop/projects/learning-repo/python-file-io-essentials/modules/04-wave-audio-headers.md) | RIFF wave header parameters parsing, sample rates, bitrates, standard library `wave`. |
| **05** | [Audio Manipulation Libraries](file:///c:/Users/Admin/Desktop/projects/learning-repo/python-file-io-essentials/modules/05-audio-processing-libraries.md) | Sound transcoding, resampling, merging, and features extraction using `pydub` and `librosa`. |
| **06** | [Chunk-by-Chunk Audio Streaming](file:///c:/Users/Admin/Desktop/projects/learning-repo/python-file-io-essentials/modules/06-chunked-audio-streaming.md) | High-performance audio stream generators, in-memory formatting buffers using `io.BytesIO`. |
| **07** | [Final Capstone Project](file:///c:/Users/Admin/Desktop/projects/learning-repo/python-file-io-essentials/modules/07-final-capstone-audio-pipeline.md) | Implementing a recursive folder-scanning, volume-normalizing, audio-transcoding pipelines CLI. |

---

## Local Environment Configuration

To configure your workspace, make sure you have **Python 3.11+** and the system-level binary dependencies installed.

### 1. System-Level Dependencies (Audio decoders)
Many Python multimedia packages (like `pydub` and `librosa`) depend on external CLI executables to decode format containers (e.g. MP3, OGG, FLAC):
*   **macOS**: `brew install ffmpeg libsndfile`
*   **Linux (Ubuntu/Debian)**: `sudo apt-get update && sudo apt-get install -y ffmpeg libsndfile1`
*   **Windows**: Download `ffmpeg` binaries from [Gyan.dev](https://www.gyan.dev/ffmpeg/builds/) or use `winget install Gyan.FFmpeg`.

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
pip install pydub>=0.25.1 librosa>=0.10.1 soundfile>=0.12.1 pytest>=8.0.0
```

---

## Grading Criteria & Defensive Success Metrics

Your progress is measured using the following engineering rubrics:

*   **System Resource Safety (30%)**: Guaranteeing file descriptors are closed under all execution paths, avoiding full file RAM buffering via chunked streams.
*   **Boundary Validation & Security (25%)**: Preventing directory traversal vulnerabilities, validating file MIME classes, and handling character encoding exceptions.
*   **Multimedia Domain Precision (25%)**: Correctly extracting, analyzing, and writing PCM WAVE frames and channel attributes.
*   **Verification Completeness (20%)**: Writing mockable file tests using pytest fixtures and temporary sandboxed directories.
