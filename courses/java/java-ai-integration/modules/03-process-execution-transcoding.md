# Module 03: Local Process Execution & Audio Transcoding

Welcome back class. Today we analyze **Local Process Execution & Audio Transcoding (CS-528)**.

While integrating models via network HTTP endpoints is clean, production systems engineering often requires executing binary command-line tools directly on the host machine. For example, before sending a candidate's recorded interview audio to the Whisper ASR engine, we must transcode the file into the exact format Whisper expects (16000Hz, 16-bit, mono PCM WAV). Spawning operating system processes in Java, however, introduces severe vulnerabilities: improper stream management causes processes to hang indefinitely, and unvalidated arguments can lead to remote command injections.

Today we study Java's **`ProcessBuilder` API**, analyze **subprocess stream buffer deadlocks**, identify **shell command injection vectors**, and write a hardened, non-blocking transcoding service in **Java 21**.

---

## 1. Academic Lecture: Spawning OS Subprocesses Safely

### 1. ProcessBuilder vs. Runtime.getRuntime().exec()
Java provides two ways to spawn operating system processes:
*   **`Runtime.exec(String command)`**: Parses the command as a single string, splitting it by whitespace. This is legacy, error-prone, and highly vulnerable to command injection.
*   **`ProcessBuilder(List<String> command)`**: Accepts arguments as discrete elements of a list. The JVM executes the binary directly, passing the list parameters directly to the operating system's process allocation table (`execve` on POSIX, `CreateProcess` on Windows). Because no shell is spawned to evaluate parameters, metadata characters (like `;`, `&`, or `|`) are treated as plain arguments, preventing injection attacks.

### 2. The Stream Buffer Deadlock Bottleneck
When the operating system spawns a subprocess, it creates pipe buffers for the child process's standard output (`stdout`) and standard error (`stderr`) streams.
*   **The Buffer Overflow**: These OS pipe buffers have tiny size limits (usually 64 Kilobytes). If the subprocess outputs data (such as FFmpeg logging frame conversion details) and the parent Java process does not actively read the pipe, the buffer fills up. Once full, the child process blocks, waiting for space to clear. The Java application blocks waiting for `process.waitFor()`, resulting in a permanent **deadlock**.
*   **The Virtual Thread Solution**: To prevent deadlocks, we must drain both stdout and stderr concurrently. Spawning two lightweight virtual threads to continuously read the streams resolves this buffer bottleneck with negligible memory footprint.

```text
[Java Application] ──(ProcessBuilder.start)──> [OS Subprocess (FFmpeg)]
        │                                                │
        ├─ Virtual Thread A: Read stdout stream <────────┤ (stdout pipe: max 64KB)
        ├─ Virtual Thread B: Read stderr stream <────────┤ (stderr pipe: max 64KB)
        │                                                │
        └─ process.waitFor(30s) ─────────────────────────┼─ Execution finishes
                                                         ▼
                                                Return Exit Code (0 = success)
```

---

## 2. Theory vs. Production Trade-offs

When choosing an integration layer for CLI binaries, compare process calls against native wrappers:

| Integration Strategy | Execution Speed | Memory Overhead | Safety Boundary | Operational Complexity |
| :--- | :--- | :--- | :--- | :--- |
| **Native JNI / JNA** | Very Fast (In-memory calls) | Very High (Leaks crash JVM) | Poor (Native crash kills JVM process) | High (Requires building OS-specific .dll/.so) |
| **OS Subprocess (ProcessBuilder)**| Moderate (Fork execution cost) | Low (Isolates memory space) | Excellent (Process crash does not crash JVM) | Low (Uses system-installed binaries) |
| **Docker Sidecar Agents** | Slow (Network REST overhead) | High (Separate container) | Outstanding (Full sandbox isolation) | High (Requires orchestration: K8s) |

---

## 3. How to Use: Hardened Subprocess Transcoder

Let us write a compile-grade Java 21 implementation of an audio transcoding service that spawns `ffmpeg` safely, drains buffers using virtual threads, and enforces timeouts.

### A. The Vulnerable Command Injection & Deadlock Pattern (Anti-Pattern)

Avoid utilizing string concatenation to compile shell commands, and do not block waiting for execution without reading stream buffers:

```java
package com.security.api.subprocess;

import java.io.File;

public class NaiveProcessRunner {
    // DANGER: Passing a concatenated string to Runtime.exec() allows command injection.
    // If incomingPath is "/opt/audio.mp3; rm -rf /", the shell executes the deletion.
    // Additionally, neglecting to read stdout/stderr streams leads to buffer locks on large files.
    public void transcodeUnsafe(String incomingPath, String outputPath) throws Exception {
        String command = "ffmpeg -i " + incomingPath + " -ar 16000 -ac 1 " + outputPath;
        Process process = Runtime.getRuntime().exec(command); // VULNERABLE to injection
        process.waitFor(); // VULNERABLE to stream deadlocks
    }
}
```

### B. The Hardened Transcoding Service (Production Pattern)

Here is the hardened pattern. We write an audio service class that parses parameters into discrete array lists, spawns virtual threads to drain stdout and stderr dynamically, and enforces a strict processing timeout boundary.

```java
package com.security.api.subprocess;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.util.List;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

public class HardenedTranscodingService {

    private final Path ffmpegPath = Path.of("ffmpeg"); // Assume configured in OS PATH

    public boolean transcodeToWhisperWav(Path sourceFile, Path destinationWav) throws IOException, InterruptedException {
        // 1. Enforce strict input validations
        if (!sourceFile.toFile().exists() || !sourceFile.toFile().isFile()) {
            throw new FileNotFoundException("Source audio file not found: " + sourceFile);
        }

        // 2. Safe List-Based Argument Definition (Blocks Command Injection)
        List<String> command = List.of(
            ffmpegPath.toString(),
            "-y",                        // Overwrite output files without prompting
            "-i", sourceFile.toString(), // Input file path (treated as literal string)
            "-ar", "16000",              // Resample rate to 16kHz
            "-ac", "1",                  // Downmix to mono channel
            "-c:a", "pcm_s16le",         // Enforce 16-bit PCM codec
            destinationWav.toString()    // Output file path (treated as literal string)
        );

        // 3. Initialize ProcessBuilder
        ProcessBuilder builder = new ProcessBuilder(command);
        Process process = builder.start();

        // 4. Spawn Virtual Threads to Drain Stream Buffers (Prevents Deadlocks)
        try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
            executor.submit(() -> drainStream(process.getInputStream(), "STDOUT"));
            executor.submit(() -> drainStream(process.getErrorStream(), "STDERR"));
            
            // Allow executor to close and manage the thread lifecycle
        }

        // 5. Enforce strict processing timeout limits (e.g. max 45 seconds execution)
        boolean finished = process.waitFor(45, TimeUnit.SECONDS);
        
        if (!finished) {
            // Forcefully terminate process if timeout is exceeded
            process.destroyForcibly();
            throw new InterruptedException("Transcoding process exceeded execution limit (45s) and was killed.");
        }

        // 6. Check Exit Code (0 represents success)
        int exitCode = process.exitValue();
        return exitCode == 0;
    }

    private void drainStream(InputStream stream, String streamType) {
        // Read stream contents buffer-by-buffer and discard or write to log
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(stream, StandardCharsets.UTF_8))) {
            String line;
            while ((line = reader.readLine()) != null) {
                // In production, log at debug level. Do not print credentials to console.
                // System.out.println("[" + streamType + "] " + line);
            }
        } catch (IOException e) {
            // Handle socket closure exceptions gracefully when process terminates
        }
    }
}
```

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Relying on the System Shell to Locate Binaries
Passing raw command lines starting with `"sh -c ..."` or `"cmd.exe /c ..."`.
*   **Why it fails**: Wrapping arguments inside a shell invokes the shell interpreter. This re-enables metadata characters evaluation, restoring the command injection vulnerability surface.
*   **Mitigation**: Avoid spawning shell wrappers. Pass arguments directly as a list, letting the OS execute the target binary directly.

### Pitfall 2: Memory leaks on zombie subprocesses
Failing to destroy subprocesses when the parent Java application thread encounters an exception or timeout.
*   **Why it fails**: If the Java thread exits due to a timeout but the process is not killed, the subprocess continues to run in the background as a "zombie" process, consuming CPU and RAM resources.
*   **Mitigation**: In the event of thread timeouts or cancellations, always invoke `process.destroyForcibly()` to release OS handles.

---

## 5. Socratic Review Questions

### Question 1
Why does passing arguments as a `List<String>` to `ProcessBuilder` mitigate command injection vulnerabilities, whereas passing a concatenated string does not?

#### Answer
A concatenated string is parsed by a shell interpreter, which evaluates symbols like `;` or `|` as instructions. `ProcessBuilder` bypasses the shell. It uses system calls (like `execve`) where the binary is executed directly, and the argument list is mapped directly to the process's string array argument index (`argv`). The OS treats the entire path string (even if it contains `; rm -rf /`) as a single literal filename argument, preventing execution.

### Question 2
What is a zombie process, and how does checking the `process.exitValue()` differ from calling `process.waitFor()`?

#### Answer
A zombie process is a terminated child process whose exit status has not yet been read by the parent process. Calling `process.waitFor()` blocks the calling thread until the child process terminates, then returns the exit code. Checking `process.exitValue()` is non-blocking. If the child process is still running, `exitValue()` throws an `IllegalThreadStateException`. We check it only after ensuring the process has finished.

---

## 6. Hands-on Challenge: OS Command Injection Guard & Process Runner

### The Challenge
In this challenge, you will implement an OS command validation check and process runner in Java.
Your task:
1. Complete the implementation of `runSecureCommand` inside `CommandValidatorRegistry`.
2. Restrict the executable commands to a whitelist consisting strictly of `/usr/bin/ffmpeg` or `ffmpeg.exe`.
3. Strip any special shell characters (`;`, `|`, `&`, `$`, `\n`) from incoming parameters.
4. Run the process, drain stderr using a thread, and return the exit code.

Complete the implementation below:

```java
package com.security.api;

import java.io.InputStream;
import java.nio.file.Path;
import java.util.List;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class CommandValidatorRegistry {
    private final List<String> commandWhitelist = List.of("ffmpeg", "/usr/bin/ffmpeg", "ffmpeg.exe");

    public int runSecureCommand(String binary, String inputPath, String outputPath) throws Exception {
        // 1. Verify binary is in the whitelist. If not, throw IllegalArgumentException.
        if (!commandWhitelist.contains(binary)) {
            throw new IllegalArgumentException("Unauthorized binary execution attempt.");
        }

        // 2. Validate input and output paths do not contain shell characters.
        //    Regexp check: if inputPath or outputPath matches any character in [;|&$`\n], throw IllegalArgumentException.
        String illegalPattern = ".*[;|&$`\\n].*";
        if (inputPath.matches(illegalPattern) || outputPath.matches(illegalPattern)) {
            throw new IllegalArgumentException("Malicious command parameters detected.");
        }

        // TODO: Implement process execution:
        // 1. Build direct command list: List.of(binary, "-i", inputPath, outputPath).
        // 2. Start the process using ProcessBuilder.
        // 3. Drain stderr using a virtual thread: Executors.newVirtualThreadPerTaskExecutor().submit(...)
        // 4. Block execution for maximum 10 seconds: process.waitFor(10, TimeUnit.SECONDS).
        //    If it times out, invoke process.destroyForcibly() and throw an InterruptedException.
        // 5. Return the process exit value.

        return -1;
    }
}
```

Write the verification rules. Save the completed file and verify that injection validation checks pass under `modules/03-process-execution-transcoding.md`.
