# Module 03: Web Audio API & Amplitude Tracking

Welcome back, class. Today we analyze **Web Audio API & Amplitude Tracking (CS-526)**.

Generating voice audio is only half the battle. To create an immersive AI interview experience, the visual representation of the interviewer must move its mouth in sync with the audio. Traditional static video players or pre-rendered lip-sync files lack the flexibility to handle dynamic follow-up questions. Instead, we must read the sound volume in real-time in the browser and translate those values into visual animations.

Today we study the browser's native **Web Audio API**. We will analyze context routing, configure an **`AnalyserNode`**, learn the math behind **Root-Mean-Square (RMS) amplitude**, and write a high-performance sampling loop synced to the screen's refresh rate.

---

## 1. Academic Lecture: Decibel Calculations and Audio Node Routing

### 1. The Web Audio API Graph Architecture
The Web Audio API functions as a modular routing graph. Audio operations are handled inside an **`AudioContext`**, where inputs, processors, and destinations are represented as connected nodes:
*   **MediaElementAudioSourceNode**: Converts a standard HTML5 `<audio>` element player into a node source.
*   **AnalyserNode**: A non-audio-modifying processor node. It captures live audio signal data (frequency distributions and time-domain amplitudes) and exposes it via buffer arrays.
*   **AudioDestinationNode**: The system output (sound card/speakers).

```text
[Audio Element] ──> [Media Source Node] ──> [Analyser Node] ──> [Destination (Speakers)]
                                                  │
                                                  └── (getByteTimeDomainData)
                                                  │
                                                  ▼
                                       [RMS Amplitude Calculation]
```

### 2. Time-Domain Sampling vs. Frequency Analysis
The `AnalyserNode` lets us sample data in two formats:
*   **Frequency-Domain Data**: Yields signal intensity mapped to pitch frequencies (bass, mid, treble). Useful for music visualizers.
*   **Time-Domain Data**: Yields raw signal waveform values. This represents the speaker cone position at a microsecond interval. This time-domain signal is what we analyze to determine speech volume.

### 3. Root-Mean-Square (RMS) Math
Time-domain samples return values ranging from `-1.0` to `1.0` (or `0` to `255` in byte arrays, where `128` represents absolute silence). To calculate the volume level over a window of time, we cannot simply calculate the average value, since positive and negative values would cancel each other out.
Instead, we calculate the **Root-Mean-Square (RMS)**:

$$\text{RMS} = \sqrt{\frac{1}{N} \sum_{i=1}^{N} x_i^2}$$

Where $x_i$ represents the deviation of each sample from the center value, and $N$ represents the total number of samples (defined by the analyser's `fftSize`).

```mermaid
sequenceDiagram
    participant UI as Browser DOM (Audio Play)
    participant Act as AudioContext
    participant Node as AnalyserNode
    participant Loop as Animation Frame (60FPS)

    UI->>Act: User Gesture: Play Audio Stream
    Act->>Node: Route signal through analyser
    loop Every Frame
        Loop->>Node: getByteTimeDomainData(buffer)
        Node->>Loop: Return sample array (values 0-255)
        Loop->>Loop: Calculate RMS deviation from 128
        Loop->>UI: Update visual mouth scaling scale(RMS)
    end
```

---

## 2. Theory vs. Production Trade-offs

When reading volume data on the frontend, evaluate these polling mechanisms:

| Polling Mechanism | Pros | Cons | Recommendation |
| :--- | :--- | :--- | :--- |
| **`setInterval` Polling** | Simple to write; decoupled from rendering threads. | Out-of-sync with screen refresh rates; generates jerky visual stuttering. | Avoid in production. |
| **`requestAnimationFrame`** | Syncs directly with browser refresh (60Hz+); buttery smooth updates. | Pauses when the browser tab is minimized or out of focus. | **Recommended for Visual Lip Sync**. |
| **ScriptProcessorNode (Legacy)**| Direct access to raw audio buffer streams. | Deprecated; runs on the main browser thread, causing audio drops. | Avoid. |
| **AudioWorkletProcessor** | Processes audio on a separate background thread; high performance. | Complex to load; requires separate JavaScript file modules. | Use for complex real-time voice filters. |

---

## 3. How to Use: Resilient Web Audio Analyzer

Let us write a compile-grade HTML5 and JavaScript module that configures the Web Audio API routing graph, handles browser autoplay blocking policies, and computes the RMS volume at 60 FPS.

### A. The Brittle Polling Pattern (Anti-Pattern)

Avoid utilizing `setInterval` loops or raw averages without cleaning center deviations. This will cause choppy mouth movement and errors on player reloads:

```javascript
// DANGER: Using setInterval blocks main threads and does not align
// with the browser's layout engine. Furthermore, averaging raw values
// directly around 128 leads to incorrect volume calculation.
function pollVolumeNaive(audioElement, analyser) {
    const dataArray = new Uint8Array(analyser.frequencyBinCount);
    setInterval(() => {
        analyser.getByteTimeDomainData(dataArray);
        // Naive average: does not square values, causing cancellation
        let sum = 0;
        for (let i = 0; i < dataArray.length; i++) {
            sum += dataArray[i];
        }
        const average = sum / dataArray.length;
        console.log("Naive Volume: ", average); // Stays close to 128 (silence)
    }, 100);
}
```

### B. The Hardened Browser Audio Analyzer (Production Pattern)

Here is the hardened pattern. We write a class that handles `AudioContext` state transitions, hooks listeners to HTML5 Audio elements, and samples time-domain parameters securely.

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Production Web Audio Analyzer</title>
</head>
<body>
    <audio id="interviewer-audio" src="speech.wav" crossorigin="anonymous"></audio>
    <button id="start-btn">Start Interview Node</button>

    <script>
        class BrowserAudioAnalyzer {
            constructor(audioElementId) {
                this.audio = document.getElementById(audioElementId);
                this.audioContext = null;
                this.analyser = null;
                this.dataArray = null;
                this.animationFrameId = null;
                this.onVolumeCallback = null;
            }

            async initializeContext() {
                // Autoplay Policy: Browser contexts must start after a user gesture
                if (!this.audioContext) {
                    this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
                    
                    // Create routing nodes
                    const source = this.audioContext.createMediaElementSource(this.audio);
                    this.analyser = this.audioContext.createAnalyser();
                    
                    // fftSize determines the sample window (must be power of 2)
                    this.analyser.fftSize = 512; 
                    const bufferLength = this.analyser.frequencyBinCount;
                    this.dataArray = new Uint8Array(bufferLength);
                    
                    // Node graph connection: Source -> Analyser -> Output
                    source.connect(this.analyser);
                    this.analyser.connect(this.audioContext.destination);
                }
                
                // Resume context if suspended by browser security policy
                if (this.audioContext.state === "suspended") {
                    await this.audioContext.resume();
                }
            }

            startAnalysis(volumeCallback) {
                this.onVolumeCallback = volumeCallback;
                
                // Prevent duplicate running frames
                if (this.animationFrameId) {
                    cancelAnimationFrame(this.animationFrameId);
                }
                
                const sampleLoop = () => {
                    if (this.analyser && !this.audio.paused) {
                        this.analyser.getByteTimeDomainData(this.dataArray);
                        
                        // Calculate RMS Volume
                        let totalSquares = 0;
                        const len = this.dataArray.length;
                        
                        for (let i = 0; i < len; i++) {
                            // Convert byte values (0-255) to normal range centered at 0
                            const normalizedSample = (this.dataArray[i] - 128) / 128;
                            totalSquares += normalizedSample * normalizedSample;
                        }
                        
                        const rms = Math.sqrt(totalSquares / len);
                        
                        // Expose RMS value to animation callback
                        if (this.onVolumeCallback) {
                            this.onVolumeCallback(rms);
                        }
                    } else {
                        // Return silence when audio is stopped
                        if (this.onVolumeCallback) this.onVolumeCallback(0);
                    }
                    // Loop at 60 FPS
                    this.animationFrameId = requestAnimationFrame(sampleLoop);
                };
                
                this.animationFrameId = requestAnimationFrame(sampleLoop);
            }

            stopAnalysis() {
                if (this.animationFrameId) {
                    cancelAnimationFrame(this.animationFrameId);
                    this.animationFrameId = null;
                }
            }
        }

        // Execution Binding
        const analyzer = new BrowserAudioAnalyzer('interviewer-audio');
        const startButton = document.getElementById('start-btn');

        startButton.addEventListener('click', async () => {
            try {
                await analyzer.initializeContext();
                analyzer.startAnalysis((volume) => {
                    // Normalize volume metric to a percentage (0 to 100)
                    const normalizedVolume = Math.min(Math.round(volume * 200), 100);
                    console.log(`Live Volume: ${normalizedVolume}%`);
                });
                analyzer.audio.play();
            } catch (err) {
                console.error("Context initialization blocked: ", err);
            }
        });
    </script>
</body>
</html>
```

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Autoplay & Context Block Errors
Executing `new AudioContext()` immediately on page load, generating console warnings: `"The AudioContext was not allowed to start. It must be resumed after a user gesture on the page."`
*   **Why it fails**: Modern browser security policies prevent pages from playing sound or starting audio operations automatically without an explicit user click.
*   **Mitigation**: Always wrap `AudioContext` initialization or `.resume()` calls inside a button click event listener.

### Pitfall 2: Cross-Origin Resource Sharing (CORS) Blocks
Loading cached audio files from a different server URL (e.g. `http://api.myserver.com/cache/123.wav`) onto an `<audio>` tag and routing it to the analyzer.
*   **Why it fails**: When routed through an `AnalyserNode`, the browser treats audio data as raw binary information. If CORS headers are not set on the audio server, the browser blocks access to the data, and `AnalyserNode` returns silence (all 128s).
*   **Mitigation**: Set `crossorigin="anonymous"` on the HTML audio element and configure the backend server to return access headers (`Access-Control-Allow-Origin: *`).

---

## 5. Socratic Review Questions

### Question 1
Why does the `getByteTimeDomainData` method return values centered around `128` rather than `0`?

#### Answer
The method uses an 8-bit unsigned byte representation (`Uint8Array`) to store sample amplitudes, where values range from `0` to `255`. Since audio waveforms are alternating current signals that swing positive and negative, the value `128` represents the midpoint (ground / silence). To convert this to a normal amplitude scale, we must subtract `128` and divide by `128`, yielding values between `-1.0` and `1.0`.

### Question 2
What is the effect of increasing the `fftSize` parameter of the `AnalyserNode` (e.g., from `256` to `2048`) on the visual lip-sync animation?

#### Answer
The `fftSize` determines the number of samples analyzed in a single window. Increasing `fftSize` provides more samples, which increases frequency detail but averages volume changes over a longer duration. This introduces a slight visual lag in lip-sync animations. Decreasing `fftSize` (e.g., `256` or `512`) reduces window size, providing more immediate volume updates that match speech dynamics better.

---

## 6. Hands-on Challenge: JavaScript Amplitude Mapper

### The Challenge
In this challenge, you will write a JavaScript processing function to convert time-domain sample arrays into normalized volume values.
Your task:
1. Complete the implementation of the function `calculateRmsFromBuffer`.
2. Iterate through the array of byte samples (0-255).
3. Normalize each sample to a range of `-1.0` to `1.0`.
4. Calculate the Root-Mean-Square (RMS) value.
5. Scale and clamp the final RMS to a percentage integer (0 to 100).

Complete the implementation below:

```javascript
/**
 * Calculates the RMS volume percentage from an array of 8-bit time-domain samples.
 * @param {Uint8Array} sampleBuffer - Array of samples (0-255).
 * @returns {number} - Volume percentage (0-100).
 */
function calculateRmsFromBuffer(sampleBuffer) {
    const len = sampleBuffer.length;
    if (len === 0) return 0;

    let sumSquares = 0;

    // TODO: Implement the RMS logic:
    // 1. Loop through sampleBuffer.
    // 2. Convert each sample value by subtracting 128 and dividing by 128 to get a float.
    // 3. Square the float and add it to sumSquares.
    // 4. Calculate the mean square (sumSquares / len).
    // 5. Take the square root to get the RMS value.
    // 6. Scale the RMS by multiplying by 200 (to boost smaller voice values).
    // 7. Clamp the result between 0 and 100, and return as a rounded integer.
    
    return 0;
}

// Verification block (simulating test assertions)
const silenceBuffer = new Uint8Array([128, 128, 128, 128]);
console.assert(calculateRmsFromBuffer(silenceBuffer) === 0, "Silence should return 0%");

const toneBuffer = new Uint8Array([255, 128, 0, 128]);
console.log("Calculated RMS for full range tone:", calculateRmsFromBuffer(toneBuffer));
```

Write the JavaScript processing logic. Save the completed file and verify that the math assertions function correctly under `modules/03-web-audio-analysernode.md`.
