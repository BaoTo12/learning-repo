# CS-526: Text-to-Speech Synthesis & Visual Avatar Animation

Welcome to **CS-526: Text-to-Speech Synthesis & Visual Avatar Animation**. I am Professor Antigravity. In this course, we will explore local Text-to-Speech (TTS) synthesis and real-time frontend mouth synchronization to build a visual, conversational AI interviewer.

In an interactive interview room, the AI interviewer needs a "MOUTH" (to speak out questions and follow-ups) and a "FACE" (to visually express speaking state changes). Deploying voice features, however, introduces severe bottlenecks: commercial cloud voice APIs incur massive transaction costs and latency, and animating realistic avatars usually requires heavy 3D rendering engines that are difficult to build and run.

To solve this, we will run the highly optimized, compact **Kokoro-82M** model locally in Python, implement an on-disk content-hashed **caching strategy** to pre-render static dialogue (reducing latency to zero), and leverage the browser's native **Web Audio API `AnalyserNode`** to animate a 2D vector avatar in real-time.

---

## Course Syllabus & Navigation

The course is divided into 5 modules:

| Module | Core Classification | Focus Topics |
| :--- | :--- | :--- |
| **01** | [Local Speech Generation](file:///c:/Users/Admin/Desktop/projects/learning-repo/tts-avatar-synthesis/modules/01-kokoro-tts-inference.md) | Kokoro-82M architecture, sample rates (24kHz outputs), generating raw audio float arrays from text strings, and writing `.wav` container files. |
| **02** | [Dialogue Caching](file:///c:/Users/Admin/Desktop/projects/learning-repo/tts-avatar-synthesis/modules/02-audio-caching-strategy.md) | Pre-generating assets for static dialogue, building a local content-hashed lookup index, and routing fallbacks to dynamic voice synthesis. |
| **03** | [Web Audio Analysis](file:///c:/Users/Admin/Desktop/projects/learning-repo/tts-avatar-synthesis/modules/03-web-audio-analysernode.md) | Audio contexts, media element node routing, AnalyserNode settings, time-domain sampling, and calculating Root-Mean-Square (RMS) volumes. |
| **04** | [2D Avatar Animating](file:///c:/Users/Admin/Desktop/projects/learning-repo/tts-avatar-synthesis/modules/04-avatar-mouth-sync.md) | Visual state layers mapping volume decibels to mouth shapes (Closed, Small, Medium, Open), CSS transitions, and driving lip-sync loops at 60 FPS. |
| **05** | [Final Capstone Project](file:///c:/Users/Admin/Desktop/projects/learning-repo/tts-avatar-synthesis/modules/05-capstone-speaking-pipeline.md) | Building a unified speaking character interface. Backed by a caching TTS server endpoint and driven by browser-only volume analysis loops. |

---

## Local Environment Configuration

To configure your workspace, ensure you have **Python 3.11+** and the necessary audio drivers installed on your operating system.

### 1. System-Level Dependencies (Audio Libraries)
Depending on your OS, you may need system-level wrappers to compile Python audio bindings (such as `soundfile` and `sounddevice`):
*   **macOS**: `brew install portaudio`
*   **Linux (Ubuntu/Debian)**: `sudo apt-get update && sudo apt-get install -y portaudio19-dev libsndfile1`
*   **Windows**: Visual C++ Redistributable packages are usually sufficient.

### 2. Python Virtual Environment & Requirements
Create your environment and install the required modules:
```bash
# Create and activate virtual environment
python -m venv .venv
# On Windows:
.venv\Scripts\Activate.ps1
# On macOS/Linux:
source .venv/bin/activate

# Install required dependencies
pip install --upgrade pip
# Install Kokoro TTS runner, PyTorch, soundfile, and web serving libraries
pip install kokoro>=0.1.2 torch>=2.1.0 soundfile>=0.12.1 sounddevice>=0.4.6 fastapi>=0.109.0 uvicorn>=0.27.0
```

### 3. Fetching Kokoro weights
The Kokoro-82M model utilizes standard ONNX models or PyTorch checkpoints. The library automatically fetches weights upon first request, but you can pre-fetch them by running a test script or pre-loading the models into your cache directory.

---

## Grading Criteria & Defensive Success Metrics

Your progress is evaluated based on the following engineering rubrics:

*   **Synthesis Efficiency (30%)**: Correctly building the cache layer, indexing assets, and avoiding redundant GPU inference execution.
*   **Lip-Sync Precision (25%)**: Implementing accurate time-domain volume calculations (RMS) and mapping signal ranges to mouth visual tags without stuttering.
*   **Frontend-Backend Coordination (25%)**: Designing secure REST headers, playing dynamic streams with chunking, and handling web socket state transitions.
*   **Verification Completeness (20%)**: Implementing automated test coverage for cache lookups, file indexing, and volume metrics math.
