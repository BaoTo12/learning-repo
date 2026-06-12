# Graduation Thesis Project Proposal & Concept Specification

## Project Title

**AI-Powered ATS & Interactive AI Technical Interview Platform with Browser-Only Integrity Guard**

---

## 1. Executive Summary

Hiring technology workers is often slow, fragmented, and costly because companies usually depend on multiple separate systems: one tool for resume screening, another for interviews, and another for candidate integrity monitoring. This creates operational complexity for recruiters and a disconnected experience for candidates.

This graduation thesis proposes a unified technical hiring platform with three connected modules:

1. **Module A: Smart Resume Reader & Semantic Screener**  
   A local-first resume screening system that extracts resume information and semantically matches candidate profiles with job descriptions.

2. **Module B: Browser-Only Integrity Guard**  
   A lightweight browser-based integrity monitoring system that detects suspicious candidate behavior without webcam surveillance.

3. **Module C: Interactive AI Technical Interview Room**  
   The main research and implementation focus of this thesis. This module provides a speech-based interview room where an AI interviewer speaks to the candidate, listens to spoken answers, transcribes speech, evaluates answers using a rubric-guided lightweight language model, and responds with follow-up questions or transitions to the next assessment step.

Although the platform contains ATS and integrity-monitoring features, the core technical contribution of this graduation project is the **Interactive AI Technical Interview Room**, especially the independent AI pipeline:

```text
Speech-to-Text (EAR)
        ↓
LLM Interview Brain (BRAIN)
        ↓
Text-to-Speech + Avatar Animation (MOUTH/FACE)
```

The goal is not to commercialize the platform or simply integrate commercial AI products. Instead, the project focuses on designing and implementing a lightweight, controllable, and thesis-defensible AI interview system using open-source foundation models, optional fine-tuning/adaptation, and custom interview flow orchestration.

---

## 2. Problem Statement

Technical hiring requires both resume filtering and technical assessment. However, existing hiring workflows often suffer from the following problems:

- Resume screening tools may rely heavily on exact keyword matching instead of meaning-based matching.
- Online technical interviews often require human interviewer availability.
- Fully commercial AI interview systems can be expensive, closed-source, and difficult to explain academically.
- Webcam-based proctoring creates privacy concerns and consumes high bandwidth.
- Realtime AI voice systems can be costly and hard to control if the entire conversation is handled by a commercial black-box API.

This project addresses these problems by building a local-first and modular platform where the most important contribution is a controlled, lightweight, speech-based AI technical interview room.

---

## 3. Project Objectives

The project aims to:

1. Build a unified web platform for technical candidate screening and assessment.
2. Implement a semantic resume screening module that extracts candidate information and compares it with job descriptions.
3. Implement browser-only candidate integrity monitoring without webcam recording.
4. Design and implement an interactive AI technical interview room where:
    - The AI interviewer speaks using local/open-source text-to-speech.
    - The candidate answers using speech.
    - Speech is transcribed using a lightweight speech-to-text model.
    - Candidate answers are evaluated using a rubric-guided lightweight LLM.
    - The AI can generate follow-up questions or proceed to the next question.
    - A dynamic animated human avatar moves while the AI is speaking.
5. Evaluate the AI pipeline using measurable criteria such as transcription accuracy, technical keyword accuracy, answer evaluation quality, and end-to-end response latency.

---

## 4. Overall System Modules

---

# Module A: Smart Resume Reader & Semantic Screener

## 4.1 Purpose

Module A supports recruiters by automatically reading candidate resumes, extracting important information, and matching resumes against job descriptions using semantic similarity instead of simple keyword matching.

This module is not the main research focus, but it is included to make the platform a complete technical hiring workflow.

---

## 4.2 Features

### 4.2.1 Resume Parsing

The system accepts resume files such as PDF and extracts text content for further processing.

Extracted fields may include:

- Candidate name
- Email
- Phone number
- Education
- Years of experience
- Technical skills
- Project experience
- Work experience
- Certifications

---

### 4.2.2 Semantic Job Matching

Traditional resume screeners may miss candidates when the resume and job description use different words for similar concepts.

Example:

```text
Resume: "Software Developer"
Job Description: "Web Engineer"
```

A keyword-based system may consider them different. A semantic matching system should recognize that they may represent related capabilities.

The system converts resumes and job descriptions into vector embeddings and compares their semantic similarity.

---

### 4.2.3 Recruiter Dashboard Output

The recruiter dashboard displays structured information such as:

- Candidate ranking
- Matching score
- Extracted technical stack
- Experience summary
- Missing skills
- Resume-job similarity explanation

---

## 4.3 Possible Technical Approach

```text
Resume file
    ↓
Text extraction
    ↓
Information extraction
    ↓
Embedding generation
    ↓
Vector similarity search
    ↓
Candidate ranking
```

Suggested technologies:

- PDF parser
- Sentence-transformers or lightweight embedding model
- PostgreSQL + pgvector or Qdrant
- Rule-based extraction + optional LLM-assisted extraction

---

## 4.4 Trade-offs

| Approach                  | Pros                          | Cons                                      | When to use                  |
| ------------------------- | ----------------------------- | ----------------------------------------- | ---------------------------- |
| Keyword matching          | Simple, fast, explainable     | Misses synonyms and related skills        | Very simple MVP              |
| Semantic embeddings       | Better meaning-based matching | Needs embedding model and vector database | Recommended for this project |
| LLM-based resume analysis | More flexible extraction      | More expensive and less deterministic     | Optional enhancement         |

---

# Module B: Browser-Only Integrity Guard

## 5.1 Purpose

Module B provides lightweight candidate integrity monitoring during online assessments without using webcam recording.

The goal is not to guarantee perfect anti-cheating protection. Instead, the system collects browser-based risk signals that can help recruiters review suspicious behavior while preserving candidate privacy.

---

## 5.2 Features

### 5.2.1 Tab and Focus Tracking

The system records events when the candidate:

- Leaves the interview tab
- Minimizes the browser
- Switches to another application
- Returns to the interview page

Tracked data:

- Number of tab switches
- Duration away from the interview page
- Timestamp of each event

---

### 5.2.2 Display Hardware Check

Before the interview starts, the system may check whether multiple displays are active.

If multiple displays are detected, the system can warn the candidate or request that extra monitors be disconnected.

This should be treated as a risk signal, not a perfect security guarantee, because browser support and permissions can vary.

---

### 5.2.3 Input Restrictions

During assessment, the system can restrict:

- Pasting text into written answers
- Copying question text
- Selecting question text
- Opening developer-console-driven hidden steps

These restrictions are not perfect security mechanisms, but they reduce easy cheating behavior.

---

### 5.2.4 Security Event Logging

Integrity events are stored with the candidate session:

```json
{
    "event_type": "TAB_SWITCH",
    "started_at": "2026-06-12T10:20:00Z",
    "duration_seconds": 18,
    "risk_level": "medium"
}
```

---

## 5.3 Trade-offs

| Method                  | Pros                                         | Cons                                                        |
| ----------------------- | -------------------------------------------- | ----------------------------------------------------------- |
| Browser-only monitoring | Privacy-friendly, lightweight, low bandwidth | Cannot fully prevent cheating                               |
| Webcam proctoring       | Stronger monitoring                          | Privacy concerns, high bandwidth, complex storage           |
| Lockdown browser        | Stronger control                             | Hard to build, platform-specific, poor candidate experience |

For this thesis, browser-only monitoring is selected because it matches the privacy-preserving design goal.

---

# Module C: Interactive AI Technical Interview Room

## 6.1 Purpose

Module C is the **main technical and research focus** of the project.

The goal is to build a browser-based AI interview room where the AI interviewer can speak, the candidate can answer by voice, and the system can transcribe, evaluate, and continue the interview flow.

This is not a fully autonomous commercial AI agent. It is a controlled AI interview system using a structured interview flow, lightweight models, and server-controlled state management.

---

## 6.2 Core Interaction Loop

The main interaction loop is:

```text
AI speaks
    ↓
Candidate listens
    ↓
Candidate speaks
    ↓
System transcribes speech
    ↓
LLM evaluates the answer
    ↓
AI asks follow-up or moves to next question
```

Expanded pipeline:

```text
Candidate speaks
    ↓
Browser records audio chunks
    ↓
faster-whisper transcribes speech
    ↓
LLM evaluates / generates follow-up
    ↓
Kokoro-82M generates AI voice
    ↓
Avatar speaks with mouth animation
```

---

## 6.3 Independent AI Pipeline

The AI interview room is divided into four parts:

```text
EAR   = Speech-to-Text
BRAIN = Lightweight LLM + rubric-guided interview logic
MOUTH = Text-to-Speech
FACE  = Dynamic audio-driven avatar animation
```

This design avoids depending on one commercial black-box voice agent. Each component can be developed, replaced, evaluated, and improved independently.

---

# 7. EAR: Speech-to-Text

## 7.1 Purpose

The EAR component converts the candidate's spoken answer into text.

This is important because the quality of answer evaluation depends heavily on transcription quality.

Bad transcription leads to bad evaluation.

```text
Bad transcript
    ↓
Bad answer evaluation
    ↓
Bad follow-up question
    ↓
Bad interview result
```

---

## 7.2 Recommended Model

Use:

```text
faster-whisper + Whisper base/small + int8 quantization
```

Recommended starting point:

```text
faster-whisper small int8
```

Why:

- Lightweight enough for thesis development.
- Faster than standard Whisper inference.
- Better latency for interactive interviews.
- Good enough accuracy for clear technical interview speech.

---

## 7.3 Model Choice

| Model                  | Use Case                   | Recommendation                           |
| ---------------------- | -------------------------- | ---------------------------------------- |
| Whisper base/base.en   | Fastest demo               | Use if hardware is weak                  |
| Whisper small/small.en | Best balance               | Recommended                              |
| Whisper medium         | Better accuracy            | Use only if small is not accurate enough |
| Whisper large-v3       | Highest accuracy but heavy | Avoid for local realtime thesis MVP      |

---

## 7.4 Fine-Tuning Strategy

Fine-tuning is optional but recommended as the main AI experiment.

Do not fine-tune immediately. First build the working system using pretrained faster-whisper.

Suggested stages:

```text
Stage 1: Use pretrained faster-whisper small int8
Stage 2: Collect technical interview speech dataset
Stage 3: Fine-tune Whisper small using Hugging Face Transformers
Stage 4: Compare original Whisper small vs fine-tuned Whisper small
Stage 5: Evaluate improvement and integrate the better model
```

---

## 7.5 Fine-Tuning Dataset

The dataset should focus on technical interview vocabulary.

Example data item:

```json
{
    "audio": "candidate_answer_001.wav",
    "text": "Dependency injection means that dependencies are provided from outside the class instead of being created inside the class."
}
```

Suggested dataset size:

|       Dataset Size | Thesis Value        |
| -----------------: | ------------------- |
|   30 audio samples | Basic demo          |
|  100 audio samples | Good thesis         |
| 300+ audio samples | Stronger experiment |

Suggested topics:

- Object-oriented programming
- Polymorphism
- Dependency injection
- Spring Boot
- JPA
- Transaction isolation
- REST API
- Database indexing
- Thread pool
- Synchronized keyword
- ExecutorService
- Docker
- CI/CD

---

## 7.6 Evaluation Metrics

| Metric                     | Meaning                                                            |
| -------------------------- | ------------------------------------------------------------------ |
| WER                        | Word Error Rate                                                    |
| CER                        | Character Error Rate                                               |
| Technical keyword accuracy | Accuracy on terms such as "Spring Boot", "JPA", "ACID", "REST API" |
| Latency                    | Time from speech upload to transcript                              |
| Memory usage               | RAM/VRAM required for inference                                    |

Example domain-specific improvement target:

| Spoken Term          | Possible Wrong Output | Desired Output       |
| -------------------- | --------------------- | -------------------- |
| Spring Boot          | spring boat           | Spring Boot          |
| JPA                  | jay pee ay            | JPA                  |
| ACID                 | a said                | ACID                 |
| REST API             | rest a p i            | REST API             |
| Dependency injection | dependency in Jackson | dependency injection |

---

# 8. BRAIN: Lightweight LLM Interview Logic

## 8.1 Purpose

The BRAIN component evaluates candidate answers and controls interview intelligence.

It should not be used as a random chatbot. Instead, it should act as a structured technical evaluator.

---

## 8.2 Recommended Model

Use a lightweight instruction model such as:

```text
Qwen2.5 3B Instruct
Qwen2.5 7B Instruct Q4
Llama 3.x 8B Instruct Q4
```

Recommended starting point:

```text
Qwen2.5 3B or 7B Instruct
```

Why:

- Lightweight enough for local or low-cost deployment.
- Good at structured output.
- Suitable for rubric-based technical answer evaluation.
- Easier to run with Ollama for prototype development.

---

## 8.3 Rubric-Guided Evaluation

Instead of asking the LLM vague questions, the system provides a rubric for each interview question.

Example question:

```text
What is dependency injection?
```

Example rubric:

```json
[
    "Dependencies are provided from outside the class",
    "It reduces tight coupling",
    "It improves testability",
    "In Spring, the IoC container manages objects and dependencies"
]
```

Expected model output:

```json
{
    "score": 7,
    "correctness": 8,
    "completeness": 6,
    "clarity": 7,
    "missing_points": [
        "did not mention loose coupling",
        "did not mention easier testing"
    ],
    "feedback": "The answer is mostly correct but incomplete.",
    "follow_up_question": "Can you explain how dependency injection improves unit testing?"
}
```

---

## 8.4 Optional LoRA Fine-Tuning

LLM fine-tuning is optional and should only be attempted if the group can create enough labeled evaluation examples.

Recommended order:

```text
Phase 1: Prompt + rubric
Phase 2: Build labeled answer dataset
Phase 3: LoRA fine-tune only if needed
```

Minimum labeled examples:

|  Dataset Size | Value                                 |
| ------------: | ------------------------------------- |
|   50 examples | Demo only                             |
|  200 examples | Good thesis                           |
| 500+ examples | Fine-tuning starts to make more sense |

Example training item:

```json
{
    "question": "What is dependency injection?",
    "rubric": [
        "dependency is provided from outside",
        "reduces tight coupling",
        "improves testability",
        "Spring IoC container manages beans"
    ],
    "candidate_answer": "Dependency injection means Spring creates objects for us.",
    "score": 5,
    "feedback": "The answer is partially correct but incomplete.",
    "follow_up_question": "Can you explain how dependency injection reduces tight coupling?"
}
```

---

## 8.5 Trade-offs

| Approach             | Pros                           | Cons                                       | Recommendation                            |
| -------------------- | ------------------------------ | ------------------------------------------ | ----------------------------------------- |
| Prompt-only LLM      | Fast to build                  | Less consistent                            | Good first version                        |
| Rubric-guided LLM    | More controllable, explainable | Requires rubric design                     | Recommended                               |
| LoRA fine-tuning     | Better domain consistency      | Requires labeled dataset and training time | Optional thesis enhancement               |
| Commercial API model | High quality                   | Less original, paid, closed                | Use only as baseline comparison if needed |

---

# 9. MOUTH: Text-to-Speech

## 9.1 Purpose

The MOUTH component converts the AI interviewer text into speech.

The AI interviewer should speak questions, transitions, and follow-up prompts.

---

## 9.2 Recommended Model

Use:

```text
Kokoro-82M
```

Why:

- Lightweight open-weight TTS model.
- Suitable for low-latency speech generation.
- Easier to run locally compared with heavier models like Bark or XTTS.
- Good enough for a standard AI interviewer persona.

---

## 9.3 TTS Strategy

The system should generate speech for:

- Interview opening
- Technical questions
- Follow-up questions
- Section transitions
- Closing message

For predictable interview questions, audio can be pre-generated and cached.

For dynamic follow-up questions, audio is generated on demand.

Recommended approach:

```text
Static question → pre-generate and cache audio
Dynamic follow-up → generate TTS when needed
```

This reduces latency during the interview.

---

## 9.4 Why Not Bark or XTTS First?

| Model      | Pros                  | Cons                        |
| ---------- | --------------------- | --------------------------- |
| Bark       | Natural voice         | Heavy and high latency      |
| XTTS v2    | Voice cloning support | Heavier and more complex    |
| Kokoro-82M | Lightweight and fast  | Less advanced voice cloning |

For this graduation project, Kokoro is the best practical choice.

---

## 9.5 Fine-Tuning TTS

TTS fine-tuning is not recommended for the first version.

Reason:

- The thesis is about interactive AI interviewing, not custom voice generation.
- TTS fine-tuning requires clean voice data.
- It is harder to evaluate objectively.
- It adds technical risk without improving interview intelligence much.

Use Kokoro built-in voices first.

---

# 10. FACE: Dynamic Animated Avatar

## 10.1 Purpose

The FACE component provides a visual AI interviewer.

The avatar does not need to understand the candidate or react emotionally. It only needs to appear dynamic and synchronized with the AI's speech.

In this project, the avatar is:

```text
A speech-synchronized animated interviewer character.
```

It is not:

```text
A fully intelligent emotional avatar.
```

---

## 10.2 Avatar States

| State     | When                  | Animation                             |
| --------- | --------------------- | ------------------------------------- |
| IDLE      | No AI speech          | Breathing, blinking, small movement   |
| SPEAKING  | TTS audio is playing  | Mouth moves, head/body slightly moves |
| LISTENING | Candidate is speaking | Attentive pose or idle listening pose |
| THINKING  | ASR/LLM is processing | Thinking/loading animation            |

---

## 10.3 Recommended Implementation

Use a 2D layered avatar with PNG/SVG assets.

Suggested assets:

```text
body.svg
head.svg
eyes_open.svg
eyes_closed.svg
mouth_closed.svg
mouth_small.svg
mouth_medium.svg
mouth_open.svg
```

The browser analyzes the TTS audio volume and maps it to mouth states:

```text
volume < 20    → mouth closed
volume < 60    → mouth small
volume < 120   → mouth medium
volume >= 120  → mouth open
```

---

## 10.4 Technical Flow

```text
Kokoro-82M TTS audio output
    ↓
Browser audio player
    ↓
Web Audio API AnalyserNode
    ↓
Calculate audio volume
    ↓
Control avatar mouth / body animation
```

When AI audio starts:

```text
avatarState = SPEAKING
start mouth animation
```

When AI audio ends:

```text
avatarState = LISTENING
enable candidate microphone
```

---

## 10.5 Alternative Avatar Approaches

| Approach                  | Pros                           | Cons                                      | Recommendation                         |
| ------------------------- | ------------------------------ | ----------------------------------------- | -------------------------------------- |
| 2D SVG/PNG layers         | Simple, reliable, controllable | Less professional than advanced animation | Recommended                            |
| Lottie                    | More polished, lightweight     | Harder precise mouth control              | Good if design team can prepare assets |
| Rive                      | Good state-machine animation   | Learning curve                            | Good optional choice                   |
| 3D avatar                 | Visually impressive            | Too much complexity                       | Avoid for thesis MVP                   |
| AI-generated video avatar | Realistic                      | Expensive and not necessary               | Avoid                                  |

---

# 11. Interview Flow and State Machine

## 11.1 Purpose

The interview state machine controls the timing of AI speech, candidate speech, transcription, evaluation, and next question transitions.

This is one of the most important engineering parts of the AI interview room.

---

## 11.2 Main States

```text
SESSION_CREATED
AI_SPEAKING
WAITING_FOR_CANDIDATE
CANDIDATE_SPEAKING
TRANSCRIBING
EVALUATING
AI_FOLLOW_UP
NEXT_QUESTION
FINISHED
```

---

## 11.3 Example Flow

```text
1. Server selects question Q1.
2. TTS generates or loads audio for Q1.
3. Frontend plays AI audio.
4. Avatar enters SPEAKING state.
5. Question script is displayed on screen.
6. When audio ends, microphone is enabled.
7. Candidate answers by voice.
8. Browser records audio chunks.
9. Backend sends audio to ASR service.
10. ASR returns transcript.
11. LLM evaluates transcript using rubric.
12. System stores transcript, score, and feedback.
13. System either asks a follow-up or moves to the next question.
```

---

## 11.4 Why Server-Controlled Flow?

The server should control the interview progress to prevent candidates from skipping questions, replaying hidden sections, or manipulating the flow from the browser.

The frontend displays the current state, but the backend decides:

- Which question comes next
- Whether the microphone should be enabled
- Whether the candidate can submit
- Whether a follow-up is needed
- Whether the interview is finished

---

# 12. Assessment Modes

Although Module C is mainly speech-based, the interview room may contain three assessment modes:

## 12.1 Part 1: Spoken Technical Interview

The AI interviewer asks technical questions using TTS.

The candidate answers by voice.

The system transcribes and evaluates the answer.

This is the core AI interaction.

---

## 12.2 Part 2: Multiple-Choice Questions

The AI voice and microphone are disabled.

The candidate answers using buttons.

This part tests quick conceptual knowledge.

---

## 12.3 Part 3: Written Response

The microphone is disabled.

The candidate writes a short conceptual answer.

The system may evaluate the written answer using the same rubric-guided LLM evaluator.

---

# 13. Proposed System Architecture

```text
Frontend Web App
    ├── Interview Room UI
    ├── Audio Recorder
    ├── Audio Player
    ├── Avatar Renderer
    ├── Script Display
    └── Integrity Event Collector

Backend API
    ├── Authentication / Session Management
    ├── Resume Screening Service
    ├── Interview Session Controller
    ├── Question & Rubric Service
    ├── Security Event Logger
    └── Result Dashboard API

AI Services
    ├── ASR Service: faster-whisper / fine-tuned Whisper
    ├── LLM Service: Qwen/Llama + rubric evaluator
    ├── TTS Service: Kokoro-82M
    └── Optional Model Fine-Tuning Pipeline

Database
    ├── Candidates
    ├── Resumes
    ├── Job Descriptions
    ├── Interview Sessions
    ├── Questions
    ├── Rubrics
    ├── Transcripts
    ├── Scores
    └── Integrity Events
```

---

# 14. Suggested Technology Stack

## 14.1 Frontend

- React or Next.js
- TypeScript
- Web Audio API
- MediaRecorder API
- WebSocket
- SVG/PNG layered avatar, Lottie, or Rive

## 14.2 Backend

- Golang
- REST API
- WebSocket
- PostgreSQL
- Redis optional for session state

## 14.3 AI Services

- Python FastAPI microservice
- faster-whisper for ASR inference
- Hugging Face Transformers for Whisper fine-tuning
- Qwen2.5 or Llama lightweight model for answer evaluation
- Ollama for local LLM prototype
- PEFT/LoRA for optional LLM fine-tuning
- Kokoro-82M for TTS

Recommended architecture for the group:

```text
Spring Boot main backend
        +
Python AI microservice
```

This separates business logic from AI inference and makes the system easier to maintain.

---

# 15. Research and Evaluation Plan

## 15.1 Experiment 1: Speech Recognition

Compare:

```text
Original Whisper small
vs
Fine-tuned Whisper small
```

Metrics:

- WER
- CER
- Technical keyword accuracy
- Transcription latency
- Memory usage

---

## 15.2 Experiment 2: Answer Evaluation

Compare:

```text
Prompt-only LLM
vs
Rubric-guided LLM
vs
Optional LoRA-tuned evaluator
```

Metrics:

- Agreement with human-labeled scores
- Feedback usefulness
- JSON output validity
- Latency

---

## 15.3 Experiment 3: End-to-End Interaction

Measure:

- Time from AI question generation to speech playback
- Time from candidate answer submission to transcript
- Time from transcript to evaluation result
- Total candidate waiting time
- Failure rate of the interactive loop

---

# 16. Scope Definition

## 16.1 In Scope

- Resume parsing and semantic screening MVP
- Browser-only integrity event tracking
- AI technical interview room
- AI speech output using Kokoro-82M
- Candidate speech capture
- Speech-to-text using faster-whisper
- Optional Whisper small fine-tuning
- Rubric-guided answer evaluation using lightweight LLM
- Optional LoRA fine-tuning for evaluator
- Dynamic 2D avatar synchronized with TTS audio
- Interview session state machine
- Recruiter dashboard showing resume match, transcript, score, and integrity events

---

## 16.2 Out of Scope

- Commercial deployment
- Full ATS business system
- Payment/subscription features
- Webcam proctoring
- Real 3D avatar
- Fully autonomous emotional avatar
- Training ASR, TTS, or LLM from scratch
- Full custom TTS voice cloning
- Large-scale production infrastructure
- Lockdown browser

---

# 17. Expected Contributions

The expected contributions of the project are:

1. A unified prototype platform for technical candidate screening and AI interview assessment.
2. A semantic resume screening module using local-first processing.
3. A browser-only privacy-preserving integrity monitoring module.
4. A lightweight interactive AI interview room using independent AI components.
5. A domain-adaptive ASR experiment for technical interview vocabulary.
6. A rubric-guided LLM evaluation pipeline for technical answers.
7. A dynamic speech-synchronized avatar system using TTS audio analysis.
8. An evaluation of model accuracy, latency, and system usability for a graduation thesis context.

---

# 18. Cost and Resource Considerations

Since this project is for graduation and not commercialization, the system should prioritize local or low-cost models.

Recommended cost-saving strategies:

- Use open-source models instead of paid commercial voice agents.
- Use faster-whisper small int8 instead of large models.
- Use Kokoro-82M instead of heavy TTS models.
- Use Qwen/Llama quantized models for local LLM inference.
- Cache TTS audio for fixed questions.
- Fine-tune only the most valuable part first: Whisper small for technical ASR.

Expected thesis development cost:

| Item                  |                                           Estimated Cost |
| --------------------- | -------------------------------------------------------: |
| Frontend development  |                                                       $0 |
| Backend development   |                                                       $0 |
| Local model inference |                              $0 if hardware is available |
| Hosting for demo      |                                             $0–$20/month |
| Optional GPU training | $0–$50 depending on available university/cloud resources |
| Commercial APIs       |                Avoid or use only for baseline comparison |

---

# 19. Risk Management

| Risk                                   | Impact                   | Mitigation                                                            |
| -------------------------------------- | ------------------------ | --------------------------------------------------------------------- |
| Local ASR latency is too high          | Candidate waits too long | Use smaller Whisper model and int8 inference                          |
| ASR does not recognize technical terms | Bad evaluation           | Fine-tune Whisper small on technical speech                           |
| LLM gives inconsistent scores          | Unreliable assessment    | Use rubric-guided structured JSON output                              |
| TTS latency is too high                | Poor interaction         | Cache fixed question audio and use Kokoro-82M                         |
| Avatar takes too much time             | Delays thesis            | Use simple 2D layered avatar                                          |
| Dataset collection is too small        | Weak fine-tuning result  | Use fine-tuning as optional experiment and keep rubric-based baseline |
| Browser security is bypassable         | Integrity weakness       | Present it as risk-signal monitoring, not perfect prevention          |

---

# 20. Final Recommended Thesis Focus

The final thesis should focus on:

```text
Interactive AI Technical Interview Room
```

The ATS and browser integrity modules support the full hiring workflow, but the main technical depth is:

```text
Speech-based AI interview loop
+ lightweight STT
+ rubric-guided LLM evaluation
+ lightweight TTS
+ audio-driven avatar animation
+ server-controlled interview state machine
```

Recommended final thesis title:

**Design and Implementation of a Lightweight Interactive AI Technical Interview Platform Using Domain-Adaptive Speech Recognition and Rubric-Guided LLM Evaluation**

---

# 21. References / Technical Sources

- SYSTRAN faster-whisper GitHub Repository: https://github.com/SYSTRAN/faster-whisper
- OpenAI Whisper GitHub Repository: https://github.com/openai/whisper
- Hugging Face Whisper Fine-Tuning Guide: https://huggingface.co/blog/fine-tune-whisper
- Hugging Face PEFT Documentation: https://huggingface.co/docs/peft
- Hugging Face Kokoro-82M Model Card: https://huggingface.co/hexgrad/Kokoro-82M
- Kokoro-82M ONNX Model: https://huggingface.co/onnx-community/Kokoro-82M-v1.0-ONNX
- Ollama Qwen2.5 Model Page: https://ollama.com/library/qwen2.5
- MDN Web Audio API AnalyserNode: https://developer.mozilla.org/en-US/docs/Web/API/AnalyserNode
- MDN MediaRecorder API: https://developer.mozilla.org/en-US/docs/Web/API/MediaRecorder
- MDN Page Visibility API: https://developer.mozilla.org/en-US/docs/Web/API/Page_Visibility_API

---

> Next.js/React (Frontend) + Golang (Main Backend) + Python (AI Inference Service)
